"""Identical-program reuse eligibility controls; fixtures are not scientific receipts."""
import harness_support
import copy
import hashlib
import json
from types import SimpleNamespace
from pathlib import Path
import shutil
import tempfile
import unittest

HERE=harness_support.LEAN
import ir
import proof_reuse
from source_fixtures import case, interface


class ProofReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        graph,spec,_=case(self.root/'source')
        self.old,plan_path,*_=interface(graph,spec,self.root/'previous/inputs')
        self.plan=ir.load(plan_path)
        self.previous=self.root/'previous'
        ir.write(self.previous/'report.json',{'status':'FRAGMENT_ASSEMBLED','contract_sha256':ir.digest(self.old)})
        ir.write(self.previous/'proofs.json',{'contract_sha256':ir.digest(self.old),
            'plan_sha256':ir.digest(self.previous/'inputs/plan.json'),
            'proofs':{'T001':'exact ⟨h_H001.1,h_H001.1⟩'}})
        shutil.copytree(self.previous/'inputs',self.root/'new')
        self.new=self.root/'new/contract.json'
    def tearDown(self):self.tmp.cleanup()

    def test_changed_explanation_does_not_reprove_identical_lean_program(self):
        plan=copy.deepcopy(self.plan);plan['steps'][0]['explanation']='A corrected implementation explanation.'
        result=proof_reuse.candidate(self.previous,self.new,plan,'T001')
        self.assertEqual(result['body'],'exact ⟨h_H001.1,h_H001.1⟩')
        self.assertIn('requires current native recheck',result['scope'])

    def test_changed_definitions_or_binders_invalidate_cached_body(self):
        for field,value in [('header','import Mathlib\ndef extraDefinition : Nat := 1\n'),
                            ('parameters',[{'name':'p','type':'Prop'},{'name':'r','type':'Prop'}])]:
            c=ir.load(self.old);c[field]=value;ir.write(self.new,c)
            plan=copy.deepcopy(self.plan);plan['contract_sha256']=ir.digest(self.new)
            self.assertIsNone(proof_reuse.candidate(self.previous,self.new,plan,'T001'))

    def test_changed_target_or_input_order_does_not_reuse(self):
        plan=copy.deepcopy(self.plan);plan['steps'][0]['statement']='p'
        self.assertIsNone(proof_reuse.candidate(self.previous,self.new,plan,'T001'))

    def test_unfinished_or_stale_proof_record_is_rejected(self):
        ir.write(self.previous/'report.json',{'status':'GRAPH_UNFINISHED','contract_sha256':ir.digest(self.old)})
        with self.assertRaises(ValueError):proof_reuse.candidate(self.previous,self.new,self.plan,'T001')

    def partial(self):
        import shared_lemmas
        body=ir.load(self.previous/'proofs.json')['proofs']['T001']
        text=ir.render(self.old,self.plan,{'T001':body},only='T001')
        report={'status':'GRAPH_UNFINISHED','contract_sha256':ir.digest(self.old),
            'plan_digest':shared_lemmas.hashed(self.plan),'proofs':{'T001':body},'jobs':[
                {'step':'T001','consumers':['T001'],'status':'LOCAL_PROOFS_CHECKED',
                 'verification':{'status':'LOCAL-PROOF-CHECKED','exit_code':0,'scope':'T001',
                    'contract_sha256':ir.digest(self.old),'lean_sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'axioms':['propext']}}]}
        ir.write(self.previous/'report.json',report);(self.previous/'proofs.json').unlink()
        return report

    def test_partial_checked_node_is_only_a_candidate_for_fresh_recheck(self):
        report=self.partial();result=proof_reuse.candidate(self.previous,self.new,self.plan,'T001')
        self.assertEqual(result['body'],report['proofs']['T001'])
        self.assertIn('requires current native recheck',result['scope'])

    def test_partial_node_must_match_actual_checked_source_and_completed_job(self):
        report=self.partial()
        for change in ('hash','unfinished'):
            value=copy.deepcopy(report)
            if change=='hash':value['jobs'][0]['verification']['lean_sha256']='0'*64
            else:value['jobs'][0]['status']='LOCAL_UNFINISHED'
            ir.write(self.previous/'report.json',value)
            with self.assertRaises(ValueError):proof_reuse.candidate(self.previous,self.new,self.plan,'T001')

    def cleanup_seed(self):
        old=self.previous/'workers/T001';old.mkdir(parents=True)
        packet=ir.local_packet(self.new,self.plan,'T001')
        profile=__import__('runtime_config').model_profile('proof')
        logs=self.root/'restored';logs.mkdir()
        stage=SimpleNamespace(step='T001',cpath=self.new,plan=self.plan,logs=logs,
            own_lean_drafts={'proof':{},'auxiliary':{}},model=profile['id'],
            model_selection=profile,system='Original rules.',prompt=lambda:json.dumps({'packet':packet}))
        result={'status':'UNFINISHED','execution_fault':'RuntimeError: Native process cleanup could not be confirmed',
            'temporary_workspace_removed':True,'isolation_violation':False,
            'identity_and_input_boundary_verified':True,'model':profile['id'],
            'effort':profile['reasoning_effort'],'model_selection':profile}
        ir.write(old/'result.json',result);ir.write(old/'prompt.txt',{'packet':packet})
        body='have h := h_H001.1\nexact ⟨h,h⟩'
        text=ir.render(self.new,self.plan,{'T001':body},only='T001')
        (old/'native-cleanup-source.lean').write_text(text)
        ir.write(old/'native-cleanup-checkpoint.json',{'source_sha256':hashlib.sha256(text.encode()).hexdigest()})
        return old,stage,text

    def test_cleanup_seed_recovers_exact_own_body_without_acceptance(self):
        old,stage,text=self.cleanup_seed()
        proof_reuse.restore_cleanup_drafts(stage,self.previous)
        row=stage.own_lean_drafts['proof'][1]
        self.assertEqual(ir.render(self.new,self.plan,{'T001':row['proof']},only='T001'),text)
        self.assertEqual(row['check']['status'],'EXECUTION_FAULT')
        self.assertIn('No prior candidate is accepted',stage.system)

    def test_cleanup_seed_refuses_a_changed_packet_or_tampered_body(self):
        old,stage,text=self.cleanup_seed()
        (old/'native-cleanup-source.lean').write_text(text+'\n')
        with self.assertRaises(ValueError):proof_reuse.restore_cleanup_drafts(stage,self.previous)

    def test_cleanup_seed_preserves_an_unaccepted_auxiliary_without_promoting_it(self):
        old,stage,_=self.cleanup_seed()
        text=ir.render_auxiliary(self.new,self.plan,'T001','True','exact True.intro')
        (old/'native-cleanup-source.lean').write_text(text)
        ir.write(old/'native-cleanup-checkpoint.json',{'source_sha256':hashlib.sha256(text.encode()).hexdigest()})
        proof_reuse.restore_cleanup_drafts(stage,self.previous)
        row=stage.own_lean_drafts['auxiliary'][1]
        self.assertFalse(stage.own_lean_drafts['proof'])
        self.assertEqual(ir.render_auxiliary(self.new,self.plan,'T001',row['statement'],row['proof']),text)
        self.assertEqual(row['check']['status'],'EXECUTION_FAULT')
        ir.write(old/'prompt.txt',{'packet':{'foreign':'target'}})
        with self.assertRaises(ValueError):proof_reuse.restore_cleanup_drafts(stage,self.previous)


if __name__=='__main__':unittest.main()
