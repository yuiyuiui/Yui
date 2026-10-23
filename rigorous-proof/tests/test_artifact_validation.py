"""Security and binding controls for structural NL0 authoring; not mathematical certification."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from artifact_validation import NL0Contract, signature_probe


class ArtifactValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_only_metadata_is_bound_and_missing_proof_is_rejected(self):
        fixture=Path(__file__).parent/'fixtures/closed-addition'
        value={'spec':json.loads((fixture/'spec.json').read_text()),
               'graph':json.loads((fixture/'nl0.json').read_text())}
        original=value['graph']['inferences'][0]['argument'][0]['text']
        contract=NL0Contract(self.root/'case',{'problem.txt':'Explicit target input.'},
                             case_id=value['spec']['case_id'])
        checked=contract(value)
        self.assertFalse(checked['mathematical_acceptance'])
        self.assertEqual(value['graph']['inferences'][0]['argument'][0]['text'],original)
        self.assertEqual(value['spec']['inputs'][0]['path'],'inputs/problem.txt')
        value['graph']['inferences']=[]
        with self.assertRaises(ValueError):contract(value)

    def test_library_probe_rejects_code_injection_before_execution(self):
        for name in ['Nat.add_zero\n#eval IO.println "bad"','Nat.add_zero;','Nat.add_zero`']:
            with self.assertRaises(ValueError):
                signature_probe(self.root,'M001',name,'Mathlib.Algebra.Group.Nat.Defs',1)
        with self.assertRaises(ValueError):
            signature_probe(self.root,'M001','Nat.add_zero','../Other',1)


if __name__=='__main__':unittest.main()
