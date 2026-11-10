"""Use the real author tools and immutable reference data without a model service."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import harness_support as support
import basis
import basis_author
import clean_stage
import controller_common
import model_pilot
import strategy_bank as bank
import translation_author
from basis_fixtures import TARGET
from lean_fixtures import norm_plan


class AuthorReference(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def stage(self, cls, phase, **kwargs):
        stage = cls(self.root/phase, 'Use the supplied target.', phase=phase, **kwargs)
        self.addCleanup(shutil.rmtree, stage.work, True)
        return stage

    def test_catalog_then_conditional_advice_before_foundation_draft(self):
        intake = basis.BasisContract(self.root, TARGET)
        stage = self.stage(basis_author.BasisStage, 'basis-authoring', validator=intake)
        self.assertFalse(intake.drafts)
        title = 'Choose a cost-preserving level of abstraction'
        self.assertNotIn(title, stage.input_prompt + stage.system)
        self.assertFalse((stage.logs/'tools.jsonl').exists() and 'consult_strategy' in (stage.logs/'tools.jsonl').read_text())
        catalog = stage.dispatch('consult_strategy', {'bank':'basis'})
        self.assertEqual(catalog['status'], 'catalog')
        self.assertTrue({f'ST0{i}' for i in range(21,26)} <= {c['id'] for c in catalog['catalog']})
        self.assertTrue(all(set(c)=={'id','title','revision','obstacle','family'} for c in catalog['catalog']))
        # Selection is by ID; the author need not spell English tags or diagnose a failure.
        request = {'bank':'basis','ids':['ST021']}
        read = stage.dispatch('consult_strategy', request)
        self.assertEqual(stage.dispatch('consult_strategy', request), read)
        card, = read['cards']
        self.assertEqual(card['title'], title)
        self.assertIn('resource_target_explicit', card['preconditions'])
        self.assertIn('bit cost', card['negative_example'])
        self.assertNotIn('path', card['evidence'][0])
        self.assertFalse(intake.drafts)
        self.assertIsNone(stage.accepted)
        self.assertEqual(stage.api_calls, 0)
        self.assertEqual(stage.dispatch('consult_strategy', {'bank':'basis','ids':[]})['cards'], [])
        self.assertEqual(stage.dispatch('consult_strategy', {'bank':'lean'})['status'], 'invalid_query')

    def test_role_handoff_and_blinded_review(self):
        stage = self.stage(translation_author.InterfaceStage, 'translation-source-preparation')
        self.assertNotIn('consult_strategy', stage.tool_names)
        self.assertIn('consult_strategy', {t['name'] for t in stage.native_tools})
        self.assertIn('error', stage.dispatch('consult_strategy', {'bank':'basis'}))
        author = self.stage(translation_author.InterfaceStage, 'interface-authoring')
        self.assertEqual(author.dispatch('consult_strategy', {'bank':'basis','ids':['ST022']})['status'], 'cards')
        reviewer = self.stage(clean_stage.ArtifactStage, 'interface-semantic-review')
        self.assertNotIn('consult_strategy', reviewer.tool_names)
        self.assertIn('error', reviewer.dispatch('consult_strategy', {'bank':'lean'}))

    def test_frozen_standalone_inputs_and_read_corruption(self):
        live = self.root/'editable'
        shutil.copytree(bank.BASIS_BANK, live)
        with patch.object(bank, 'BASIS_BANK', live):
            stage = self.stage(basis_author.BasisStage, 'basis-authoring',
                               validator=basis.BasisContract(self.root, TARGET))
        args = {'bank':'basis','ids':['ST023']}
        before = stage.dispatch('consult_strategy', args)
        self.assertEqual(before['status'], 'cards')
        (live/'strategies.json').write_text('[]')
        self.assertEqual(stage.dispatch('consult_strategy', args), before)
        with patch.object(bank, 'BASIS_BANK', live):
            resumed = bank.reference_bindings(('basis',), stage.logs/'strategy-reference')
        self.assertEqual(resumed, stage.strategy_banks)
        frozen = Path(stage.strategy_banks['basis']['path'])
        for relative in ('evidence/resource-models.md','cards/ST023.json','index.json','strategies.json'):
            with self.subTest(relative=relative):
                path = frozen/relative
                original = path.read_bytes()
                path.write_bytes(original+b' ')
                self.assertEqual(stage.dispatch('consult_strategy', args)['status'], 'unavailable')
                path.write_bytes(original)
                self.assertEqual(stage.dispatch('consult_strategy', args), before)
        unknown = stage.dispatch('consult_strategy', {'bank':'basis','ids':['ST023','ST999']})
        self.assertEqual((unknown['status'], unknown['ids']), ('not_in_catalog', ['ST999']))
        with patch.object(stage, 'native_timeout_lean_version', '0.0'):
            self.assertEqual(stage.dispatch('consult_strategy', {'bank':'basis'})['catalog'], [])
            self.assertEqual(stage.dispatch('consult_strategy', args)['status'], 'not_in_catalog')

        (frozen/'cards/ST023.json').unlink()
        (frozen/'cards/ST023.json').symlink_to(live/'cards/ST023.json')
        self.assertEqual(stage.dispatch('consult_strategy', args)['status'], 'unavailable')

    def test_later_case_stages_use_the_run_manifest_not_changes_to_the_bank(self):
        core = self.root/'runtime'
        frozen = core/'nl0/basis-bank'
        shutil.copytree(bank.BASIS_BANK, frozen)
        manifest = self.root/'runtime-manifest.json'
        rows = [{'relative_path':str(path.relative_to(core)), 'sha256':bank.sha(path)}
                for path in (frozen/'strategies.json', frozen/'index.json')]
        manifest.write_text(json.dumps({'runtime_root':str(core), 'files':rows}))
        (self.root/'job.json').write_text(json.dumps({'runtime_snapshot':{'manifest':{'sha256':bank.sha(manifest)}}}))
        with patch.object(bank, 'HERE', core/'nl02lean'), patch.object(bank, 'BASIS_BANK', frozen):
            first = bank.reference_bindings(('basis',), self.root/'unused')
            bank.bound_bank_data(first['basis'])
            (frozen/'strategies.json').write_text('[]')
            bank.build(frozen)
            later = bank.reference_bindings(('basis',), self.root/'unused')
            self.assertEqual(first, later)
            with self.assertRaisesRegex(ValueError, 'changed'):
                bank.bound_bank_data(later['basis'])
        self.assertFalse((self.root/'unused').exists())

    def test_snapshot_includes_every_card_and_all_evidence(self):
        bound = {Path(r['path']):r['sha256'] for r in controller_common.runtime_bindings()}
        ids = set()
        for root in (bank.BASIS_BANK, bank.BANK):
            cards = json.loads((root/'strategies.json').read_text())
            index = json.loads((root/'index.json').read_text())
            self.assertTrue(ids.isdisjoint(index['metadata']))
            self.assertEqual(set(index['metadata']), {c['id'] for c in cards})
            ids.update(index['metadata'])
            for row in cards:
                bank.validate_card(row, root)
                for relative in ('strategies.json','index.json',f"cards/{row['id']}.json",
                                 *(e['path'] for e in row['evidence'])):
                    path = root/relative
                    self.assertEqual(bound[path], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertTrue({'ST012','ST015','ST020',*(f'ST0{i}' for i in range(21,27))} <= ids)

    def test_invalid_reference_does_not_displace_the_compiler_diagnostic(self):
        contract = support.FIXTURES/'lean/examples/case1_norm_sup/contract.json'
        stage = model_pilot.Stage(self.root/'proof', contract, 'proof', None,
                                  norm_plan(contract), 'T001')
        self.addCleanup(shutil.rmtree, stage.work, True)
        stage.last_diagnostic = 'prior Lean diagnostic'
        reply = stage.dispatch('consult_strategy', {'bank':'lean', 'ids':['../irrelevant']})
        self.assertEqual(reply['status'], 'invalid_query')
        self.assertEqual(stage.last_diagnostic, 'prior Lean diagnostic')
        self.assertIsNone(stage.accepted)

    def test_direct_proof_cannot_dispatch_either_lookup_by_name(self):
        directory = support.FIXTURES/'lean/examples/case1_norm_sup'
        contract = directory/'contract.json'
        stage = model_pilot.Stage(self.root/'direct', contract, 'proof', None,
                                  norm_plan(contract), 'T001', instruction_arm='direct')
        self.addCleanup(shutil.rmtree, stage.work, True)
        for name, args in [('consult_strategy', {'bank':'lean'}),
                           ('find_strategies', {'query_json':'{"family":"interface"}'})]:
            self.assertNotIn(name, stage.tool_names)
            with self.assertRaises(PermissionError):
                stage.dispatch(name, args)
        self.assertIsNone(stage.accepted)


if __name__ == '__main__':
    unittest.main()
