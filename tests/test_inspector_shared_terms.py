"""Actual Lean inspection of shared proof terms; no model requests."""
import harness_support
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from pilot_common import run_lean
import basis_native
import inspection_evidence
import ir


class SharedTermInspectionTests(unittest.TestCase):
    def test_template_markers_inside_actual_string_propositions_remain_literal_data(self):
        literal='#[] -- YUI_OWNED_MODULES #[`AuditBExport.P] __AUDIT_CHECKS__'
        target='('+json.dumps(literal)+' : String) = '+json.dumps(literal)
        probe=basis_native.inspector([('P','YuiStringProbe.P',target)],['YuiStringProbe.P'],owned_modules=['YuiOtherModule'])
        self.assertIn(json.dumps(target,ensure_ascii=False),probe)
        with tempfile.TemporaryDirectory() as raw:
            work=Path(raw);(work/'input').mkdir();(work/'output').mkdir()
            source='import Mathlib\nnamespace YuiStringProbe\ntheorem P : '+target+' := rfl\nend YuiStringProbe\n'
            file=work/'output/Inspection.lean';file.write_text(source+probe)
            native=run_lean(file,work)
            self.assertEqual(native['exit_code'],0,native)
            out=work/'retained';out.mkdir()
            evidence=inspection_evidence.capture(native,work,out)
            self.assertTrue(evidence['comparisons'][0]['definitionally_equal'])

    def test_incomplete_native_bytes_are_retained_for_diagnosis_without_any_acceptance(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);work=root/'work';(work/'output').mkdir(parents=True)
            incomplete=b'{"dependencies":{"declarations":['
            (work/'output/yui-inspection.json').write_bytes(incomplete)
            for code in (0,124):
                out=root/str(code);out.mkdir()
                native={'exit_code':code,'timed_out':True,'stdout':'','stderr':''}
                self.assertIsNone(inspection_evidence.capture(native,work,out))
                self.assertIsNone(ir.load(out/'elaborated.json'))
                self.assertEqual((out/'incomplete-inspection.json').read_bytes(),incomplete)
                self.assertTrue(native['incomplete_inspection_evidence']['diagnostic_only'])
                self.assertEqual(native['incomplete_inspection_evidence']['sha256'],ir.digest(out/'incomplete-inspection.json'))
                with self.assertRaises(ValueError):inspection_evidence.verify(native,out)

    def test_complete_axiom_sets_match_lean_for_shared_cyclic_and_imported_dependencies(self):
        source = '''import Mathlib
axiom FixtureProperty : Prop
axiom fixtureProof : FixtureProperty
inductive FixtureBox where
  | pack : FixtureProperty → FixtureBox
  | next : FixtureBox → FixtureBox
def boxed : FixtureBox := .next (.pack fixtureProof)
theorem shared : FixtureProperty := fixtureProof
namespace AuditBExport
theorem P : FixtureProperty ∧ FixtureProperty := ⟨shared, shared⟩
end AuditBExport
'''
        probe = basis_native.inspector([('P','AuditBExport.P','FixtureProperty ∧ FixtureProperty')],
                                       ['AuditBExport.P','boxed'])
        oracle = '''
open Lean Meta Elab Command in
run_cmd do
  let raw ← liftIO <| IO.FS.readFile "yui-inspection.json"
  let value ← ofExcept (Json.parse raw)
  let deps ← ofExcept (value.getObjVal? "dependencies")
  let rows ← ofExcept (deps.getObjValAs? (Array Json) "declarations")
  for row in rows do
    let name ← ofExcept (row.getObjValAs? String "name")
    let actual ← ofExcept (row.getObjValAs? (Array String) "axioms")
    let expected ← liftTermElabM do
      let axes ← collectAxioms ((name.splitOn ".").foldl Name.str .anonymous)
      return (axes.qsort Name.lt).map Name.toString
    unless actual == expected do throwError "Axiom oracle mismatch at {name}: {actual} vs {expected}"
  logInfo "YUI_AXIOM_ORACLE_VERIFIED"
'''
        with tempfile.TemporaryDirectory() as raw:
            work=Path(raw);(work/'input').mkdir();(work/'output').mkdir()
            file=work/'output/Control.lean';file.write_text(source+'\n'+probe+'\n'+oracle)
            native=run_lean(file,work)
            self.assertEqual(native['exit_code'],0,native['stdout'][-5000:])
            self.assertIn('YUI_AXIOM_ORACLE_VERIFIED',native['stdout'])
            out=work/'retained';out.mkdir()
            evidence=inspection_evidence.capture(native,work,out)
            self.assertIsNotNone(evidence,native)
            self.assertEqual(inspection_evidence.verify(native,out),evidence)
            rows={row['name']:row for row in evidence['dependencies']['declarations']}
            self.assertIn('fixtureProof',rows['AuditBExport.P']['axioms'])
            self.assertIn('FixtureBox.pack',rows)
            self.assertIn('signature',rows['AuditBExport.P'])
            self.assertNotIn('type',rows['shared'])
            self.assertEqual(rows['shared']['detail'],'dependency')
            self.assertLess(len(native['stdout']), (out/'elaborated.json').stat().st_size)
            problems=basis_native.errors(native,evidence,[('P','AuditBExport.P','FixtureProperty ∧ FixtureProperty')],['AuditBExport.P'])
            self.assertTrue(any(p.startswith('UNPERMITTED_AXIOM:') for p in problems),problems)
            original=(out/'elaborated.json').read_bytes()
            (out/'elaborated.json').write_bytes(original+b' ')
            with self.assertRaisesRegex(ValueError,'evidence changed'):inspection_evidence.verify(native,out)
            (out/'elaborated.json').unlink()
            with self.assertRaisesRegex(ValueError,'artifact'):inspection_evidence.verify(native,out)
            partial={**native,'timed_out':True}
            self.assertIsNone(inspection_evidence.capture(partial,work,out))
            self.assertIsNone(ir.load(out/'elaborated.json'))
            broken=ir.load(work/'output/yui-inspection.json')
            del broken['dependencies']['declarations'][0]['axioms']
            ir.write(work/'output/yui-inspection.json',broken)
            self.assertIsNone(inspection_evidence.capture(dict(native),work,out))

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
            # The shared theorem's own kernel elaboration can exceed 30s on a
            # cold/current toolchain. This is a correctness control, not a
            # machine-speed requirement or a change to production timeouts.
            result = run_lean(source, work, timeout=120)
            data = json.loads((work/'output/yui-inspection.json').read_text()) if result['exit_code'] == 0 else None
        self.assertEqual(result['exit_code'], 0, result)
        self.assertEqual(result['stdout'].count('NL2LEAN_AUDIT_FILE:yui-inspection.json'), 1, result)
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
