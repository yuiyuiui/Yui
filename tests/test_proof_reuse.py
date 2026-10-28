"""Identical-program reuse eligibility controls; fixtures are not scientific receipts."""
import harness_support
import copy
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


if __name__=='__main__':unittest.main()
