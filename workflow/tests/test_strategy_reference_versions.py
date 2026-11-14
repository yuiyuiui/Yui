"""Independent disclosure and authority expectations for cross-version references."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from blocks import strategy_reference as reference
from wfcore.model import Model


ENVIRONMENT = {'lean_version': '4.32.2', 'mathlib_commit': 'a'*40,
               'basis': 'historical_configuration'}


def card():
    return {'id': 'ST900', 'revision': 1, 'title': 'Check the proposed conversion',
            'family': 'representation', 'obstacle': 'Two representations need a bridge.',
            'domains': ['general'], 'tags': ['conversion'], 'preconditions': ['a bridge is proved'],
            'contraindications': [], 'procedure': ['Prove the required relation is preserved.'],
            'verification': 'Check the local use in the selected environment.',
            'positive_example': 'Preserve equality through a function.',
            'negative_example': 'Infer injectivity without justification.',
            'reference_environments': [deepcopy(ENVIRONMENT)], 'status': 'GENERAL_GUIDANCE',
            'evidence': [{'kind': 'design_rule', 'note': 'Synthetic reference, not a checked proof.'}]}


def reply(kind):
    value = {'bank': 'lean', 'revision': 'f'*64, 'status': kind,
             'reference_only': True, 'current_environment_verification_required': True,
             'usage_notice': 'Adapt and check this reference in the current environment.'}
    if kind == 'catalog':
        value['catalog'] = [{key: card()[key] for key in
                            ('id', 'revision', 'title', 'family', 'obstacle', 'reference_environments')}]
    else:
        value.update(cards=[card()], omitted=[])
    return value


class PairedReference(unittest.TestCase):
    def setUp(self):
        self.model = Model(ROOT)

    def test_catalog_origin_exposes_the_paired_historical_environment(self):
        value = reply('catalog')
        self.model.check('StrategyReply@2', value, 'catalog reference')
        self.assertEqual(value['catalog'][0]['reference_environments'], [ENVIRONMENT])
        del value['catalog'][0]['reference_environments']
        with self.assertRaises(ValueError):
            self.model.check('StrategyReply@2', value, 'undisclosed source environment')

    def test_full_card_origin_exposes_the_paired_historical_environment(self):
        value = reply('cards')
        self.model.check('StrategyReply@2', value, 'complete reference')
        self.assertEqual(value['cards'][0]['reference_environments'], [ENVIRONMENT])
        del value['cards'][0]['reference_environments']
        with self.assertRaises(ValueError):
            self.model.check('StrategyReply@2', value, 'undisclosed source environment')

    def test_missing_or_malformed_source_pairs_are_rejected_in_both_views(self):
        bad = [[], [{k: v for k, v in ENVIRONMENT.items() if k != 'mathlib_commit'}],
               [dict(ENVIRONMENT, lean_version='')], [dict(ENVIRONMENT, mathlib_commit='guessed')],
               [dict(ENVIRONMENT, basis='native_verified')], [ENVIRONMENT, ENVIRONMENT]]
        for environments in bad:
            with self.subTest(environments=environments), self.assertRaises(ValueError):
                reference.validate_environments(environments)
            for kind in ('catalog', 'cards'):
                value = reply(kind);value[kind][0]['reference_environments'] = environments
                with self.subTest(kind=kind, environments=environments), self.assertRaises(ValueError):
                    self.model.check('StrategyReply@2', value, 'invalid source pair')

    def test_multiple_recorded_pairs_remain_provenance(self):
        environments = [ENVIRONMENT, dict(ENVIRONMENT, lean_version='4.35.0', mathlib_commit='b'*40)]
        reference.validate_environments(environments)
        for kind in ('catalog', 'cards'):
            value = reply(kind);value[kind][0]['reference_environments'] = environments
            self.model.check('StrategyReply@2', value, 'multiple reference contexts')

    def test_reference_and_current_check_requirements_cannot_be_removed_or_disabled(self):
        for kind in ('catalog', 'cards'):
            for key in ('reference_only', 'current_environment_verification_required'):
                for replacement in (None, False):
                    value = reply(kind)
                    if replacement is None:del value[key]
                    else:value[key] = replacement
                    with self.subTest(kind=kind, key=key, replacement=replacement), self.assertRaises(ValueError):
                        self.model.check('StrategyReply@2', value, 'reference authority weakened')

    def test_reading_a_reference_cannot_supply_a_proof_handoff(self):
        value = reply('cards')
        for port in ('Foundation@2', 'Audited@2', 'Outcome@1'):
            with self.subTest(port=port), self.assertRaises(ValueError):
                self.model.check(port, value, 'reference offered as proof')

    def test_historical_reply_contract_remains_separate_from_current_disclosure(self):
        legacy = reply('cards')
        for key in ('reference_only', 'current_environment_verification_required', 'usage_notice'):
            del legacy[key]
        del legacy['cards'][0]['reference_environments']
        legacy['cards'][0]['lean_versions'] = ['4.32.2']
        self.model.check('StrategyReply@1', legacy, 'historical reply')
        with self.assertRaises(ValueError):
            self.model.check('StrategyReply@2', legacy, 'historical data is not a current reply')

    def test_unknown_id_errors_do_not_claim_to_deliver_a_reference(self):
        value = {'bank': 'lean', 'revision': 'f'*64, 'status': 'not_in_catalog', 'ids': ['ST999']}
        self.model.check('StrategyReply@2', value, 'unknown reference')
        value.update(reference_only=True, current_environment_verification_required=True,
                     usage_notice='No card was delivered.')
        with self.assertRaises(ValueError):
            self.model.check('StrategyReply@2', value, 'error mixed with reference delivery')


if __name__ == '__main__':
    unittest.main()
