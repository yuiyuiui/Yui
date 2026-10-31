"""Actual Lean inspection of shared proof terms; no model requests."""
import harness_support
import json
from pathlib import Path
import re
import tempfile
import unittest

from pilot_common import run_lean


class SharedTermInspectionTests(unittest.TestCase):
    def test_shared_proof_keeps_types_dependencies_and_axioms_without_expansion(self):
        # Each new proof uses its predecessor twice. The stored expression is a
        # shared graph; expanding every let would duplicate work exponentially.
        lines = ['import Mathlib',
                 'def Doubling : Nat → Prop | 0 => True | n+1 => Doubling n ∧ Doubling n',
                 'theorem seed : True := True.intro',
                 'theorem sharedProof : Doubling 22 := by',
                 '  have h0 : Doubling 0 := seed']
        for n in range(1, 23):
            lines.append(f'  have h{n} : Doubling {n} := ⟨h{n-1}, h{n-1}⟩')
        lines += ['  exact h22', 'namespace AuditBExport',
                  'theorem P : Doubling 22 := sharedProof', 'end AuditBExport']
        checks = '#[("P", "decl:AuditBExport.P", "Doubling 22", #["AuditBExport", "P"]), ' \
                 '("__frozen__P", "decl:AuditBExport.P", "Doubling 22", #["AuditBExport", "P"])]'
        probe = (harness_support.LEAN/'scripts/audit_probe.lean').read_text()
        with tempfile.TemporaryDirectory(prefix='yui-inspector-shared-control-') as raw:
            work = Path(raw)
            (work/'input').mkdir()
            (work/'output').mkdir()
            source = work/'output/Audit.lean'
            source.write_text('\n'.join(lines)+'\n'+probe.replace('__AUDIT_CHECKS__', checks))
            result = run_lean(source, work, timeout=30)
        self.assertEqual(result['exit_code'], 0, result)
        rows = re.findall(r'NL2LEAN_AUDIT_JSON:(\{[^\n]*\})', result['stdout'])
        self.assertEqual(len(rows), 1, result)
        data = json.loads(rows[0])
        self.assertTrue(data['comparisons'][0]['definitionally_equal'])
        self.assertTrue(data['frozen_comparisons'][0]['definitionally_equal'])
        self.assertFalse(data['dependencies']['truncated'])
        declarations = {r['name']: r for r in data['dependencies']['declarations']}
        self.assertIn('sharedProof', declarations)
        self.assertIn('seed', declarations)
        self.assertIn('seed', declarations['sharedProof']['direct_constants'])
        self.assertEqual(declarations['sharedProof']['kind'], 'theorem')
        self.assertFalse(declarations['sharedProof']['imported'])
        self.assertEqual(declarations['AuditBExport.P']['axioms'], [])


if __name__ == '__main__':
    unittest.main()
