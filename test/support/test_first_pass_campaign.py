"""Cold input/freeze controls only; no model calls or invented mathematical verdicts."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import uuid

import first_pass_campaign as f


class FirstPassCampaignTests(unittest.TestCase):
    def setUp(self):
        self.index = int(uuid.uuid4().hex[:9], 16)
        self.out = f.ROOT/'test/results'/('first-pass-control-'+uuid.uuid4().hex)
        self.manifest = f.prepare(self.out, self.index)

    def tearDown(self):
        for row in self.manifest['cases']:
            for key in ['author', 'audit']:
                path = Path(row[key])
                self.assertEqual(path.parent, f.ROOT/'test/results')
                if path.exists(): shutil.rmtree(path)
        shutil.rmtree(self.out)

    def test_each_cold_author_has_only_its_own_identical_problem_and_no_audit_reuse(self):
        f.verify_frozen(self.manifest)
        for row in self.manifest['cases']:
            author = Path(row['author'])
            inputs = f.read(author/'inputs.json')['inputs']
            self.assertEqual([item['id'] for item in inputs], ['problem.md'])
            self.assertEqual((author/'problem.md').read_bytes(), Path(row['original_input']).read_bytes())
            job = f.read(self.out/'pending'/f'{row["id"]}.json')
            self.assertNotIn('reuse_audits', job)
            self.assertEqual(job['kind'], 'nl0')
            self.assertEqual(job['stop_after'], 'audit_a')
        row = self.manifest['cases'][0]
        path = Path(row['author'])/'inputs.json'
        value = f.read(path); value['inputs'].append({'id':'old-audit','path':'hidden','sha256':'0'*64})
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'only its own problem'):
            f.verify_frozen(self.manifest)

    def test_runtime_hash_mismatch_blocks_a_qualifying_round(self):
        modified = copy.deepcopy(self.manifest)
        key = next(iter(modified['runtime_source_hashes']))
        modified['runtime_source_hashes'][key] = '0'*64
        with self.assertRaisesRegex(ValueError, 'runtime changed'):
            f.verify_frozen(modified)

    def test_changed_model_or_owner_help_policy_blocks_the_frozen_round(self):
        modified = copy.deepcopy(self.manifest)
        modified['profile']['model'] = 'different-model'
        with self.assertRaisesRegex(ValueError, 'profile'):
            f.verify_frozen(modified)
        modified = copy.deepcopy(self.manifest)
        modified['owner_intervention_policy']['mathematical_help'] = True
        with self.assertRaisesRegex(ValueError, 'owner'):
            f.verify_frozen(modified)

    def test_staged_author_prompt_cannot_change_after_freeze(self):
        author = Path(self.manifest['cases'][0]['author'])
        path = author/'prompt.txt'
        path.write_text(path.read_text()+'\nUnapproved extra instruction.\n')
        with self.assertRaisesRegex(ValueError, 'prompt'):
            f.verify_frozen(self.manifest)

    def test_runtime_snapshot_preserves_exact_uncommitted_source_bytes(self):
        snapshot=Path(self.manifest['runtime_snapshot'])
        for relative,digest in self.manifest['runtime_source_hashes'].items():
            self.assertEqual(f.sha(snapshot/relative),digest)
        relative=next(iter(self.manifest['runtime_source_hashes']))
        (snapshot/relative).write_text('Synthetic archived-source tamper.')
        with self.assertRaisesRegex(ValueError,'snapshot changed'):f.verify_frozen(self.manifest)

    def test_calibration_stop_retains_unstarted_cases_without_rendering_missing_sources(self):
        report = f.collect(self.out, 'CALIBRATION_FAILED')
        self.assertFalse(report['goal_achieved'])
        self.assertTrue(all(row['status']['status'] == 'NOT_STARTED' for row in report['cases'].values()))

    def test_invalid_unfinished_source_view_cannot_abort_or_upgrade_round_collection(self):
        row=self.manifest['cases'][0];stage=Path(row['author'])/'stage';source=stage/'case';source.mkdir(parents=True)
        fixture=f.a.CORE/'tests/fixtures/closed-addition'
        graph=json.loads((fixture/'nl0.json').read_text());graph['inferences']=[]
        (source/'nl0.json').write_text(json.dumps(graph));shutil.copyfile(fixture/'spec.json',source/'spec.json')
        (stage/'result.json').write_text(json.dumps({'status':'UNFINISHED','usage':{'complete':False}}))
        report=f.collect(self.out,'ROUND_DID_NOT_PASS')
        self.assertEqual(len(report['cases']),3)
        self.assertFalse(report['goal_achieved'])
        self.assertFalse(report['cases'][row['id']]['first_audit_passed'])
        self.assertEqual(report['cases'][row['id']]['readable_view']['status'],'RENDER_FAILED')
        self.assertFalse(report['accounting']['usage_complete'])
        self.assertTrue((self.out/'round-result.json').exists())

    def test_neutral_control_pair_has_the_same_goal_without_expected_labels_in_packets(self):
        spec = importlib.util.spec_from_file_location('neutral_control_test', f.a.CORE/'scripts/prepare-review-cases.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        pair = [row for row in module.controls() if row[0]['case_id'] == 'neutral-local-algebra']
        self.assertEqual({row[1] for row in pair}, {'PASS', 'FAIL'})
        self.assertEqual(pair[0][0]['output'], pair[1][0]['output'])
        for packet, *_ in pair:
            self.assertEqual(packet['inputs'], [])
            self.assertNotIn('expected_verdict', json.dumps(packet))

    def test_analysis_permission_control_preserves_the_missing_premise_defect(self):
        spec=importlib.util.spec_from_file_location('analysis_control_test',f.a.CORE/'scripts/prepare-review-cases.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        row=next(row for row in module.controls() if row[0]['case_id']=='neutral-analysis-permission')
        packet,expected,_,location=row
        self.assertEqual(expected,'FAIL')
        self.assertEqual([p['id'] for p in packet['inputs']],['H001'])
        self.assertEqual(packet['inference']['applications'],[])
        self.assertIn('mean value theorem',packet['inference']['argument'][0]['text'])
        self.assertIn('author additionally permits',repr(packet['logic']))
        self.assertNotIn('expected_verdict',json.dumps(packet))
        self.assertEqual(location,'/inference/argument/0')

    def test_definition_controls_keep_same_predicate_without_importing_exercise_data(self):
        spec=importlib.util.spec_from_file_location('definition_control_test',f.a.CORE/'scripts/prepare-review-cases.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        pair=[row for row in module.controls() if row[0]['case_id']=='neutral-definition-unfolding']
        self.assertEqual({row[1] for row in pair},{'PASS','FAIL'})
        self.assertEqual(pair[0][0]['output'],pair[1][0]['output'])
        self.assertEqual(pair[0][0]['definitions'],pair[1][0]['definitions'])
        self.assertEqual([p['id'] for p in pair[0][0]['inputs']],['H001'])
        self.assertEqual(pair[1][0]['inputs'],[])
        for packet,*_ in pair:
            self.assertNotIn('expected_verdict',json.dumps(packet))
            self.assertNotIn('compact',json.dumps(packet))

    def test_parameter_condition_controls_differ_only_in_legitimate_H_availability(self):
        spec=importlib.util.spec_from_file_location('parameter_control_test',f.a.CORE/'scripts/prepare-review-cases.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        pair=[row for row in module.controls() if row[0]['case_id']=='neutral-parameter-hypothesis']
        self.assertEqual({row[1] for row in pair},{'PASS','FAIL'})
        self.assertEqual(pair[0][0]['output'],pair[1][0]['output'])
        self.assertEqual([p['id'] for p in pair[0][0]['inputs']],['H001'])
        self.assertEqual(pair[1][0]['inputs'],[])
        for packet,*_ in pair:self.assertNotIn('expected_verdict',json.dumps(packet))

    def test_control_location_keys_are_owner_only_and_resolve_in_actual_packets(self):
        spec=importlib.util.spec_from_file_location('owner_locator_test',f.a.CORE/'scripts/prepare-review-cases.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        directory=self.out/'neutral-locations';module.prepare(directory)
        key=f.read(directory/'owner/expected.json')
        for name,expected in key['expected'].items():
            packet=f.read(directory/'reviewer'/name)
            self.assertNotIn('expected_verdict',json.dumps(packet))
            self.assertNotIn('accepted_locations',json.dumps(packet))
            self.assertEqual(packet['packet_sha256'],expected['packet_sha256'])
            if expected['location'] is not None:
                self.assertIn(expected['location'],expected['accepted_locations'])
                for pointer in expected['accepted_locations']:module.nl0.closure.resolve(packet,pointer)


class FreshStartupTests(unittest.TestCase):
    def test_prepare_creates_the_missing_disposable_results_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for case in f.CASES.values():
                target=root/'test'/case/'problem.md';target.parent.mkdir(parents=True)
                shutil.copyfile(f.ROOT/'test'/case/'problem.md',target)
            out=root/'test/results/fresh-start'
            self.assertFalse(out.parent.exists())
            git=f.subprocess.CompletedProcess([],0,stdout='a'*40+'\n')
            with patch.object(f,'ROOT',root),patch.object(f,'runtime_hashes',return_value={}),patch.object(f.subprocess,'run',return_value=git):
                manifest=f.prepare(out,1)
            self.assertEqual(len(manifest['cases']),3)
            self.assertTrue((out/'round-manifest.json').is_file())
            self.assertTrue(all(Path(row['author']).is_dir() for row in manifest['cases']))


if __name__ == '__main__': unittest.main()
