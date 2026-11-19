"""Independent pre-freeze examples: a true proof is not a complete native source."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import harness_support
import basis
import basis_native
from controller_common import manifest
import ir
from basis_fixtures import artifact, dependency, checked_context


def direct():
    row=dependency(typ='∀ a b c : ℕ, a / b / c = a / c / b',
                   proof='intro a b c; exact Nat.div_right_comm a b c', compatibility='native')
    row['origin']['declaration']='Nat.div_right_comm'
    row['statement']='For all natural numbers a, b and c, a / b / c = a / c / b.'
    return row


class FrozenSources(unittest.TestCase):
    def contract(self, root):
        (root/'inputs').mkdir(parents=True)
        (root/'inputs/problem.md').write_text('Source coverage software test.')
        manifest(root/'inputs')
        return basis.BasisContract(root,artifact()['full_target'])

    def test_whole_native_theorem_is_checked_and_handed_off_before_review(self):
        import basis_sources
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);contract=self.contract(root);value=artifact(direct())
            contract(value)
            frozen=basis_sources.material(value,ir.load(contract.last_receipt['path'])['native'])
            self.assertEqual(frozen['B001']['mode'],'native')
            self.assertEqual(frozen['B001']['source']['declaration'],'Nat.div_right_comm')
            self.assertTrue(frozen['B001']['source']['module'].startswith('Mathlib.'))

    def test_compiled_conjunction_cannot_cite_only_its_first_native_clause(self):
        row=direct()
        row['lean']={'type':'(∀ a b c : ℕ, a / b / c = a / c / b) ∧ True',
                     'proof':'exact ⟨Nat.div_right_comm, True.intro⟩'}
        row['statement']+=' Also True holds.'
        with tempfile.TemporaryDirectory() as raw:
            contract=self.contract(Path(raw))
            with self.assertRaisesRegex(ValueError,'(?i)(signature|whole|source)'):
                contract(artifact(row))
            self.assertIsNone(contract.selected)
            compiler=ir.load(Path(raw)/'candidates/0001/native/compiler.json')
            self.assertEqual(compiler['exit_code'],0)  # The proof is true; the source claim is false.

    def test_bundle_as_a_prepared_derivation_has_its_own_downstream_reference(self):
        import basis_sources
        base=direct();base['port']=None
        derived=dependency('B002',3,typ='(∀ a b c : ℕ, a / b / c = a / c / b) ∧ True')
        derived['lean']['proof']='exact ⟨YuiBasis.B001, True.intro⟩'
        derived['statement']='The division identity holds, and True holds.'
        value=artifact(base,derived)
        with tempfile.TemporaryDirectory() as raw:
            contract=self.contract(Path(raw));contract(value)
            handoff=basis_sources.material(value,ir.load(contract.last_receipt['path'])['native'])
            self.assertEqual(handoff['B002']['mode'],'prepared')
            self.assertEqual(handoff['B002']['declaration'],'YuiBasis.B002')
            self.assertNotIn('source',handoff['B002'])

    def test_metadata_only_correction_reuses_verified_native_check(self):
        with tempfile.TemporaryDirectory() as raw:
            contract=self.contract(Path(raw));value=artifact(direct())
            with patch.object(basis_native,'check',wraps=basis_native.check) as compiler:
                contract(value)
                changed=deepcopy(value);changed['dependencies'][0]['justification']+=' Clarified attribution.'
                contract(changed)
                self.assertEqual(compiler.call_count,1)
                changed['dependencies'][0]['lean']['proof']='intro a b c\nexact Nat.div_right_comm a b c'
                contract(changed)
                self.assertEqual(compiler.call_count,2)

    def test_selector_is_required_data_and_not_extracted_from_reference_prose(self):
        for selector in (None,'','Nat.div_right_comm\n#eval 7'):
            row=direct();row['origin']['declaration']=selector
            with self.subTest(selector=selector),self.assertRaises(ValueError):
                basis.validate(artifact(row),artifact()['full_target'])

    def test_global_native_root_cannot_bypass_the_pre_freeze_inventory(self):
        value=artifact()
        value['global_graph']['propositions'].append({'id':'M001','statement':'A library fact.'})
        value['global_graph']['inferences'][-1]['inputs'].append('M001')
        with self.assertRaisesRegex(ValueError,'Native proposition has no basis authority'):
            basis.validate(value,value['full_target'])

    def test_direct_polymorphic_source_is_prepared_without_a_model_worker(self):
        from types import SimpleNamespace
        import basis_planning
        row=dependency(compatibility='native',
            typ='∀ {A : Sort v} {B : Sort w} [Subsingleton A] (f : A → B), Function.Injective f')
        row['port']=None;row['origin']['declaration']='Function.injective_of_subsingleton';row['lean']['proof']=None
        value=artifact(row);value['lean_header']='import Mathlib\nuniverse v w\n'
        with tempfile.TemporaryDirectory() as raw:
            contract=self.contract(Path(raw));stage=SimpleNamespace(validator=contract,logs=Path(raw)/'stage')
            contract.owner_stage=stage;contract.save(value)
            with patch.object(basis_planning,'deliver',side_effect=AssertionError('No model for an exact native fact')):
                result=basis_planning.prepare(stage,{'candidate':1})
            self.assertFalse(result['proof_workers_started'])
            checked=deepcopy(contract.drafts[result['candidate']]);contract(checked)
            self.assertTrue(ir.load(ir.load(contract.last_receipt['path'])['native']['path'])['passed'])

    def test_non_theorem_or_missing_source_never_reaches_freeze(self):
        for selector in ('Nat.div','Nat.this_theorem_does_not_exist'):
            row=direct();row['origin']['declaration']=selector
            with self.subTest(selector=selector),tempfile.TemporaryDirectory() as raw:
                contract=self.contract(Path(raw))
                with self.assertRaises(ValueError):contract(artifact(row))
                self.assertIsNone(contract.selected)


class SourceHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch=tempfile.TemporaryDirectory();cls.root=Path(cls.scratch.name)
        row=direct()
        cls.location={'document':'inputs/basis-proof.md','locator':'Lemma 2.1'}
        row['usage']={'references':[cls.location]}
        cls.value=artifact(row)
        cls.value['proof']='Lemma 2.1. '+cls.value['proof']
        cls.context=checked_context(cls.root/'2basis/0001',cls.value)

    @classmethod
    def tearDownClass(cls):cls.scratch.cleanup()

    def author(self, name, *, change=None, rename=False):
        import frozen_graph
        directory=self.root/name
        documents={'proof-context.json':self.context,'basis-registry.json':self.value}
        import json
        docs={key:json.dumps(value,ensure_ascii=False,indent=2)+'\n' for key,value in documents.items()}
        docs['basis-proof.md']=self.value['proof']
        contract=frozen_graph.AuthorContract(directory,docs,'closed-addition-format-example',frozen_graph.BASIS)
        original=ir.load(harness_support.FIXTURES/'closed-addition/nl0.json')
        details={p['id']:{k:v for k,v in p.items() if k not in ('id','statement')} for p in original['propositions']}
        details['M001']={'kind':'mathlib','definitions':[],'binders':[],'objects':[]}
        if change:details['M001']['source']=change
        payload={'spec':ir.load(harness_support.FIXTURES/'closed-addition/spec.json'),
                 'proposition_details':details,'inference_definitions':{r['id']:r['definitions'] for r in original['inferences']},
                 'proof_outline':harness_support.elementary_outline(original['inferences'])}
        payload['proof_outline']['R002']['steps'][0]['uses'].append('B001')
        if rename:payload['rename_foundations']={'B001':'M014'}
        contract(payload)
        return directory,payload

    def test_actual_global_reader_inherits_source_without_another_probe_or_compilation(self):
        import artifact_validation
        with patch.object(artifact_validation,'signature_probe',side_effect=AssertionError('No rediscovery')), \
             patch.object(basis_native,'check',side_effect=AssertionError('No repeat compilation')):
            directory,payload=self.author('inherited')
        prop=next(p for p in payload['graph']['propositions'] if p['id']=='M001')
        self.assertEqual(prop['source']['declaration'],'Nat.div_right_comm')
        self.assertEqual(prop['usage'],{'inferences':['R002'],'references':[self.location]})
        report=ir.load(directory/prop['source']['evidence'][0]['path'])
        self.assertEqual(report['inheritance']['basis_id'],'B001')
        self.assertNotIn('result',report)  # Reused evidence is not reported as fresh execution.
        basis.check_graph_sources(self.context,self.value,payload['graph'])

    def test_renumbering_preserves_source_and_later_source_override_is_rejected(self):
        _,payload=self.author('renumbered',rename=True)
        prop=next(p for p in payload['graph']['propositions'] if p['id']=='M014')
        self.assertEqual(prop['source']['declaration'],'Nat.div_right_comm')
        self.assertEqual(prop['usage'],{'inferences':['R002'],'references':[self.location]})
        with self.assertRaisesRegex(ValueError,'changed frozen source'):
            self.author('override',change={'declaration':'Nat.succ_injective'})

    def test_review_packet_covers_classification_and_exact_handoff_and_corruption_fails(self):
        import basis_review
        import basis_sources
        packet=ir.load(self.root/'2basis/0001/review/inputs'/basis_review.PACKET)
        self.assertEqual(packet['items']['B001']['handoff']['source']['declaration'],'Nat.div_right_comm')
        native=Path(self.context['native']['path']);before=native.read_bytes()
        try:
            raw=ir.load(native);raw['native_sources']['B001']['declaration']='Nat.succ_injective'
            native.write_text(__import__('json').dumps(raw))
            with self.assertRaises(ValueError):basis_sources.material(self.value,self.context['native'])
        finally:native.write_bytes(before)


if __name__=='__main__':unittest.main()
