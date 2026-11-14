"""Real Lean uses and assembly of generic internal obligations. No model or research input."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import harness_support
import ir
import scheduler
import local_helpers
import proof_reuse


class DependencyInstanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'contract.json'
        source = self.path.with_name('source.json')
        ir.write(source, {'text':'Distance symmetry at two types.'})
        self.contract = {'id':'instances','version':2,'source':{'path':source.name,'sha256':ir.digest(source)},
            'source_steps':[{'id':'S001','text':'Apply symmetry in the supplied spaces.'}],
            'pins':{'lean_version':ir.load_lock()['lean']['version_number'],'mathlib_commit':ir.load_lock()['mathlib']['rev']},
            'header':'import Mathlib\nabbrev Rn (n : ℕ) := EuclideanSpace ℝ (Fin n)\n',
            'parameters':[{'name':'n','type':'ℕ'}], 'premises':[],
            'conclusion':{'type':'∀ p q : Rn n, dist p q = dist q p','statement':'Symmetry.'},
            'objects':[], 'shared_obligations':[], 'representation':'Euclidean space.',
            'review':{'mode':'development_owner_review'}}
        ir.write(self.path, self.contract)
        self.plan={'version':2,'contract_sha256':ir.digest(self.path),'representation_notes':'Actual distances.',
            'terminal':'T002','steps':[
                {'id':'T001','statement':'∀ (M : Type u) [MetricSpace M] (p q : M), dist p q = dist q p',
                 'universe_params':['u'],'inputs':[],'source_steps':['S001'],'explanation':'Distance symmetry.'},
                {'id':'T002','statement':self.contract['conclusion']['type'],'inputs':['T001'],
                 'input_instances':{'T001':[{'levels':['0'],'uses':[{'args':['Rn n']}]}]},
                 'source_steps':['S001'],'explanation':'Apply symmetry on Rn.'}]}
        self.proofs={'T001':'intro M _ p q; exact dist_comm p q','T002':'exact h_T001 (Rn n)'}

    def test_actual_application_local_helper_and_fresh_assembly(self):
        preflight = ir.render(self.path,self.plan,types_only=True)
        self.assertIn('def __signature_P : Prop',preflight)
        self.assertNotIn('\ntheorem P ',preflight)
        result=scheduler.prove_graph(self.path,self.plan,lambda sid,packet:{'proof':self.proofs[sid]},max_workers=2)
        self.assertEqual(result['status'],'FRAGMENT_ASSEMBLED',result)
        self.assertEqual(result['fresh_verifier']['exit_code'],0)
        result=ir.check_auxiliary(self.path,self.plan,'T002',self.contract['conclusion']['type'],
                                  self.proofs['T002'],out=self.path.parent/'helper')
        self.assertTrue(result['auxiliary_valid'],result['stdout'])

    def test_an_inapplicable_specialization_never_dispatches_a_worker(self):
        # Type 1 is a perfectly legal universe. Rn n cannot inhabit it.
        self.plan['steps'][1]['input_instances']['T001'][0]['levels']=['1']
        native=ir.check(self.path,self.plan,types_only=True)
        self.assertNotEqual(native['exit_code'],0)
        self.assertIn('Rn n',native['stdout'])
        self.assertEqual(native['failed_input_uses'],['T002 <- T001 (h_T001, use 1)'])
        called=[]
        with self.assertRaises(ValueError):
            scheduler.prove_graph(self.path,self.plan,lambda *a:called.append(a))
        self.assertEqual(called,[])

    def test_implicit_polymorphic_producer_requires_use_before_dispatch(self):
        prod,consumer=self.plan['steps']
        prod.pop('universe_params');prod['statement']=prod['statement'].replace('Type u','Type*')
        consumer.pop('input_instances')
        with self.assertRaisesRegex(ValueError,'T002.*T001'):
            ir.check(self.path,self.plan,types_only=True)

    def test_unknown_step_field_is_not_inert(self):
        self.plan['steps'][0]['universee_params']=['u']
        with self.assertRaisesRegex(ValueError,'T001.*universee_params'):
            ir.validate(self.path,self.plan)

    def test_incomplete_draft_can_be_saved_but_unknown_step_setup_and_disk_errors_are_distinct(self):
        import errno
        from unittest.mock import patch
        import translation_author as author
        c=author.InterfaceContract.__new__(author.InterfaceContract)
        c.out=self.path.parent;c.documents={};c.drafts={};c.attempt=0
        s=author.InterfaceStage.__new__(author.InterfaceStage)
        s.logs=self.path.parent;s.accepted=None;s.validator=c;s.type_probes=0
        self.assertTrue(s.dispatch('save_interface_draft',{'artifact':{'steps':[{'id':'T001'}]}})['saved'])
        bad=s.dispatch('save_interface_draft',{'artifact':{'steps':[{'id':'T001','unknown_universes':['u']}]}})
        self.assertIn('/steps/0 (T001)',bad['error'])
        self.assertIn('unknown_universes',bad['error'])
        self.assertEqual(c.attempt,1)
        missing=s.dispatch('read_interface_draft',{'kind':'probe','candidate':7,'pointer':''})
        self.assertFalse(missing['accepted'])
        with patch.object(author,'write',side_effect=OSError(errno.ENOSPC,'injected full disk')),self.assertRaises(OSError):
            s.dispatch('save_interface_draft',{'artifact':{'steps':[]}})
        self.assertEqual(s.tool_execution_fault['errno'],errno.ENOSPC)
        self.assertEqual(c.attempt,1)

    def test_lean_finds_levels_hidden_by_an_abbreviation_and_keeps_public_bound_levels(self):
        self.contract['header']+='universe sourceLevel\nabbrev Family.{l} : Prop := ∀ (M : Type l) (p : M), p = p\n'
        p,q=self.plan['steps']
        p['statement']='Family.{sourceLevel}';p.pop('universe_params')
        q.pop('input_instances')
        ir.write(self.path,self.contract);self.plan['contract_sha256']=ir.digest(self.path)
        rejected=ir.check(self.path,self.plan,types_only=True)
        self.assertNotEqual(rejected['exit_code'],0)
        self.assertIn('T002 <- T001: undeclared internal universes',rejected['stdout'])
        self.contract['parameters'].append({'name':'A','type':'Type sourceLevel'})
        ir.write(self.path,self.contract);self.plan['contract_sha256']=ir.digest(self.path)
        accepted=ir.check(self.path,self.plan,types_only=True)
        self.assertEqual(accepted['exit_code'],0,accepted['stdout'])

    def test_generic_chain_independent_index_multiple_instances_and_product(self):
        first,second=self.plan['steps']
        first.update(universe_params=['w','i'],
            statement='∀ (M : Type w) (I : Type i) (f : I → M) (j : I), f j = f j')
        second.update(universe_params=['m'],statement='∀ (M : Type m) (x : M), x = x',
            input_instances={'T001':[{'levels':['m','0'],'uses':[{'parameters':[
                {'name':'M','type':'Type m'},{'name':'N','type':'ℕ → ℕ'}],
                'args':['M','Σ j : ℕ, Fin (N j)']}]}]})
        final='∀ p : Rn n, p = p ∧ (0 : ℕ) = 0 ∧ (0 : ℕ) = 0'
        last={'id':'T003','statement':final,'inputs':['T002','T001'],'explanation':'Three actual uses.',
              'source_steps':['S001'],'input_instances':{
                  'T002':[{'levels':['0'],'uses':[{'args':['Rn n']},{'args':['Rn n × ℝ']}]}],
                  'T001':[{'levels':['0','0'],'uses':[{'args':['ℕ','ℕ']}]},
                          {'levels':['1','0'],'uses':[{'args':['ULift.{1} ℕ','ℕ']}]}]}}
        self.plan['steps'].append(last);self.plan['terminal']='T003'
        self.contract['conclusion']['type']=final;ir.write(self.path,self.contract)
        self.plan['contract_sha256']=ir.digest(self.path)
        proofs={'T001':'intro M I f j; rfl',
            'T002':'intro M x; exact h_T001 M ℕ (fun _ => x) 0',
            'T003':'intro p\nrefine ⟨h_T002 (Rn n) p, h_T001 ℕ ℕ id 0, ?_⟩\n'
                   'exact congrArg ULift.down (h_T001_2 (ULift.{1} ℕ) ℕ (fun x => ULift.up x) 0)'}
        report=scheduler.prove_graph(self.path,self.plan,lambda sid,packet:{'proof':proofs[sid]},max_workers=2)
        self.assertEqual(report['status'],'FRAGMENT_ASSEMBLED',report)
        program=ir.render(self.path,self.plan,proofs)
        self.assertNotIn('__yui_preflight',program)
        self.assertNotIn('False.elim',program)
        self.assertTrue(set(report['fresh_verifier']['axioms']) <= {'propext','Classical.choice','Quot.sound'})
        # With the valid ambient instance left intact, a bad index must still be located.
        second['input_instances']['T001'][0]['levels'][1]='1'
        wrong=ir.check(self.path,self.plan,types_only=True)
        self.assertEqual(wrong['failed_input_uses'],['T002 <- T001 (h_T001, use 1)'])

    def test_changed_application_invalidates_old_packet_even_when_binder_type_is_identical(self):
        revised=deepcopy(self.plan)
        revised['steps'][1]['input_instances']['T001'][0]['uses']=[{'args':['Rn n × ℝ']}]
        self.assertFalse(proof_reuse.same_port(self.path,self.plan,self.path,revised,'T002'))
        self.assertNotEqual(local_helpers.context(self.path,self.plan,'T002'),
                            local_helpers.context(self.path,revised,'T002'))
        self.assertTrue(proof_reuse.same_port(self.path,self.plan,self.path,revised,'T001'))

    def test_interface_repair_can_change_instances_but_not_public_header(self):
        import internal_interface_repair as repair
        prior={'header':self.contract['header'],'steps':self.plan['steps'],'conclusion_type':self.contract['conclusion']['type']}
        revised=deepcopy(prior);revised['steps'][1]['input_instances']['T001'][0]['levels']=['1']
        repair.protect_candidate(revised,prior)
        for key in ('header','conclusion_type'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'preserve'):
                repair.protect_candidate({**revised,key:'changed'},prior)
        self.assertEqual(repair.delta(prior,revised)['affected_steps'],['T002'])

    def test_invalid_instance_rows_do_not_silently_change_the_input(self):
        for row in ({'levels':[],'uses':[{'args':['ℕ']}]},{'levels':['0'],'uses':[]},
                    {'levels':['0'] ,'uses':[{'args':[]}]},{'levels':['0'],'uses':[{'args':[False]}]},
                    {'levels':['0'],'uses':[{'args':['Nat'],'extra':1}]},
                    {'levels':['_'],'uses':[{'args':['ℕ']}]},
                    {'levels':['0)\naxiom bad : False'],'uses':[{'args':['ℕ']}]},
                    {'levels':['0'],'uses':[{'args':['Nat'],'parameters':[{'name':'h_T001','type':'Nat'}]}]}):
            plan=deepcopy(self.plan);plan['steps'][1]['input_instances']['T001']=[row]
            with self.subTest(row=row),self.assertRaises(ValueError):
                ir.validate(self.path,plan)

    def test_interface_author_through_audit_b_uses_the_real_producer_and_keeps_public_hypothesis(self):
        import audit_b
        import final_acceptance
        import final_acceptance_fixtures as fixture
        import workflow
        def translate(value):
            consumer=value['steps'][0]
            consumer['inputs'].append('T003')
            consumer['input_instances']={'T003':[{'levels':['0'],'uses':[
                {'args':['ℕ','a','b','h_H001'],'expected':'b = a'}]}]}
            value['steps'].insert(0,{'id':'T003','statement':'∀ (M : Type u) (x y : M), x = y → y = x',
                'universe_params':['u'],'inputs':[],'source_steps':['S001'],'explanation':'Equality symmetry.'})
        proofs={'T003':'intro M x y h; exact h.symm','T001':'exact h_T003 ℕ a b h_H001',
                'T002':'simpa only [Nat.add_zero] using h_T001.symm'}
        work=fixture.frozen_case(self.path.parent/'end-to-end',transform_interface=translate,bodies=proofs)
        manifest=workflow.bound(work)
        report=scheduler.prove_graph(manifest['contract'],ir.load(manifest['plan']),
            lambda sid,packet:{'proof':proofs[sid]},max_workers=2)
        self.assertEqual(report['status'],'FRAGMENT_ASSEMBLED',report)
        self.assertEqual(fixture.build(work)['status'],'AUDIT-B-MECHANICAL-PASSED')
        final_acceptance.finish(work)
        out=work/'audit-b'
        self.assertEqual(audit_b.check(out,out/'machine-acceptance.json')['status'],'AUDIT-B-PASSED')
        exported=(out/'Proof.lean').read_text().split('namespace AuditBExport')[-1]
        self.assertIn('(h_H001 : a = b)',exported)
        self.assertNotIn('__yui_preflight',(out/'Proof.lean').read_text())
