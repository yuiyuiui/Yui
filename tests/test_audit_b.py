import harness_support
from audit_b_fixtures import fixture, prepare_control, synthetic_receipt
from pathlib import Path
import shutil
import tempfile
import unittest

HERE=harness_support.LEAN
import ir
import audit_b as audit








class AuditBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=Path(tempfile.mkdtemp(prefix='audit-b-controls-'))
        cls.directories={}
        cls.outcomes={}
        for variant in ('identity','wrong_target','hidden_field','mathlib','unmapped_mathlib','weakened_external','unmapped_instance','extra_axiom','equivalent_target'):
            directory=prepare_control(cls.base/variant,variant)
            cls.outcomes[variant]=audit.build(directory)
            cls.directories[variant]=directory

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.base)

    def setUp(self):
        self.copy=Path(tempfile.mkdtemp(prefix='audit-b-receipt-'))/'audit'
        shutil.copytree(self.directories['identity'],self.copy)

    def tearDown(self): shutil.rmtree(self.copy.parent)

    def test_review_only_reuse_preserves_proofs_without_compiling_again(self):
        from unittest.mock import patch
        continued=self.copy.parent/'continued'
        original_hashes={name:ir.digest(self.copy/name) for name in ['compiler.json','elaborated.json','Proof.lean']}
        with patch.object(ir,'run_lean',side_effect=AssertionError('No native rerun is allowed')):
            report=audit.prepare_review_reuse(self.copy,continued)
            self.assertFalse(report['native_checks_rerun'])
            self.assertEqual(original_hashes,{name:ir.digest(continued/name) for name in original_hashes})
            result=audit.check(continued,synthetic_receipt(continued))
            self.assertEqual(result['native_evidence_origin'],'inherited_checked_run')
        proof=continued/'Proof.lean';proof.write_text(proof.read_text()+'\n-- changed copy\n')
        with self.assertRaisesRegex(ir.Invalid,'inherited artifact copy'):audit.bound_inputs(continued)

    def test_actual_positive_kernel_inspection(self):
        self.assertEqual(self.outcomes['identity']['status'],'AUDIT-B-MECHANICAL-PASSED',self.outcomes)
        data=ir.load(self.directories['identity']/'elaborated.json')
        self.assertTrue(all(x['definitionally_equal'] for x in data['comparisons']))

    def test_lean_valid_weakened_target_rejected(self):
        report=ir.load(self.directories['wrong_target']/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertIn('ELABORATED_SIGNATURE_MISMATCH',report['errors'])

    def test_hidden_proof_field_is_exposed_and_extra_parameter_rejected(self):
        directory=self.directories['hidden_field'];report=ir.load(directory/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertIn('ELABORATED_SIGNATURE_MISMATCH',report['errors'])
        declarations=ir.load(directory/'elaborated.json')['dependencies']['declarations']
        constructor=next(d for d in declarations if d['name']=='Box.mk')
        self.assertTrue(any(b['proof_valued'] for b in constructor['signature']['binders']))

    def test_mathlib_premise_is_discharged_by_an_actual_library_proof(self):
        self.assertEqual(self.outcomes['mathlib']['status'],'AUDIT-B-MECHANICAL-PASSED',self.outcomes['mathlib'])
        data=ir.load(self.directories['mathlib']/'elaborated.json')
        exported=next(r for r in data['comparisons'] if r['id']=='P')
        self.assertNotIn('h_M001',exported['actual_type'])

    def test_equivalent_encoding_is_passed_to_review_not_automatically_certified(self):
        directory=self.directories['equivalent_target']
        report=ir.load(directory/'mechanical.json')
        self.assertTrue(report['passed'])
        note=ir.load(directory/'review-packet.json')['endpoints']['P']['correspondence']
        self.assertEqual(note['mode'],'equivalent')
        with self.assertRaises(ir.Invalid):
            audit.check(directory,directory/'review-template.json')

    def test_unlisted_mathlib_result_is_freely_available(self):
        report=ir.load(self.directories['unmapped_mathlib']/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertTrue(report['passed'])
        self.assertNotIn('unmapped_imported_proofs',report)

    def test_library_instance_can_be_used_as_an_ordinary_proof(self):
        report=ir.load(self.directories['unmapped_instance']/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertTrue(report['passed'])
        self.assertEqual(set(report['required_review_locations']),{'P'})

    def test_unproved_project_axiom_is_still_rejected(self):
        report=ir.load(self.directories['extra_axiom']/'mechanical.json')
        self.assertFalse(report['passed'])
        self.assertIn('UNPROVED_OR_EXECUTABLE_HEADER_DECLARATION',report['errors'])
        self.assertTrue(any(e.startswith('UNPERMITTED_AXIOM:') for e in report['errors']))

    def test_external_input_with_same_count_but_changed_content_rejected(self):
        directory=self.directories['weakened_external'];report=ir.load(directory/'mechanical.json')
        self.assertEqual(report['compiler_exit_code'],0)
        self.assertIn('ELABORATED_SIGNATURE_MISMATCH',report['errors'])
        comparison=next(r for r in ir.load(directory/'elaborated.json')['comparisons'] if r['id']=='E001')
        self.assertFalse(comparison['definitionally_equal'])

    def test_only_external_and_complete_target_have_semantic_rows(self):
        for variant in ('identity','mathlib','unmapped_mathlib'):
            report=ir.load(self.directories[variant]/'mechanical.json')
            self.assertEqual(set(report['required_review_locations']),{'P'})
        report=ir.load(self.directories['weakened_external']/'mechanical.json')
        self.assertEqual(set(report['required_review_locations']),{'E001','P'})

    def test_explanation_is_required_and_bound_to_review(self):
        c=ir.contract(self.base/'identity/case/contract.json')
        inventory=ir.load(self.copy/'source-inventory.json')
        mapping=ir.load(self.copy/'mapping.json')
        mapping['entries']['P']['correspondence']['explanation']=''
        with self.assertRaisesRegex(ir.Invalid,'/entries/P/correspondence/explanation:'):
            audit.validate_mapping(c,inventory,mapping)
        path=synthetic_receipt(self.copy);record=ir.load(path)
        record['nodes']['P']['locations'].remove('/endpoints/P/correspondence')
        ir.write(path,record)
        with self.assertRaisesRegex(ir.Invalid,'paired source/kernel'): audit.check(self.copy,path)

    def test_pending_template_never_passes(self):
        with self.assertRaises(ir.Invalid): audit.check(self.copy,self.copy/'review-template.json')

    def test_synthetic_complete_receipt_checks_shape_but_not_independence(self):
        result=audit.check(self.copy,synthetic_receipt(self.copy))
        self.assertEqual(result['status'],'DEVELOPMENT-AUDIT-B-PASSED')
        self.assertFalse(result['whole_nl0_and_current_audit_a'])
        self.assertFalse(result['semantic_review_automatically_verified'])

    def test_missing_source_mapping_rejected(self):
        c=ir.contract(self.base/'identity/case/contract.json');inventory=ir.load(self.copy/'source-inventory.json')
        mapping=ir.load(self.copy/'mapping.json');del mapping['entries']['P']
        with self.assertRaisesRegex(ir.Invalid,r'/entries:.*missing=.*P'): audit.validate_mapping(c,inventory,mapping)

    def test_mismatched_root_source_kind_rejected(self):
        c=ir.contract(self.base/'identity/case/contract.json');inventory=ir.load(self.copy/'source-inventory.json')
        inventory['propositions'][0]['kind']='external'
        with self.assertRaisesRegex(ir.Invalid,"/entries: missing=\\['H001'\\]"):
            audit.validate_mapping(c,inventory,ir.load(self.copy/'mapping.json'))

    def test_different_or_decoy_root_rejected(self):
        c=ir.contract(self.base/'identity/case/contract.json');inventory=ir.load(self.copy/'source-inventory.json')
        mapping=ir.load(self.copy/'mapping.json');mapping['entries']['P']['selector']='decl:True.intro'
        with self.assertRaisesRegex(ir.Invalid,r'/entries/P/selector:.*AuditBExport.P'): audit.validate_mapping(c,inventory,mapping)

    def test_missing_paired_semantic_locations_rejected(self):
        path=synthetic_receipt(self.copy);record=ir.load(path);record['nodes']['P']['locations']=['/inventory']
        ir.write(path,record)
        with self.assertRaisesRegex(ir.Invalid,'paired source/kernel'): audit.check(self.copy,path)

    def test_self_review_cannot_claim_independence(self):
        path=synthetic_receipt(self.copy);record=ir.load(path);record['reviewer']['independent']=True;ir.write(path,record)
        with self.assertRaisesRegex(ir.Invalid,'independence'): audit.check(self.copy,path)

    def test_changed_review_packet_rejected(self):
        path=synthetic_receipt(self.copy);ir.write(self.copy/'review-packet.json',{'changed':True})
        with self.assertRaisesRegex(ir.Invalid,'kernel audit artifact'): audit.check(self.copy,path)

    def test_modified_mapping_revokes_review(self):
        path=synthetic_receipt(self.copy);m=ir.load(self.copy/'mapping.json');m['entries']['P']['expected_type']='True';ir.write(self.copy/'mapping.json',m)
        with self.assertRaisesRegex(ir.Invalid,'semantic mapping'): audit.check(self.copy,path)

    def test_changed_evidence_revokes_review(self):
        path=synthetic_receipt(self.copy);(self.copy/'test-only-evidence.txt').write_text('changed')
        with self.assertRaisesRegex(ir.Invalid,'semantic evidence'): audit.check(self.copy,path)

    def test_old_policy_or_permission_ledger_is_not_silently_reused(self):
        c=ir.contract(self.base/'identity/case/contract.json')
        inventory=ir.load(self.copy/'source-inventory.json')
        mapping=ir.load(self.copy/'mapping.json');mapping['version']=1
        with self.assertRaisesRegex(ir.Invalid,'/version: expected'):
            audit.validate_mapping(c,inventory,mapping)
        mapping['version']=audit.VERSION;mapping['calculation_links']={}
        with self.assertRaisesRegex(ir.Invalid,'unexpected=.*calculation_links'):
            audit.validate_mapping(c,inventory,mapping)

    def test_equivalence_explanation_does_not_override_independent_rejection(self):
        path=synthetic_receipt(self.copy);record=ir.load(path)
        record['nodes']['P']['verdict']='FAIL'
        record['nodes']['P']['notes']='Synthetic negative: the stated identification omits a hypothesis.'
        ir.write(path,record)
        with self.assertRaisesRegex(ir.Invalid,'unperformed/failed semantic review: P'):
            audit.check(self.copy,path)


if __name__=='__main__':unittest.main()
