"""End-to-end wiring controls with mocked model gates, never exercise passes."""
import harness_support

from pathlib import Path
import tempfile
import unittest
import shutil
from unittest.mock import patch

import audit_a_campaign as a
import full_workflow as f
from execution_health import StageFailure
import execution_state as e


class WorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.results=self.root/'generated';self.results.mkdir(parents=True)
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
        self.assertEqual(f.accepted(directory),row)
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
            with self.assertRaises((StageFailure,e.Cancelled)):f.accepted(directory)

    def test_source_must_match_real_submit_and_current_release_binding(self):
        directory,row=self.submitted_fixture()
        progress=directory/'stage/case/author-check-progress.json'
        value=a.json.loads(progress.read_text());value['author_release_ready']=False;a.write(progress,value)
        with self.assertRaises(StageFailure):f.nl0_artifact_for_audit(directory)
        value['author_release_ready']=True;a.write(progress,value)
        (directory/'stage/tools.jsonl').write_text('')
        with self.assertRaisesRegex(StageFailure,'matching complete author submit'):
            f.nl0_artifact_for_audit(directory)

    def test_unchanged_accepted_source_does_not_launch_a_new_audit(self):
        (self.source/'audit-a.json').write_text('{}')
        with patch.object(a.nl0,'validate',return_value=({'current_standard_receipt_valid':True,'audit_status':'SYNTHETIC_ONLY'},)),\
             patch.object(a,'prepare') as prepare,patch.object(a,'run') as run,patch.object(a,'collect') as collect:
            result=f.audit_source('neutral',self.source,'new-audit',None,lambda *args,**kwargs:None)
        self.assertTrue(result['reused_unchanged_acceptance'])
        prepare.assert_not_called();run.assert_not_called();collect.assert_not_called()


if __name__=='__main__':unittest.main()
