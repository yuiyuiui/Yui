"""Controller routing across repeated assignments, without a model or math verdict."""
import harness_support
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import shutil
import case_runner
import concurrency
import full_workflow
import final_acceptance
from controller_common import write
from execution_health import StageFailure


class WorkflowHandoffTests(unittest.TestCase):
    def test_b_final_changed_or_missing_findings_refuse_all_decisions_after_user_wait(self):
        for action,mutation in ((a,m) for a in ('deliver-actual','recheck','reset-translation')
                                for m in ('replace','remove')):
            with self.subTest(action=action,mutation=mutation),tempfile.TemporaryDirectory() as raw:
                out=Path(raw)/'workflow'
                def prepare(audit,directory,**kwargs):
                    write(Path(directory)/'report.json',{'all_checks_passed':False,'synthetic':'reviewed findings'})
                def decide(gate,*args,**kwargs):
                    write(gate.path,{'state':'USER_DECIDED','control':{'action':action}})
                    if mutation=='remove':(gate.logs.parent/'report.json').unlink()
                    else:write(gate.logs.parent/'report.json',{'all_checks_passed':False,'synthetic':'changed while awaiting user'})
                    return {'control':{'action':action}}
                with patch.object(final_acceptance,'check',return_value={'interface_consistent':False}), \
                     patch.object(full_workflow.audit_b_review,'prepare',side_effect=prepare), \
                     patch.object(full_workflow.audit_b_review,'run'), \
                     patch.object(full_workflow.audit_b_review,'collect',return_value={'all_checks_passed':False}), \
                     patch('fault_control.Gate.pause',decide):
                    with self.assertRaises(StageFailure) as caught:
                        full_workflow.finish_translation('synthetic',out,concurrency.serial_budget(),lambda *a,**kw:None)
                self.assertEqual(caught.exception.result['status'],'FINAL_ARTIFACT_CHANGED')

    def test_unchanged_nl0_does_not_end_the_same_author_reviewer_loop(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);baseline=root/'baseline'
            shutil.copytree(harness_support.FIXTURES/'closed-addition',baseline)
            def prepare(inputs,out,**kwargs):
                shutil.copytree(baseline,out/'stage/case')
                (out/'prompt.txt').write_text('Synthetic retained author assignment.')
            class SubmittedStage:
                def __init__(self,*args,**kwargs):pass
                def execute(self):pass
            budget=SimpleNamespace(execution=SimpleNamespace(check=lambda:None))
            with patch.object(case_runner.nl0_author,'prepare',side_effect=prepare),\
                 patch.object(case_runner,'ArtifactStage',SubmittedStage),\
                 patch.object(full_workflow,'stage_seconds',return_value=None),\
                 patch.object(full_workflow,'nl0_artifact_for_audit',return_value={}):
                source=case_runner.author_stage({'root':str(root),'case':'synthetic'},root/'author',budget,
                    baseline=baseline,obligations={'synthetic':'review findings'})
            self.assertEqual(case_runner.source_key(source),case_runner.source_key(baseline))
            self.assertTrue((source/'nl0.json').is_file())

    def test_unchanged_interface_is_reviewed_by_the_retained_pair_without_automatic_pause(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);previous=root/'previous.json';write(previous,{'synthetic':'same interface'})
            def prepare(source,problem,out,**kwargs):
                write(out/'stage/accepted.json',full_workflow.ir.load(previous))
            with patch.object(full_workflow.author,'prepare',side_effect=prepare),\
                 patch.object(full_workflow.author,'run'),patch.object(full_workflow,'accepted',return_value={}),\
                 patch.object(full_workflow,'stage_seconds',return_value=None),\
                 patch.object(full_workflow,'from_interface',return_value={'status':'REVIEW_REACHED'}) as review:
                result=full_workflow.translate('synthetic',root/'source',root/'interface',root/'workflow',None,
                    lambda *a,**k:None,prior_interface=previous,prior_run=root/'retained')
            self.assertEqual(result['status'],'REVIEW_REACHED');review.assert_called_once()

    def test_b_final_recheck_occurs_only_after_the_user_selects_it(self):
        with tempfile.TemporaryDirectory() as raw:
            out=Path(raw)/'workflow';events=[]
            def prepare(audit,directory,**kwargs):
                write(Path(directory)/'review.json',{'synthetic':'review'})
                write(Path(directory)/'report.json',{'all_checks_passed':False});events.append('prepare')
            def decide(gate,*args,**kwargs):
                events.append('user-recheck');write(gate.path,{'state':'USER_DECIDED','control':{'action':'recheck'}})
                return {'control':{'action':'recheck'}}
            with patch.object(final_acceptance,'check',return_value={'interface_consistent':False}),\
                 patch.object(full_workflow.audit_b_review,'prepare',side_effect=prepare),\
                 patch.object(full_workflow.audit_b_review,'run',side_effect=lambda *a,**kw:events.append('review')),\
                 patch.object(full_workflow.audit_b_review,'collect',side_effect=[{'all_checks_passed':False},{'all_checks_passed':True}]),\
                 patch('fault_control.Gate.pause',decide),\
                 patch.object(full_workflow.workflow,'finish',return_value={'status':'SYNTHETIC_ACCEPTANCE'}) as finish:
                result=full_workflow.finish_translation('neutral',out,concurrency.serial_budget(),lambda *a,**kw:None)
            self.assertEqual(events,['prepare','review','user-recheck','prepare','review'])
            self.assertEqual(result['status'],'SYNTHETIC_ACCEPTANCE')
            self.assertEqual(finish.call_count,1)

    def test_source_and_interface_findings_return_to_the_same_role_manager(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);authority={'graph':str(root/'source/nl0.json'),'spec':str(root/'source/spec.json'),'audit_a':str(root/'source/audit-a.json')}
            calls=[];managers=[]
            def prepare(actual,out,budget,**kwargs):
                calls.append(('prepare',kwargs));managers.append(kwargs['sessions'])
                if len(calls)==1:
                    write(out/'stage/accepted.json',{'candidate':'synthetic extraction'})
                    write(out/'review-findings.json',{'notes':'Synthetic located source defect.'})
                    raise StageFailure('SOURCE_EXTRACTION_REVIEW_FAILED','Synthetic finding',phase='source-extraction-review',evidence=out/'review-findings.json')
                self.assertTrue(Path(kwargs['prior_artifact']).is_file())
                self.assertTrue(Path(kwargs['findings']).is_file());return actual
            def translate(case,source,interface,destination,budget,progress,**kwargs):
                calls.append(('translate',kwargs));managers.append(kwargs['sessions'])
                if kwargs['prior_interface'] is None:
                    write(interface/'stage/accepted.json',{'candidate':'synthetic interface'})
                    write(interface.parent/'interface-review/report.json',{'all_checks_passed':False})
                    write(interface.parent/'interface-review/stage/accepted.json',{'findings':['Synthetic paired mismatch.']})
                    raise StageFailure('INTERFACE_REVIEW_FAILED','Synthetic finding',phase='interface-review')
                self.assertTrue(Path(kwargs['prior_interface']).is_file())
                self.assertIn('actual_review',kwargs['diagnostics'])
                raise StageFailure('TEST_STOP','Reached the next proof assignment')
            with patch.object(case_runner.source_refactor,'run',side_effect=prepare),patch.object(case_runner.f,'translate',side_effect=translate):
                with self.assertRaisesRegex(StageFailure,'next proof assignment'):
                    case_runner.translation_work({'root':str(root),'case':'neutral','policy':'normal'},authority,concurrency.CaseBudgets(2),lambda *a,**k:None)
            self.assertEqual([kind for kind,kw in calls],['prepare','prepare','translate','translate'])
            self.assertTrue(all(manager is managers[0] for manager in managers))

    def test_operational_source_failure_does_not_become_an_author_revision(self):
        with tempfile.TemporaryDirectory() as raw:
            error=StageFailure('EXECUTION_FAULT','Synthetic controller error',phase='source-preparation')
            with patch.object(case_runner.source_refactor,'run',side_effect=error) as prepare,patch.object(case_runner.f,'translate') as translate:
                with self.assertRaises(StageFailure) as raised:
                    case_runner.translation_work({'root':raw,'case':'neutral','policy':'normal'},{},concurrency.CaseBudgets(2),lambda *a,**k:None)
            self.assertIs(raised.exception,error);self.assertEqual(prepare.call_count,1);translate.assert_not_called()


if __name__=='__main__':unittest.main()
