import harness_support
from lean_fixtures import norm_plan
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE=harness_support.LEAN
import ir




class StructureTests(unittest.TestCase):
    def setUp(self):
        self.work=Path(tempfile.mkdtemp(prefix='ir-test-'))
        for n in ('source.json','contract.json'):
            shutil.copyfile(harness_support.FIXTURES/'lean/examples/case1_norm_sup'/n,self.work/n)
        self.cpath=self.work/'contract.json'
        self.plan=norm_plan(self.cpath)

    def tearDown(self): shutil.rmtree(self.work)

    def rejects(self,plan,pattern):
        with self.assertRaisesRegex(ir.Invalid,pattern):ir.validate(self.cpath,plan)

    def test_topology_and_conditional_packet(self):
        c,nodes,order=ir.validate(self.cpath,self.plan)
        self.assertEqual(order,['T001','T002'])
        packet=ir.local_packet(self.cpath,self.plan,'T002')
        self.assertEqual([p['id'] for p in packet['inputs']],['T001'])
        self.assertNotIn('H001',json.dumps(packet))
        self.assertNotIn('proof',packet)

    def test_reordered_plan_is_still_acyclic(self):
        self.plan['steps'].reverse()
        self.assertEqual(ir.validate(self.cpath,self.plan)[2],['T001','T002'])

    def test_cycle(self):
        self.plan['steps'][0]['inputs']=['T002']
        self.rejects(self.plan,'cyclic')

    def test_unknown_input(self):
        self.plan['steps'][0]['inputs']=['H999']
        self.rejects(self.plan,'unregistered input')

    def test_changed_target(self):
        self.plan['steps'][1]['statement']='True'
        self.rejects(self.plan,'target mismatch')

    def test_missing_source_step(self):
        self.plan['steps'][1]['source_steps']=['S001']
        self.rejects(self.plan,'unmapped NL')

    def test_retained_unconnected_step(self):
        self.plan['steps'].append({'id':'T003','statement':'True','inputs':[],
                                 'source_steps':['S001'],'explanation':'unused'})
        self.rejects(self.plan,'does not reach')

    def test_stale_contract(self):
        c=ir.load(self.cpath)
        c['review']['pending']=['changed review binding']
        ir.write(self.cpath,c)
        self.rejects(self.plan,'stale interface')

    def test_source_mutation(self):
        (self.work/'source.json').write_text('changed source')
        self.rejects(self.plan,'stale source')

    def test_proof_coverage_not_axiomized(self):
        with self.assertRaisesRegex(ir.Invalid,'missing proof'):
            ir.render(self.cpath,self.plan,{'T002':'exact iSup_congr h_T001'})

    def test_forbidden_commands_and_placeholders(self):
        for text in ('sorry','admit','axiom x : True','exact (by sorry)','run_tac pure ()'):
            with self.assertRaises(ir.Invalid):ir.proof_text(text)

    def test_duplicate_json_key(self):
        p=self.work/'bad.json';p.write_text('{"version":1,"version":2}')
        with self.assertRaisesRegex(ir.Invalid,'duplicate JSON'):ir.load(p)

    def test_schema_placeholder(self):
        self.plan['representation_notes']='choices'
        self.rejects(self.plan,'schema placeholder')

    def test_retained_development_inputs_are_self_contained(self):
        for case in ('case1_norm_sup','case2_weighted_l2','case2_continuous_representatives'):
            cpath=harness_support.FIXTURES/'lean/examples'/case/'contract.json'
            contract=ir.contract(cpath)
            self.assertEqual(ir.digest(cpath.parent/contract['source']['path']),contract['source']['sha256'])


class LeanBoundaryTests(unittest.TestCase):
    def test_common_outer_indentation_preserves_layout(self):
        c=harness_support.FIXTURES/'lean/examples/case1_norm_sup/contract.json';p=norm_plan(c)
        body='\n    intro r\n    exact (enorm_eq_iff_norm_eq).2 (h_H001 r)\n'
        result=ir.check(c,p,{'T001':body},only='T001')
        self.assertEqual(result['exit_code'],0,result['stdout'])

    def test_valid_local_proofs_and_assembly(self):
        c=harness_support.FIXTURES/'lean/examples/case1_norm_sup/contract.json';p=norm_plan(c)
        result=ir.check(c,p,{'T001':'exact fun r => (enorm_eq_iff_norm_eq).2 (h_H001 r)',
                             'T002':'exact iSup_congr h_T001'})
        self.assertEqual(result['exit_code'],0,result['stdout'])
        self.assertNotIn('sorryAx',result['axioms'])

    def test_noninput_premise_is_not_visible(self):
        c=harness_support.FIXTURES/'lean/examples/case1_norm_sup/contract.json';p=norm_plan(c)
        result=ir.check(c,p,{'T002':'exact iSup_congr h_H001'},only='T002')
        self.assertNotEqual(result['exit_code'],0)
        self.assertIn('h_H001',result['stdout'])

    def test_ae_equality_does_not_supply_pointwise_without_inputs(self):
        c=harness_support.FIXTURES/'lean/examples/case2_continuous_representatives/contract.json'
        p={'version':1,'contract_sha256':ir.digest(c),
           'representation_notes':'Negative control omits both continuity inputs.',
           'steps':[{'id':'T001','statement':'f = g','inputs':['H003'],
                     'source_steps':['S001'],'explanation':'Intentionally invalid attempt to evaluate an a.e. equality.'}],
           'terminal':'T001'}
        result=ir.check(c,p,{'T001':'exact h_H003'},only='T001')
        self.assertNotEqual(result['exit_code'],0)

    def test_strengthened_interface_rejected(self):
        c=harness_support.FIXTURES/'lean/examples/case2_continuous_representatives/contract.json'
        original=ir.contract(c)
        proposal={'parameters':original['parameters'],
                  'premises':[{'id':p['id'],'type':p['type']} for p in original['premises']],
                  'conclusion_type':'True','representation_notes':'Deliberately weakened goal.'}
        result=ir.check_interface(c,proposal)
        self.assertNotEqual(result['exit_code'],0)


class ToolFeedbackTests(unittest.TestCase):
    def test_valid_check_is_not_reported_as_failed_submission(self):
        from model_pilot import Stage
        work=Path(tempfile.mkdtemp(prefix='ir-tool-feedback-'))
        c=harness_support.FIXTURES/'lean/examples/case1_norm_sup/contract.json'
        stage=Stage(work/'stage',c,'plan',120)
        try:
            plan=norm_plan(c)
            result=stage.dispatch('check_plan',{'plan_json':json.dumps(plan)})
            self.assertTrue(result['accepted'])
            self.assertFalse(result['stage_complete'])
            self.assertIsNone(stage.accepted)
            submitted=stage.dispatch('submit_plan',{'plan_json':json.dumps(plan)})
            self.assertTrue(submitted['accepted'])
            self.assertTrue(submitted['stage_complete'])
            self.assertEqual(stage.accepted,plan)
        finally:
            shutil.rmtree(stage.work)
            shutil.rmtree(work)


if __name__=='__main__':unittest.main()
