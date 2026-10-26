"""Actual author-contract compatibility of mechanically routed review diagnostics."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

CORE=Path(__file__).resolve().parents[1]
for path in (CORE/'scripts',CORE/'translation/scripts'):sys.path.insert(0,str(path))
from case_runner import repair_obligations
from artifact_validation import NL0Contract
from acceptance import current


class RepairDiagnosticTests(unittest.TestCase):
    def test_local_and_global_findings_import_into_the_real_author_issue_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=CORE/'tests/fixtures/closed-addition'
            for group,record in [('R001',{'checks':{'object_closure':{'verdict':'FAIL',
                    'notes':'Neutral diagnostic fixture only.','locations':['/inference/argument/0']}}}),
                 ('global',{'target_review':{'verdict':'FAIL','notes':'Neutral target diagnostic only.',
                                             'locations':['spec.json#/full_target']}})]:
                directory=root/'review'/group/'stage';directory.mkdir(parents=True)
                (directory/'accepted.json').write_text(json.dumps(record))
            issues=repair_obligations(source,root/'review')
            baseline={'spec':json.loads((source/'spec.json').read_text()),
                      'graph':json.loads((source/'nl0.json').read_text())}
            contract=NL0Contract(root/'author',{'baseline.json':json.dumps(baseline),
                'repair-obligations.json':json.dumps(issues)},case_id=baseline['spec']['case_id'])
            self.assertEqual(len(contract.author_check.open_issues),2)
            self.assertEqual({r['criterion'] for r in issues['issues']},{'object_closure','target'})
            self.assertTrue(all(r['criterion'] in current().rows for r in issues['issues']))


if __name__=='__main__':unittest.main()
