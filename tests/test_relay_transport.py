"""HTTP wire and failure-origin regressions, without a real provider or CLI."""
import harness_support
import errno
import gzip
import http.client
import json
from pathlib import Path
import re
import tempfile
import unittest
import socketserver
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import remote_retry
import run_pilot
from relay_fixtures import RelayFixture, event, COMPLETE


class RelayTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.wire=self.enterContext(RelayFixture(Path(self.temp.name)))

    def statuses(self,wire):return re.findall(rb'HTTP/1\.1 (\d{3})',wire)

    def test_normal_response_has_one_status_and_retains_identical_events(self):
        raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'200'])
        self.assertEqual(raw.split(b'\r\n\r\n',1)[1],event()+COMPLETE)
        self.assertEqual((self.wire.stage.logs/'response-0001.sse').read_bytes(),event()+COMPLETE)
        self.assertEqual(self.wire.records('relay-errors.jsonl'),[])
        self.assertEqual(len(self.wire.calls),1)

    def test_truncated_chunked_stream_closes_without_inserting_http_error_into_sse(self):
        self.wire.respond=lambda h:self.wire.stream(h,[event()],complete=False)
        raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'200'])
        self.assertEqual(raw.split(b'\r\n\r\n',1)[1],event())
        failure=self.wire.stage.last_relay_failure['error']
        self.assertEqual(remote_retry.diagnose(failure)['category'],'model_stream_interrupted')
        self.assertEqual(self.wire.records('relay-errors.jsonl')[0]['error_type'],'IncompleteRead')
        self.assertNotIn(b'response.completed',raw)

    def test_failure_before_upstream_headers_is_a_single_valid_502(self):
        with patch.object(http.client.HTTPConnection,'getresponse',side_effect=TimeoutError('synthetic header timeout')):
            raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'502'])
        payload=json.loads(raw.split(b'\r\n\r\n',1)[1])
        self.assertEqual(remote_retry.diagnose(payload['error'])['category'],'model_timeout')

    def test_upstream_read_timeout_after_headers_preserves_http_framing(self):
        with patch.object(http.client.HTTPResponse,'read1',side_effect=TimeoutError('synthetic upstream read timeout')):
            raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'200'])
        self.assertEqual(raw.split(b'\r\n\r\n',1)[1],b'')
        self.assertEqual(remote_retry.diagnose(self.wire.stage.last_relay_failure['error'])['category'],'model_timeout')

    def test_failed_http_status_and_body_are_forwarded_once(self):
        body=b'{"error":{"code":"insufficient_quota"}}'
        self.wire.respond=lambda h:self.wire.stream(h,[body],status=429,content_type='application/json')
        raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'429'])
        self.assertEqual(json.loads(raw.split(b'\r\n\r\n',1)[1]),json.loads(body))

    def test_fragmented_utf8_crlf_keepalive_and_terminal_without_final_separator(self):
        body=b': keepalive\r\n\r\n'+event('response.created',label='synthetic α').replace(b'\n',b'\r\n')+COMPLETE.rstrip(b'\n')
        self.wire.respond=lambda h:self.wire.stream(h,[body[i:i+1] for i in range(len(body))])
        raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'200'])
        self.assertEqual(raw.split(b'\r\n\r\n',1)[1],body)
        self.assertTrue(any(row['event']=='PROVIDER_TERMINAL' for row in self.wire.records('request-lifecycle.jsonl')))

    def test_local_disk_error_after_headers_is_retained_without_corrupting_stream(self):
        original=Path.open
        def open_file(path,*args,**kwargs):
            if path.name.startswith('response-'):raise OSError(errno.ENOSPC,'synthetic full disk')
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',open_file):raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'200'])
        self.assertEqual(self.wire.stage.last_relay_failure['error']['code'],'harness_bug')
        self.assertTrue(self.wire.stage.non_remote_relay_fault)

    def test_unexpected_downstream_disconnect_is_local_not_a_remote_retry(self):
        original=socketserver._SocketWriter.write
        def disconnect(writer,data):
            if writer._sock.getsockname()[1]==self.wire.port and data.startswith(b'data:'):
                raise BrokenPipeError('synthetic downstream closed')
            return original(writer,data)
        with patch.object(socketserver._SocketWriter,'write',disconnect):
            self.wire.exchange()
        failure=self.wire.stage.last_relay_failure['error']
        self.assertEqual(remote_retry.diagnose(failure)['category'],'harness_bug')
        self.assertIsNone(remote_retry.classify(failure))

    def test_local_timeout_is_not_reclassified_as_remote_timeout(self):
        with patch.object(self.wire.stage,'observe_model_event',side_effect=TimeoutError('local bookkeeping timeout')):
            self.wire.exchange()
        self.assertEqual(self.wire.stage.last_relay_failure['error']['code'],'harness_bug')

    def test_invalid_gzip_is_a_local_protocol_rejection_with_no_upstream_request(self):
        raw=self.wire.exchange(raw_body=b'not a gzip stream',headers={'Content-Encoding':'gzip'})
        self.assertEqual(self.statuses(raw),[b'400'])
        self.assertEqual(self.wire.calls,[])
        self.assertTrue(self.wire.stage.local_protocol_fault)

    def test_valid_gzip_and_wrong_model_are_distinguished(self):
        raw=self.wire.exchange(raw_body=gzip.compress(json.dumps(self.wire.payload()).encode()),headers={'Content-Encoding':'gzip'})
        self.assertEqual(self.statuses(raw),[b'200'])
        bad=self.wire.payload();bad['model']='different-model'
        raw=self.wire.exchange(payload=bad)
        self.assertEqual(self.statuses(raw),[b'400']);self.assertEqual(len(self.wire.calls),1)

    def test_auth_quota_capacity_and_request_errors_preserve_status_and_body(self):
        for status in (400,401,402,403,404,422,429,500,502,503):
            with self.subTest(status=status):
                body=json.dumps({'error':{'httpStatusCode':status,'message':'synthetic'}}).encode()
                self.wire.respond=lambda h:self.wire.stream(h,[body],status=status,content_type='application/json')
                raw=self.wire.exchange()
                self.assertEqual(self.statuses(raw),[str(status).encode()])
                self.assertEqual(raw.split(b'\r\n\r\n',1)[1],body)
        self.assertIsNone(self.wire.stage.last_response_success)

    def test_partial_downstream_headers_cannot_be_followed_by_another_status(self):
        original=socketserver._SocketWriter.write
        def partial(writer,data):
            if writer._sock.getsockname()[1]==self.wire.port and data.startswith(b'HTTP/'):
                original(writer,data[:16]);raise TimeoutError('synthetic partial header write')
            return original(writer,data)
        with patch.object(socketserver._SocketWriter,'write',partial):raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'200'])
        self.assertTrue(self.wire.stage.non_remote_relay_fault)
        self.assertEqual(self.wire.records('relay-errors.jsonl')[0]['origin'],'downstream_headers')

    def test_exact_registered_downstream_cancellation_is_not_a_remote_failure(self):
        original=socketserver._SocketWriter.write
        def cancelled(h):
            self.wire.stage.cancelled_requests[self.wire.stage.api_calls]={'reason':'EXTERNAL_CANCEL'}
            self.wire.stream(h,[event()])
        def disconnect(writer,data):
            if writer._sock.getsockname()[1]==self.wire.port and data.startswith(b'data:'):
                raise BrokenPipeError('synthetic cancelled reader')
            return original(writer,data)
        self.wire.respond=cancelled
        with patch.object(socketserver._SocketWriter,'write',disconnect):self.wire.exchange()
        self.assertIsNone(self.wire.stage.last_relay_failure)
        self.assertEqual(self.wire.records('relay-errors.jsonl'),[])
        self.assertEqual(self.wire.records('local-cancellations.jsonl')[0]['reason'],'EXTERNAL_CANCEL')

    def test_http_200_partial_failed_or_incomplete_stream_does_not_count_as_success(self):
        for body in (b'',event(),event('response.failed',response={'id':'failed','status':'failed'}),
                     event('response.incomplete',response={'id':'incomplete','status':'incomplete'})):
            with self.subTest(body=body):
                self.wire.respond=lambda h:self.wire.stream(h,[body] if body else [])
                self.wire.exchange();self.assertIsNone(self.wire.stage.last_response_success)

    def test_local_model_catalog_cannot_reset_retry_history(self):
        (self.wire.stage.work/'state/models_cache.json').write_text(json.dumps({'models':[{'slug':self.wire.stage.model}]}))
        connection=http.client.HTTPConnection('127.0.0.1',self.wire.port,timeout=3)
        try:
            connection.request('GET','/models');response=connection.getresponse()
            self.assertEqual(response.status,200);self.assertTrue(json.loads(response.read())['models'])
        finally:connection.close()
        self.assertEqual(self.wire.calls,[]);self.assertEqual(self.wire.stage.api_calls,0)
        self.assertIsNone(self.wire.stage.last_response_success)

    def test_missing_model_catalog_is_reported_as_local_failure(self):
        raw=self.wire.exchange(method='GET',path='/models')
        self.assertEqual(self.statuses(raw),[b'500'])
        self.assertEqual(json.loads(raw.split(b'\r\n\r\n',1)[1])['error']['code'],'harness_bug')
        self.assertTrue(self.wire.stage.non_remote_relay_fault)
        self.assertEqual(self.wire.stage.api_calls,0);self.assertEqual(self.wire.calls,[])

    def test_invalid_model_catalog_json_wakes_the_local_error_guard(self):
        (self.wire.stage.work/'state/models_cache.json').write_text('invalid catalog JSON')
        raw=self.wire.exchange(method='GET',path='/models')
        self.assertEqual(self.statuses(raw),[b'500'])
        with self.assertRaisesRegex(RuntimeError,'local_model_catalog'):
            self.wire.stage.check_argument_guard()
        self.assertEqual(self.wire.records('relay-errors.jsonl')[0]['category'],'harness_bug')

    def test_catalog_body_write_failure_does_not_append_another_http_response(self):
        (self.wire.stage.work/'state/models_cache.json').write_text('{"models":[]}')
        original=socketserver._SocketWriter.write
        def disconnect(writer,data):
            if writer._sock.getsockname()[1]==self.wire.port and data.startswith(b'{'):
                raise BrokenPipeError('synthetic catalog downstream closed')
            return original(writer,data)
        with patch.object(socketserver._SocketWriter,'write',disconnect):
            raw=self.wire.exchange(method='GET',path='/models')
        self.assertEqual(self.statuses(raw),[b'200'])
        self.assertTrue(self.wire.stage.non_remote_relay_fault)
        self.assertIsNone(remote_retry.classify(self.wire.stage.last_relay_failure['error']))

    def test_unsupported_get_body_failure_preserves_its_single_403_status(self):
        original=socketserver._SocketWriter.write
        def disconnect(writer,data):
            if writer._sock.getsockname()[1]==self.wire.port and data.startswith(b'<!DOCTYPE'):
                raise BrokenPipeError('synthetic rejected-route downstream closed')
            return original(writer,data)
        with patch.object(socketserver._SocketWriter,'write',disconnect):
            raw=self.wire.exchange(method='GET',path='/unsupported')
        self.assertEqual(self.statuses(raw),[b'403'])
        self.assertTrue(self.wire.stage.non_remote_relay_fault)

    def test_unexpected_response_close_failure_is_local_and_releases_stream_waiters(self):
        original=http.client.HTTPResponse.close
        def close(response):
            original(response);raise RuntimeError('synthetic response finalization fault')
        with patch.object(http.client.HTTPResponse,'close',close):raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'200'])
        self.assertTrue(self.wire.stage.non_remote_relay_fault)
        self.assertIsNone(self.wire.stage.last_response_success)
        self.assertTrue(all(done.is_set() for done in self.wire.stage.relay_streams.values()))

    def test_local_error_before_headers_uses_500_not_an_upstream_gateway_error(self):
        with patch.object(self.wire.stage,'normalize_request',side_effect=OSError('synthetic local storage fault')):
            raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'500'])
        self.assertEqual(json.loads(raw.split(b'\r\n\r\n',1)[1])['error']['code'],'harness_bug')
        self.assertEqual(self.wire.calls,[])

    def test_terminal_event_followed_by_truncated_transport_does_not_reset_failures(self):
        self.wire.respond=lambda h:self.wire.stream(h,[COMPLETE],complete=False)
        raw=self.wire.exchange()
        self.assertEqual(self.statuses(raw),[b'200'])
        self.assertIsNone(self.wire.stage.last_response_success)
        self.assertIsNotNone(remote_retry.classify(self.wire.stage.last_relay_failure['error']))

    def test_late_old_response_cannot_clear_a_newer_failed_request(self):
        arrived=threading.Event();release=threading.Event()
        def interleaved(h):
            if len(self.wire.calls)==1:
                arrived.set()
                if not release.wait(3):raise AssertionError('Synthetic ordering timed out')
                self.wire.stream(h,[event(),COMPLETE])
            else:self.wire.stream(h,[event()],complete=False)
        self.wire.respond=interleaved
        with ThreadPoolExecutor(max_workers=1) as pool:
            first=pool.submit(self.wire.exchange)
            self.assertTrue(arrived.wait(3))
            # Use the raw socket for the second response: waiting for all streams
            # would intentionally wait on the first, still-gated response.
            with self.wire.connected() as client:
                while client.recv(65536):pass
            release.set();first.result(timeout=5)
        self.assertIsNone(self.wire.stage.last_response_success)
        self.assertEqual(self.wire.stage.last_relay_failure['request_number'],2)

    def test_stream_registry_is_released_even_when_final_metadata_write_fails(self):
        original=run_pilot.append
        def fail_final(path,value):
            if value.get('event')=='STREAM_CLOSED':raise OSError(errno.ENOSPC,'synthetic finalization disk failure')
            return original(path,value)
        with patch.object(run_pilot,'append',fail_final):self.wire.exchange()
        self.assertTrue(all(done.is_set() for done in self.wire.stage.relay_streams.values()))
        self.assertIsNone(self.wire.stage.last_response_success)
        self.assertTrue(self.wire.stage.non_remote_relay_fault)

    def test_failed_response_object_is_closed_even_when_its_body_is_truncated(self):
        original=http.client.HTTPResponse.close;closed=[]
        def close(response):
            closed.append(response);return original(response)
        self.wire.respond=lambda h:self.wire.stream(h,[event()],complete=False)
        with patch.object(http.client.HTTPResponse,'close',close):self.wire.exchange()
        self.assertTrue(closed)
        self.assertTrue(all(response.closed for response in closed))


if __name__=='__main__':unittest.main()
