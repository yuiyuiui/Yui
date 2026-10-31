"""Completion protocol controls; synthetic JSON is not a mathematical proof."""
import harness_support
import http.client
import io
import json
from pathlib import Path
import shutil
import tempfile
import time
import threading
import hashlib
import unittest
from unittest.mock import Mock, patch

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
        shutil.rmtree(self.worker.work,ignore_errors=True);self.temp.cleanup()

    def call(self,name):
        args={'artifact':{'control':'candidate'}}
        self.worker.model_calls['synthetic-call']={'name':name,'arguments':json.dumps(args)}
        return {'id':91,'method':'item/tool/call','params':{'threadId':self.worker.thread_id,'turnId':'synthetic-turn','tool':name,'callId':'synthetic-call','arguments':args}}

    def test_real_submission_closes_without_waiting_for_another_model_turn(self):
        self.worker.inbox.put(self.call('submit_draft'));calls=[]
        def rpc(method,params,seconds=30):
            calls.append(method)
            if method=='turn/start':return {'turn':{'id':'synthetic-turn'}}
            return {}
        send=self.worker.send
        def interrupt(method,params):
            calls.append(method);rid=send(method,params)
            self.worker.inbox.put({'id':rid,'result':{}})
            self.worker.inbox.put({'method':'turn/completed','params':{'turn':{'id':'synthetic-turn','status':'interrupted'}}})
            return rid
        self.worker.rpc=rpc
        self.worker.send=interrupt
        result=self.worker.solve_turns('Synthetic explicit task')
        self.assertEqual(calls,['turn/start','turn/interrupt'])
        self.assertTrue(self.worker.submission_closed)
        self.assertEqual(self.worker.accepted,{'control':'candidate'})
        self.assertEqual(self.worker.continuation_count,0)
        self.assertEqual(result['params']['turn']['status'],'interrupted')
        self.assertIn('submission_completed',(self.root/'stage/controller.jsonl').read_text())
        written=[json.loads(line) for line in self.worker.proc.stdin.getvalue().splitlines()]
        self.assertEqual(written[0]['method'],'turn/interrupt')
        self.assertEqual(written[1]['id'],91)

    def test_already_completed_interrupt_race_requires_matching_terminal_event(self):
        self.worker.handoff_interrupt=7
        self.worker.inbox.put({'id':7,'error':{'code':-32600,'message':'no active turn to interrupt'}})
        self.worker.inbox.put({'method':'turn/completed','params':{'turn':{'id':'synthetic-turn','status':'completed'}}})
        self.worker.interrupt_active_turn(reason='ACCEPTED_ARTIFACT')
        self.assertEqual(self.worker.last_turn_event['params']['turn']['id'],'synthetic-turn')

    def test_unrelated_interrupt_error_is_not_hidden_by_an_accepted_artifact(self):
        self.worker.accepted={'control':'candidate'};self.worker.handoff_interrupt=7
        self.worker.inbox.put({'id':7,'error':{'code':-32600,'message':'unrelated invalid thread'}})
        with self.assertRaisesRegex(RuntimeError,'unrelated invalid thread'):
            self.worker.interrupt_active_turn(reason='ACCEPTED_ARTIFACT')




    def test_provisional_check_does_not_close_the_stage(self):
        self.worker.started=time.monotonic();self.worker.inbox.put(self.call('check_draft'))
        self.worker.inbox.put({'method':'turn/completed','params':{'turn':{'id':'synthetic-turn','status':'completed'}}})
        self.worker.receive_until(lambda m:m.get('method')=='turn/completed',time.monotonic()+2)
        self.assertIsNone(self.worker.accepted);self.assertFalse(self.worker.submission_closed)



    def test_actual_tool_response_delivery_records_native_call_identity(self):
        self.worker.started=time.monotonic()
        self.worker.inbox.put(self.call('check_draft'))
        self.worker.inbox.put({'method':'turn/completed','params':{'turn':{'id':'synthetic-turn','status':'completed'}}})
        self.worker.receive_until(lambda m:m.get('method')=='turn/completed',time.monotonic()+2)
        rows=[json.loads(l) for l in (self.worker.logs/'request-lifecycle.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['call_id'],'synthetic-call')
        self.assertEqual(rows[-1]['tool'],'check_draft')
        self.assertNotIn('awaiting_provider_terminal',rows[-1])
        self.assertIn('flushed to native carrier',rows[-1]['delivery_boundary'])
        self.assertTrue(json.loads(self.worker.proc.stdin.getvalue())['result']['success'])

    def test_late_tool_after_protocol_stop_is_not_executed(self):
        self.worker._stopping=True;self.worker.native_infrastructure_fault={'code':'harness_bug'}
        self.worker.dispatch=Mock()
        self.worker.inbox.put(self.call('check_draft'))
        self.worker.inbox.put({'method':'turn/completed','params':{'turn':{'id':'synthetic-turn','status':'interrupted'}}})
        self.worker.receive_until(lambda m:m.get('method')=='turn/completed',time.monotonic()+2)
        self.worker.dispatch.assert_not_called()
        self.assertEqual(json.loads(self.worker.proc.stdin.getvalue())['error']['code'],-32800)



if __name__=='__main__':unittest.main()
