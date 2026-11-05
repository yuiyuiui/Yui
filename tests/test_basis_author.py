"""Bounded own-draft tools and retained native-fault evidence; no model calls."""
import harness_support
from basis_fixtures import artifact, dependency, TARGET
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import basis
import basis_author
import basis_native
import ir
from controller_common import manifest
from read_views import encoded_size,MAX_TOOL_BYTES


class BasisDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        inputs=self.root/'inputs';inputs.mkdir();(inputs/'problem.md').write_text(TARGET);manifest(inputs)
        self.validator=basis.BasisContract(self.root,TARGET)
        self.stage=basis_author.BasisStage(self.root/'stage',basis.PROMPT,phase='basis-authoring',
            validator=self.validator,inputs=inputs/'inputs.json')
    def tearDown(self):
        self.stage.release_resources('USER_CANCELLED');self.temp.cleanup()

    def test_missing_evidence_is_repairable_in_the_same_stage(self):
        row=dependency()
        row['origin']['evidence']=[{'path':'external-sources/misspelled.txt','sha256':'0'*64}]
        result=self.stage.dispatch('submit_draft',{'artifact':artifact(row)})
        self.assertEqual(result['feedback_kind'],'candidate_rejected')
        self.assertIn('B001',result['error'])
        self.assertIn('misspelled.txt',result['error'])
        self.assertIsNone(self.stage.accepted)
        fixed=self.stage.dispatch('submit_draft',{'artifact':{'base_candidate':1,'patches':[
            {'op':'replace','path':'/dependencies/0/origin/evidence','value':[{'input':'problem.md'}]}]}})
        self.assertTrue(fixed['stage_complete'])
        self.assertEqual(self.validator.last_checked,2)

    def test_selecting_the_checked_candidate_reuses_only_the_verified_native_receipt(self):
        value=artifact(dependency())
        with patch.object(basis_native,'check',wraps=basis_native.check) as compiler:
            checked=self.stage.dispatch('check_draft',{'artifact':value})
            self.assertFalse(checked['stage_complete'])
            accepted=self.stage.dispatch('submit_draft',{'artifact':{'accept_candidate':1}})
            self.assertTrue(accepted['stage_complete'])
            self.assertEqual(compiler.call_count,1)
        self.assertEqual(self.stage.accepted,value)
        self.assertFalse((self.validator.out/'review').exists())
        path=Path(self.validator.last_receipt['path'])
        path.write_text('{}')
        with self.assertRaises(RuntimeError):
            self.validator({'accept_candidate':1})

    def test_genuine_filesystem_fault_and_loss_of_a_declared_input_are_execution_errors(self):
        value=artifact(dependency(category=4))
        row=value['dependencies'][0]
        row['origin']['evidence']=[{'path':'unreadable','sha256':'0'*64}]
        candidate=self.stage.logs/'unreadable';candidate.write_text('locally retained content')
        original=basis.bind
        def denied(path):
            if Path(path)==candidate:raise PermissionError(13,'Permission denied',str(path))
            return original(path)
        with patch.object(basis,'bind',denied),self.assertRaises(PermissionError):
            self.stage.dispatch('submit_draft',{'artifact':value})
        self.assertEqual(self.stage.tool_execution_fault['error_type'],'PermissionError')
        row['origin']['evidence']=[{'input':'problem.md'}]
        (self.validator.out/'inputs/problem.md').unlink()
        with self.assertRaises(FileNotFoundError):self.stage.dispatch('submit_draft',{'artifact':value})

    def test_partial_draft_can_be_saved_and_read_without_native_or_mathematical_acceptance(self):
        self.assertEqual(self.stage.output_verbosity,'high')
        self.assertEqual(ir.load(self.stage.logs/'execution-manifest.json')['output_verbosity'],'high')
        with patch.object(basis_native,'check',side_effect=AssertionError('No compiler for a partial save')):
            result=self.stage.dispatch('save_basis_draft',{'artifact':{'proof':'Concrete partial work.'}})
        self.assertTrue(result['saved']);self.assertFalse(result['mathematical_acceptance'])
        self.assertIsNone(self.validator.selected)
        read=self.stage.dispatch('read_basis_draft',{'kind':'candidate','candidate':1,'pointer':'/proof'})
        self.assertEqual(read['value'],'Concrete partial work.')
        self.assertEqual(self.stage.controller_checkpoint()['latest_candidate'],1)

    def test_long_unicode_draft_reads_losslessly_with_bounded_continuations(self):
        proof='数学 proof 🌟 '*18000
        self.stage.dispatch('save_basis_draft',{'artifact':{'proof':proof}})
        chunks=[];offset=0
        while True:
            row=self.stage.dispatch('read_basis_draft',{'kind':'candidate','candidate':1,'pointer':'/proof','offset':offset})
            self.assertLessEqual(encoded_size(row),MAX_TOOL_BYTES);chunks.append(row['value'])
            if not row['has_more']:break
            offset=row['next_offset']
        self.assertEqual(''.join(chunks),proof)

    def test_saved_partial_revision_survives_context_reset_index(self):
        self.validator.save({'proof':'Old partial work.'})
        self.validator.save({'base_candidate':1,'patches':[{'op':'replace','path':'/proof','value':'New concrete work.'}]})
        row=self.stage.dispatch('read_basis_draft',{'kind':'index'})
        self.assertEqual(row['value']['candidates'],[1,2])
        self.assertIsNone(row['value']['last_machine_checked_candidate'])
        self.assertEqual(self.validator.drafts[2]['proof'],'New concrete work.')

    def test_foreign_candidates_and_post_submission_tools_are_rejected(self):
        for number in (True,0,-1,999):
            row=self.stage.dispatch('read_basis_draft',{'kind':'candidate','candidate':number})
            self.assertFalse(row['accepted'])
        self.stage.accepted=artifact()
        row=self.stage.dispatch('save_basis_draft',{'artifact':{'proof':'too late'}})
        self.assertFalse(row['accepted']);self.assertEqual(self.validator.attempt,0)

    def test_unfinished_work_is_not_a_terminal_mathematical_obstacle(self):
        row=self.stage.dispatch('report_obstacle',{'status':'TASK_INCOMPLETE','explanation':'Still drafting.'})
        self.assertFalse(row['stage_complete']);self.assertEqual(row['feedback_kind'],'author_action_required')
        self.assertIsNone(self.stage.accepted)

    def test_malformed_legacy_obstacle_is_candidate_feedback_not_execution_fault(self):
        for value in ('[]','null','"text"','{invalid'):
            with self.subTest(value=value):
                row=self.stage.dispatch('report_obstacle',{'obstacle_json':value})
                self.assertFalse(row['accepted']);self.assertEqual(row['feedback_kind'],'candidate_rejected')
                self.assertIsNone(self.stage.accepted)

    def test_native_shutdown_fault_retains_marked_workspace_for_owned_cleanup(self):
        out=self.root/'native-fault'
        with patch.object(ir,'run_lean',side_effect=RuntimeError('Native process cleanup could not be confirmed')):
            with self.assertRaises(RuntimeError):basis_native.check('import Mathlib\n',[],[],out)
        saved=ir.load(out/'workspace-retained.json');work=Path(saved['workspace'])
        try:
            self.assertFalse(saved['cleanup_confirmed']);self.assertTrue(work.exists())
            self.assertTrue((work/'.yui-workspace-owner.json').is_file())
        finally:shutil.rmtree(work)  # This fixture never launched a process.

    def test_native_ownership_setup_fault_rolls_back_before_start(self):
        import run_resources
        original=basis_native.tempfile.mkdtemp;created=[]
        def allocate(*args,**kwargs):
            path=original(*args,**kwargs);created.append(Path(path));return path
        with patch.object(basis_native.tempfile,'mkdtemp',side_effect=allocate), \
             patch.object(run_resources,'register_workspace',side_effect=OSError('ownership record unavailable')), \
             patch.object(ir,'run_lean',side_effect=AssertionError('No child may start')),self.assertRaises(OSError):
            basis_native.check('import Mathlib\n',[],[],self.root/'ownership-fault')
        self.assertTrue(created);self.assertTrue(all(not p.exists() for p in created))


if __name__=='__main__':unittest.main()
