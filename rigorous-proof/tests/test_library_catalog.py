"""Pinned native metadata reuse, not source restatement or applicability audits."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import library_catalog as c
from artifact_validation import signature_probe


class LibraryCatalogTests(unittest.TestCase):
    def test_catalog_contains_only_actual_proved_pinned_sources(self):
        value=c.load();self.assertGreaterEqual(len(value['entries']),8)
        for entry in value['entries']:
            row,report,_=c.verified(entry)
            self.assertEqual(row['declaration_kind'],'theorem')
            self.assertEqual(report['exit_code'],0)
            self.assertIn('original',json.dumps(value).lower())

    def test_new_source_id_reuses_metadata_without_repeating_native_query(self):
        with tempfile.TemporaryDirectory() as raw,patch('artifact_validation.run_lean',side_effect=AssertionError('No new native query expected')):
            root=Path(raw)
            row=signature_probe(root,'M017','MeasureTheory.integral_add','Mathlib.MeasureTheory.Integral.Bochner.Basic',1)
            report=json.loads((root/row['evidence'][0]['path']).read_text())
            self.assertTrue(row['metadata_reused']);self.assertIn('M017',report['sources'])
            self.assertIn('original_native_cost_seconds',report['metadata_reuse'])
            self.assertNotIn('mathematical_acceptance',row)

    def test_catalog_lookup_preserves_complete_formal_conditions(self):
        sources=c.lookup('integral addition')['sources']
        self.assertEqual(len(sources),1)
        self.assertIn('Integrable',sources[0]['signature'])
        self.assertNotIn('MeasureTheory.Measure.pi',{row['declaration'] for row in c.lookup('measure')['sources']})


if __name__=='__main__':unittest.main()
