"""Real native work interrupted after a persisted tool checkpoint, no inference."""
import harness_support
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from native_fault_fixtures import NativeFaultFixture
import fault_control
import execution_state
import execution_health

@unittest.skipUnless(shutil.which('codex'),'Native Codex executable required')
class NativeFaultTests(unittest.TestCase):
    def assert_checkpoint(self,f):
        self.assertEqual(f.checkpoint_writes,1)
        self.assertEqual(json.loads(f.checkpoint.read_text()),{'saved':True})
        self.assertIn('call-1',f.stage.tool_history)

    def assert_paused(self,f,categories,retries=0):
        f.wait(lambda:(f.paused() or {}).get('notification',{}).get('status')=='QUEUED')
        state=f.paused()
        self.assertIn(state['fault']['category'],categories,json.dumps(state['error']))
        self.assertEqual(state['retries'],retries)
        self.assertFalse(state['cleanup_authorized'])
        self.assertTrue(f.worker.is_alive());self.assertIsNone(f.stage.proc.poll())
        self.assertTrue(f.stage.work.exists());self.assertFalse(f.outcomes)
        self.assertEqual(len(f.notifications),1);self.assert_checkpoint(f)
        return state

    def test_auth_balance_and_rejected_request_after_checkpoint_pause_without_retry(self):
        for status,categories in [(401,{'model_auth'}),(403,{'model_auth'}),(402,{'model_balance','model_unknown'}),
                (400,{'model_request_rejected','model_unknown'}),(404,{'model_auth','model_request_rejected','model_unknown'}),(422,{'model_request_rejected','model_unknown'})]:
            with self.subTest(status=status),tempfile.TemporaryDirectory() as root,NativeFaultFixture(root,status) as f:
                f.start();self.assert_paused(f,categories)
                self.assertEqual(len(f.calls),2);self.assertEqual(f.waits,[])

    def test_transient_capacity_and_stream_loss_continue_same_thread_without_duplicate_tool(self):
        for failure in (503,429,'disconnect','timeout'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as root,NativeFaultFixture(root,failure) as f:
                f.start();f.wait();self.assertEqual(f.outcomes[0][0]['status'],'ACCEPTED')
                self.assertEqual(f.waits,[60]);self.assertEqual(len(f.calls),3);self.assert_checkpoint(f)
                checked=execution_health.require_review_execution(f.outcomes[0][0],f.stage.logs/'result.json')
                self.assertTrue(checked['submitted_record_qualified']);self.assertFalse(checked['measurement_valid'])
                starts=[json.loads(x) for x in (f.stage.logs/'client.jsonl').read_text().splitlines() if json.loads(x).get('method')=='turn/start']
                self.assertEqual(len(starts),2)
                self.assertEqual(len({x['params']['threadId'] for x in starts}),1)
                self.assertFalse((f.stage.logs/'relay-errors.jsonl').exists())

    def test_thirty_failures_pause_with_exactly_thirty_controlled_retries(self):
        with tempfile.TemporaryDirectory() as root,NativeFaultFixture(root,failures=31) as f:
            f.start();self.assert_paused(f,{'model_stream_interrupted','model_transport'},30)
            self.assertEqual(f.waits,[60]*30);self.assertEqual(len(f.calls),32)

    def test_explicit_resume_after_auth_fault_reuses_native_process_and_thread(self):
        with tempfile.TemporaryDirectory() as root,NativeFaultFixture(root,403) as f:
            f.start();state=self.assert_paused(f,{'model_auth'})
            pid=f.stage.proc.pid;thread=f.stage.thread_id
            fault_control.resume(f.stage.logs,state['incident']);f.wait()
            self.assertEqual(f.outcomes[0][0]['status'],'ACCEPTED')
            self.assertEqual((f.stage.proc.pid,f.stage.thread_id),(pid,thread));self.assert_checkpoint(f)
            result=f.outcomes[0][0]
            self.assertTrue(execution_health.require_review_execution(result,f.stage.logs/'result.json')['submitted_record_qualified'])
            altered={**result,'error_pauses':[]}
            self.assertFalse(execution_health.record_qualification(altered)['submitted_record_qualified'])

    def test_one_actual_sixty_second_wait_recovers_after_mid_work_disconnect(self):
        with tempfile.TemporaryDirectory() as root,NativeFaultFixture(root,real_wait=True) as f:
            f.start();f.wait(seconds=72)
            self.assertGreaterEqual(f.call_times[2]-f.call_times[1],60)
            self.assertEqual(f.stage.remote_retry_count,1);self.assert_checkpoint(f)

    def test_user_cancel_interrupts_real_retry_wait_without_waiting_for_the_minute(self):
        with tempfile.TemporaryDirectory() as root,NativeFaultFixture(root,real_wait=True) as f:
            f.start();f.wait(lambda:(f.stage.logs/'remote-retries.jsonl').exists())
            start=time.monotonic();execution_state.request_cancel(f.recorder.root)
            f.wait(seconds=4);self.assertLess(time.monotonic()-start,4)
            self.assertEqual(f.outcomes[0][0]['status'],'CANCELLED');self.assertEqual(len(f.calls),2)
