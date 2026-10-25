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

    def test_note_library_permission_is_local_and_does_not_add_an_assumption(self):
        note={'id':'BG001','kind':'mathlib','at':'/inference/argument/0/text','fact':'test',
              'grounds':[],'source':{'declaration':'Nat.add_comm'}}
        inventory={'background_mode':bg.REFERENCE_ONLY,'logic':{},'background_supplement':{
            'notes':{'R001':[note]}},'inferences':[
                {'id':'R001','inputs':[],'output':'N001'},
                {'id':'R002','inputs':['N001'],'output':'P'}]}
        plan={'terminal':'T002','steps':[{'id':'T001','inputs':[]},
                                       {'id':'T002','inputs':['T001']}]}
        mapping={'entries':{'N001':{'selector':'decl:Translation.T001'},
                            'P':{'selector':'decl:AuditBExport.P'}},'calculation_links':{}}
        decls=[{'name':'Translation.T001','imported':False,'direct_constants':['Nat.add_comm']},
               {'name':'Translation.T002','imported':False,'direct_constants':[]},
               {'name':'Nat.add_comm','imported':True,'proof_valued':True}]
        rows=audit_b.dependency_correspondence(inventory,mapping,plan,decls)
        self.assertTrue(all(r['matched'] for r in rows))
        self.assertEqual(rows[0]['actual_boundary_inputs'],[])
        self.assertEqual(list(rows[0]['background_library_uses']),['Nat.add_comm'])
        decls[1]['direct_constants']=['Nat.add_comm']
        rows=audit_b.dependency_correspondence(inventory,mapping,plan,decls)
        self.assertFalse(rows[1]['matched'])
        self.assertEqual(rows[1]['unpermitted_imported_proofs'],['Nat.add_comm'])

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

    def test_instance_support_excludes_ordinary_proof_uses(self):
        declaration={'name':'TEST_ONLY.instance','imported':True,'proof_valued':True,'instance_declaration':True}
        use={'name':'Translation.T001','imported':False,'proof_valued':True,
             'proof_uses':{'ordinary':[],'instance_argument':['TEST_ONLY.instance']}}
        self.assertEqual(audit_b.instance_support([declaration,use]),{'TEST_ONLY.instance'})
        use['proof_uses']['ordinary'].append('TEST_ONLY.instance')
        self.assertEqual(audit_b.instance_support([declaration,use]),set())

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
