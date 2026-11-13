"""Stopped native-cleanup recovery guards; synthetic records, no model calls."""
import harness_support
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock

import native_cleanup_recovery as recovery
import case_runner
from controller_common import write


class NativeCleanupRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=(Path(self.temp.name)/'prior').resolve();self.root.mkdir()
        self.stage=self.root/'nl0-to-lean/0001/workflow/proof-run/workers/T002'
        self.workflow=self.stage.parents[2];self.interface=self.workflow.parent/'interface'
        self.old={'root':str(self.root),'policy':'normal','time_budget_seconds':None,'case':'synthetic',
                  'profiles':{'nl0':'synthetic-profile','lean':'synthetic-profile'},'max_concurrency':2,
                  'documents':[{'sha256':'input-hash'}]}
        write(self.root/'job.json',self.old)
        self.state={'run_id':'old','controller':{'pid':99999999,'started':'old','pgid':99999999},
            'processes':{},'tasks':{'T001':{'id':'T001','role':'proof','state':'LOCAL_CHECKED'},
             'T002':{'id':'T002','role':'proof','state':'UNFINISHED','log_path':str(self.stage)}}}
        write(self.root/'execution-status.json',self.state)
        write(self.root/'case-result.json',{'result':{'status':'PROOF_UNFINISHED'}})
        write(self.stage/'result.json',{'execution_fault':recovery.FAULT,
            'identity_and_input_boundary_verified':True,'isolation_violation':False,
            'temporary_workspace_removed':True})
        write(self.stage/'prompt.txt',{'packet':{'synthetic':True}})
        for name in ('manifest.json','freeze-seal.json','proof-run/inputs/contract.json',
                     'proof-run/inputs/plan.json'):
            write(self.workflow/name,{})
        write(self.workflow/'proof-run/report.json',{'status':'GRAPH_UNFINISHED','proofs':{'T001':'retained-body'}})
        write(self.interface/'accepted-interface-paths.json',{})
        self.manifest={'interface_binding':str(self.interface/'accepted-interface-paths.json'),
            'authority':{'graph':str(self.root/'source/nl0.json')},'bindings':[],'frozen_input_bindings':[]}
        self.dead=patch('execution_state.same_process',return_value=False);self.dead.start()
        self.bound=patch('full_workflow.workflow.bound',return_value=self.manifest);self.bound.start()
        self.job_validator=patch('jobs.validate',side_effect=lambda job,**kwargs:job);self.job_validator.start()
        self.owner_snapshot=patch('owner_observation.snapshot',return_value={'all_process_exits_verified':True});self.owner_snapshot.start()

    def tearDown(self):self.owner_snapshot.stop();self.job_validator.stop();self.bound.stop();self.dead.stop();self.temp.cleanup()

    def test_qualified_stop_binds_own_records_and_exact_partial_scope(self):
        old,descriptor,files=recovery.qualify(self.root)
        self.assertEqual(descriptor['failed_steps'],['T002'])
        self.assertIn(str(self.stage/'result.json'),{r['path'] for r in files})
        job={**old,'root':str(self.root.parent/'new'),'track':'translate','resume':descriptor,'authority_bindings':files}
        recovery.validate_descriptor(job)
        job['max_concurrency']=3
        with self.assertRaisesRegex(ValueError,'max_concurrency'):recovery.validate_descriptor(job)

    def test_live_controller_or_noncleanup_failure_cannot_be_replayed(self):
        with patch('execution_state.same_process',return_value=True):
            with self.assertRaisesRegex(ValueError,'still live'):recovery.qualify(self.root)
        value=json.loads((self.stage/'result.json').read_text());value['execution_fault']='different fault'
        write(self.stage/'result.json',value)
        with self.assertRaisesRegex(ValueError,'non-cleanup'):recovery.qualify(self.root)

    def test_partial_coverage_mismatch_is_rejected(self):
        write(self.workflow/'proof-run/report.json',{'status':'GRAPH_UNFINISHED','proofs':{}})
        with self.assertRaisesRegex(ValueError,'coverage'):recovery.qualify(self.root)

    def test_translation_resumes_frozen_interface_without_preparing_or_authoring_again(self):
        _,descriptor,_=recovery.qualify(self.root)
        out=self.root.parent/'new';out.mkdir()
        job={'root':str(out),'case':'synthetic','resume':descriptor,'policy':'normal'}
        def from_interface(*args,**kwargs):
            receipt=Path(args[3])/'audit-b/machine-acceptance.json'
            write(receipt,{'synthetic':'Controller wiring only; not actual acceptance'})
            return {'status':'WORKFLOW-PASSED','audit_b':{'status':'AUDIT-B-PASSED',
                'receipt_path':str(receipt),'acceptance_basis':'SYNTHETIC_CONTROL_ONLY'}}
        with patch.object(recovery,'validate_descriptor'), \
                patch.object(case_runner.source_refactor,'run') as prepare, \
                patch.object(case_runner.f,'translate') as author, \
                patch.object(case_runner.f,'from_interface',side_effect=from_interface) as resume:
            result=case_runner.translation_work(job,{},SimpleNamespace(serial=None,proof=None),Mock())
        self.assertEqual(result['status'],'WORKFLOW-PASSED')
        prepare.assert_not_called();author.assert_not_called()
        self.assertEqual(resume.call_args.kwargs['prior_run'],Path(descriptor['prior_proof_run']))


if __name__=='__main__':unittest.main()
