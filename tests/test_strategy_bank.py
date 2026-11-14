"""General advice retrieval and maintenance boundaries, without proof templates."""
import harness_support
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import strategy_bank as bank


class StrategyBankTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='strategy-bank-')
        self.root=Path(self.temp.name)
        (self.root/'evidence.md').write_text('Synthetic general advice fixture; no successful proof is claimed.\n')
        self.cards=[self.card('ST900','representation',['conversion'],['relation_preserved'],['lossy_map']),
                    self.card('ST901','representation',['quotient'],['invariance_proved']),
                    self.card('ST902','execution',['transport','environment'])]
        self.build()

    def tearDown(self):
        self.temp.cleanup()

    def card(self,sid,family,tags,preconditions=None,contraindications=None):
        return dict(id=sid,revision=1,title='Generic implementation procedure',family=family,
            domains=['general'],tags=tags,obstacle='An explicit local implementation obstacle.',
            preconditions=preconditions or [],contraindications=contraindications or [],
            procedure=['Check the required conditions before applying the operation.'],
            verification='Compile the exact local application and inspect its signature.',
            positive_example='Apply an operation with all its required conditions proved.',
            negative_example='Apply it with a missing condition.',reference_environments=[
                {'lean_version':'0.0.1','mathlib_commit':'a'*40,'basis':'historical_configuration'}],
            status='GENERAL_GUIDANCE',evidence=[dict(kind='design_rule',path='evidence.md',
                sha256=bank.sha(self.root/'evidence.md'),note='Synthetic editorial guidance only.')])

    def build(self):
        (self.root/'strategies.json').write_text(json.dumps(self.cards))
        return bank.build(self.root)

    def query(self,**kw):
        return bank.search(dict(family='representation',tags=['conversion'],facts=[],
                                lean_version='0.0.1',**kw),self.root)

    def test_matching_advice_is_bounded_and_never_verifies_prerequisites(self):
        result=self.query()
        card=result['strategies'][0]
        self.assertEqual(card['id'],'ST900')
        self.assertEqual(card['missing_preconditions'],['relation_preserved'])
        self.assertEqual(card['applicability'],'CONDITIONAL')
        reported=bank.search(dict(family='representation',tags=['conversion'],
            facts=['relation_preserved'],lean_version='0.0.1'),self.root)['strategies'][0]
        self.assertEqual(reported['applicability'],'PRECONDITIONS_REPORTED')
        self.assertFalse(reported['preconditions_independently_verified'])
        self.assertLess(result['counts']['metadata_scored'],result['counts']['bank_size'])
        self.assertLessEqual(result['counts']['full_cards_read'],3)
        self.assertEqual(set(card['card']['evidence'][0]),{'kind','note'})

    def test_reported_contraindication_excludes_recommendation(self):
        q=dict(family='representation',tags=['conversion'],facts=[],
               lean_version='0.0.1',contraindications=['lossy_map'])
        self.assertEqual(bank.search(q,self.root)['status'],'NO_APPLICABLE_CANDIDATE')

    def test_query_version_does_not_exclude_reference_candidates(self):
        for version in ('0.0.1','0.0.2','0.0.3',None):
            with self.subTest(version=version):
                q=dict(family='representation',tags=['conversion'],facts=[],lean_version=version)
                self.assertEqual(bank.search(q,self.root)['strategies'][0]['id'],'ST900')

    def test_unknown_or_unmatched_diagnosis_abstains(self):
        for family,tags in [('unknown',[]),('representation',['absent_tag'])]:
            result=bank.search(dict(family=family,tags=tags,lean_version='0.0.1'),self.root)
            self.assertEqual(result['status'],'ABSTAIN')
            self.assertEqual(result['counts']['full_cards_read'],0)

    def test_scoring_and_card_reads_remain_bounded_for_large_bank(self):
        self.cards=[self.card(f'ST{i:03d}','representation',['conversion']) for i in range(100,180)]
        self.build()
        result=self.query()
        self.assertTrue(result['counts']['truncated'])
        self.assertEqual(result['counts']['metadata_scored'],bank.MAX_SCORED)
        self.assertEqual(result['counts']['full_cards_read'],3)

    def test_stale_source_card_and_evidence_cannot_be_retrieved(self):
        for path in [self.root/'strategies.json',self.root/'cards/ST900.json',self.root/'evidence.md']:
            original=path.read_bytes()
            path.write_bytes(original+b' ')
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'stale/modified|stale '):
                self.query()
            path.write_bytes(original)

    def test_build_rejects_specific_domains_identifiers_and_proof_payloads(self):
        base=deepcopy(self.cards)
        for change,pattern in [({'domains':['pde']},'broad domain'),
                               ({'title':'Reuse the solution at N055'},'proof-node'),
                               ({'evidence':[dict(base[0]['evidence'][0],excerpt='Old proof')]},'sanitized')]:
            self.cards=deepcopy(base);self.cards[0].update(change)
            before=(self.root/'cards/ST900.json').read_bytes()
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,pattern):self.build()
            self.assertEqual((self.root/'cards/ST900.json').read_bytes(),before)

    def test_evidence_cannot_escape_the_bank(self):
        self.cards[0]['evidence'][0]['path']='../outside.md'
        with self.assertRaisesRegex(ValueError,'inside the bank'):self.build()

    def test_duplicate_ids_rejected_and_deleted_cards_do_not_linger(self):
        self.cards.append(deepcopy(self.cards[0]))
        with self.assertRaisesRegex(ValueError,'duplicate strategy'):self.build()
        self.cards=self.cards[:1];self.build()
        self.assertEqual({p.stem for p in (self.root/'cards').glob('*.json')},{'ST900'})

    def test_notation_does_not_automatically_choose_a_mathematical_strategy(self):
        for text in ['‖f‖ₑ = ‖g‖ₑ; ENNReal', 'Continuous f; f =ᵐ[volume] g',
                     'Fourier normalization 2π', 'MemLp f; AEStronglyMeasurable f']:
            self.assertEqual(bank.diagnose(dict(goal=text,diagnostic='type mismatch'))['family'],'unknown')

    def test_grounding_binds_version_without_overriding_explicit_diagnosis(self):
        q,receipt=bank.grounded_query(dict(family='representation',tags=['quotient'],
            facts=['invariance_proved'],lean_version='guessed'), 'f = g', 'local hypotheses','0.0.1')
        self.assertEqual(q['lean_version'],'0.0.1')
        self.assertEqual(q['tags'],['quotient'])
        self.assertEqual(bank.search(q,self.root)['strategies'][0]['id'],'ST901')
        self.assertEqual(receipt['precondition_verification'],'not performed by routing')

    def test_explicit_execution_fault_is_separate_from_mathematics(self):
        q=bank.diagnose(dict(transport_fault=True,diagnostic='type mismatch',lean_version='0.0.1'))
        self.assertEqual(q['family'],'execution')
        self.assertEqual(bank.search(q,self.root)['strategies'][0]['id'],'ST902')

    def test_native_timeout_advice_is_conditional_and_excludes_controller_faults(self):
        query=dict(family='execution',tags=['native_timeout'],lean_version='0.0.1',facts=[])
        candidate=bank.search(query)['strategies'][0]
        self.assertEqual(candidate['id'],'ST020')
        self.assertEqual(candidate['applicability'],'CONDITIONAL')
        self.assertIn('native_resource_failure_recorded',candidate['missing_preconditions'])
        qualified=dict(query,facts=candidate['card']['preconditions'])
        self.assertEqual(bank.search(qualified)['strategies'][0]['applicability'],
                         'PRECONDITIONS_REPORTED')
        excluded=dict(qualified,contraindications=['provider_or_controller_fault'])
        self.assertEqual(bank.search(excluded)['status'],'NO_APPLICABLE_CANDIDATE')
        # A stored card does not silently activate diagnostic routing.
        observation=bank.diagnose(dict(diagnostic='LEAN_TIMEOUT',lean_version='0.0.1'))
        self.assertEqual(bank.search(observation)['status'],'ABSTAIN')

    def test_repository_bank_is_current_general_guidance_with_no_orphan_cards(self):
        cards=json.loads((bank.BANK/'strategies.json').read_text())
        index=json.loads((bank.BANK/'index.json').read_text())
        self.assertEqual(index['source_sha256'],bank.sha(bank.BANK/'strategies.json'))
        ids={card['id'] for card in cards}
        self.assertEqual(set(index['metadata']),ids)
        self.assertEqual({p.stem for p in (bank.BANK/'cards').glob('*.json')},ids)
        for card in cards:
            bank.validate_card(card,bank.BANK)
            self.assertEqual(card['status'],'GENERAL_GUIDANCE')
            self.assertEqual(index['metadata'][card['id']]['sha256'],bank.sha(bank.BANK/'cards'/f'{card["id"]}.json'))


if __name__=='__main__':unittest.main()
