"""Independent state and real filesystem handoff examples inside translate."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


BLOCK = Path(__file__).resolve().parents[1] / 'blocks/proof_rounds.py'
SPEC = importlib.util.spec_from_file_location('round_rules_under_test', BLOCK)
rounds = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rounds)
VERSION = 'nl0-lean-workflow-1'


class RoundStates(unittest.TestCase):
    def test_four_producer_outcomes_keep_their_meanings(self):
        self.assertEqual(rounds.state_for(complete=True, accepted=True, repair_requested=False),
                         'FRAGMENT_ASSEMBLED')
        self.assertEqual(rounds.state_for(complete=True, accepted=False, repair_requested=False),
                         'GRAPH_ASSEMBLY_REPAIR_REQUIRED')
        self.assertEqual(rounds.state_for(complete=False, accepted=False, repair_requested=True),
                         'GRAPH_REPAIR_REQUIRED')
        self.assertEqual(rounds.state_for(complete=False, accepted=False, repair_requested=False),
                         'GRAPH_UNFINISHED')

    def test_assembly_readiness_does_not_grant_compiler_acceptance(self):
        for status, local, compiled in (
                ('FRAGMENT_ASSEMBLED', True, True),
                ('GRAPH_ASSEMBLY_REPAIR_REQUIRED', True, False),
                ('GRAPH_REPAIR_REQUIRED', False, False),
                ('GRAPH_UNFINISHED', False, False)):
            with self.subTest(status=status):
                self.assertEqual(rounds.locally_complete(status), local)
                self.assertEqual(rounds.compiler_accepted(status), compiled)
                self.assertTrue(rounds.retains_bodies(status))

    def test_unknown_worker_cancelled_and_malformed_states_grant_no_graph_authority(self):
        for status in ('CANCELLED', 'LOCAL_PROOFS_CHECKED', 'WORKFLOW-PASSED', 'UNKNOWN',
                       '', None, False, 0, [], {}, ['FRAGMENT_ASSEMBLED']):
            with self.subTest(status=status):
                self.assertFalse(rounds.locally_complete(status))
                self.assertFalse(rounds.compiler_accepted(status))
                self.assertFalse(rounds.retains_bodies(status))

    def test_inconsistent_producer_inputs_cannot_claim_compiler_success(self):
        for complete, accepted, requested in ((False, True, False), (True, True, True),
                                               (True, False, True)):
            with self.subTest(complete=complete, accepted=accepted, requested=requested), \
                    self.assertRaises(ValueError):
                rounds.state_for(complete=complete, accepted=accepted, repair_requested=requested)


class RoundReader(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='round-reader-')
        self.root = Path(self.temp.name).resolve()
        self.selected = self.root / 'proof-repairs/0002'
        self.paths = ('report.json', 'proofs.json', 'inputs/contract.json', 'inputs/plan.json')
        self.files('GRAPH_ASSEMBLY_REPAIR_REQUIRED')

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def files(self, status):
        for name in self.paths:
            self.write(self.selected / name, {'status': status} if name == 'report.json'
                       else {'fixture': 'Filesystem handoff; no scientific proof or verdict.'})

    def record(self):
        """The independent fixture uses the existing public selection-file format."""
        return {'version': VERSION, 'directory': 'proof-repairs/0002',
                'scope': 'Independent original report retained.', 'evidence': [
                    {'path': str(self.selected / name),
                     'sha256': hashlib.sha256((self.selected / name).read_bytes()).hexdigest()}
                    for name in self.paths]}

    def save(self, value=None):
        self.write(self.root / 'proof-selection.json', self.record() if value is None else value)

    def test_default_origin_resolves_without_granting_a_verdict(self):
        default = self.root / 'proof-run'
        self.write(default / 'report.json', {'status': 'GRAPH_ASSEMBLY_REPAIR_REQUIRED'})
        before = (default / 'report.json').read_bytes()
        self.assertEqual(rounds.read(self.root, VERSION), default)
        self.assertEqual((default / 'report.json').read_bytes(), before)
        self.assertFalse((self.root / 'proof-selection.json').exists())

    def test_selected_origin_reads_the_same_repairable_status(self):
        self.save()
        before = {name: (self.selected / name).read_bytes() for name in self.paths}
        self.assertEqual(rounds.read(self.root, VERSION), self.selected)
        self.assertEqual(rounds.read(self.root, VERSION), self.selected)
        self.assertEqual({name: (self.selected / name).read_bytes() for name in self.paths}, before)
        self.assertFalse((self.root / 'report.json').exists())

    def test_selection_and_reader_agree_on_both_complete_states(self):
        for status in ('FRAGMENT_ASSEMBLED', 'GRAPH_ASSEMBLY_REPAIR_REQUIRED'):
            self.files(status)
            value = rounds.selection(self.root, self.selected, VERSION)
            self.assertEqual(value['version'], VERSION)
            self.assertEqual(value['directory'], 'proof-repairs/0002')
            self.save(value)
            self.assertEqual(rounds.read(self.root, VERSION), self.selected)
            self.assertEqual(json.loads((self.selected / 'report.json').read_text())['status'], status)

    def test_default_path_remains_available_for_unstarted_and_partial_diagnosis(self):
        self.assertEqual(rounds.read(self.root, VERSION), self.root / 'proof-run')
        for status in ('GRAPH_REPAIR_REQUIRED', 'GRAPH_UNFINISHED'):
            self.write(self.root / 'proof-run/report.json', {'status': status})
            self.assertEqual(rounds.read(self.root, VERSION), self.root / 'proof-run')

    def test_incomplete_and_unknown_rounds_cannot_be_selected_or_admitted_by_a_record(self):
        for status in ('GRAPH_REPAIR_REQUIRED', 'GRAPH_UNFINISHED', 'CANCELLED', 'UNKNOWN',
                       'LOCAL_PROOFS_CHECKED', None, [], {}):
            self.files(status)
            with self.subTest(status=status), self.assertRaises(ValueError):
                rounds.selection(self.root, self.selected, VERSION)
            self.save()
            with self.subTest(read_status=status), self.assertRaises(ValueError):
                rounds.read(self.root, VERSION)

    def test_exactly_four_distinct_owned_evidence_files_are_required(self):
        for kind in ('duplicate', 'missing', 'foreign', 'bad-hash'):
            value = self.record()
            if kind == 'duplicate':
                value['evidence'].append(copy.deepcopy(value['evidence'][0]))
            elif kind == 'missing':
                value['evidence'].pop()
            elif kind == 'foreign':
                path = self.root / 'foreign.json'
                self.write(path, {})
                value['evidence'][0] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            else:
                value['evidence'][0]['sha256'] = '0' * 64
            self.save(value)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                rounds.read(self.root, VERSION)

    def test_all_bound_files_are_checked_on_every_read(self):
        for name in self.paths:
            self.files('GRAPH_ASSEMBLY_REPAIR_REQUIRED')
            self.save()
            path = self.selected / name
            path.write_bytes(path.read_bytes() + b'\n')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'stale'):
                rounds.read(self.root, VERSION)

    def test_missing_bound_files_block_both_selection_and_reading(self):
        for name in self.paths:
            self.files('GRAPH_ASSEMBLY_REPAIR_REQUIRED')
            self.save()
            (self.selected / name).unlink()
            with self.subTest(select_missing=name), self.assertRaises(ValueError):
                rounds.selection(self.root, self.selected, VERSION)
            with self.subTest(read_missing=name), self.assertRaises(ValueError):
                rounds.read(self.root, VERSION)

    def test_malformed_reports_cannot_acquire_authority_through_a_matching_hash(self):
        for value in ([], {}, 'FRAGMENT_ASSEMBLED', {'status': False}):
            self.write(self.selected / 'report.json', value)
            self.save()
            with self.subTest(value=value), self.assertRaises(ValueError):
                rounds.read(self.root, VERSION)
            with self.assertRaises(ValueError):
                rounds.selection(self.root, self.selected, VERSION)
        for text in ('{', '{"status":"GRAPH_UNFINISHED","status":"FRAGMENT_ASSEMBLED"}'):
            (self.selected / 'report.json').write_text(text)
            self.save()
            with self.subTest(text=text), self.assertRaises(ValueError):
                rounds.read(self.root, VERSION)

    def test_each_evidence_binding_has_its_exact_required_shape(self):
        original = self.record()
        first = original['evidence'][0]
        for entry in (None, [], {}, {'path': first['path']}, {**first, 'sha256': None},
                      {**first, 'path': []}, {**first, 'unbound': True}):
            value = copy.deepcopy(original)
            value['evidence'][0] = entry
            self.save(value)
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                rounds.read(self.root, VERSION)

    def test_wrong_version_malformed_records_and_unsafe_directories_are_rejected(self):
        original = self.record()
        variants = [[], {}, {**original, 'version': 'old'},
                    *[{**original, 'directory': d} for d in ('', '.', '..', '../outside', '/tmp/foreign', None, [])],
                    *[{**original, 'evidence': e} for e in (None, {}, [], [None])]]
        for value in variants:
            self.save(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                rounds.read(self.root, VERSION)

    def test_directory_and_artifact_links_cannot_escape_the_selected_owned_round(self):
        with tempfile.TemporaryDirectory(prefix='foreign-round-') as raw:
            outside = Path(raw).resolve()
            for name in self.paths:
                self.write(outside / name, {})
            alias = self.root / 'foreign-round'
            alias.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                rounds.selection(self.root, alias, VERSION)
            path = self.selected / 'proofs.json'
            path.unlink()
            path.symlink_to(outside / 'proofs.json')
            with self.assertRaises(ValueError):
                rounds.selection(self.root, self.selected, VERSION)
            self.save()
            with self.assertRaises(ValueError):
                rounds.read(self.root, VERSION)

    def test_selection_file_itself_cannot_be_a_symlink(self):
        outside = self.root / 'other-selection.json'
        self.write(outside, self.record())
        (self.root / 'proof-selection.json').symlink_to(outside)
        with self.assertRaises(ValueError):
            rounds.read(self.root, VERSION)

    def test_default_location_cannot_be_redirected_by_a_symlink(self):
        with tempfile.TemporaryDirectory(prefix='foreign-default-') as raw:
            (self.root / 'proof-run').symlink_to(Path(raw), target_is_directory=True)
            with self.assertRaises(ValueError):
                rounds.read(self.root, VERSION)

    def test_duplicate_json_fields_cannot_override_the_record(self):
        record = json.dumps(self.record())
        (self.root / 'proof-selection.json').write_text('{"directory":"../outside",' + record[1:])
        with self.assertRaises(ValueError):
            rounds.read(self.root, VERSION)


if __name__ == '__main__':
    unittest.main()
