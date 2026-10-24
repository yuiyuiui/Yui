"""Deterministic source discovery; candidates remain verified native metadata."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import library_catalog as c


class CatalogTests(unittest.TestCase):
    def test_exact_canonical_name_returns_only_its_native_metadata(self):
        rows=c.lookup('MeasureTheory.lintegral_tsum')['sources']
        self.assertEqual([r['declaration'] for r in rows],['MeasureTheory.lintegral_tsum'])
        self.assertEqual(rows[0]['match_kind'],'exact_declaration')
        self.assertEqual(rows[0]['declaration_kind'],'theorem')
        self.assertTrue(rows[0]['signature'])

    def test_natural_queries_keep_relevant_candidates_without_matching_every_word(self):
        for query,expected in [('the integral of a finite sum','MeasureTheory.integral_finsetSum'),
                ('continuous integrable compact support','Continuous.integrable_of_hasCompactSupport'),
                ('finitely generated module image under a linear map','Submodule.FG.map')]:
            rows=c.lookup(query)['sources']
            self.assertEqual(rows[0]['declaration'],expected)
            self.assertEqual(rows[0]['match_kind'],'keyword_candidate')
            self.assertTrue(rows[0]['matched_terms'])
            self.assertLessEqual(len(rows),12)

    def test_unmatched_terms_do_not_invent_sources_and_order_is_stable(self):
        self.assertEqual(c.lookup('quokka-xylophone-unmatched')['sources'],[])
        entries=c.load()['entries']
        a=c.ranked(entries,'integral linearity');b=c.ranked(list(reversed(entries)),'integral linearity')
        self.assertEqual([r[0]['declaration'] for r in a],[r[0]['declaration'] for r in b])

    def test_ranking_cannot_bypass_pin_and_evidence_verification(self):
        with patch.object(c,'verified',side_effect=ValueError('Changed native source evidence')):
            with self.assertRaisesRegex(ValueError,'Changed native source'):
                c.lookup('MeasureTheory.lintegral_tsum')


if __name__=='__main__':unittest.main()
