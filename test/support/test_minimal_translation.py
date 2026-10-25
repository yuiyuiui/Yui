"""Controls for stage-two simplification; no model requests or exercise claims."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import audit_a_campaign as a
import translation_author as author
import full_workflow as flow
import execution_state as execution
import background_inputs as bg
import audit_b
import ir
from clean_stage import ArtifactStage

TRANSLATION_TESTS=a.CORE/'translation/tests'
sys.path.insert(0,str(TRANSLATION_TESTS))
from source_fixture import case, synthetic_audit, interface


class MinimalTranslationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='yui-minimal-control-')
        self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def prepared(self):
        graph,spec,_=case(self.root/'case');receipt=synthetic_audit(graph,spec)
        shutil.copyfile(receipt,self.root/'case/audit-a.json')
        author.prepare(self.root/'case',self.root/'case',self.root/'author')
        return author.InterfaceContract(self.root/'author')

    def test_incomplete_candidate_survives_completeness_rejection_and_accepts_edits(self):
        validator=self.prepared()
        with self.assertRaisesRegex(ValueError,'Candidate 1 saved'):
            validator({'header':'import Mathlib\n'})
        stored=json.loads((self.root/'author/candidates/0001/artifact.json').read_text())
        self.assertEqual(stored,{'header':'import Mathlib\n'})
        changed,_=validator.save({'base_candidate':1,'patches':[
            {'op':'add','path':'/parameters','value':[{'name':'p','type':'Prop'}]}]})
        self.assertEqual(changed['parameters'],[{'name':'p','type':'Prop'}])
        self.assertNotIn('parameters',validator.drafts[1])
        self.assertFalse((self.root/'author/accepted-interface-paths.json').exists())

    def test_reference_mode_does_not_expand_roots_and_notes_are_not_cross_imported(self):
        data=[{'background_notes':{}},None,None,{'H001':{'kind':'hypothesis'}},
              {'R001':{'inputs':['H001']}},None]
        with patch.object(bg.background,'effective',side_effect=AssertionError('must not promote')):
            props,steps=bg.effective(data)
        self.assertEqual(set(props),{'H001'})
        self.assertEqual(steps['R001']['inputs'],['H001'])
        source={'paragraph_mapping':{'S001':{'inference':'R001','paragraph':'S001'},
                                     'S002':{'inference':'R002','paragraph':'S001'}}}
        supplement={'notes':{'R001':[{'id':'BG001','at':'/inference/argument/0/text'}]}}
        steps=[{'id':'T001','source_steps':['S001']},{'id':'T002','source_steps':['S002']}]
        attached=bg.attach_notes(steps,source,supplement)
        self.assertEqual(attached[0]['background_notes'],['R001.BG001'])
        self.assertEqual(attached[1]['background_notes'],[])
        steps[1]['background_notes']=['R001.BG001']
        with self.assertRaisesRegex(ValueError,'another paragraph'):
            bg.attach_notes(steps,source,supplement)

    def test_notes_do_not_create_a_library_permission_gate(self):
        self.assertNotIn('calculation_links', author.PROMPT)
        self.assertIn('freely available', author.PROMPT)
        self.assertNotIn('library_and_calculation_correspondence', audit_b.REVIEW_CHECKS)
        self.assertFalse(hasattr(audit_b, 'dependency_correspondence'))

    def test_deferred_freeze_is_not_a_synthetic_semantic_pass(self):
        graph,spec,_=case(self.root/'case');receipt=synthetic_audit(graph,spec)
        cp,pp,rp=interface(graph,spec,self.root/'interface')
        old=ir.load(rp)
        binding={k:old[k] for k in ('paragraph_mapping','source_outputs','source_graph_sha256','contract_sha256','plan_sha256')}
        binding['status']='IR_TYPES_CHECKED_SEMANTIC_REVIEW_PENDING_AUDIT_B'
        bp=self.root/'interface/binding.json';ir.write(bp,binding)
        out=self.root/'workflow'
        row=flow.workflow.freeze(graph,spec,cp,pp,None,out,audit_a=receipt,interface_binding=bp)
        self.assertIsNone(row['interface_review'])
        self.assertEqual(row['interface_semantic_status'],'PENDING_AUDIT_B')
        self.assertNotIn('reviewer',row)
        self.assertFalse((out/'report.json').exists())
        with self.assertRaises((OSError,ValueError)):
            flow.workflow.finish(out,self.root/'nonexistent-review.json')
        binding['source_graph_sha256']='0'*64;ir.write(bp,binding)
        with self.assertRaisesRegex(ValueError,'stale interface binding'):
            flow.workflow.freeze(graph,spec,cp,pp,None,self.root/'stale',audit_a=receipt,interface_binding=bp)

    def test_shared_deadline_is_not_reset_by_another_stage(self):
        recorder=execution.Recorder(self.root/'run','test',a.concurrency.resolve(2),time_budget_seconds=10)
        try:
            first=flow.stage_seconds(a.concurrency.Budget(a.concurrency.resolve(1),execution=recorder))
            recorder.deadline-=4
            second=flow.stage_seconds(a.concurrency.Budget(a.concurrency.resolve(1),execution=recorder))
            self.assertLess(second,first-3.9)
            recorder.deadline=time.monotonic()-1
            with self.assertRaises(execution.CaseDeadlineExceeded):recorder.check()
            self.assertFalse(recorder.cancelled())
        finally:recorder.close('SYNTHETIC_DEADLINE_CONTROL')
        self.assertTrue(execution.inspect(self.root/'run')['time_budget']['expired'])

    def test_unlimited_case_does_not_gain_a_stage_deadline(self):
        recorder=execution.Recorder(self.root/'unlimited','test',a.concurrency.resolve(2))
        try:
            budget=a.concurrency.Budget(a.concurrency.resolve(1),execution=recorder)
            self.assertIsNone(flow.stage_seconds(budget))
            self.assertIsNone(recorder.deadline)
            self.assertIsNone(recorder.state['time_budget']['seconds'])
            recorder.check()
            execution.request_cancel(recorder.root)
            with self.assertRaises(execution.Cancelled):recorder.check()
        finally:recorder.close('SYNTHETIC_UNLIMITED_CONTROL')

    def test_instance_proofs_need_no_separate_semantic_permission_row(self):
        self.assertFalse(hasattr(audit_b, 'instance_support'))
        self.assertEqual(len(audit_b.REVIEW_CHECKS),4)

    def test_artifact_obstacle_api_has_no_routine_incomplete_report(self):
        stage=ArtifactStage(self.root/'stage','test',phase='interface-authoring',library=False)
        try:
            tool=next(t for t in stage.tools if t['name']=='report_obstacle')
            self.assertNotIn('TASK_INCOMPLETE',tool['inputSchema']['properties']['status']['enum'])
            self.assertLess(len(stage.continuation_prompt),240)
            answer=stage.dispatch('report_obstacle',{'status':'TASK_INCOMPLETE','location':'here',
                'explanation':'working','basis':'working','partial_progress':'working'})
            self.assertFalse(answer['accepted'])
            self.assertIsNone(stage.accepted)
        finally:shutil.rmtree(stage.work)


if __name__=='__main__':unittest.main()
