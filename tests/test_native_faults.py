"""Real in-flight service faults through native client and production controller."""
import harness_support
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
import http.client
import subprocess
import sys

from native_fault_fixtures import NativeFaultFixture
import fault_control
import run_pilot


@unittest.skipUnless(sys.platform=='darwin' and Path('/usr/bin/sandbox-exec').is_file() and shutil.which('codex'),
    'The production macOS sandbox and compatible local Codex CLI are required')
class NativeFaultTests(unittest.TestCase):
    def assert_checkpoint(self, fixture):
        self.assertEqual(fixture.checkpoint_writes,1)
        self.assertEqual(json.loads(fixture.checkpoint.read_text()),{'saved':True})
        self.assertIn('call-1',fixture.stage.tool_history)
        self.assertFalse(any(key.startswith('partial-call-') for key in fixture.stage.tool_history))

    def assert_pause(self, fixture, category, retries):
        def paused():
            if fixture.outcomes:raise AssertionError('Native task continued instead of pausing: '+repr(fixture.outcomes[0][0]['status']))
            return ((fixture.paused() or {}).get('notification',{}).get('status')=='QUEUED' and
                fixture.recorder.state['tasks'].get(fixture.stage.execution_task,{}).get('state')=='PAUSED_ERROR')
        fixture.until(paused,seconds=45)
        state=fixture.paused()
        self.assertEqual(state['state'],'PAUSED_ERROR')
        self.assertEqual(state['fault']['category'],category,repr(state['error']))
        self.assertEqual(state['retries'],retries)
        self.assertFalse(state['cleanup_authorized'])
        self.assertTrue(fixture.worker.is_alive());self.assertIsNone(fixture.stage.proc.poll())
        self.assertTrue(fixture.stage.work.is_dir());self.assertFalse(fixture.outcomes)
        self.assert_checkpoint(fixture)
        messages=[json.loads(line) for line in fixture.outbox.read_text().splitlines()]
        self.assertEqual(len(messages),1)
        self.assertEqual(messages[0][:4],['queue','--thread','synthetic-fault-owner','--message'])
        self.assertIn('[Yui ERROR PAUSED]',messages[0][4]);self.assertIn(category,messages[0][4])
        self.assertIn(str(fixture.stage.logs/'error-state.json'),messages[0][4])
        self.assertIn(state['incident'],messages[0][4])
        self.assertIn('paused, not finished',messages[0][4])
        self.assertIn('no automatic cleanup',messages[0][4])
        before=len(fixture.calls);time.sleep(.2)
        self.assertEqual(len(fixture.calls),before)
        return state

    def test_real_stream_disconnect_waits_one_real_minute_and_preserves_progress(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw, NativeFaultFixture(raw,real_wait=True) as fixture:
            fixture.start();fixture.until(lambda:bool(fixture.rows('remote-retries.jsonl')))
            process=fixture.stage.proc.pid;thread=fixture.stage.thread_id
            self.assert_checkpoint(fixture)
            self.assertEqual(len(fixture.calls),2);self.assertIsNone(fixture.stage.proc.poll())
            self.assertEqual(fixture.rows('remote-retries.jsonl')[0]['delay_seconds'],60)
            fixture.until(lambda:bool(fixture.outcomes),seconds=80)
            result,artifact=fixture.outcomes[0]
            self.assertEqual(result['status'],'ACCEPTED',result)
            self.assertEqual(artifact,{'complete':True})
            self.assertEqual(len(fixture.calls),3)
            self.assert_checkpoint(fixture)
            self.assertEqual(fixture.stage.remote_retry_count,1)
            self.assertEqual(fixture.waits,[])
            self.assertGreaterEqual(fixture.calls[2]['at']-fixture.calls[1]['at'],60)
            self.assertEqual(fixture.stage.proc.pid,process);self.assertEqual(fixture.stage.thread_id,thread)
            self.assertEqual(fixture.rows('relay-errors.jsonl')[0]['category'],'model_stream_interrupted')
            starts=[row for row in fixture.rows('client.jsonl') if row.get('method')=='turn/start']
            self.assertEqual(len({row['params']['threadId'] for row in starts}),1)
            self.assertEqual(len(starts),2)
            self.assertIsNone(fixture.stage.proc.poll())
            self.assertFalse(fixture.server_errors)
            outputs=[item for item in fixture.calls[2]['payload']['input'] if item.get('type')=='function_call_output']
            prior=next(item for item in outputs if item['call_id']=='call-1')
            self.assertEqual(json.loads(prior['output']),fixture.stage.tool_history['call-1'])

    def test_service_capacity_recovers_after_progress_in_the_same_native_thread(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw, NativeFaultFixture(raw,'capacity') as fixture:
            fixture.start();fixture.until(lambda:bool(fixture.outcomes))
            self.assertEqual(fixture.outcomes[0][0]['status'],'ACCEPTED')
            self.assertEqual(len(fixture.calls),3);self.assertEqual(fixture.stage.remote_retry_count,1)
            self.assertEqual(fixture.waits,[{'configured_seconds':60,'virtual_seconds':60}])
            self.assert_checkpoint(fixture)
            starts=[row for row in fixture.rows('client.jsonl') if row.get('method')=='turn/start']
            self.assertEqual(len({row['params']['threadId'] for row in starts}),1)
            self.assertEqual([row['status'] for row in fixture.rows('http.jsonl') if row.get('path')=='/responses'],[200,503,200])

    def test_http_403_pauses_notifies_and_waits_for_explicit_same_thread_resume(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw, NativeFaultFixture(raw,'auth') as fixture:
            fixture.start();state=self.assert_pause(fixture,'model_auth',0)
            process=fixture.stage.proc.pid;thread=fixture.stage.thread_id
            self.assertEqual(len(fixture.calls),2);self.assertEqual(fixture.waits,[])
            fault_control.resume(fixture.stage.logs,state['incident'])
            fixture.until(lambda:bool(fixture.outcomes))
            self.assertEqual(fixture.outcomes[0][0]['status'],'ACCEPTED')
            self.assertEqual(fixture.paused()['state'],'RESUMED')
            self.assertEqual(fixture.stage.proc.pid,process);self.assertEqual(fixture.stage.thread_id,thread)
            self.assertEqual(len(fixture.calls),3);self.assert_checkpoint(fixture)

    def test_real_connection_refusal_is_retried_without_losing_the_checkpoint(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw, NativeFaultFixture(raw,'offline') as fixture:
            fixture.start();fixture.until(lambda:bool(fixture.outcomes))
            self.assertEqual(fixture.outcomes[0][0]['status'],'ACCEPTED')
            self.assertEqual(fixture.stage.remote_retry_count,1)
            self.assertEqual(len(fixture.calls),3);self.assertTrue(fixture.calls[1]['connection_refused'])
            error=fixture.rows('relay-errors.jsonl')[0]
            self.assertEqual(error['error_type'],'ConnectionRefusedError')
            self.assertEqual(error['category'],'model_transport');self.assert_checkpoint(fixture)

    def test_balance_quota_and_request_rejection_pause_instead_of_auto_retrying(self):
        for failure,category in [('balance','model_balance'),('quota','model_quota'),('request','model_request_rejected')]:
            with self.subTest(failure=failure),tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw, NativeFaultFixture(raw,failure) as fixture:
                fixture.start();self.assert_pause(fixture,category,0)
                self.assertEqual(len(fixture.calls),2);self.assertEqual(fixture.waits,[])
                fixture.cancel();fixture.until(lambda:bool(fixture.outcomes))
                self.assertEqual(fixture.outcomes[0][0]['status'],'CANCELLED')

    def test_thirty_failed_retries_retain_live_process_checkpoint_and_notification(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw, NativeFaultFixture(raw,failures=31) as fixture:
            fixture.start();self.assert_pause(fixture,'model_stream_interrupted',30)
            self.assertEqual(len(fixture.calls),32) # checkpoint + original failure + 30 retries
            self.assertEqual(fixture.stage.remote_retry_count,30)
            self.assertEqual(len(fixture.waits),30)
            self.assertTrue(all(row=={'configured_seconds':60,'virtual_seconds':60} for row in fixture.waits))
            fixture.cancel();fixture.until(lambda:bool(fixture.outcomes))
            self.assertEqual(fixture.outcomes[0][0]['status'],'CANCELLED')
            self.assert_checkpoint(fixture)

    def test_actual_read_timeout_recovers_without_replaying_a_completed_tool(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw, NativeFaultFixture(raw,'timeout') as fixture:
            fixture.start();fixture.until(lambda:bool(fixture.outcomes))
            self.assertEqual(fixture.outcomes[0][0]['status'],'ACCEPTED')
            self.assertEqual(fixture.stage.remote_retry_count,1)
            self.assertEqual(fixture.rows('relay-errors.jsonl')[0]['category'],'model_timeout')
            self.assertEqual(fixture.rows('relay-errors.jsonl')[0]['origin'],'upstream_body')
            self.assert_checkpoint(fixture)

    def test_local_disk_fault_pauses_without_remote_retry_or_automatic_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw, NativeFaultFixture(raw,'disk') as fixture:
            fixture.start();state=self.assert_pause(fixture,'harness_bug',0)
            self.assertEqual(len(fixture.calls),2);self.assertEqual(fixture.waits,[])
            self.assertFalse(state['resumable'])
            with self.assertRaises(ValueError):fault_control.resume(fixture.stage.logs,state['incident'])
            self.assertIn('Synthetic evidence disk full',json.dumps(state))
            fixture.cancel();fixture.until(lambda:bool(fixture.outcomes))
            self.assertEqual(fixture.outcomes[0][0]['status'],'CANCELLED')

    def test_operator_cancellation_interrupts_a_real_retry_wait(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw, NativeFaultFixture(raw,real_wait=True) as fixture:
            fixture.start();fixture.until(lambda:bool(fixture.rows('remote-retries.jsonl')))
            self.assert_checkpoint(fixture);start=time.monotonic()
            fixture.cancel();fixture.until(lambda:bool(fixture.outcomes),seconds=5)
            self.assertLess(time.monotonic()-start,5)
            self.assertEqual(len(fixture.calls),2)
            self.assertEqual(fixture.outcomes[0][0]['status'],'CANCELLED')

    def test_fixture_failure_cleans_process_and_restores_test_isolation(self):
        popen=subprocess.Popen;connection=http.client.HTTPSConnection;notify=fault_control.queue_notification
        with tempfile.TemporaryDirectory(prefix='yui-native-fault-') as raw:
            with self.assertRaisesRegex(RuntimeError,'deliberate test-body failure'):
                with NativeFaultFixture(raw,real_wait=True) as fixture:
                    fixture.start();fixture.until(lambda:bool(fixture.rows('remote-retries.jsonl')))
                    raise RuntimeError('deliberate test-body failure')
            self.assertFalse(fixture.worker.is_alive());self.assertIsNotNone(fixture.stage.proc.poll())
            self.assertFalse(fixture.stage.work.exists())
        self.assertIs(subprocess.Popen,popen);self.assertIs(http.client.HTTPSConnection,connection)
        self.assertIs(fault_control.queue_notification,notify);self.assertIs(run_pilot.time,time)


if __name__=='__main__':unittest.main()
