"""Real Lean declaration checks; no exercise-specific mathematics or model calls."""
import harness_support
import copy
from pathlib import Path
import tempfile
import unittest

import ir


class StrictInterfaceTypesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        ir.write(self.root/'source.json', {'input': 'Neutral identity.'})
        self.contract = {
            'version': 2, 'id': 'strict_signature_control',
            'source': {'path': 'source.json', 'sha256': ir.digest(self.root/'source.json')},
            'source_steps': [{'id': 'S001', 'text': 'Retain the identity.'}],
            'pins': {'lean_version': ir.load_lock()['lean']['version_number'], 'mathlib_commit': ir.load_lock()['mathlib']['rev']},
            'header': 'import Mathlib\ndef hiddenIndex {n : Nat} (x : Nat) : Prop := x = n\n',
            'parameters': [{'name': 'n', 'type': 'Nat'}, {'name': 'x', 'type': 'Nat'}],
            'premises': [{'id': 'H001', 'kind': 'hypothesis', 'statement': 'Identity.', 'type': 'True'}],
            'conclusion': {'statement': 'Identity.', 'type': 'True'},
            'representation': 'Neutral natural-number parameters.', 'objects': [],
            'shared_obligations': [], 'review': {'mode': 'development_owner_review'},
        }
        self.path = self.root/'contract.json'
        self.plan = {'version': 2, 'contract_sha256': '', 'representation_notes': 'Neutral.',
                     'steps': [{'id': 'T001', 'statement': 'True', 'inputs': ['H001'],
                                'source_steps': ['S001'], 'explanation': 'Retain.'}], 'terminal': 'T001'}

    def tearDown(self):
        self.temp.cleanup()

    def checked(self, statement, *, premise='True'):
        value = copy.deepcopy(self.contract)
        value['premises'][0]['type'] = premise
        value['conclusion']['type'] = statement
        ir.write(self.path, value)
        plan = copy.deepcopy(self.plan)
        plan['contract_sha256'] = ir.digest(self.path)
        plan['steps'][0]['statement'] = statement
        return ir.check(self.path, plan, types_only=True)

    def test_noninferable_implicit_parameter_is_rejected(self):
        result = self.checked('hiddenIndex x')
        self.assertNotEqual(result['exit_code'], 0, result['stdout'])

    def test_explicit_existing_parameter_is_accepted(self):
        result = self.checked('hiddenIndex (n := n) x')
        self.assertEqual(result['exit_code'], 0, result['stdout'])

    def test_unresolved_parameter_in_direct_input_is_rejected(self):
        result = self.checked('True', premise='hiddenIndex x')
        self.assertNotEqual(result['exit_code'], 0, result['stdout'])

    def test_unused_public_premise_is_checked_in_the_complete_export_signature(self):
        self.contract['premises'].append({'id':'E001','kind':'external',
            'statement':'Neutral unused external control.','type':'hiddenIndex x'})
        result = self.checked('True')
        self.assertNotEqual(result['exit_code'], 0, result['stdout'])

    def test_a_nonproposition_cannot_be_a_proof_obligation(self):
        result = self.checked('Nat')
        self.assertNotEqual(result['exit_code'], 0, result['stdout'])

    def test_legitimate_implicit_inference_is_preserved(self):
        result = self.checked('id x = x')
        self.assertEqual(result['exit_code'], 0, result['stdout'])


if __name__ == '__main__':
    unittest.main()
