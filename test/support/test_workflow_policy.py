"""End-to-end wiring controls with mocked model gates, never exercise passes."""
import json
from pathlib import Path
import tempfile
import unittest
import shutil
from unittest.mock import patch

import audit_a_campaign as a
import case_runner
import full_workflow as f
from execution_health import StageFailure
import execution_state as e


class WorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.results=self.root/'test/results';self.results.mkdir(parents=True)
        self.source=self.results/'source';self.source.mkdir()
        for name in ['spec.json','nl0.json']:(self.source/name).write_text('{}')

    def tearDown(self):self.tmp.cleanup()

    def submitted_fixture(self):
        from author_check import digest
        import acceptance
        directory=self.results/'author';stage=directory/'stage';case=stage/'case'
        case.mkdir(parents=True)
        for p in (a.CORE/'tests/fixtures/closed-addition').iterdir():
            if p.is_file() and p.name!='audit-a.json':shutil.copyfile(p,case/p.name)
        value={'spec':a.json.loads((case/'spec.json').read_text()),
               'graph':a.json.loads((case/'nl0.json').read_text())}
        authority=acceptance.current().metadata();key=digest(value)
        a.write(stage/'accepted.json',value)
        a.write(case/'author-check-progress.json',{'content_sha256':key,'author_release_ready':True,
            'reported_readiness':'no_known_issue','open_issues':[],'acceptance_contract':authority})
        row={'status':'ACCEPTED','temporary_workspace_removed':True,'isolation_violation':False,
            'execution_health':'NO_RECORDED_FAULT','usage':{'complete':True},
            'transport_health':{'status':'NO_RECORDED_FAULT','faults':[],'uncertainty':[]},
            'exposure':{'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[__import__('run_pilot').MODEL],
                        'standard_tier_verified':True,'acceptance_contract':authority}}
        a.write(stage/'result.json',row)
        (stage/'tools.jsonl').write_text(a.json.dumps({'tool':'submit_draft','result':{
            'stage_complete':True,'author_closing_check':{'author_release_ready':True,'content_sha256':key}}})+'\n')
        return directory,row

    def test_complete_source_recovered_transport_can_be_audited_without_timing_upgrade(self):
        directory,row=self.submitted_fixture();row['execution_health']='FAULT'
        row['usage']['complete']=False
        row['transport_health']={'status':'FAULT','faults':[{'kind':'RELAY_ERROR','request_number':2,'details':'TLS EOF'}],
            'uncertainty':[{'kind':'HTTP_EVIDENCE_INCOMPLETE','missing_requests':[2]}]}
        a.write(directory/'stage/result.json',row)
        result=f.nl0_artifact_for_audit(directory)
        self.assertTrue(result['author_artifact_ready_for_audit'])
        self.assertFalse(result['author_timing_qualified'])
        self.assertFalse(result['execution']['execution_qualified'])
        self.assertEqual(result['transport_recovery_disclosure'],row['transport_health'])
        with self.assertRaises(StageFailure):f.accepted(directory)
        self.assertEqual(a.json.loads((directory/'stage/result.json').read_text()),row)

    def test_incomplete_or_faulted_sources_cannot_bypass_first_a_eligibility(self):
        directory,original=self.submitted_fixture()
        import copy
        variants=[]
        for status in ['UNFINISHED','BLOCKED','CANCELLED']:
            row=copy.deepcopy(original);row['status']=status;variants.append(row)
        row=copy.deepcopy(original);row['isolation_violation']=True;variants.append(row)
        row=copy.deepcopy(original);row['execution_fault']='controller error';variants.append(row)
        row=copy.deepcopy(original);row['exposure']['actual_model_ids']=['other-model'];variants.append(row)
        row=copy.deepcopy(original);row['exposure']['standard_tier_verified']=False;variants.append(row)
        row=copy.deepcopy(original);row['execution_health']='UNVERIFIED';variants.append(row)
        row=copy.deepcopy(original);row['execution_health']='FAULT'
        row['transport_health']['faults']=[{'kind':'TOOL_SERVICE_ERROR'}];variants.append(row)
        for row in variants:
            a.write(directory/'stage/result.json',row)
            with self.assertRaises((StageFailure,e.Cancelled)):f.nl0_artifact_for_audit(directory)

    def test_source_must_match_real_submit_and_current_release_binding(self):
        directory,row=self.submitted_fixture()
        progress=directory/'stage/case/author-check-progress.json'
        value=a.json.loads(progress.read_text());value['author_release_ready']=False;a.write(progress,value)
        with self.assertRaises(StageFailure):f.nl0_artifact_for_audit(directory)
        value['author_release_ready']=True;a.write(progress,value)
        (directory/'stage/tools.jsonl').write_text('')
        with self.assertRaisesRegex(StageFailure,'matching complete author submit'):
            f.nl0_artifact_for_audit(directory)

    def test_case_owner_passes_serial_and_proof_budgets_separately(self):
        job={'kind':'translate','case':'neutral','source':'source','interface':'typed','workflow':'frozen','max_concurrency':5}
        def translate(case,source,interface,workflow,budget,progress,*,proof_budget):
            self.assertEqual(budget.configuration['effective'],1)
            self.assertEqual(proof_budget.configuration['effective'],5)
            self.assertIs(budget.execution,proof_budget.execution)
            with budget:pass
            with proof_budget:pass
            return {'status':'SYNTHETIC_CONTROL_ONLY_NOT_A_MATHEMATICAL_PASS'}
        with patch.object(a,'ROOT',self.root),patch.object(f,'translate',side_effect=translate):
            case_runner.execute(job,self.root/'run')
        row=json.loads((self.root/'run/case-result.json').read_text())
        self.assertEqual(row['concurrency']['proof']['effective'],5)
        self.assertEqual(row['concurrency']['preparation_review']['effective'],1)
        self.assertFalse(e.inspect(self.root/'run')['inspection']['residual_owned_processes'])

    def test_audit_a_only_boundary_never_dispatches_translation(self):
        job={'kind':'audit_source','case':'neutral','source':'source','audit':'audit',
             'stop_after':'audit_a','audit_controls':'fresh-controls'}
        with patch.object(a,'ROOT',self.root),patch.object(f,'audit_source',return_value={'full_acceptance':True}) as audit,\
             patch.object(f,'translate') as translate,patch.object(f,'from_interface') as interface:
            result=case_runner.execute(job,self.root/'run')
        self.assertEqual(result['status'],'DRAFT-AUDIT-PASSED')
        self.assertEqual(result['acceptance_scope'],'NL0_AND_AUDIT_A_ONLY')
        self.assertEqual(audit.call_args.kwargs['controls'],self.results/'fresh-controls/behavioral-summary.json')
        translate.assert_not_called();interface.assert_not_called()

    def test_freeze_and_runner_receive_five_not_the_serial_limit(self):
        review=self.results/'typed-review';review.mkdir()
        contract=self.results/'contract.json';contract.write_text('{"shared_obligations":[]}')
        plan=self.results/'plan.json';plan.write_text('{}')
        copied=self.results/'interface-inputs';copied.mkdir()
        for name in ['nl0.json','spec.json']:(copied/name).write_bytes((self.source/name).read_bytes())
        a.write(review/'bindings.json',{'source_graph':a.bind(copied/'nl0.json'),'spec':a.bind(copied/'spec.json'),
                                     'contract':a.bind(contract),'plan':a.bind(plan)})
        recorder=e.Recorder(self.root/'execution','neutral',a.concurrency.resolve(5))
        budgets=a.concurrency.CaseBudgets(5,execution=recorder)
        try:
            with patch.object(a,'ROOT',self.root),patch.object(f.interface_review,'prepare'),patch.object(f.interface_review,'run'),\
                 patch.object(f.interface_review,'collect',return_value={'all_checks_passed':True}),\
                 patch.object(f.workflow,'freeze') as freeze,\
                 patch.object(f.workflow,'bound',return_value={'contract':str(contract),'plan':str(plan)}),\
                 patch.object(f.run_graph,'run',return_value={'status':'SYNTHETIC_UNFINISHED'}) as run:
                with self.assertRaises(StageFailure) as failed:
                    f.from_interface('neutral',self.source,'typed','frozen',budgets.serial,lambda *args,**kwargs:None,proof_budget=budgets.proof,review_name='typed-review')
                self.assertEqual(failed.exception.result['phase'],'proof')
                self.assertEqual(freeze.call_args.kwargs['max_concurrency'],5)
                self.assertIs(run.call_args.kwargs['budget'],budgets.proof)
                freeze.reset_mock();(copied/'nl0.json').write_text('{"changed":true}')
                with self.assertRaisesRegex(ValueError,'exact source bytes'):
                    f.from_interface('neutral',self.source,'typed','frozen',budgets.serial,lambda *args,**kwargs:None,proof_budget=budgets.proof,review_name='typed-review')
                freeze.assert_not_called()
        finally:recorder.close('SYNTHETIC_CONTROL_ONLY')

    def test_unchanged_accepted_source_does_not_launch_a_new_audit(self):
        (self.source/'audit-a.json').write_text('{}')
        with patch.object(a.nl0,'validate',return_value=({'current_standard_receipt_valid':True,'audit_status':'SYNTHETIC_ONLY'},)),\
             patch.object(a,'prepare') as prepare,patch.object(a,'run') as run,patch.object(a,'collect') as collect:
            result=f.audit_source('neutral',self.source,'new-audit',None,lambda *args,**kwargs:None)
        self.assertTrue(result['reused_unchanged_acceptance'])
        prepare.assert_not_called();run.assert_not_called();collect.assert_not_called()


if __name__=='__main__':unittest.main()
