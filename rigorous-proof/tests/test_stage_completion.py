"""Completion protocol controls; synthetic JSON is not a mathematical proof."""
import http.client
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from clean_stage import ArtifactStage


class DummyProcess:
    def __init__(self):self.stdin=io.StringIO()
    def poll(self):return None


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.worker=ArtifactStage(self.root/'stage','Synthetic protocol control only.',phase='control',library=False)
        self.worker.proc=DummyProcess();self.worker.thread_id='synthetic-thread';self.worker.active_turn_id='synthetic-turn'

    def tearDown(self):
        if self.worker.relay:self.worker.relay.shutdown();self.worker.relay.server_close()
        shutil.rmtree(self.worker.work);self.temp.cleanup()

    def call(self,name):
        args={'artifact':{'control':'candidate'}}
        self.worker.model_calls['synthetic-call']={'name':name,'arguments':json.dumps(args)}
        return {'id':91,'method':'item/tool/call','params':{'tool':name,'callId':'synthetic-call','arguments':args}}

    def test_real_submission_closes_without_waiting_for_another_model_turn(self):
        self.worker.inbox.put(self.call('submit_draft'));calls=[]
        def rpc(method,params,seconds=30):
            calls.append(method)
            if method=='turn/start':return {'turn':{'id':'synthetic-turn'}}
            self.worker.last_turn_event={'method':'turn/completed','params':{'turn':{'id':'synthetic-turn','status':'interrupted'}}}
            return {}
        self.worker.rpc=rpc
        result=self.worker.solve_turns('Synthetic explicit task')
        self.assertEqual(calls,['turn/start','turn/interrupt'])
        self.assertTrue(self.worker.submission_closed)
        self.assertEqual(self.worker.accepted,{'control':'candidate'})
        self.assertEqual(self.worker.continuation_count,0)
        self.assertEqual(result['params']['turn']['status'],'interrupted')
        self.assertIn('submission_completed',(self.root/'stage/controller.jsonl').read_text())

    def test_provisional_check_does_not_close_the_stage(self):
        self.worker.started=time.monotonic();self.worker.inbox.put(self.call('check_draft'))
        self.worker.inbox.put({'method':'turn/completed','params':{'turn':{'id':'synthetic-turn','status':'completed'}}})
        self.worker.receive_until(lambda m:m.get('method')=='turn/completed',time.monotonic()+2)
        self.assertIsNone(self.worker.accepted);self.assertFalse(self.worker.submission_closed)

    def test_post_submission_requests_are_suppressed_locally_not_forwarded(self):
        self.worker.submission_closed=True;port=self.worker.start_relay()
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
        connection.request('POST','/responses',body=b'{"control":"never-forward"}',headers={'Content-Type':'application/json'})
        response=connection.getresponse();self.assertEqual(response.status,409);response.read();connection.close()
        self.assertEqual(self.worker.api_calls,0)
        self.assertFalse((self.root/'stage/requests.jsonl').exists())
        row=json.loads((self.root/'stage/local-cancellations.jsonl').read_text())
        self.assertIs(row['upstream_transmitted'],False)

    def test_shutdown_waits_for_the_actual_response_log_to_finish(self):
        done=threading.Event();self.worker.relay_stream_lock=threading.Lock()
        self.worker.relay_streams={7:done}
        timer=threading.Timer(0.04,done.set);timer.start()
        self.worker.drain_relay_streams(timeout=1)
        self.assertTrue(done.is_set());timer.join()
        self.worker.relay_streams={8:threading.Event()}
        with self.assertRaisesRegex(RuntimeError,'logging did not finish'):
            self.worker.drain_relay_streams(timeout=0.01)


if __name__=='__main__':unittest.main()
