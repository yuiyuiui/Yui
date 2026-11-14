"""Reference availability is independent of the task's compilation environment."""
import harness_support
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import runtime_config
import strategy_bank as bank


SOURCE = {'lean_version': '4.32.2',
          'mathlib_commit': '905b95818eb32af7874a58b427f50c1711a5e96c',
          'basis': 'historical_configuration'}
VERSIONS = (SOURCE['lean_version'], '0.0.1', '99.0.0', 'NOT_SELECTED', None)


class CrossVersionReferences(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def stage(self, name, version):
        root = bank.BASIS_BANK if name == 'basis' else bank.BANK
        binding = {'path': str(root), 'source': bank.sha(root/'strategies.json'),
                   'index': bank.sha(root/'index.json')}
        return SimpleNamespace(mode='interface-authoring', instruction_arm='yui',
                               native_timeout_lean_version=version,
                               strategy_banks={name: binding})

    def assert_reference(self, reply):
        self.assertIs(reply['reference_only'], True)
        self.assertIs(reply['current_environment_verification_required'], True)
        self.assertTrue(reply['usage_notice'])

    def test_every_card_is_listed_and_readable_for_old_new_unlisted_and_no_lean(self):
        for name, root, count in (('basis', bank.BASIS_BANK, 5), ('lean', bank.BANK, 17)):
            expected = {c['id'] for c in json.loads((root/'strategies.json').read_text())}
            self.assertEqual(len(expected), count)
            for version in VERSIONS:
                with self.subTest(bank=name, version=version):
                    stage = self.stage(name, version)
                    reply = bank.consult(stage, {'bank': name})
                    self.assertEqual(reply['status'], 'catalog', reply)
                    self.assertEqual({c['id'] for c in reply['catalog']}, expected)
                    self.assert_reference(reply)
                    for row in reply['catalog']:
                        self.assertEqual(row['reference_environments'], [SOURCE])
                    for identifier in sorted(expected):
                        read = bank.consult(stage, {'bank': name, 'ids': [identifier]})
                        self.assertEqual(read['status'], 'cards', read)
                        self.assert_reference(read)
                        self.assertEqual([c['id'] for c in read['cards']], [identifier])
                        self.assertEqual(read['cards'][0]['reference_environments'], [SOURCE])

    def test_reference_lookup_never_selects_or_queries_a_native_environment(self):
        stage = self.stage('basis', None)
        with patch.object(runtime_config, 'scientific_pins', side_effect=AssertionError('No environment lookup for advice')), \
                patch.object(runtime_config, 'selected_environment', side_effect=AssertionError('No environment selection for advice')):
            reply = bank.consult(stage, {'bank': 'basis', 'ids': ['ST021']})
        self.assertEqual(reply['status'], 'cards', reply)
        self.assert_reference(reply)

    def test_unknown_ids_return_a_located_error_under_every_version(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                reply = bank.consult(self.stage('basis', version),
                                     {'bank': 'basis', 'ids': ['ST021', 'ST999']})
                self.assertEqual(reply['status'], 'not_in_catalog', reply)
                self.assertEqual(reply['ids'], ['ST999'])
                self.assertNotIn('cards', reply)

    def test_ranked_search_keeps_reference_versions_without_using_them_as_a_filter(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                reply = bank.search({'family': 'representation', 'tags': ['conversion'],
                                     'lean_version': version, 'facts': []})
                self.assertEqual(reply['status'], 'CANDIDATES', reply)
                self.assert_reference(reply)
                first = reply['strategies'][0]
                self.assertEqual(first['id'], 'ST001')
                self.assertEqual(first['card']['reference_environments'], [SOURCE])
                self.assertFalse(first['preconditions_independently_verified'])

    def test_timeout_advice_is_available_cross_version_without_accepting_the_failure(self):
        failure = {'exit_code': 124, 'timed_out': True, 'error_kind': 'LEAN_TIMEOUT',
                   'timeout_scope': 'native_call', 'stdout': '', 'stderr': 'Retained timeout.'}
        frozen = bank.freeze_native_timeout_policy(self.root/'advice')
        self.assertEqual(frozen['status'], 'READY')
        for version in VERSIONS:
            with self.subTest(version=version):
                reply = bank.native_timeout_feedback(failure, version, frozen)
                self.assertEqual(reply['status'], 'ADVICE_DELIVERED', reply)
                self.assert_reference(reply)
                self.assertEqual(reply['strategy']['card']['reference_environments'], [SOURCE])
                self.assertEqual(failure['exit_code'], 124)
                self.assertTrue(failure['timed_out'])


if __name__ == '__main__':
    unittest.main()
