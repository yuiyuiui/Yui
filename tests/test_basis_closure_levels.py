"""Generic native universe controls, independent of research problem statements.

The matrix isolates the production renderer with synthetic context metadata.
The full workflow fixture also verifies real basis/A/B receipts and readback.
"""
import harness_support
from basis_fixtures import artifact,dependency,checked_context
from final_acceptance_fixtures import frozen_case,build
from test_b2lean import attach
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_b
import basis
import basis_native
import b2lean
import ir
import workflow


class ClosureUniverseMatrix(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def check(self,rows,*,parameters=(),premises=(),conclusion='True',body='exact True.intro',
              header='import Mathlib\nuniverse u v w\n',legacy=False,passed=True,replace=None):
        value=artifact(*rows);value['lean_header']=header
        external=[{'id':r['port'],'kind':'external','type':r['lean']['type']} for r in rows if r['port']]
        c={'header':header,'parameters':list(parameters),'premises':list(premises)+external,'conclusion':{'type':conclusion}}
        binders=ir.binder_text(c)+' '+' '.join(f"(h_{p['id']} : {p['type']})" for p in c['premises'])
        conditional=header+f'\nnamespace AuditBExport\ntheorem P {binders} : {conclusion} := by\n{ir.proof_text(body)}\nend AuditBExport\n'
        # Only the legacy control consumes this metadata. The new renderer
        # obtains declaration parameters from Lean, including auto-generated ones.
        levels={'parameters':['u','v'],'export_used_parameters':['u','v']}
        with patch.object(basis,'verify_context',return_value=value),patch.object(basis,'check_interface'):
            source,expected,retained=b2lean.render(c,{},conditional,levels,legacy=legacy)
        if replace:source=replace(source)
        out=self.root/('check-'+str(len(list(self.root.iterdir()))))
        native=basis_native.check(source,[('P','YuiClosed.P',expected)],['YuiClosed.P'],out)
        self.assertEqual(native['passed'],passed,ir.load(out/'compiler.json')['stdout'][:6000])
        return native,ir.load(out/'elaborated.json'),retained

    def test_two_private_levels_reproduce_old_failure_and_close_with_new_renderer(self):
        row=dependency(category=2,typ='∀ (A : Type u) (B : Type v), True',proof='intro A B; trivial')
        body='exact h_E001 (ULift.{u} Unit) (ULift.{v} Unit)'
        failed,_,_=self.check([row],body=body,legacy=True,passed=False)
        self.assertIn('LEAN_COMPILE_FAILED',failed['errors'])
        _,native,_=self.check([row],body=body)
        declarations={r['name']:r for r in native['dependencies']['declarations']}
        self.assertIn('YuiBasis.B001',declarations)
        self.assertEqual(declarations['YuiClosed.P']['levels'],[])

    def test_mixed_public_private_and_shared_levels(self):
        rows=[dependency(category=2,typ='∀ (A : Type u) (B : Type v), True',proof='intro A B; trivial'),
            dependency('B002',2,typ='∀ (B : Type v) (C : Type w), True',proof='intro B C; trivial')]
        _,native,_=self.check(rows,parameters=[{'name':'A','type':'Type u'},{'name':'a','type':'A'}],
            conclusion='a = a',body='have h := h_E001 A (ULift.{v} Unit)\nhave k := h_E002 (ULift.{v} Unit) (ULift.{w} Unit)\ncases h\ncases k\nrfl')
        declaration=next(r for r in native['dependencies']['declarations'] if r['name']=='YuiClosed.P')
        self.assertEqual(len(declaration['levels']),1)

    def test_retained_h_and_class4_keep_their_own_levels(self):
        rows=[dependency(category=2,typ='∀ A : Type u, True',proof='intro A; trivial'),
            dependency('B002',4,typ='∀ B : Type v, True')]
        _,native,retained=self.check(rows,premises=[{'id':'H001','kind':'hypothesis','type':'∀ C : Type w, True'}],
            body='have h := h_E001 (ULift.{u} Unit)\nhave k := h_E002 (ULift.{v} Unit)\nexact h_H001 (ULift.{w} Unit)')
        self.assertEqual(retained,['H001','E002'])
        d=next(r for r in native['dependencies']['declarations'] if r['name']=='YuiClosed.P')
        self.assertEqual(len(d['levels']),2)

    def test_hidden_level_in_abbreviation_is_retained(self):
        header='import Mathlib\nuniverse u v\nabbrev Witness (A : Type u) := A → True\n'
        self.check([dependency(category=2,typ='∀ B : Type v, True',proof='intro B; trivial')],header=header,
            parameters=[{'name':'A','type':'Type u'},{'name':'a','type':'A'}],
            premises=[{'id':'H001','kind':'hypothesis','type':'Witness A'}],body='exact h_H001 a')

    def test_type_star_levels_come_from_lean_without_python_level_names(self):
        self.check([dependency(category=2,typ='∀ (A B : Type*), True',proof='intro A B; trivial')],
            parameters=[{'name':'A','type':'Type*'},{'name':'a','type':'A'}],conclusion='a = a',body='rfl')

    def test_inferred_levels_can_be_renumbered_after_an_earlier_premise_disappears(self):
        # The old E001/E002/E003 levels are u_1/u_2/u_3. The retained E002/E003
        # levels become u_1/u_2. Equal auto-generated names are not identities.
        self.check([dependency(category=2,typ='∀ A : Type*, True',proof='intro A; trivial'),
            dependency('B002',4,typ='∀ B : Type*, True'),dependency('B003',4,typ='∀ C : Type*, True')],
            header='import Mathlib\n')

    def test_explicit_level_name_that_looks_generated_stays_explicit(self):
        self.check([dependency(category=2,typ='∀ C : Type*, True',proof='intro C; trivial')],
            header='import Mathlib\nuniverse u_1 u_2\n',
            parameters=[{'name':'A','type':'Type (max u_1 u_2)'},{'name':'a','type':'A'}],conclusion='a = a',body='rfl')

    def test_sort_and_composite_levels_are_not_collapsed(self):
        for typ in ('Sort u','Type (max u v)','Sort (imax u v)','Type (u + 1)'):
            with self.subTest(typ=typ):
                self.check([dependency(category=2,typ='∀ C : Sort w, True',proof='intro C; trivial')],
                    parameters=[{'name':'A','type':typ},{'name':'a','type':'A'}],conclusion='a = a',body='rfl')

    def test_implicit_and_instance_parameters(self):
        self.check([dependency(category=2,typ='∀ B : Type v, True',proof='intro B; trivial')],
            parameters=[{'name':'A','type':'Type u','binder_kind':'implicit'},
                {'name':'inst','type':'Monoid A','binder_kind':'instance'},{'name':'a','type':'A'}],
            conclusion='a * 1 = a',body='exact mul_one a')

    def test_all_zero_public_specialization_remains_rejected(self):
        self.check([dependency(category=2,typ='∀ B : Type v, True',proof='intro B; trivial')],
            parameters=[{'name':'A','type':'Type u'},{'name':'a','type':'A'}],conclusion='a = a',body='rfl',
            replace=lambda s:s.replace('if !used.contains name then pure Level.zero','if true then pure Level.zero'),passed=False)

    def test_sorry_and_wrong_basis_proof_still_fail(self):
        with self.assertRaisesRegex(ValueError,'forbidden'):
            self.check([dependency(category=2,typ='∀ A : Type u, True',proof='sorry')],passed=False)
        self.check([dependency(category=2,typ='∀ A : Type u, True',proof='exact False.elim (by trivial)')],
            body='exact h_E001 (ULift.{u} Unit)',passed=False)
        # Even if a bad source bypasses the author-side placeholder filter,
        # transitive native trust inspection still rejects it.
        native,_,_=self.check([dependency(category=2,typ='∀ A : Type u, True',proof='intro A; trivial')],
            body='exact h_E001 (ULift.{u} Unit)',
            replace=lambda s:s.replace('intro A; trivial','sorry'),passed=False)
        self.assertTrue(any(e.startswith('UNPERMITTED_AXIOM:') for e in native['errors']))


class PrivateLevelWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.value=artifact(dependency(category=2,typ='∀ (A : Type u) (B : Type v), True',proof='intro A B; trivial'))
        cls.value['lean_header']+='universe u v\n'
        cls.context=checked_context(cls.root/'basis',cls.value)
        def transform(payload):
            payload['header']=cls.value['lean_header']
            payload['premise_types']['E001']=cls.value['dependencies'][0]['lean']['type']
            payload['steps'][-1]['inputs'].append('E001')
            payload['endpoint_correspondence']['E001']={'mode':'direct','explanation':'Synthetic polymorphic true proposition.'}
        cls.workflow=frozen_case(cls.root/'shared',prepare_source=lambda s:attach(s,cls.context),
            transform_interface=transform,bodies={'T001':'exact h_H001.symm',
                'T002':'have witness := h_E001 (ULift.{u} Unit) (ULift.{v} Unit)\ncases witness\nsimpa only [Nat.add_zero] using h_T001.symm'})
        build(cls.workflow);cls.intermediate=workflow.finish(cls.workflow,machine=True)
        cls.out=cls.root/'closed'
        cls.result=b2lean.finish(cls.workflow,cls.out,context=cls.context,intermediate=cls.intermediate)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_checked_basis_through_a_b_and_real_final_export(self):
        report=b2lean.validate_receipt(self.out)
        self.assertEqual(report['version'],'yui-b2lean-3')
        self.assertEqual(report['status'],'WORKFLOW-PASSED')
        self.assertEqual(report['closure']['remaining_premises'],['H001'])
        self.assertFalse(report['final_semantic_model_called'])
        evidence=ir.load(self.out/'elaborated.json')
        self.assertTrue(evidence['comparisons'][0]['definitionally_equal'])
        self.assertIn('YuiBasis.B001',{r['name'] for r in evidence['dependencies']['declarations']})

    def test_authority_change_before_publication_is_rejected(self):
        out=self.root/'changed-before-publish'
        def reject():raise ValueError('changed original recovery evidence')
        with self.assertRaisesRegex(ValueError,'changed original'):
            b2lean.finish(self.workflow,out,context=self.context,intermediate=self.intermediate,before_publish=reject)
        self.assertTrue((out/'check.json').is_file());self.assertFalse((out/'report.json').exists())


if __name__=='__main__':unittest.main()
