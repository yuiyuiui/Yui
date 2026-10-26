"""Neutral reviewer-control fixtures; no mathematical model calls."""
import harness_support
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
CORE=Path(__file__).resolve().parents[1]
import audit_a_campaign
f=SimpleNamespace(a=audit_a_campaign,read=lambda p:json.loads(Path(p).read_text()))

class FirstPassCampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name)/'controls'
    def tearDown(self):self.temp.cleanup()

    def test_neutral_control_pair_has_the_same_goal_without_expected_labels_in_packets(self):
        spec = importlib.util.spec_from_file_location('neutral_control_test', f.a.CORE/'nl0/scripts/prepare-review-cases.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        pair = [row for row in module.controls() if row[0]['case_id'] == 'neutral-local-algebra']
        self.assertEqual({row[1] for row in pair}, {'PASS', 'FAIL'})
        self.assertEqual(pair[0][0]['output'], pair[1][0]['output'])
        for packet, *_ in pair:
            self.assertEqual(packet['inputs'], [])
            self.assertNotIn('expected_verdict', json.dumps(packet))

    def test_analysis_permission_control_preserves_the_missing_premise_defect(self):
        spec=importlib.util.spec_from_file_location('analysis_control_test',f.a.CORE/'nl0/scripts/prepare-review-cases.py')
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
        spec=importlib.util.spec_from_file_location('definition_control_test',f.a.CORE/'nl0/scripts/prepare-review-cases.py')
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
        spec=importlib.util.spec_from_file_location('parameter_control_test',f.a.CORE/'nl0/scripts/prepare-review-cases.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        pair=[row for row in module.controls() if row[0]['case_id']=='neutral-parameter-hypothesis']
        self.assertEqual({row[1] for row in pair},{'PASS','FAIL'})
        self.assertEqual(pair[0][0]['output'],pair[1][0]['output'])
        self.assertEqual([p['id'] for p in pair[0][0]['inputs']],['H001'])
        self.assertEqual(pair[1][0]['inputs'],[])
        for packet,*_ in pair:self.assertNotIn('expected_verdict',json.dumps(packet))

    def test_control_location_keys_are_owner_only_and_resolve_in_actual_packets(self):
        spec=importlib.util.spec_from_file_location('owner_locator_test',f.a.CORE/'nl0/scripts/prepare-review-cases.py')
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


if __name__=='__main__':unittest.main()
