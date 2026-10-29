"""Instruction delivery and snapshot controls; no model or Lean execution."""
import harness_support
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE = harness_support.LEAN
import ir
import model_pilot
from lean_fixtures import norm_plan


class LeanWritingGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yui-writing-control-')
        self.root = Path(self.temp.name)
        self.stages = []
        for name in ('source.json', 'contract.json'):
            shutil.copyfile(harness_support.FIXTURES/'lean/examples/case1_norm_sup'/name,
                            self.root/name)
        self.cp = self.root/'contract.json'
        self.plan = norm_plan(self.cp)
        self.rules = self.root/'rules.md'
        self.rules.write_text('INITIAL_RULE_SENTINEL\n', encoding='utf-8')

    def tearDown(self):
        for stage in self.stages:
            shutil.rmtree(stage.work, ignore_errors=True)
        self.temp.cleanup()

    def stage(self, *, mode='proof', arm='yui'):
        with patch.object(model_pilot, 'LEAN_WRITING_PATH', self.rules):
            stage = model_pilot.Stage(self.root/f'run-{len(self.stages)}',
                                      self.cp, mode, None, plan=self.plan,
                                      step='T001', instruction_arm=arm)
        self.stages.append(stage)
        return stage

    def test_only_yui_proof_workers_receive_rules(self):
        proof = self.stage()
        self.assertEqual(proof.lean_writing_rules, self.rules.read_text())
        self.assertIn(proof.lean_writing_rules, proof.system)
        for mode, arm in [('proof', 'direct'), ('plan', 'yui'),
                          ('interface', 'yui'), ('audit-b', 'yui')]:
            stage = self.stage(mode=mode, arm=arm)
            self.assertIsNone(stage.lean_writing_rules)
            self.assertNotIn('INITIAL_RULE_SENTINEL', stage.system)

    def test_guidance_preserves_math_packet_and_common_checking_contract(self):
        proof = self.stage()
        direct = self.stage(arm='direct')
        packet = ir.local_packet(self.cp, self.plan, 'T001')
        self.assertEqual(json.loads(proof.prompt())['packet'], packet)
        self.assertEqual(json.loads(direct.prompt())['packet'], packet)
        self.assertEqual([t for t in proof.tools if t['name']!='report_proof_obstruction'], direct.tools)
        self.assertNotIn('report_proof_obstruction',direct.tool_names)
        self.assertIsNone(proof.timeout)
        self.assertIsNone(proof.accepted)
        self.assertEqual((proof.api_calls, proof.lean_calls), (0, 0))

    def test_snapshot_keeps_the_rules_loaded_by_this_stage(self):
        proof = self.stage()
        original = proof.lean_writing_rules
        original_system = proof.system
        self.rules.write_text('FUTURE_RULE_SENTINEL\n', encoding='utf-8')
        future = self.stage()
        self.assertIn('FUTURE_RULE_SENTINEL', future.system)
        self.assertEqual(proof.system, original_system)

        # Stop at the process boundary after writing the actual input snapshot.
        # Neither the provider carrier nor a native compiler may start.
        with patch.object(proof, 'start_process',
                          side_effect=RuntimeError('OFFLINE_PROCESS_BOUNDARY')) as start, \
                patch.object(ir, 'check', side_effect=AssertionError('No Lean call')):
            proof._execute()
        start.assert_called_once_with()
        saved = proof.logs/'harness-snapshot/nl02lean/references/lean-writing.md'
        self.assertEqual(saved.read_text(encoding='utf-8'), original)
        manifest = json.loads((proof.logs/'execution-manifest.json').read_text())
        rows = [r for r in manifest['runtime_files']
                if r['path'] == 'nl02lean/references/lean-writing.md']
        self.assertEqual(rows, [{'path':'nl02lean/references/lean-writing.md',
                                 'sha256':hashlib.sha256(saved.read_bytes()).hexdigest()}])
        self.assertEqual((proof.logs/'system.txt').read_text(), original_system+'\n')
        self.assertEqual((proof.api_calls, proof.lean_calls), (0, 0))


if __name__ == '__main__':
    unittest.main()
