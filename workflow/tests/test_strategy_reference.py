"""Independent examples for the optional reference tool inside reduce and translate."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from blocks import strategy_reference as reference
from wfcore.model import Model


class StrategyReferenceTests(unittest.TestCase):
    def test_authors_and_independent_roles(self):
        for phase, expected in [
            ('basis-authoring', ('basis',)), ('basis-frontier', ('basis',)),
            ('interface-authoring', ('basis', 'lean')), ('proof', ('lean',)),
            ('translation-source-preparation', ()), ('basis-semantic-review', ()),
            ('audit-a-global', ()), ('audit-b-review', ()), ('nl0-local-authoring', ()),
        ]:
            with self.subTest(phase=phase):
                self.assertEqual(reference.banks_for(phase, 'yui'), expected)
                self.assertEqual(reference.banks_for(phase, 'direct'), ())

    def test_catalog_is_optional_and_empty_selection_is_valid(self):
        model = Model(ROOT)
        for query in [{'bank':'basis'}, {'bank':'basis', 'ids':[]},
                      {'bank':'lean', 'ids':['ST026']}]:
            model.check('StrategyQuery@1', query, 'author')
        for ids in [['ST021']*2, ['ST001','ST002','ST003','ST004'], ['../rule.md']]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                model.check('StrategyQuery@1', {'bank':'basis','ids':ids}, 'author')
        result = {'bank':'lean', 'revision':'f'*64, 'status':'cards', 'cards':[], 'omitted':[]}
        model.check('StrategyReply@1', result, 'ignored guidance')
        for port in ('Foundation@2', 'Audited@2', 'Outcome@1'):
            with self.subTest(port=port), self.assertRaises(ValueError):
                model.check(port, result, 'guidance offered as proof')
        with self.assertRaises(ValueError):
            model.check('StrategyReply@1', {'accepted':True,'stage_complete':True}, 'receipt')

    def test_bound_returns_only_whole_cards_and_identifies_skips(self):
        cards = [{'id':'ST021', 'text':'大'*9500}, {'id':'ST022', 'text':'small'}]
        selected, omitted = reference.bounded_cards(cards)
        self.assertEqual(selected, cards[1:])
        self.assertEqual(omitted, ['ST021'])


if __name__ == '__main__':
    unittest.main()
