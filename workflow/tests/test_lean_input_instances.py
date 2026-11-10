"""Independent examples for the two sources of a specialized Lean proof input."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'blocks'))
import lean_input_instances as inputs


class Sources(unittest.TestCase):
    def test_internal(self):
        nodes = {'T001': {'universe_params': ['v'], 'statement': '∀ A : Type v, A → A'}}
        port = inputs.resolve('T001', nodes, {})
        self.assertEqual(port, ('__connected_T001', ['v'], True))
        self.assertEqual(inputs.application(port, ['0'], ['n', 'h_H001']), '(@__connected_T001.{0} n h_H001)')

    def test_prepared(self):
        prepared = {'E002': {'basis': 'B017', 'levels': ['u_1', 'u_2']}}
        port = inputs.resolve('E002', {}, prepared)
        self.assertEqual(port, ('YuiBasis.B017', ['u_1', 'u_2'], False))
        self.assertEqual(inputs.application(port, ['v', '0'], ['n', 'h_H001']), '(@YuiBasis.B017.{v, 0})')

    def test_unproven_has_no_declaration_to_specialize(self):
        for key in ('H001', 'E001', 'M001'):
            self.assertIsNone(inputs.resolve(key, {}, {}))


if __name__ == '__main__':
    unittest.main()
