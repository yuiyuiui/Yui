"""Deadline propagation through real stage/case controls; no production model."""
import harness_support
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from clean_stage import ArtifactStage
from native_fixture import NativeFixture
import case_runner
import concurrency
import execution_state as execution
import fault_control
import ir
import jobs
import remote_retry


class DeadlinePathTests(unittest.TestCase):
    def test_expiration_before_start_retains_stage_and_reaches_case_in_both_tracks(self):
        with tempfile.TemporaryDirectory(prefix='yui-deadline-before-') as raw:
            for phase in ('nl0-authoring', 'audit-a-global', 'translation-preparation'):
                with self.subTest(phase=phase):
                    root = Path(raw)/phase
                    recorder = execution.Recorder(root/'run', 'synthetic-deadline', {})
                    stage = ArtifactStage(root/'stage', 'Synthetic explicit frozen stage.', phase=phase,
                                          library=False, budget=concurrency.serial_budget())
                    try:
                        recorder.deadline = time.monotonic()-1
                        with execution.activate(recorder), \
                             patch.object(stage, 'pause_error', side_effect=AssertionError('Worker must propagate the case deadline')):
                            with self.assertRaises(execution.CaseDeadlineExceeded): stage.execute()
                        result = ir.load(stage.logs/'result.json')
                        self.assertEqual(result['stop_reason'], 'CASE_DEADLINE')
                        self.assertFalse(result['identity_and_input_boundary_verified'])
                        self.assertTrue(stage.work.exists())
                        self.assertTrue(any(s is stage for s,_ in recorder.retained_stages))
                        self.assertEqual(recorder.state['concurrency']['active_model_stages'], 0)
                    finally:
                        stage.release_resources('USER_CANCELLED');recorder.close('CANCELLED')

    def test_native_work_deadline_saves_health_without_a_worker_error_pause(self):
        with tempfile.TemporaryDirectory(prefix='yui-native-deadline-') as raw:
            def respond(fixture, handler, number, payload):
                fixture.tool(handler, number, 'check_draft', {'synthetic_checkpoint':True})
            with NativeFixture(Path(raw), responder=respond) as fixture:
                original = fixture.stage.dispatch
                def expire_after_tool(name, args):
                    result = original(name, args)
                    fixture.recorder.deadline = time.monotonic()-1
                    return result
                with patch.object(fixture.stage, 'dispatch', side_effect=expire_after_tool), \
                     patch.object(fixture.stage, 'pause_error', side_effect=AssertionError('Budget is not a worker software fault')):
                    fixture.start();fixture.worker.join(8)
                self.assertFalse(fixture.worker.is_alive())
                self.assertEqual(len(fixture.exceptions), 1)
                self.assertIsInstance(fixture.exceptions[0], execution.CaseDeadlineExceeded)
                result = ir.load(fixture.stage.logs/'result.json')
                self.assertEqual(result['task_outcome'], 'MODEL_BUDGET_EXHAUSTED')
                self.assertEqual(result['stop_reason'], 'CASE_DEADLINE')
                self.assertTrue(result['identity_and_input_boundary_verified'])
                self.assertFalse(result.get('tool_execution_fault'))
                self.assertIsNone(fixture.stage.proc.poll(), 'Budget alone must preserve the carrier')
                self.assertFalse((fixture.stage.logs/'error-state.json').exists())

    def test_real_native_result_keeps_identity_in_the_case_summary(self):
        with tempfile.TemporaryDirectory(prefix='yui-stage-health-') as raw:
            with NativeFixture(Path(raw)) as fixture:
                fixture.start();fixture.wait()
                result = fixture.outcomes[0][0]
                summary = fixture.recorder.state['tasks'][fixture.stage.execution_task]['stage_result']
                self.assertTrue(result['identity_and_input_boundary_verified'])
                self.assertIs(summary.get('identity_and_input_boundary_verified'), True)

    def test_case_retains_the_native_budget_outcome_until_explicit_cancellation(self):
        with tempfile.TemporaryDirectory(prefix='yui-case-deadline-') as raw:
            root = Path(raw);problem=root/'proof.txt';problem.write_text('Synthetic control task, not a proof claim.')
            def respond(fixture, handler, number, payload):
                fixture.tool(handler, number, 'check_draft', {'synthetic_checkpoint':True})
            with NativeFixture(root/'native', responder=respond) as fixture:
                job = jobs.prepare(problem, track='nl0', profiles=harness_support.PROFILES,
                                   max_concurrency=1, output=root/'run', time_budget_seconds=60)
                original_dispatch = fixture.stage.dispatch
                observed = []
                def expire(name, args):
                    result = original_dispatch(name, args)
                    fixture.stage.execution.deadline = time.monotonic()-1
                    return result
                def work(job, recorder, budget, progress, **kwargs):
                    fixture.stage.budget = budget
                    fixture.stage.execute()
                    raise AssertionError('Deadline should leave the stage')
                original_pause = fault_control.Gate.pause
                def pause(gate, error, **kwargs):
                    self.assertEqual(gate.task, 'case-controller', 'Only the case controller may pause for this budget')
                    observed.append(error)
                    self.assertEqual(remote_retry.diagnose(error)['category'], 'workflow_blocked')
                    self.assertTrue(fixture.stage.work.exists())
                    self.assertIsNone(fixture.stage.proc.poll())
                    gate.notify = lambda *_:{'status':'QUEUED','synthetic':True}
                    gate.wait = lambda _:execution.request_cancel(gate.recorder.root)
                    return original_pause(gate, error, **kwargs)
                try:
                    with patch.object(case_runner, 'nl0_work', side_effect=work), \
                         patch.object(fixture.stage, 'dispatch', side_effect=expire), \
                         patch.object(fault_control.Gate, 'pause', pause):
                        result = case_runner.execute(job)
                finally:
                    recorder=getattr(fixture.stage,'execution',None)
                    if recorder and not recorder.done.is_set():recorder.close('CANCELLED')
                self.assertEqual(len(observed), 1)
                self.assertEqual(result['retained_error']['task_outcome'], 'MODEL_BUDGET_EXHAUSTED')
                self.assertEqual(result['retained_error']['stop_reason'], 'CASE_DEADLINE')
                self.assertEqual(result['status'], 'CANCELLED')
                self.assertFalse(result['completion']['acceptance_target_satisfied'])
                self.assertEqual(ir.load(Path(job['root'])/'case-result.json')['result']['status'], 'CANCELLED')


if __name__ == '__main__': unittest.main()
