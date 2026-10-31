"""Offline lifecycle regressions: no model, provider, theorem or Lean calls."""
import harness_support
import io
import errno
import http.client
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import execution_state as execution
import fault_control as faults
import remote_retry
import run_pilot
import run_resources
from clean_stage import ArtifactStage


def terminal(number, error=None):
    return {'method':'turn/completed','params':{'turn':{
        'id':str(number),'status':'failed' if error else 'completed','error':error}}}


class FaultFixture:
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.notifier=Mock(return_value={'status':'QUEUED'})
    def tearDown(self):self.temp.cleanup()

    def gate(self, **kwargs):return faults.Gate(self.root,notify=self.notifier,**kwargs)

    def cancel(self, gate):execution.atomic(gate.root/'cancel-request.json',{'external_cancel':True})


class FaultControlTests(FaultFixture,unittest.TestCase):
    def test_b_final_decisions_require_an_explicit_matching_live_incident(self):
        for action in ('deliver-actual','recheck','reset-translation'):
            with self.subTest(action=action):
                gate=self.gate()
                def choose(_):
                    with self.assertRaises(ValueError):faults.resume(gate.root,gate.state['incident'])
                    with self.assertRaises(ValueError):faults.final_decision(gate.root,'stale',action)
                    with self.assertRaises(ValueError):faults.final_decision(gate.root,gate.state['incident'],'unfreeze')
                    faults.final_decision(gate.root,gate.state['incident'],action)
                    with self.assertRaises(ValueError):faults.final_decision(gate.root,gate.state['incident'],action)
                gate.wait=choose
                state=gate.pause({'code':'workflow_blocked'},resumable=False,
                    decisions=('deliver-actual','recheck','reset-translation'))
                self.assertEqual(state['state'],'USER_DECIDED');self.assertEqual(state['control']['action'],action)
                self.assertFalse(state['cleanup_authorized'])

    def test_final_report_write_waits_for_operator_instead_of_exiting(self):
        import controller_common as common
        path=self.root/'case-result.json';payload={'result':{'status':'SOFTWARE_CONTROL_ONLY'}}
        original=common.write;attempts=[];finished=[]
        def flaky(target,value):
            attempts.append(1)
            if len(attempts)==1:raise OSError(5,'synthetic final report failure')
            original(target,value)
        def worker():finished.append(common.final_write(path,payload))
        with patch.object(common,'write',side_effect=flaky),patch.object(faults,'queue_notification',self.notifier):
            thread=threading.Thread(target=worker);thread.start()
            try:
                state=self.root/'logs/final-write-errors/error-state.json';deadline=time.monotonic()+3
                while not state.is_file() and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(thread.is_alive());self.assertFalse(path.exists());self.assertEqual(finished,[])
                row=json.loads(state.read_text());faults.resume(row['root'],row['incident'])
                thread.join(3)
                self.assertFalse(thread.is_alive());self.assertEqual(finished,[True])
                self.assertEqual(json.loads(path.read_text()),payload);self.assertEqual(len(attempts),2)
            finally:
                if thread.is_alive():
                    execution.atomic(state.parent/'cancel-request.json',{'external_cancel':True});thread.join(3)

    def test_classification_matrix_and_no_termination_decision(self):
        expected={401:('model_auth',False),403:('model_auth',False),402:('model_balance',False),
            400:('model_request_rejected',False),404:('model_request_rejected',False),422:('model_request_rejected',False),
            429:('model_capacity',True),503:('model_capacity',True),408:('model_timeout',True)}
        for code,(kind,retry) in expected.items():
            with self.subTest(code=code):
                row=remote_retry.diagnose({'codexErrorInfo':{'httpConnectionFailed':{'httpStatusCode':code}}})
                self.assertEqual((row['category'],row['retryable']),(kind,retry))
                self.assertNotIn('exit',row);self.assertNotIn('cleanup',row)
        for code,kind in [('insufficient_quota','model_quota'),('usage_limit_reached','model_quota'),
            ('credit_balance_exhausted','model_balance'),('network_error','model_transport'),
            ('response_stream_disconnected','model_stream_interrupted'),('timeout','model_timeout'),
            ('local_protocol_rejected','harness_bug'),('harness_bug','harness_bug')]:
            self.assertEqual(remote_retry.diagnose({'code':code})['category'],kind)
        self.assertEqual(remote_retry.diagnose(OSError(5,'disk failure'))['category'],'harness_bug')
        self.assertEqual(remote_retry.diagnose(OSError(errno.ENOSPC,'full disk'))['category'],'harness_bug')
        self.assertEqual(remote_retry.diagnose(OSError(errno.ENETUNREACH,'offline'))['category'],'model_transport')
        self.assertEqual(remote_retry.diagnose(http.client.IncompleteRead(b'partial'))['category'],'model_stream_interrupted')
        self.assertEqual(remote_retry.diagnose({'code':'network_error','carrier_error':{'httpStatusCode':502}})['category'],'model_transport')

    def test_quota_auth_and_rejection_override_capacity(self):
        for error in [{'code':'insufficient_quota','httpStatusCode':429},
                      {'code':'authentication_error','httpStatusCode':503},
                      {'code':'context_length_exceeded','httpStatusCode':503}]:
            self.assertFalse(remote_retry.diagnose(error)['retryable'])

    def test_unresolved_mathematics_is_not_misreported_as_a_service_or_software_fault(self):
        row=faults.outcome_error({'status':'SUBSTANTIVE_GAP','error':'located unresolved implication'})
        self.assertEqual(remote_retry.diagnose(row)['category'],'workflow_blocked')
        self.assertFalse(remote_retry.diagnose(row)['retryable'])
        self.assertEqual(row['outcome']['status'],'SUBSTANTIVE_GAP')

    def test_standalone_paused_stage_has_a_guarded_cancel_command(self):
        gate=self.gate();gate.wait=lambda _:faults.cancel_paused(self.root)
        with self.assertRaises(execution.Cancelled):gate.pause({'httpStatusCode':403})
        self.assertEqual(gate.state['state'],'CANCELLED')

    def test_nonretryable_fault_keeps_a_live_checkpoint_and_cancels_only_on_request(self):
        gate=self.gate();stopped=[]
        def wait(_):
            self.assertEqual(gate.state['state'],'PAUSED_ERROR')
            self.assertFalse(gate.state['cleanup_authorized'])
            self.assertTrue(gate.path.is_file());self.cancel(gate)
        gate.wait=wait
        with self.assertRaises(execution.Cancelled):gate.pause({'httpStatusCode':403})
        row=json.loads(gate.path.read_text())
        self.assertEqual(row['state'],'CANCELLED');self.assertEqual(row['retries'],0)
        self.notifier.assert_called_once()

    def test_explicit_resume_is_incident_bound_and_records_the_original_fault(self):
        gate=self.gate()
        def wait(_):faults.resume(self.root,gate.state['incident'])
        gate.wait=wait
        result=gate.pause({'code':'network_error'},retries=10,checkpoint={'thread_id':'same-thread'})
        self.assertEqual(result['state'],'RESUMED');self.assertEqual(result['retries'],10)
        self.assertEqual(result['checkpoint']['thread_id'],'same-thread')
        self.assertEqual(len(gate.resumed),1);self.assertEqual(faults.pending(self.root),[])
        with self.assertRaises(ValueError):faults.resume(self.root,result['incident'])

    def test_local_bug_requires_verified_repair_and_cannot_blindly_replay(self):
        gate=self.gate()
        def wait(_):
            with self.assertRaises(ValueError):faults.resume(self.root,gate.state['incident'])
            self.cancel(gate)
        gate.wait=wait
        with self.assertRaises(execution.Cancelled):gate.pause(ValueError('duplicate evidence index'),resumable=False)
        self.assertIn('duplicate evidence index',json.dumps(gate.state))

    def test_old_incident_control_cannot_resume_a_new_error(self):
        gate=self.gate();count=0
        def wait(_):
            nonlocal count
            count+=1
            if count==1:
                execution.atomic(gate.logs/'error-control'/'old.json',{'incident':'old','action':'resume'})
            else:self.cancel(gate)
        gate.wait=wait
        with self.assertRaises(execution.Cancelled):gate.pause({'httpStatusCode':401})
        self.assertEqual(count,2)

    def test_pending_delivery_does_not_exit_or_spam(self):
        gate=self.gate();gate.notify=Mock(return_value={'status':'PENDING','reason':'offline UI'})
        def wait(_):
            for _ in range(5):gate.report()
            self.cancel(gate)
        gate.wait=wait
        with self.assertRaises(execution.Cancelled):gate.pause({'httpStatusCode':402})
        self.assertEqual(gate.notify.call_count,3)
        self.assertEqual(gate.state['notification']['status'],'PENDING')

    def test_successful_notification_is_not_repeated(self):
        gate=self.gate()
        def wait(_):
            for _ in range(10):gate.report()
            self.cancel(gate)
        gate.wait=wait
        with self.assertRaises(execution.Cancelled):gate.pause({'code':'usage_limit_reached'})
        self.assertEqual(self.notifier.call_count,1)

    def test_error_detail_redaction_preserves_useful_diagnostics(self):
        gate=self.gate();gate.wait=lambda _:self.cancel(gate)
        with self.assertRaises(execution.Cancelled):
            gate.pause({'httpStatusCode':403,'message':'Denied: Bearer secret-credential',
                        'access_token':'other-secret','accessToken':'camel-secret','detail':{'request_id':'r123'}})
        text=gate.path.read_text()
        self.assertNotIn('secret-credential',text);self.assertNotIn('other-secret',text)
        self.assertNotIn('camel-secret',text)
        self.assertIn('r123',text);self.assertIn('403',text)

    def test_local_queue_uses_exact_task_and_no_model_command(self):
        response=Mock(returncode=0,stdout='queued',stderr='')
        with patch.dict(os.environ,{'YUI_CODEX_BINARY':'/portable/codex'}),patch.object(faults.subprocess,'run',return_value=response) as run:
            row=faults.queue_notification('owner-task','fixed diagnostic')
        self.assertEqual(row['status'],'QUEUED')
        self.assertEqual(run.call_args.args[0],['/portable/codex','queue','--thread','owner-task','--message','fixed diagnostic'])
        self.assertEqual(run.call_args.kwargs['timeout'],15)

    def test_missing_owner_remains_a_local_pending_notification(self):
        with patch.object(faults.subprocess,'run') as run:
            result=faults.queue_notification(None,'message')
        self.assertEqual(result['status'],'PENDING');run.assert_not_called()

    def test_invalid_auth_header_is_rejected_without_echoing_credentials_or_contacting_service(self):
        import access_recovery
        execution.atomic(self.root/'auth.json',{'tokens':{'access_token':'synthetic-secret\ninvalid','account_id':'synthetic-account'}})
        with patch.object(access_recovery,'auth_home',return_value=self.root), \
                patch.object(access_recovery.http.client,'HTTPSConnection') as connect:
            with self.assertRaises(ValueError) as error:access_recovery.check({})
        self.assertNotIn('synthetic-secret',str(error.exception));connect.assert_not_called()

    def test_owner_routing_is_saved_outside_all_mathematical_inputs(self):
        import jobs
        from harness_support import PROFILES
        problem=self.root/'problem.md';problem.write_text('Explicit software-control input.')
        with patch.dict(os.environ,{'YUI_OWNER_THREAD_ID':'owner-routing-only-canary'}):
            job=jobs.prepare(problem,track='nl0',profiles=PROFILES)
        root=Path(job['root'])
        self.assertEqual(json.loads((root/'owner-context.json').read_text())['thread_id'],'owner-routing-only-canary')
        self.assertNotIn('owner-routing-only-canary',''.join(p.read_text() for p in (root/'inputs').iterdir()))

    def test_live_resume_refuses_changed_frozen_input(self):
        import jobs
        from harness_support import PROFILES
        problem=self.root/'problem.md';problem.write_text('Explicit frozen software input.')
        job=jobs.prepare(problem,track='nl0',profiles=PROFILES)
        gate=faults.Gate(Path(job['root'])/'logs/stage',notify=self.notifier)
        def wait(_):
            (Path(job['root'])/'inputs/problem.md').write_text('changed input')
            with self.assertRaises(ValueError):faults.resume(gate.root,gate.state['incident'])
            self.cancel(gate)
        gate.wait=wait
        with self.assertRaises(execution.Cancelled):gate.pause({'httpStatusCode':403})
        self.assertEqual(gate.state['state'],'CANCELLED')

    def test_a_raw_resume_control_cannot_bypass_frozen_job_validation(self):
        import jobs
        from harness_support import PROFILES
        problem=self.root/'problem.md';problem.write_text('Explicit frozen software input.')
        job=jobs.prepare(problem,track='nl0',profiles=PROFILES)
        gate=faults.Gate(Path(job['root'])/'logs/stage',notify=self.notifier);count=0
        def wait(_):
            nonlocal count
            count+=1
            if count==1:
                (Path(job['root'])/'inputs/problem.md').write_text('changed input')
                execution.atomic(gate.logs/'error-control'/(gate.state['incident']+'.json'),
                    {'incident':gate.state['incident'],'action':'resume','id':'raw-control'})
            else:
                self.assertIn('resume_rejected',gate.state);self.cancel(gate)
        gate.wait=wait
        with self.assertRaises(execution.Cancelled):gate.pause({'httpStatusCode':403})
        self.assertEqual(gate.resumed,[])

    def test_real_paused_python_thread_sleeps_and_retains_drafts(self):
        draft=self.root/'draft.json';draft.write_text('{"saved":true}')
        gate=self.gate();outcomes=[]
        def worker():
            try:gate.pause({'httpStatusCode':403})
            except execution.Cancelled:outcomes.append('user_cancelled')
        thread=threading.Thread(target=worker);thread.start()
        try:
            deadline=time.monotonic()+2
            while not gate.path.is_file() and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(thread.is_alive());self.assertEqual(json.loads(draft.read_text()),{'saved':True})
            self.assertEqual(json.loads(gate.path.read_text())['state'],'PAUSED_ERROR')
            self.assertEqual(outcomes,[])
        finally:self.cancel(gate);thread.join(timeout=3)
        self.assertFalse(thread.is_alive());self.assertEqual(outcomes,['user_cancelled'])


