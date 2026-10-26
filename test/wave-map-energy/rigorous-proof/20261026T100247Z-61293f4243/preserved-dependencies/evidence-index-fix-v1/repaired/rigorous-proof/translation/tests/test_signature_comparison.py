"""Native controls for signature binding; no model or semantic certification."""
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'scripts'))
import ir


class SignatureComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp(prefix='yui-signature-controls-'))
        (cls.work/'input').mkdir(); (cls.work/'output').mkdir()
        source = '''import Mathlib
universe ua ub va vb
namespace AuditBExport
theorem P : True := True.intro
end AuditBExport
theorem pairTypes (A : Type ua) (B : Type ub) : True := True.intro
theorem naturalIdentity (n : Nat) : n = n := rfl
'''
        rows = [
            ('renamed', 'decl:pairTypes', '∀ (X : Type va) (Y : Type vb), True', ['pairTypes']),
            ('collapsed', 'decl:pairTypes', '∀ (X : Type va) (Y : Type va), True', ['pairTypes']),
            ('successor', 'decl:pairTypes', '∀ (X : Type (va+1)) (Y : Type vb), True', ['pairTypes']),
            ('changed_type', 'decl:naturalIdentity', '∀ (b : Bool), b = b', ['naturalIdentity']),
            ('renamed_term_binder', 'decl:naturalIdentity', '∀ (x : Nat), x = x', ['naturalIdentity']),
        ]
        encoded = '#[' + ', '.join('(' + ', '.join(
            '#['+', '.join(json.dumps(y) for y in x)+']' if isinstance(x,list)
            else json.dumps(x) for x in row) + ')' for row in rows) + ']'
        source += (HERE/'scripts/audit_probe.lean').read_text().replace('__AUDIT_CHECKS__', encoded)
        path = cls.work/'output/Signatures.lean'; path.write_text(source)
        cls.native = ir.run_lean(path, cls.work)
        matches = re.findall(r'NL2LEAN_AUDIT_JSON:(\{[^\n]*\})', cls.native['stdout'])
        cls.rows = {r['id']:r for r in json.loads(matches[-1])['comparisons']} if matches else {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work)

    def test_probe_compiles(self):
        self.assertEqual(self.native['exit_code'], 0, self.native['stdout'][-6000:])

    def test_bijective_universe_renaming_is_equal(self):
        self.assertTrue(self.rows['renamed']['definitionally_equal'])
        self.assertEqual(self.rows['renamed']['comparison_method'], 'bijective_universe_renaming')

    def test_distinct_universes_cannot_be_collapsed(self):
        self.assertFalse(self.rows['collapsed']['definitionally_equal'])

    def test_successor_relationship_cannot_be_erased(self):
        self.assertFalse(self.rows['successor']['definitionally_equal'])

    def test_term_type_changes_are_rejected(self):
        self.assertFalse(self.rows['changed_type']['definitionally_equal'])

    def test_term_binder_names_do_not_matter(self):
        self.assertTrue(self.rows['renamed_term_binder']['definitionally_equal'])


if __name__ == '__main__':
    unittest.main()
