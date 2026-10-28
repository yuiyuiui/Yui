"""Note-presentation/isolation controls with synthetic payloads; no model or math audit."""
import harness_support
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = harness_support.LEAN
import ir
import model_pilot
import background
from lean_fixtures import norm_plan


class LocalBackgroundGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yui-note-access-control-')
        self.root = Path(self.temp.name)
        self.stages = []
        for name in ('source.json', 'contract.json'):
            shutil.copyfile(harness_support.FIXTURES/'lean/examples/case1_norm_sup'/name, self.root/name)
        self.cp = self.root/'contract.json'
        self.notes = {
            'R001': [self.note('FIRST', 'mathlib')],
            'R002': [self.note('SECOND', 'elementary')],
        }
        c = ir.load(self.cp)
        payload = {'policy':background.POLICY, 'graph_sha256':'TEST_ONLY_GRAPH',
                   'spec_sha256':'TEST_ONLY_SPEC', 'notes':copy.deepcopy(self.notes)}
        self.supplement = {**payload, 'sha256':background.digest(payload)}
        c['source'].update(background_supplement=self.supplement,
                           background_supplement_sha256=self.supplement['sha256'])
        ir.write(self.cp, c)
        self.plan = norm_plan(self.cp)
        for i, step in enumerate(self.plan['steps'], 1):
            step['background_notes'] = [f'R{i:03d}.BG001']

    def tearDown(self):
        for stage in self.stages:
            shutil.rmtree(stage.work, ignore_errors=True)
        self.temp.cleanup()

    @staticmethod
    def note(label, kind):
        value = {'id':'BG001', 'at':'/inference/argument/0/text', 'kind':kind,
                 'fact':label+'_TEST_ONLY_FACT',
                 'grounds':[{'location':'/inputs/0/statement', 'reason':label+'_GROUND'}],
                 'justification':label+'_FULL_DETAIL_SENTINEL'}
        if kind == 'mathlib':
            value['source'] = {'declaration':'TEST_ONLY.interface',
                               'signature':'FIRST_SIGNATURE_SENTINEL'}
        return value

    def stage(self, step='T001', *, arm='yui', mode='proof'):
        stage = model_pilot.Stage(self.root/f'run-{len(self.stages)}', self.cp,
                                  mode, 120, plan=self.plan, step=step,
                                  instruction_arm=arm)
        self.stages.append(stage)
        return stage

    def test_compact_prompt_preserves_inputs_and_canonical_packet(self):
        original = ir.local_packet(self.cp, self.plan, 'T001')
        stage = self.stage()
        text = stage.prompt()
        packet = json.loads(text)['packet']
        self.assertEqual(packet['inputs'], original['inputs'])
        self.assertEqual(packet['source_steps'], original['source_steps'])
        self.assertEqual(packet['background_supplement_sha256'], self.supplement['sha256'])
        self.assertEqual([n['id'] for n in packet['background_note_index']], ['R001.BG001'])
        self.assertEqual(packet['background_note_index'][0]['declaration'], 'TEST_ONLY.interface')
        self.assertNotIn('accepted_background_notes', packet)
        for hidden in ('FIRST_FULL_DETAIL_SENTINEL', 'FIRST_SIGNATURE_SENTINEL',
                       'SECOND_TEST_ONLY_FACT', 'SECOND_FULL_DETAIL_SENTINEL'):
            self.assertNotIn(hidden, text)
        self.assertEqual(ir.local_packet(self.cp, self.plan, 'T001'), original)

    def test_exact_readback_is_logged_without_model_or_lean_calls(self):
        stage = self.stage()
        value = stage.dispatch('read_background_note', {'id':'R001.BG001'})
        self.assertEqual(value['note'], self.notes['R001'][0])
        self.assertEqual(value['background_supplement_sha256'], self.supplement['sha256'])
        self.assertIsNone(stage.accepted)
        self.assertEqual((stage.api_calls, stage.lean_calls), (0, 0))
        trace = json.loads((stage.logs/'tools.jsonl').read_text())
        self.assertEqual(trace['tool'], 'read_background_note')
        self.assertEqual(trace['result'], value)

    def test_other_task_unknown_unqualified_and_path_ids_are_rejected(self):
        stage = self.stage()
        for key in ('R002.BG001', 'R001.BG999', 'BG001', '../../contract.json'):
            value = stage.dispatch('read_background_note', {'id':key})
            self.assertFalse(value['accepted'])
            self.assertNotIn('note', value)
        self.assertIsNone(stage.accepted)

    def test_sibling_with_same_local_id_can_only_read_its_qualified_note(self):
        stage = self.stage('T002')
        packet = json.loads(stage.prompt())['packet']
        self.assertEqual([n['id'] for n in packet['background_note_index']], ['R002.BG001'])
        self.assertEqual(stage.dispatch('read_background_note', {'id':'R002.BG001'})['note'],
                         self.notes['R002'][0])
        self.assertFalse(stage.dispatch('read_background_note', {'id':'R001.BG001'})['accepted'])

    def test_tampered_supplement_cannot_be_read_back(self):
        stage = self.stage()
        c = ir.load(self.cp)
        c['source']['background_supplement']['notes']['R001'][0]['justification'] = 'CHANGED'
        ir.write(self.cp, c)
        value = stage.dispatch('read_background_note', {'id':'R001.BG001'})
        self.assertFalse(value['accepted'])
        self.assertIn('changed background supplement', value['error'])
        self.assertNotIn('note', value)

    def test_direct_arm_keeps_existing_packet_and_has_no_note_tool(self):
        stage = self.stage(arm='direct')
        self.assertIsNone(stage.background_note_policy)
        self.assertNotIn('read_background_note', stage.tool_names)
        self.assertEqual(json.loads(stage.prompt())['packet'],
                         ir.local_packet(self.cp, self.plan, 'T001'))
        self.assertFalse(stage.dispatch('read_background_note', {'id':'R001.BG001'})['accepted'])

    def test_no_note_worker_keeps_existing_packet_and_tools(self):
        c = ir.load(self.cp)
        del c['source']['background_supplement']
        del c['source']['background_supplement_sha256']
        ir.write(self.cp, c)
        self.plan = norm_plan(self.cp)
        stage = self.stage()
        self.assertIsNone(stage.background_note_policy)
        self.assertNotIn('read_background_note', stage.tool_names)
        self.assertEqual(json.loads(stage.prompt())['packet'],
                         ir.local_packet(self.cp, self.plan, 'T001'))

    def test_planner_retains_full_source_authority(self):
        stage = self.stage(mode='plan')
        self.assertIsNone(stage.background_note_policy)
        self.assertNotIn('read_background_note', stage.tool_names)
        self.assertEqual(json.loads(stage.prompt())['contract']['background_supplement'],
                         self.supplement)


if __name__ == '__main__':
    unittest.main()