class ActualTurnTreatmentTests(FaultFixture,unittest.TestCase):
    def trial(self, errors):
        t=run_pilot.Trial.__new__(run_pilot.Trial)
        t.logs=self.root;t.thread_id='retained-thread';t.timeout=None;t.strict=True
        t.model_selection={'id':'gpt-6.1-sol','reasoning_effort':'high','speed':'standard'}
        t.allowed_user_messages=set();t.continuation_count=0;t.turn_results=[];t.accepted=None
        t.api_calls=0;t.proc=Mock();t.proc.poll.return_value=None;t.execution=None;t.execution_task='worker'
        t.request_lock=threading.Lock();t.native_turn_generation=0;t.request_turns={};t.last_response_success=None
        t.tool_history={'old-call':{'result':'retained'}};t.check_runtime_state=Mock()
        t._fault_gate=self.gate();t.refresh_after_error_pause=Mock()
        values=[terminal(i,error) for i,error in enumerate(errors)]+[terminal(len(errors))]
        t.rpc=Mock(side_effect=lambda *a,**k:{'turn':{'id':str(t.rpc.call_count-1)}})
        t.receive_until=Mock(side_effect=lambda *a:values.pop(0));t.wait_remote_retry=Mock()
        return t

    def test_thirty_one_failed_attempts_mean_thirty_retries_then_pause_without_next_call(self):
        t=self.trial([{'httpStatusCode':503}]*31)
        t._fault_gate.wait=lambda _:self.cancel(t._fault_gate)
        with self.assertRaises(execution.Cancelled):t.solve_turns('Frozen original task',smoke=True)
        self.assertEqual(t.rpc.call_count,31);self.assertEqual(t.wait_remote_retry.call_count,30)
        self.assertEqual(t._fault_gate.state['retries'],30)
        self.assertEqual([c.args[0] for c in t.wait_remote_retry.call_args_list],[60]*30)
        self.assertIsNone(t.proc.poll());self.assertEqual(t.tool_history,{'old-call':{'result':'retained'}})

    def test_auth_fault_waits_for_manual_resume_in_the_same_thread(self):
        t=self.trial([{'httpStatusCode':403}])
        t._fault_gate.wait=lambda _:faults.resume(self.root,t._fault_gate.state['incident'])
        self.assertEqual(t.solve_turns('Frozen original task',smoke=True),terminal(1))
        t.wait_remote_retry.assert_not_called();t.refresh_after_error_pause.assert_called_once()
        self.assertTrue(all(c.args[1]['threadId']=='retained-thread' for c in t.rpc.call_args_list))

    def test_same_account_credentials_refresh_without_replacing_context(self):
        t=self.trial([]);t.work=self.root/'workspace';(t.work/'state').mkdir(parents=True)
        old={'tokens':{'access_token':'synthetic-old','account_id':'synthetic-account'}}
        new={'tokens':{'access_token':'synthetic-refreshed','account_id':'synthetic-account'}}
        execution.atomic(t.work/'state/auth.json',old)
        home=self.root/'authentication';home.mkdir();execution.atomic(home/'auth.json',new)
        with patch('runtime_config.auth_home',return_value=home),patch.object(run_pilot,'system_https_proxy',return_value=None):
            run_pilot.Trial.refresh_after_error_pause(t)
        self.assertEqual(json.loads((t.work/'state/auth.json').read_text()),old)
        t.rpc.assert_called_with('account/read',{'refreshToken':True})
        self.assertFalse(hasattr(t,'resumed_auth_headers'))
        self.assertEqual(t.thread_id,'retained-thread');self.assertEqual(t.tool_history,{'old-call':{'result':'retained'}})

    def test_retry_exhaustion_resumes_only_after_operator_action(self):
        t=self.trial([{'code':'network_error'}]*31)
        t._fault_gate.wait=lambda _:faults.resume(self.root,t._fault_gate.state['incident'])
        self.assertEqual(t.solve_turns('Frozen task',smoke=True),terminal(31))
        self.assertEqual(t.rpc.call_count,32);self.assertEqual(t.remote_retry_count,30)

    def test_actual_retry_wait_has_sixty_seconds_of_cancellable_local_sleep(self):
        t=self.trial([]);t.wait_remote_retry=run_pilot.Trial.wait_remote_retry.__get__(t)
        t.remote_retry_count=1;clock=[0.]
        sleeper=Mock();sleeper.wait.side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)
        with patch.object(run_pilot.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(run_pilot.threading,'Event',return_value=sleeper):
            t.wait_remote_retry(60,{'category':'model_transport'},{'id':'failed'},None)
        self.assertEqual(clock[0],60)
        t.rpc.assert_not_called();self.assertEqual(t.thread_id,'retained-thread')


class CarrierRetentionTests(unittest.TestCase):
    def test_postprocessing_cancellation_preserves_existing_call_counts(self):
        with tempfile.TemporaryDirectory() as raw:
            stage=ArtifactStage(Path(raw)/'stage','Offline accounting control.',phase='control',library=False)
            stage.execution=None;stage.execution_task='control'
            stage.api_calls=7;stage.lean_calls=3;stage.remote_retry_count=4
            result,_=stage.cancel_before_start(execution.Cancelled('Synthetic explicit cancellation'))
            self.assertEqual(result['api_calls'],7);self.assertEqual(result['lean_calls'],3)
            self.assertEqual(result['remote_retries'],4);self.assertFalse(result['measurement_valid'])

    def test_located_review_blocker_returns_to_repair_controller_without_teardown(self):
        with tempfile.TemporaryDirectory() as raw:
            stage=ArtifactStage(Path(raw)/'stage','Software control only.',phase='audit-a-global',library=False)
            stage.accepted={'status':'REVIEW_BLOCKED_INCOMPLETE'}
            stage.execution=None
            try:
                with patch.object(stage,'start_process'),patch.object(stage,'rpc',return_value={'thread':{'id':'control'}}), \
                        patch.object(stage,'solve_turns'),patch.object(stage,'pause_error',side_effect=AssertionError('Normal located repair must reach its controller')):
                    result,artifact=stage._execute()
                self.assertEqual(result['status'],'BLOCKED');self.assertEqual(result['task_outcome'],'MATHEMATICAL_REVIEW_FAILED')
                self.assertEqual(artifact,stage.accepted);self.assertTrue(stage.work.exists())
            finally:stage.release_resources('USER_CANCELLED')

    def test_an_error_status_cannot_terminate_a_registered_live_process(self):
        with tempfile.TemporaryDirectory() as raw:
            recorder=execution.Recorder(Path(raw)/'run','synthetic',{'effective':1})
            child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(30)'],start_new_session=True)
            try:
                recorder.register_process(child,'synthetic-carrier')
                with self.assertRaises(ValueError):recorder.close('EXECUTION_FAULT')
                self.assertIsNone(child.poll());self.assertFalse(recorder.done.is_set())
            finally:recorder.close('CANCELLED')
            self.assertIsNotNone(child.poll())

    def test_accepted_author_carrier_is_retained_until_a_finalize_or_user_cancel(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);recorder=execution.Recorder(root/'run','synthetic',{'effective':1})
            stage=ArtifactStage(root/'stage','Software lifecycle control only.',phase='nl0-authoring',library=False)
            child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(30)'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,start_new_session=True)
            try:
                recorder.register_process(child,'synthetic-carrier','author')
                stage.execution=recorder;stage.execution_task='author';stage.proc=child
                stage.thread_id='synthetic-thread'
                stage.accepted={'synthetic_artifact':True}
                with patch.object(stage,'start_process'),patch.object(stage,'rpc',return_value={'thread':{'id':'synthetic-thread'}}),patch.object(stage,'solve_turns'):
                    result,_=stage._execute()
                self.assertEqual(result['status'],'ACCEPTED');self.assertIsNone(child.poll())
                self.assertTrue(stage.work.exists());self.assertTrue(run_resources.safe_stage_workspace(result))
                with self.assertRaises(ValueError):stage.release_resources('ERROR')
                self.assertIsNone(child.poll())
                stage.mode='proof'
                with self.assertRaises(ValueError):stage.release_resources('AUDIT_A_FINALIZED')
                self.assertIsNone(child.poll());stage.mode='nl0-authoring'
                recorder.release_retained('nl0','AUDIT_A_FINALIZED')
                self.assertIsNotNone(child.poll());self.assertFalse(stage.work.exists())
                self.assertTrue(run_resources.safe_stage_workspace(result))
                release=stage.logs/'resources/release.json'
                data=json.loads(release.read_text());data['result_sha256']='changed';execution.atomic(release,data)
                self.assertFalse(run_resources.safe_stage_workspace(result))
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=3)
                recorder.close('CANCELLED')
                if stage.work.exists():__import__('shutil').rmtree(stage.work)


if __name__=='__main__':unittest.main()
