"""Target selection is source-bound and precedes author/model dispatch."""
import harness_support
from harness_support import PROFILES
import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import target_selection as targets
import entrypoint
import jobs
from artifact_validation import NL0Contract


class TargetSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.paper=self.root/'paper.md'
        self.paper.write_text('Theorem 1. For a natural number n, n=n.\nProof. Reflexivity.\n')
    def tearDown(self):self.temp.cleanup()

    def test_unique_candidate_needs_caller_readback_not_an_extra_human_question(self):
        value=targets.resolve(self.paper)
        self.assertEqual(value['status'],'TARGET_REVIEW_REQUIRED')
        self.assertFalse(value['needs_user_input'])
        self.assertEqual(value['candidates'][0]['label'],'Theorem 1')

    def test_in_text_reference_is_not_a_target_and_attached_title_is_recognized(self):
        self.paper.write_text('Theorem 4.3 gives the cited bound.\nTheorem 1(Main result). Let n be a natural number. Then n=n.\nProof. Reflexivity.\n')
        value=targets.inspect(self.paper)
        self.assertEqual([c['label'] for c in value['candidates']],['Theorem 1'])

    def test_multiple_independent_targets_request_selection_without_starting_a_job(self):
        self.paper.write_text(self.paper.read_text()+'Theorem 2. For n, n+0=n.\nProof. Arithmetic.\n')
        p=argparse.ArgumentParser();entrypoint.parsers(p.add_subparsers(dest='command'))
        args=p.parse_args(['run',str(self.paper),'--track','full','--use-config-profiles','--max-concurrency','2'])
        with patch.object(jobs,'prepare') as prepare,patch.object(entrypoint,'launch') as launch:
            value=entrypoint.dispatch(args)
        self.assertEqual(value['status'],'TARGET_SELECTION_REQUIRED')
        prepare.assert_not_called();launch.assert_not_called()

    def test_explicit_statement_and_multi_target_binding_cannot_silently_change(self):
        value=targets.resolve(self.paper,requested='For every natural n, n=n.')
        self.assertEqual(value['status'],'SELECTED')
        multi=targets.select(self.paper,[dict(id=str(i),label='Chosen '+str(i),statement=s,start_line=i)
            for i,s in enumerate(['For n, n=n.','For n, n+0=n.'],1)])
        self.assertIn('\nAND\n',multi['full_target'])
        multi['full_target']='Only the easy part.'
        with self.assertRaisesRegex(ValueError,'differs'):targets.validate(multi)
        self.paper.write_text('Changed paper')
        with self.assertRaisesRegex(ValueError,'changed'):targets.validate(value)

    def test_named_selection_does_not_guess_missing_standing_hypotheses(self):
        value=targets.resolve(self.paper,requested='Theorem 1')
        self.assertEqual(value['selected_labels'],['Theorem 1'])
        self.assertFalse(value['needs_user_input'])
        self.assertNotEqual(value['status'],'SELECTED')

    def test_selected_target_is_staged_and_rechecked_before_authoring(self):
        value=targets.resolve(self.paper,requested='For every natural n, n=n.')
        job=jobs.prepare(self.paper,track='nl0',profiles=PROFILES,max_concurrency=2,target=value)
        jobs.validate(job)
        self.assertEqual(json.loads((Path(job['root'])/'inputs/target-selection.json').read_text()),value)
        fixture=harness_support.CORE/'tests/fixtures/closed-addition'
        artifact={key:json.loads((fixture/name).read_text()) for key,name in [('spec','spec.json'),('graph','nl0.json')]}
        contract=NL0Contract(self.root/'author',{'paper.md':self.paper.read_text(),'target-selection.json':json.dumps(value)})
        with self.assertRaisesRegex(ValueError,'TARGET_SELECTION'):contract(artifact)


if __name__=='__main__':unittest.main()
