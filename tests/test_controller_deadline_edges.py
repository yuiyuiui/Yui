"""Real retry/native limits and evidence-integrity edges for shared case budgets."""
import harness_support
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

import concurrency
from controller_common import write
import execution_state as execution
import fault_control
import ir
from native_fault_fixtures import NativeFaultFixture
from native_fixture import NativeFixture
from clean_stage import ArtifactStage
import pilot_common
import native_client
from unittest.mock import patch


class DeadlineEdgeTests(unittest.TestCase):
    def test_initialization_deadline_is_unverified_but_preserves_recorded_faults(self):
        for fault in ('none','context','transport','isolation'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(prefix='yui-startup-budget-') as raw:
                with NativeFixture(raw) as fixture:
                    rpc=fixture.stage.rpc
                    def expire(method,params,**kwargs):
                        response=rpc(method,params,**kwargs)
                        if method=='thread/start':
                            if fault=='transport':
                                (fixture.stage.logs/'native-errors.jsonl').write_text(json.dumps(
                                    {'error':{'code':'service_unavailable','message':'Synthetic recorded startup transport fault'}})+'\n')
                            if fault=='isolation':
                                (fixture.stage.logs/'isolation-violations.jsonl').write_text(json.dumps(
                                    {'synthetic':'Recorded isolation fault before deadline'})+'\n')
                            fixture.recorder.deadline=time.monotonic()-1
                            raise execution.CaseDeadlineExceeded('Synthetic deadline during native initialization')
                        return response
                    original_audit=native_client.audit
                    def audit(path):
                        if fault=='context':raise ValueError('Synthetic real provenance corruption')
                        return original_audit(path)
                    with patch.object(fixture.stage,'rpc',side_effect=expire),patch.object(native_client,'audit',side_effect=audit):
                        fixture.start();fixture.worker.join(5)
                    self.assertFalse(fixture.worker.is_alive())
                    self.assertIsInstance(fixture.exceptions[0],execution.CaseDeadlineExceeded)
                    self.assertEqual(len(fixture.calls),0)
                    result=ir.load(fixture.stage.logs/'result.json')
                    self.assertEqual(result['task_outcome'],
                        'UNFINISHED_ATTRIBUTION_UNVERIFIED' if fault=='none' else 'UNFINISHED_WITH_EXECUTION_FAULT')
                    self.assertEqual(bool(result.get('execution_fault')),fault=='context')
                    if fault=='transport':self.assertTrue(result['transport_health']['faults'])
                    if fault=='isolation':self.assertTrue(result['isolation_violation'])

    def test_constructed_queued_stage_expires_without_starting_a_carrier_or_losing_workspace(self):
        with tempfile.TemporaryDirectory(prefix='yui-queued-budget-') as raw:
            root=Path(raw);recorder=execution.Recorder(root/'run','synthetic-queue',concurrency.resolve(1))
            budget=concurrency.serial_budget(concurrency.Budget(concurrency.resolve(1),execution=recorder))
            stage=ArtifactStage(root/'queued','Synthetic queued work.',phase='control',library=False,budget=budget)
            errors=[]
            def wait_for_slot():
                try:
                    with execution.activate(recorder,'queued'):stage.execute()
                except BaseException as error:errors.append(error)
            try:
                with budget:
                    worker=threading.Thread(target=wait_for_slot);worker.start()
                    until=time.monotonic()+3
                    while 'queued' not in recorder.state['tasks'] and time.monotonic()<until:time.sleep(.01)
                    recorder.deadline=time.monotonic()-1;worker.join(3)
                    self.assertFalse(worker.is_alive())
                    self.assertIsInstance(errors[0],execution.CaseDeadlineExceeded)
                    self.assertIsNone(stage.proc)
                    self.assertTrue(stage.work.exists())
                    self.assertEqual(ir.load(stage.logs/'result.json')['stop_reason'],'CASE_DEADLINE')
                self.assertEqual(budget.report()['active_model_stages'],0)
            finally:recorder.close('CANCELLED')

    def test_failed_native_interrupt_is_retained_as_fault_instead_of_healthy_budget_exhaustion(self):
        with tempfile.TemporaryDirectory(prefix='yui-unconfirmed-interrupt-') as raw:
            def respond(fixture,handler,number,payload):fixture.tool(handler,number,'check_draft',{'synthetic':True})
            with NativeFixture(raw,responder=respond) as fixture:
                dispatch=fixture.stage.dispatch
                def expire(name,args):
                    result=dispatch(name,args);fixture.recorder.deadline=time.monotonic()-1;return result
                with patch.object(fixture.stage,'dispatch',side_effect=expire), \
                     patch.object(fixture.stage,'interrupt_active_turn',side_effect=RuntimeError('Synthetic missing native acknowledgement')):
                    fixture.start();fixture.worker.join(5)
                self.assertFalse(fixture.worker.is_alive())
                self.assertIsInstance(fixture.exceptions[0],execution.CaseDeadlineExceeded)
                result=ir.load(fixture.stage.logs/'result.json')
                self.assertEqual(result['task_outcome'],'UNFINISHED_WITH_EXECUTION_FAULT')
                self.assertIn('interruption unconfirmed',result['execution_fault'])
                self.assertTrue(fixture.stage.work.exists())

    def test_explicit_cancel_wins_when_cancel_and_case_deadline_are_both_present(self):
        with tempfile.TemporaryDirectory(prefix='yui-cancel-budget-race-') as raw:
            def respond(fixture,handler,number,payload):fixture.tool(handler,number,'check_draft',{'synthetic':True})
            with NativeFixture(raw,responder=respond) as fixture:
                dispatch=fixture.stage.dispatch
                def cancel(name,args):
                    result=dispatch(name,args)
                    fixture.recorder.deadline=time.monotonic()-1
                    execution.request_cancel(fixture.recorder.root)
                    return result
                with patch.object(fixture.stage,'dispatch',side_effect=cancel):fixture.start();fixture.wait()
                result=fixture.outcomes[0][0]
                self.assertEqual(result['status'],'CANCELLED')
                self.assertEqual(result['task_outcome'],'EXTERNAL_CANCELLED')
                self.assertEqual(result['stop_reason'],'EXTERNAL_CANCEL')

    def test_remote_retry_wait_expires_without_another_work_request_or_losing_original_fault(self):
        with tempfile.TemporaryDirectory(prefix='yui-retry-deadline-') as raw:
            with NativeFaultFixture(raw,503,real_wait=True) as fixture:
                fixture.start();fixture.wait(lambda:(fixture.stage.logs/'remote-retries.jsonl').exists())
                fixture.recorder.deadline=time.monotonic()-1
                fixture.worker.join(6)
                self.assertFalse(fixture.worker.is_alive())
                self.assertEqual(len(fixture.exceptions),1)
                self.assertIsInstance(fixture.exceptions[0],execution.CaseDeadlineExceeded)
                self.assertEqual(len(fixture.calls),2,'No service retry is authorized beyond the case budget')
                result=ir.load(fixture.stage.logs/'result.json')
                self.assertEqual(result['task_outcome'],'UNFINISHED_WITH_EXECUTION_FAULT')
                self.assertTrue(result['transport_health']['faults'])
                self.assertFalse(result.get('execution_fault'),'The original provider error is not a harness bug')

    def test_deadline_during_real_lean_check_is_case_scope_and_not_tool_failure(self):
        with tempfile.TemporaryDirectory(prefix='yui-lean-case-deadline-') as raw:
            root=Path(raw);work=root/'work';(work/'input').mkdir(parents=True)
            source=work/'input/Slow.lean';source.write_text('import Lean\n#eval IO.sleep 30000\n')
            recorder=execution.Recorder(root/'run','synthetic-lean-budget',concurrency.resolve(1))
            recorder.task('T001',state='RUNNING',role='proof')
            try:
                recorder.deadline=time.monotonic()+.4
                with execution.activate(recorder,'T001'),self.assertRaises(execution.CaseDeadlineExceeded):
                    pilot_common.run_lean(source,work)
                checked=recorder.state['tasks']['T001']['latest_lean_check']
                result=ir.load(checked['log_path'])
                self.assertEqual(result['timeout_scope'],'whole_case')
                self.assertEqual(result['error_kind'],'CASE_DEADLINE')
                self.assertFalse(recorder.state['tasks']['T001'].get('current_lean_check'))
                self.assertTrue(all(p['state']=='EXITED' for p in recorder.state['processes'].values()))
                self.assertFalse(recorder.cancelled())
            finally:recorder.close('CANCELLED')

    def test_missing_identity_empty_history_and_changed_health_evidence_are_not_healthy_exhaustion(self):
        with tempfile.TemporaryDirectory(prefix='yui-health-integrity-') as raw:
            root=Path(raw);recorder=execution.Recorder(root/'run','synthetic-health',{})
            error=execution.CaseDeadlineExceeded('Synthetic explicit deadline')
            try:
                self.assertEqual(recorder.deadline_result(error)['task_outcome'],'UNFINISHED_ATTRIBUTION_UNVERIFIED')
                unknown={'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT'}
                write(root/'old/result.json',unknown);recorder.record_stage('old',root/'old',unknown)
                self.assertEqual(recorder.deadline_result(error)['task_outcome'],'UNFINISHED_ATTRIBUTION_UNVERIFIED')
                known={'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT',
                       'identity_and_input_boundary_verified':True}
                write(root/'current/result.json',known);recorder.record_stage('current',root/'current',known)
                write(root/'old/result.json',{'silently':'replaced evidence'})
                result=recorder.deadline_result(error)
                self.assertEqual(result['task_outcome'],'UNFINISHED_WITH_EXECUTION_FAULT')
                self.assertIn('Bound stage result changed',str(result))
            finally:recorder.close('CANCELLED')

    def test_ordinary_resume_cannot_silently_extend_budget_and_explicit_cancel_keeps_stop_reason(self):
        with tempfile.TemporaryDirectory(prefix='yui-budget-control-') as raw:
            root=Path(raw);messages=[];gate=fault_control.Gate(root,notify=lambda thread,text:messages.append(text) or {'status':'QUEUED'})
            def control(_):
                with self.assertRaisesRegex(ValueError,'budget is exhausted'):
                    fault_control.resume(root,gate.state['incident'])
                fault_control.cancel_paused(root)
            gate.wait=control
            outcome={'status':'UNFINISHED','stop_reason':'CASE_DEADLINE','task_outcome':'MODEL_BUDGET_EXHAUSTED'}
            with self.assertRaises(execution.Cancelled):
                gate.pause(fault_control.outcome_error(outcome),resumable=False)
            self.assertEqual(gate.state['fault']['category'],'workflow_blocked')
            self.assertFalse(gate.state['cleanup_authorized'])
            self.assertEqual(gate.state['error']['outcome']['stop_reason'],'CASE_DEADLINE')
            self.assertIn('budget is exhausted',messages[0])


if __name__=='__main__':unittest.main()
