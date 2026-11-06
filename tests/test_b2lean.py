"""Actual Lean discharge and shared-flow regression with synthetic review judgments."""
import harness_support
from basis_fixtures import artifact, dependency, checked_context, TARGET, add_external_applications
from final_acceptance_fixtures import frozen_case, build
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import basis
import basis_native
import b2lean
import final_acceptance
import ir
import workflow
from controller_common import bind,write


def attach(source, context):
    value=basis.verify_context(context)
    write(source/basis.CONTEXT,context)
    (source/'basis-proof.md').write_text(value['proof']);write(source/'basis-registry.json',value)
    spec=ir.load(source/'spec.json')
    spec['inputs'] += [{'path':basis.CONTEXT,'sha256':ir.digest(source/basis.CONTEXT)}]
    write(source/'spec.json',spec)
    graph=ir.load(source/'nl0.json');graph['spec_sha256']=ir.digest(source/'spec.json')
    add_external_applications(graph,value,[{'path':'problem.txt','sha256':ir.digest(source/'problem.txt')}])
    write(source/'nl0.json',graph)
    names=['problem.txt',basis.CONTEXT,'basis-proof.md','basis-registry.json']
    write(source/'inputs.json',{'inputs':[{'id':n,'path':n,'sha256':ir.digest(source/n)} for n in names]})


class BasisDischargeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.value=artifact(dependency(compatibility='adapted'),dependency('B002',2))
        cls.context=checked_context(cls.root/'basis',cls.value)
        def transform(payload):
            for row in cls.value['dependencies']:
                payload['premise_types'][row['port']]=row['lean']['type']
                payload['steps'][-1]['inputs'].append(row['port'])
                payload['endpoint_correspondence'][row['port']]={'mode':'direct','explanation':'SYNTHETIC universal natural-number identity.'}
        cls.workflow=frozen_case(cls.root/'shared',prepare_source=lambda s:attach(s,cls.context),
            transform_interface=transform,bodies={'T001':'exact h_H001.symm',
                'T002':'simpa only [h_E001 a] using h_T001.symm'})
        build(cls.workflow)
        cls.intermediate=workflow.finish(cls.workflow,machine=True)
        cls.out=cls.root/'closed'
        cls.result=b2lean.finish(cls.workflow,cls.out,context=cls.context,intermediate=cls.intermediate)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_actual_shared_workflow_then_discharge_preserves_H_and_removes_E(self):
        self.assertEqual(self.result['status'],'WORKFLOW-PASSED')
        self.assertEqual(self.result['closure']['remaining_premises'],['H001'])
        native=ir.load(self.out/'elaborated.json')
        actual=native['comparisons'][0]['actual_type']
        self.assertIn('h_H001',actual);self.assertNotIn('h_E001',actual);self.assertNotIn('h_E002',actual)
        self.assertFalse(self.result['final_semantic_model_called'])
        self.assertTrue(self.result['closure']['kernel_closed'])
        self.assertEqual(self.result['concurrency'],self.intermediate['concurrency'])
        self.assertEqual(self.result['proof_phase_wall_seconds'],self.intermediate['proof_phase_wall_seconds'])
        b2lean.validate_receipt(self.out)

    def test_closed_kernel_proof_does_not_promote_source_qualification(self):
        receipt=final_acceptance.validate_receipt(self.intermediate['audit_b']['receipt_path'])
        qualified={**receipt,'source_conditional':True,'status':'AUDIT-B-CONDITIONAL'}
        out=self.root/'source-qualified'
        with patch.object(final_acceptance,'validate_receipt',return_value=qualified):
            result=b2lean.finish(self.workflow,out,context=self.context,intermediate=self.intermediate)
            self.assertEqual(result['status'],'WORKFLOW-CONDITIONAL')
            self.assertTrue(result['closure']['kernel_closed']);self.assertFalse(result['closure']['unconditional'])
            self.assertEqual(result['achieved_scope'],'CLOSED_LEAN_SOURCE_QUALIFIED')
            self.assertTrue((out/'warn.md').exists());b2lean.validate_receipt(out)

    def test_legacy_renderer_receipt_remains_valid_without_reinterpretation(self):
        original=b2lean.render
        out=self.root/'legacy-renderer'
        with patch.object(b2lean,'render',side_effect=lambda *a,**kw:original(*a,**kw,legacy=True)):
            result=b2lean.finish(self.workflow,out,context=self.context,intermediate=self.intermediate)
        result['version']='yui-b2lean-1';write(out/'report.json',result)
        self.assertEqual(b2lean.validate_receipt(out)['version'],'yui-b2lean-1')
        result['version']='yui-b2lean-2';write(out/'report.json',result)
        with self.assertRaisesRegex(ValueError,'Closed export changed'):b2lean.validate_receipt(out)

    def test_final_compiler_failure_retains_failed_scope_and_never_publishes_acceptance(self):
        from execution_health import StageFailure
        out=self.root/'failed-close'
        with patch.object(basis_native,'check',return_value={'passed':False,'errors':['ACTUAL_SIGNATURE_MISMATCH']}):
            with self.assertRaises(StageFailure) as caught:
                b2lean.finish(self.workflow,out,context=self.context,intermediate=self.intermediate)
        self.assertEqual(caught.exception.result['status'],'BASIS_FINAL_CLOSURE_FAILED')
        self.assertFalse((out/'report.json').exists())

    def test_conditional_receipt_is_not_already_final_closure(self):
        self.assertNotIn('closure',self.intermediate)
        self.assertIn('(h_E001 :', (self.workflow/'audit-b/Proof.lean').read_text())
        self.assertNotIn('(h_E001 :',(self.out/'Proof.lean').read_text().split('namespace YuiClosed')[1])

    def test_wrong_basis_and_wrong_workflow_receipts_are_rejected(self):
        changed=deepcopy(self.context);changed['full_target']='True'
        with self.assertRaises(ValueError):b2lean.finish(self.workflow,self.root/'bad-context',context=changed,intermediate=self.intermediate)
        changed=deepcopy(self.intermediate);changed['audit_b']['receipt_path']=str(self.root/'missing.json')
        with self.assertRaises((ValueError,OSError)):b2lean.finish(self.workflow,self.root/'bad-receipt',context=self.context,intermediate=changed)

    def test_mutated_final_proof_or_native_evidence_cannot_validate(self):
        for name in ('Proof.lean','elaborated.json','compiler.json'):
            path=self.out/name;original=path.read_bytes()
            try:
                path.write_bytes(original+b'\n-- changed\n')
                with self.subTest(name=name),self.assertRaises((ValueError,OSError)):b2lean.validate_receipt(self.out)
            finally:path.write_bytes(original)

    def test_final_status_and_remaining_scope_cannot_be_promoted(self):
        path=self.out/'report.json';original=path.read_bytes()
        for change in ({'status':'DEVELOPMENT-PASSED'},{'closure':dict(self.result['closure'],remaining_premises=[])},
                {'achieved_scope':'CONDITIONAL_LEAN'},{'formalization_goal':'conditional'}):
            try:
                value=deepcopy(self.result);value.update(change);write(path,value)
                with self.subTest(change=change),self.assertRaises(ValueError):b2lean.validate_receipt(self.out)
            finally:path.write_bytes(original)

    def test_changed_prepared_proof_is_detected_after_shared_freeze(self):
        path=Path(self.context['basis']['path']);original=path.read_bytes()
        try:
            value=ir.load(path);value['dependencies'][0]['lean']['proof']='exact False.elim (by contradiction)';write(path,value)
            with self.assertRaises(ValueError):workflow.bound(self.workflow)
            with self.assertRaises(ValueError):b2lean.validate_receipt(self.out)
        finally:path.write_bytes(original)

    def test_class3_is_never_an_external_port(self):
        context=deepcopy(self.context)
        source=self.workflow.parent/'source';path=source/'nl0.json';original=path.read_bytes()
        try:
            value=ir.load(path);value['propositions'].insert(0,{'id':'E999','kind':'external','statement':'unproved internal derivation'})
            write(path,value)
            with self.assertRaisesRegex(ValueError,'external ports'):basis.source_context(path,source/'spec.json')
        finally:path.write_bytes(original)


class BasisStandaloneClosureTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def native_close(self,value,parameters,premises,conclusion,body,*,approved=False,header=None):
        context=checked_context(self.root/'basis',value,approved=approved)
        c={'header':header or value['lean_header'],'parameters':parameters,'premises':premises,'conclusion':{'type':conclusion}}
        binders=ir.binder_text(c)+' '+' '.join(f"(h_{p['id']} : {p['type']})" for p in premises if p['kind']!='mathlib')
        conditional=c['header']+f'\nnamespace AuditBExport\nset_option autoImplicit false\ntheorem P {binders} : {conclusion} := by\n{ir.proof_text(body)}\nend AuditBExport\n'
        levels={'parameters':[],'export_used_parameters':[]}
        if 'universe u' in c['header']:levels={'parameters':['u'],'export_used_parameters':['u']}
        source,expected,retained=b2lean.render(c,context,conditional,levels)
        checked=basis_native.check(source,[('P','YuiClosed.P',expected)],['YuiClosed.P'],self.root/'closed')
        self.assertTrue(checked['passed'],ir.load(self.root/'closed/compiler.json'))
        return context,retained,ir.load(self.root/'closed/elaborated.json')

    def test_approved_residual4_remains_explicit_in_actual_signature(self):
        row=dependency(category=4)
        context,retained,evidence=self.native_close(artifact(row),[],[
            {'id':'E001','kind':'external','type':row['lean']['type'],'statement':row['statement']}],
            '∀ n : ℕ, n + 0 = n','exact h_E001',approved=True)
        self.assertEqual(retained,['E001']);self.assertIn('h_E001',evidence['comparisons'][0]['actual_type'])

    def test_no_external_dependencies_and_unused_original_H(self):
        _,retained,_=self.native_close(artifact(),[],[{'id':'H001','kind':'hypothesis','type':'True','statement':'True'}],
            'True','exact True.intro')
        self.assertEqual(retained,['H001'])

    def test_actual_universe_and_instance_export(self):
        row=dependency(category=2,typ='∀ {α : Type u} [Monoid α] (a : α), a * 1 = a',proof='intro α inst a; exact mul_one a')
        value=artifact(row);value['lean_header']+='universe u\n'
        self.native_close(value,[{'name':'α','type':'Type u'},{'name':'inst','type':'Monoid α','binder_kind':'instance'},
            {'name':'a','type':'α'}],[{'id':'E001','kind':'external','type':row['lean']['type'],'statement':row['statement']}],
            'a * 1 = a','exact h_E001 a')


if __name__=='__main__':unittest.main()
