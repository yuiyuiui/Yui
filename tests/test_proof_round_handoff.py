"""Real proof-round readers and handoffs; external semantic authority is synthetic."""
import harness_support
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import audit_b_mapping
import basis_defect
import ir
import proof_reuse
import shared_lemmas
import source_preparation
import workflow
from lean_fixtures import LIFT, SUP, shared_fixture


class ProofRoundHandoff(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yui-round-handoff-')
        self.root = Path(self.temp.name).resolve()
        self.contract, self.plan = shared_fixture(self.root / 'source')
        self.plan_path = self.contract.parent / 'plan.json'
        ir.write(self.plan_path, self.plan)
        self.frozen = {'contract': str(self.contract), 'plan': str(self.plan_path)}
        self.serial = 0

    def tearDown(self):
        self.temp.cleanup()

    def retained(self, status, *, name='proof-repairs/0002', root=None):
        self.serial += 1
        root = root or self.root / str(self.serial) / 'workflow'
        selected = root / name
        shutil.copytree(self.contract.parent, selected / 'inputs')
        proofs = {'T001': LIFT, 'T002': SUP}
        report = {'status': status, 'contract_sha256': ir.digest(selected / 'inputs/contract.json'),
                  'plan_digest': shared_lemmas.hashed(self.plan), 'proofs': proofs, 'jobs': []}
        for step, body in proofs.items():
            text = ir.render(selected / 'inputs/contract.json', self.plan, {step: body}, only=step)
            report['jobs'].append({'step': step, 'consumers': [step], 'status': 'LOCAL_PROOFS_CHECKED',
                'verification': {'status': 'LOCAL-PROOF-CHECKED', 'exit_code': 0, 'scope': step,
                    'contract_sha256': report['contract_sha256'],
                    'lean_sha256': hashlib.sha256(text.encode()).hexdigest(), 'axioms': ['propext']}})
        ir.write(selected / 'report.json', report)
        ir.write(selected / 'proofs.json', {'contract_sha256': report['contract_sha256'],
            'plan_sha256': ir.digest(selected / 'inputs/plan.json'), 'proofs': proofs})
        for name in ('manifest.json', 'freeze-seal.json'):
            ir.write(root / name, {'fixture': 'Frozen theorem authority mocked only in these controls.'})
        return root, selected

    def select(self, root, selected):
        with patch.object(workflow, 'bound', return_value=self.frozen):
            return workflow.select_proof_run(root, selected)

    def selection(self, root, selected):
        """Write the legacy on-disk format without calling the selector under test."""
        ir.write(root / 'proof-selection.json', {'version': workflow.VERSION,
            'directory': str(selected.relative_to(root)), 'scope': 'Independent retained-round fixture.',
            'evidence': [source_preparation.binding(selected / name) for name in
                ('report.json', 'proofs.json', 'inputs/contract.json', 'inputs/plan.json')]})

    def test_selected_compiled_round_reaches_the_real_reader(self):
        root, selected = self.retained('FRAGMENT_ASSEMBLED')
        self.assertEqual(self.select(root, selected), selected)
        self.assertEqual(workflow.proof_run(root), selected)

    def test_selected_assembly_failure_reaches_the_real_reader_without_promotion(self):
        root, selected = self.retained('GRAPH_ASSEMBLY_REPAIR_REQUIRED')
        before = (selected / 'report.json').read_bytes()
        self.assertEqual(self.select(root, selected), selected)
        self.assertEqual(workflow.proof_run(root), selected)
        self.assertEqual((selected / 'report.json').read_bytes(), before)
        self.assertFalse((root / 'report.json').exists())

    def test_first_round_can_also_be_explicitly_selected_for_assembly_repair(self):
        root, selected = self.retained('GRAPH_ASSEMBLY_REPAIR_REQUIRED', name='proof-run')
        self.assertEqual(self.select(root, selected), selected)

    def test_every_incomplete_unknown_or_malformed_status_is_rejected_without_selection(self):
        for status in ('GRAPH_UNFINISHED', 'GRAPH_REPAIR_REQUIRED', 'CANCELLED',
                       'LOCAL_PROOFS_CHECKED', 'WORKFLOW-PASSED', 'UNKNOWN', '', None, [], {}):
            with self.subTest(status=status):
                root, selected = self.retained(status)
                with self.assertRaises(ValueError):
                    self.select(root, selected)
                self.assertFalse((root / 'proof-selection.json').exists())

    def test_default_resolution_preserves_status_and_partial_recovery_access(self):
        for status in ('FRAGMENT_ASSEMBLED', 'GRAPH_ASSEMBLY_REPAIR_REQUIRED',
                       'GRAPH_REPAIR_REQUIRED', 'GRAPH_UNFINISHED'):
            with self.subTest(status=status):
                root, selected = self.retained(status, name='proof-run')
                self.assertEqual(workflow.proof_run(root), selected)
                self.assertEqual(ir.load(selected / 'report.json')['status'], status)
        empty = self.root / 'not-started'
        self.assertEqual(workflow.proof_run(empty), empty / 'proof-run')

    def test_manual_selection_cannot_admit_incomplete_or_unknown_rounds(self):
        for status in ('GRAPH_REPAIR_REQUIRED', 'GRAPH_UNFINISHED', 'CANCELLED', None, {}):
            root, selected = self.retained(status)
            self.selection(root, selected)
            with self.subTest(status=status), self.assertRaises(ValueError):
                workflow.proof_run(root)

    def test_current_frozen_contract_and_plan_must_match_before_selection(self):
        for name in ('contract.json', 'plan.json'):
            root, selected = self.retained('GRAPH_ASSEMBLY_REPAIR_REQUIRED')
            path = selected / 'inputs' / name
            path.write_text(path.read_text() + '\n')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'interface differs'):
                self.select(root, selected)
            self.assertFalse((root / 'proof-selection.json').exists())

    def test_missing_proof_bundle_does_not_publish_a_selection(self):
        root, selected = self.retained('GRAPH_ASSEMBLY_REPAIR_REQUIRED')
        (selected / 'proofs.json').unlink()
        with self.assertRaises((ValueError, OSError)):
            self.select(root, selected)
        self.assertFalse((root / 'proof-selection.json').exists())

    def test_foreign_or_self_selection_is_rejected_without_writing(self):
        root, selected = self.retained('FRAGMENT_ASSEMBLED')
        for target in (root, selected.parent.parent.parent):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.select(root, target)
            self.assertFalse((root / 'proof-selection.json').exists())

    def test_escaping_artifact_symlink_is_rejected_before_selection_publication(self):
        root, selected = self.retained('FRAGMENT_ASSEMBLED')
        path = selected / 'proofs.json'
        outside = self.root / 'foreign-proofs.json'
        path.rename(outside)
        path.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.select(root, selected)
        self.assertFalse((root / 'proof-selection.json').exists())

    def test_selection_cannot_be_overwritten(self):
        root, selected = self.retained('FRAGMENT_ASSEMBLED')
        self.select(root, selected)
        before = (root / 'proof-selection.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'existing proof selection'):
            self.select(root, selected)
        self.assertEqual((root / 'proof-selection.json').read_bytes(), before)

    def test_each_selected_artifact_is_revalidated(self):
        for name in ('report.json', 'proofs.json', 'inputs/contract.json', 'inputs/plan.json'):
            root, selected = self.retained('FRAGMENT_ASSEMBLED')
            self.select(root, selected)
            path = selected / name
            path.write_text(path.read_text() + '\n')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'stale'):
                workflow.proof_run(root)

    def test_duplicate_missing_or_foreign_evidence_is_rejected(self):
        for kind in ('duplicate', 'missing', 'foreign'):
            root, selected = self.retained('FRAGMENT_ASSEMBLED')
            self.selection(root, selected)
            path = root / 'proof-selection.json'
            value = ir.load(path)
            if kind == 'duplicate':
                value['evidence'].append(copy.deepcopy(value['evidence'][0]))
            elif kind == 'missing':
                value['evidence'].pop()
            else:
                value['evidence'][0] = source_preparation.binding(self.contract)
            ir.write(path, value)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                workflow.proof_run(root)

    def test_unsafe_relative_absolute_and_versioned_selections_are_rejected(self):
        for change in ({'directory': '../foreign'}, {'directory': '/tmp/foreign'},
                       {'directory': '.'}, {'directory': ''}, {'version': 'unknown'}):
            root, selected = self.retained('FRAGMENT_ASSEMBLED')
            self.selection(root, selected)
            path = root / 'proof-selection.json'
            ir.write(path, {**ir.load(path), **change})
            with self.subTest(change=change), self.assertRaises(ValueError):
                workflow.proof_run(root)

    def test_selected_repair_round_is_readable_after_a_fresh_process_import(self):
        root, selected = self.retained('GRAPH_ASSEMBLY_REPAIR_REQUIRED')
        self.selection(root, selected)
        code = ('import sys;sys.path[:0]=sys.argv[2:];import workflow;'
                'print(workflow.proof_run(sys.argv[1]))')
        result = subprocess.run([sys.executable, '-B', '-c', code, str(root),
            str(harness_support.LEAN / 'scripts'), str(harness_support.CORE / 'nl0/scripts')],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(selected))

    def test_real_audit_preparation_receives_the_selected_complete_round(self):
        for status in ('FRAGMENT_ASSEMBLED', 'GRAPH_ASSEMBLY_REPAIR_REQUIRED'):
            root, selected = self.retained(status)
            self.frozen.update(authority={'fixture': 'Unrelated theorem authority.'})
            self.select(root, selected)
            def prepare(contract, plan, proofs, out, **authority):
                self.assertEqual((contract, plan, proofs), (selected / 'inputs/contract.json',
                    selected / 'inputs/plan.json', selected / 'proofs.json'))
                ir.write(out / 'mapping.json', {'fixture': 'Preparation I/O only.'})
                return {'status': 'AUDIT-B-PREPARED'}
            with patch.object(workflow, 'bound', return_value=self.frozen), \
                    patch.object(workflow.audit_b, 'prepare', side_effect=prepare):
                self.assertEqual(workflow.prepare_audit(root)['status'], 'AUDIT-B-PREPARED')
            self.assertEqual(ir.load(selected / 'report.json')['status'], status)

    def test_partial_default_round_cannot_enter_audit_preparation(self):
        for status in ('GRAPH_REPAIR_REQUIRED', 'GRAPH_UNFINISHED', 'CANCELLED'):
            root, selected = self.retained(status, name='proof-run')
            with patch.object(workflow, 'bound', return_value=self.frozen), \
                    patch.object(workflow.audit_b, 'prepare') as prepare, \
                    self.subTest(status=status), self.assertRaises(ValueError):
                workflow.prepare_audit(root)
            prepare.assert_not_called()
            self.assertFalse((root / 'audit-b').exists())

    def test_mapping_preparation_rejects_partial_default_rounds(self):
        for status in ('GRAPH_REPAIR_REQUIRED', 'GRAPH_UNFINISHED', 'CANCELLED'):
            root, selected = self.retained(status, name='proof-run')
            with patch.object(workflow, 'bound', return_value=self.frozen), \
                    self.subTest(status=status), self.assertRaises(ValueError):
                audit_b_mapping.prepare(root, root / 'mapping')
            self.assertFalse((root / 'mapping').exists())

    def test_all_four_graph_statuses_can_supply_bound_candidates_for_fresh_local_recheck(self):
        for status in ('FRAGMENT_ASSEMBLED', 'GRAPH_ASSEMBLY_REPAIR_REQUIRED',
                       'GRAPH_REPAIR_REQUIRED', 'GRAPH_UNFINISHED'):
            root, selected = self.retained(status)
            with self.subTest(status=status):
                result = proof_reuse.candidate(selected, self.contract, self.plan, 'T001')
                self.assertEqual(result['body'], LIFT)
                self.assertIn('requires current native recheck', result['scope'])

    def test_repairable_round_cannot_reuse_a_stale_complete_bundle(self):
        root, selected = self.retained('GRAPH_ASSEMBLY_REPAIR_REQUIRED')
        path = selected / 'proofs.json'
        value = ir.load(path)
        value['plan_sha256'] = '0' * 64
        ir.write(path, value)
        with self.assertRaisesRegex(ValueError, 'Stale prior proof-run evidence'):
            proof_reuse.candidate(selected, self.contract, self.plan, 'T001')

    def test_basis_revision_retains_each_known_status_with_actual_local_bodies(self):
        for status in ('FRAGMENT_ASSEMBLED', 'GRAPH_ASSEMBLY_REPAIR_REQUIRED',
                       'GRAPH_REPAIR_REQUIRED', 'GRAPH_UNFINISHED'):
            base = self.root / status
            scope = base / 'nl0-to-lean/0001/workflow'
            root, selected = self.retained(status, root=scope, name='proof-run')
            stage = scope / 'assembly/stage'
            with patch.object(workflow, 'bound', return_value=self.frozen):
                previous, evidence = basis_defect.previous_program(stage, base)
            with self.subTest(status=status):
                self.assertEqual(previous, str(selected))
                self.assertIn(source_preparation.binding(selected / 'proofs.json'), evidence)

    def test_basis_revision_does_not_preserve_unknown_or_empty_programs_as_proofs(self):
        for status in ('CANCELLED', 'UNKNOWN', 'GRAPH_UNFINISHED'):
            base = self.root / status
            scope = base / 'nl0-to-lean/0001/workflow'
            root, selected = self.retained(status, root=scope, name='proof-run')
            if status == 'GRAPH_UNFINISHED':
                value = ir.load(selected / 'report.json')
                value['proofs'] = {}
                ir.write(selected / 'report.json', value)
            with patch.object(workflow, 'bound', return_value=self.frozen):
                self.assertEqual(basis_defect.previous_program(scope / 'assembly/stage', base), (None, []))


if __name__ == '__main__':
    unittest.main()
