"""Control preparation/type checks only; no semantic model is called."""

import sys as _test_sys
from pathlib import Path as _TestPath
_test_core = _TestPath(__file__).resolve().parents[1]
for _test_path in (_test_core/"scripts", _test_core/"translation/scripts", _test_core/"tests/tooling"):
    _test_sys.path.insert(0,str(_test_path))
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import interface_controls as controls
import interface_review as review
import ir


class InterfaceControlTests(unittest.TestCase):
    def test_owner_labels_are_withheld_and_every_typed_candidate_elaborates(self):
        with tempfile.TemporaryDirectory() as raw:
            out=Path(raw)/'controls';result=controls.prepare(out)
            self.assertEqual(result['status'],'PREPARED_NOT_RUN')
            self.assertEqual(len(result['cases']),5)
            for name in result['cases']:
                inputs=out/name/'inputs';manifest=ir.load(inputs/'inputs.json')
                self.assertNotIn('expected.json',{row['id'] for row in manifest['inputs']})
                text='\n'.join((inputs/row['path']).read_text() for row in manifest['inputs'])
                self.assertNotIn('expected_verdict',text)
                self.assertNotIn('SYNTHETIC_CONTROL_EXPECTED_CANARY',text)
                actual=ir.check(inputs/'contract.json',ir.load(inputs/'plan.json'),types_only=True)
                self.assertEqual(actual['exit_code'],0,actual)

    def test_dispute_evidence_requires_actual_matching_quotes(self):
        docs={'spec.json':{'hypothesis':'The predicate holds on C.'},'contract.json':{'premise':'pc c'}}
        comparison={'source':{'document':'spec.json','pointer':'/hypothesis','quote':'holds on C'},
                    'formal':{'document':'contract.json','pointer':'/premise','quote':'pc c'},
                    'difference':'Synthetic comparison only; this test does not decide its mathematical validity.'}
        review.validate_comparison(comparison,docs)
        comparison['source']['quote']='This is not in the source.'
        with self.assertRaisesRegex(ValueError,'absent'):review.validate_comparison(comparison,docs)


if __name__=='__main__':unittest.main()
