"""Independent environment-selection examples; no host tools or downloads."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[1] / 'blocks/lean_environments.py'
SPEC = importlib.util.spec_from_file_location('environment_rules_under_test', PATH)
rules = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rules)


def candidate(version='4.35.0', revision='b' * 40, root='/tools/new'):
    return {'version': 'yui-lean-environment-1',
            'lean': {'toolchain': 'leanprover/lean4:v' + version,
                     'version': 'Lean (version ' + version + ', example, Release)',
                     'version_number': version, 'local_path': root + '/lean',
                     'binary_sha256': 'a' * 64},
            'mathlib': {'url': 'https://github.com/leanprover-community/mathlib4.git',
                        'rev': revision, 'ref': 'v' + version, 'local_path': root + '/mathlib',
                        'manifest_sha256': 'c' * 64, 'toolchain_sha256': 'd' * 64},
            'dependencies': [],
            'compatibility': {'exit_code': 0, 'accepted': True, 'source_sha256': 'e' * 64}}


class EnvironmentSelection(unittest.TestCase):
    def test_one_verified_pair_can_be_used_without_a_version_preference(self):
        expected = candidate()
        self.assertEqual(rules.select([expected]), expected)

    def test_two_versions_require_an_explicit_choice(self):
        old = candidate('4.32.2', 'f' * 40, '/tools/old')
        with self.assertRaises(rules.SelectionRequired) as caught:
            rules.select([old, candidate()])
        request = caught.exception.request
        self.assertEqual(request['status'], 'LEAN_ENVIRONMENT_SELECTION_REQUIRED')
        self.assertEqual(len(request['candidates']), 2)
        self.assertIn('paths', request['choices'])
        self.assertIn('versions', request['choices'])

    def test_explicit_version_and_exact_revision_select_the_requested_pair(self):
        old = candidate('4.32.2', 'f' * 40, '/tools/old')
        expected = candidate()
        self.assertEqual(rules.select([old, expected], lean_version='4.35.0'), expected)
        self.assertEqual(rules.select([old, expected], mathlib_ref='b' * 40), expected)
        self.assertEqual(rules.select([old, expected], mathlib_ref='v4.32.2'), old)

    def test_aliases_of_the_same_pair_are_one_choice(self):
        expected = candidate()
        self.assertEqual(rules.select([expected, deepcopy(expected)]), expected)

    def test_same_version_with_two_revisions_is_still_ambiguous(self):
        with self.assertRaises(rules.SelectionRequired):
            rules.select([candidate(), candidate(revision='f' * 40, root='/tools/other')],
                         lean_version='4.35.0')

    def test_missing_unavailable_and_incompatible_choices_never_fall_back(self):
        for rows, selection in (([], {}), ([candidate()], {'lean_version': '4.99.0'}),
                                ([candidate()], {'mathlib_ref': 'missing'})):
            with self.subTest(selection=selection), self.assertRaises(rules.SelectionRequired):
                rules.select(rows, **selection)
        wrong = candidate()
        wrong['lean']['toolchain'] = 'leanprover/lean4:v4.32.2'
        with self.assertRaises(ValueError):
            rules.validate(wrong)

    def test_native_timeout_partial_output_and_cancelled_results_are_not_compatible(self):
        for change in ({'exit_code': 124}, {'accepted': False}, {'timed_out': True},
                       {'cancelled': True}, {'exit_code': False}):
            value = candidate()
            value['compatibility'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                rules.validate(value)

    def test_descriptor_and_pin_projection_do_not_mutate_the_selected_authority(self):
        value = candidate()
        original = deepcopy(value)
        selected = rules.select([value])
        selected['lean']['local_path'] = '/unrelated'
        self.assertEqual(value, original)
        self.assertEqual(rules.pins(value), {'lean_version': '4.35.0',
                         'mathlib_commit': 'b' * 40, 'mathlib_root': '/tools/new/mathlib'})
        self.assertEqual(rules.pins(None), {'lean_version': 'NOT_SELECTED',
                         'mathlib_commit': 'NOT_SELECTED', 'mathlib_root': 'NOT_SELECTED'})


if __name__ == '__main__':
    unittest.main()
