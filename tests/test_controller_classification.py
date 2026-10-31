"""Real interface handoffs and explicit error treatment; no mathematical claim."""
import harness_support
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import case_runner
import concurrency
import execution_state
import fault_control
import full_workflow
import remote_retry
import jobs
import source_fixtures
from controller_common import write
from execution_health import StageFailure


class ClassificationPathTests(unittest.TestCase):
    def test_first_pass_qualified_interface_nonpass_reaches_workflow_blocker(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);authority={k:str(root/'source'/name) for k,name in
                [('graph','nl0.json'),('spec','spec.json'),('audit_a','audit-a.json')]}
            job={'root':str(root),'case':'synthetic-interface','policy':'first-pass'}
            def translate(case,source,interface,destination,budget,progress,**kwargs):
                write(interface/'accepted-interface-paths.json',{'contract':'unused-control','plan':'unused-control'})
                return full_workflow.from_interface(case,source,interface,destination,budget,progress,
                    proof_budget=kwargs['proof_budget'],authority=authority)
            with patch.object(case_runner.source_refactor,'run',return_value=authority), \
                 patch.object(full_workflow,'translate',side_effect=translate), \
                 patch.object(full_workflow.interface_review,'prepare'), \
                 patch.object(full_workflow.interface_review,'run'), \
                 patch.object(full_workflow.interface_review,'collect',return_value={
                     'all_checks_passed':False,'review_status':'MATHEMATICAL_REVIEW_FAILED'}):
                with self.assertRaises(StageFailure) as caught:
                    case_runner.translation_attempt(job,authority,concurrency.CaseBudgets(1),lambda *a,**kw:None)
            error=fault_control.outcome_error(caught.exception.result)
            self.assertEqual(error['outcome']['status'],'INTERFACE_REVIEW_FAILED')
            diagnosis=remote_retry.diagnose(error)
            self.assertEqual(diagnosis['category'],'workflow_blocked')
            self.assertFalse(diagnosis['retryable'])

    def test_budget_is_not_remote_timeout_but_real_faults_and_unknown_outcomes_stay_faults(self):
        for error in [execution_state.CaseDeadlineExceeded('Explicit case budget'),
                      fault_control.outcome_error({'status':'UNFINISHED','stop_reason':'CASE_DEADLINE',
                                                  'task_outcome':'UNFINISHED_ATTRIBUTION_UNVERIFIED'})]:
            with self.subTest(error=error):
                self.assertEqual(remote_retry.diagnose(error)['category'],'workflow_blocked')
        for result in [{'status':'UNFINISHED'}, {'status':'UNKNOWN_OUTCOME'},
                       {'status':'INTERFACE_REVIEW_FAILED','execution_fault':'Actual local tool failure'}]:
            with self.subTest(result=result):
                self.assertEqual(remote_retry.diagnose(fault_control.outcome_error(result))['category'],'harness_bug')
        self.assertEqual(remote_retry.diagnose(TimeoutError('Remote request timed out'))['category'],'model_timeout')
        self.assertEqual(remote_retry.diagnose({'code':'insufficient_quota'})['category'],'model_quota')

    def test_first_pass_nonpass_reaches_actual_case_pause_and_preserves_its_outcome_on_cancel(self):
        with tempfile.TemporaryDirectory(prefix='yui-first-pass-case-') as raw:
            root=Path(raw);graph,spec,_=source_fixtures.case(root/'source')
            receipt=source_fixtures.synthetic_audit(graph,spec)
            (root/'source/audit-a.json').write_bytes(receipt.read_bytes())
            job=jobs.prepare(root/'source/problem.txt',track='translate',source=root/'source',
                profiles=harness_support.PROFILES,max_concurrency=1,policy='first-pass',output=root/'run')
            def translate(case,source,interface,destination,budget,progress,**kwargs):
                write(interface/'accepted-interface-paths.json',{'contract':'unused-control','plan':'unused-control'})
                return full_workflow.from_interface(case,source,interface,destination,budget,progress,
                    proof_budget=kwargs['proof_budget'],authority=job['source_authority'])
            def review(out):
                verdict={'all_checks_passed':False,'review_status':'MATHEMATICAL_REVIEW_FAILED'}
                write(Path(out)/'report.json',verdict);return verdict
            original_pause=fault_control.Gate.pause
            observed=[]
            def pause(gate,error,**kwargs):
                observed.append(error)
                self.assertEqual(remote_retry.diagnose(error)['category'],'workflow_blocked')
                gate.notify=lambda *_:{'status':'QUEUED','synthetic':True}
                gate.wait=lambda _:execution_state.request_cancel(gate.recorder.root)
                return original_pause(gate,error,**kwargs)
            with patch.object(case_runner.source_refactor,'run',return_value=job['source_authority']), \
                 patch.object(full_workflow,'translate',side_effect=translate), \
                 patch.object(full_workflow.interface_review,'prepare'), \
                 patch.object(full_workflow.interface_review,'run'), \
                 patch.object(full_workflow.interface_review,'collect',side_effect=review), \
                 patch.object(fault_control.Gate,'pause',pause):
                result=case_runner.execute(job)
            self.assertEqual(len(observed),1)
            self.assertEqual(result['retained_error']['status'],'INTERFACE_REVIEW_FAILED')
            self.assertEqual(result['status'],'CANCELLED')
            self.assertFalse(result['completion']['acceptance_target_satisfied'])


if __name__=='__main__':unittest.main()
