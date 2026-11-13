"""Actual Lean round failure/repair and final gates; semantic judgments are synthetic."""
import harness_support
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_b_mapping
import case_status
import concurrency
import full_workflow
import ir
import run_graph
import shared_lemmas
import workflow
from final_acceptance_fixtures import frozen_case, qualified_artifact


class ProofRoundNative(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yui-round-native-')
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def test_actual_failed_graph_reaches_connection_repair_and_final_acceptance(self):
        out = frozen_case(self.root / 'case')
        frozen = workflow.bound(out)
        prior = out / 'seed-local-bodies'
        (out / 'proof-run').rename(prior)
        report = ir.load(prior / 'report.json')
        report.update(contract_sha256=ir.digest(prior / 'inputs/contract.json'),
                      plan_digest=shared_lemmas.hashed(ir.load(prior / 'inputs/plan.json')))
        ir.write(prior / 'report.json', report)
        render = ir.render

        def generated_failure(cpath, plan, proofs=None, only=None, types_only=False):
            text = render(cpath, plan, proofs, only, types_only)
            if proofs and only is None and not types_only:
                # A deterministic generator fault: locals still really compile,
                # while Lean rejects both actual whole-file verification calls.
                text += '\nexample : False := by trivial\n'
            return text

        with patch.object(ir, 'render', side_effect=generated_failure), \
                patch.object(run_graph.pilot, 'Stage', side_effect=AssertionError('Freshly recheck retained bodies; no model call')):
            result, selected = full_workflow.prove_with_repair('closed-addition', frozen, out,
                out.parent / 'author', concurrency.serial_budget(),
                concurrency.Budget(concurrency.resolve(1), role='proof'), lambda *a, **k: None,
                prior_run=prior)
        self.assertEqual(result['status'], 'GRAPH_ASSEMBLY_REPAIR_REQUIRED', result)
        self.assertTrue(all(job['status'] == 'LOCAL_PROOFS_CHECKED' for job in result['jobs']))
        self.assertTrue(all(job['verification']['exit_code'] == 0 for job in result['jobs']))
        self.assertNotEqual(result['assembly']['exit_code'], 0)
        self.assertNotEqual(result['fresh_verifier']['exit_code'], 0)
        self.assertEqual(result['worker_calls'], 0)
        recorded_tools = ir.load(selected / 'configuration.json')['script_sha256']
        self.assertIn('proof_round_policy.py', recorded_tools)
        self.assertIn('proof_rounds.py', recorded_tools)
        self.assertIn(str(ir.ROOT / 'workflow/blocks/proof_rounds.py'),
                      {item['path'] for item in frozen['tools']})
        self.assertTrue((selected / 'proofs.json').is_file())
        self.assertEqual(workflow.proof_run(out), selected)
        original_report = (selected / 'report.json').read_bytes()
        with self.assertRaises((ValueError, OSError)):
            workflow.finish(out, machine=True)
        self.assertFalse((out / 'report.json').exists())

        workflow.prepare_audit(out)
        mapping_dir = self.root / 'connection-repair'
        audit_b_mapping.prepare(out, mapping_dir)
        validator = audit_b_mapping.MappingContract(mapping_dir)
        mapping = ir.load(mapping_dir / 'inputs/mapping.json')
        invalid = {**copy.deepcopy(mapping), 'proof_patches': {'T002': 'exact DefinitelyMissing'}}
        with self.assertRaisesRegex(ValueError, 'Candidate 1:'):
            validator(invalid)
        self.assertFalse((mapping_dir / 'accepted-mapping-path.json').exists())
        self.assertFalse((out / 'report.json').exists())
        fixed = {**copy.deepcopy(mapping), 'proof_patches': {
            'T002': 'have h := h_T001.symm\nsimpa only [Nat.add_zero] using h'}}
        self.assertEqual(validator(fixed)['status'], 'AUDIT-B-MECHANICAL-PASSED')
        qualified_artifact(mapping_dir / 'stage', fixed)
        audit_b_mapping.adopt(mapping_dir)

        native_file = out / 'audit-b/assembly-compiler.json'
        mechanical_file = out / 'audit-b/mechanical.json'
        old_native, old_mechanical = native_file.read_bytes(), mechanical_file.read_bytes()
        try:
            native = ir.load(native_file)
            native.update(timed_out=True, error_kind='LEAN_TIMEOUT')
            ir.write(native_file, native)
            mechanical = ir.load(mechanical_file)
            mechanical['artifacts']['assembly-compiler.json'] = ir.digest(native_file)
            ir.write(mechanical_file, mechanical)
            with self.assertRaises(ValueError):
                workflow.finish(out, machine=True)
            self.assertFalse((out / 'report.json').exists())
        finally:
            native_file.write_bytes(old_native)
            mechanical_file.write_bytes(old_mechanical)

        final = workflow.finish(out, machine=True)
        self.assertEqual(final['status'], 'WORKFLOW-PASSED')
        self.assertEqual((selected / 'report.json').read_bytes(), original_report)
        self.assertEqual(ir.load(selected / 'report.json')['status'], 'GRAPH_ASSEMBLY_REPAIR_REQUIRED')
        self.assertTrue((out / 'audit-b/Proof.lean').is_file())
        self.assertFalse(final['audit_b']['final_semantic_model_called'])

    def test_real_preparation_agrees_between_default_and_selected_repair_origins(self):
        out = frozen_case(self.root / 'case')
        selected = out / 'proof-run'
        report = ir.load(selected / 'report.json')
        report['status'] = 'GRAPH_ASSEMBLY_REPAIR_REQUIRED'
        ir.write(selected / 'report.json', report)
        original = (selected / 'report.json').read_bytes()
        self.assertEqual(workflow.prepare_audit(out)['status'], 'AUDIT-B-PREPARED')
        default_mapping = self.root / 'default-mapping'
        audit_b_mapping.prepare(out, default_mapping)
        workflow.select_proof_run(out, selected)
        explicit_mapping = self.root / 'selected-mapping'
        audit_b_mapping.prepare(out, explicit_mapping)
        for name in ('mapping.json', 'source-inventory.json', 'contract.json', 'plan.json',
                     'proofs.json', 'spec.json', 'nl0.json', 'source-outputs.json'):
            with self.subTest(name=name):
                self.assertEqual((default_mapping / 'inputs' / name).read_bytes(),
                                 (explicit_mapping / 'inputs' / name).read_bytes())
        status = case_status.project(out.parent / 'source', workflow=out)
        self.assertEqual(status['gates']['lean_assembly'], 'GRAPH_ASSEMBLY_REPAIR_REQUIRED')
        self.assertFalse(status['full_acceptance'])
        self.assertEqual((selected / 'report.json').read_bytes(), original)
        self.assertFalse((out / 'report.json').exists())

    def test_complete_status_alone_cannot_supply_a_missing_proof_to_real_preparation(self):
        out = frozen_case(self.root / 'case')
        selected = out / 'proof-run'
        report = ir.load(selected / 'report.json')
        report['status'] = 'GRAPH_ASSEMBLY_REPAIR_REQUIRED'
        ir.write(selected / 'report.json', report)
        bundle = ir.load(selected / 'proofs.json')
        del bundle['proofs']['T002']
        ir.write(selected / 'proofs.json', bundle)
        workflow.select_proof_run(out, selected)
        with self.assertRaises(ValueError):
            workflow.prepare_audit(out)
        self.assertFalse((out / 'report.json').exists())
        self.assertFalse((out / 'audit-b/mechanical.json').exists())


if __name__ == '__main__':
    unittest.main()
