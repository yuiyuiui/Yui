"""Stage-specific model isolation and carrier checks, without model requests."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import runtime_config
import run_pilot
from clean_stage import ArtifactStage


class ModelProfileTests(unittest.TestCase):
    def test_all_production_phases_select_the_declared_model(self):
        for phase in ['nl0-authoring', 'audit-a-global', 'audit-a-packet-replay', 'audit-a-behavior']:
            self.assertEqual(runtime_config.model_profile(phase)['id'], 'gpt-6.1-sol')
        for phase in ['proof', 'plan', 'interface', 'interface-authoring',
                      'interface-semantic-review', 'interface-dispute-review',
                      'audit-b-mapping', 'audit-b-semantic-review', 'translation-preparation',
                      'assembly', 'FROZEN_LEAN_PROOF_WORK']:
            p = runtime_config.model_profile(phase)
            self.assertEqual(p['id'], 'gpt-6.1-sol', phase)
            self.assertEqual((p['reasoning_effort'], p['speed'], p['automatic_fallback']),
                             ('high', 'standard', False))
            self.assertEqual(len(p['config_sha256']), 64)

    def test_invalid_translation_configuration_never_falls_back(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / 'config.json'
            original = json.loads((runtime_config.CORE / 'config.json').read_text())
            for field, value in [('reasoning_effort', 'medium'), ('speed', 'priority'),
                                 ('automatic_fallback', True), ('id', '')]:
                data = json.loads(json.dumps(original))
                data['phase_models']['nl0_to_lean'][field] = value
                file.write_text(json.dumps(data))
                with patch.object(runtime_config, 'CORE', Path(root)):
                    with self.assertRaises(ValueError): runtime_config.model_profile('proof')
            file.write_text(json.dumps({'model': original['model']}))
            with patch.object(runtime_config, 'CORE', Path(root)):
                with self.assertRaises(KeyError): runtime_config.model_profile('proof')

    def test_live_stage_models_are_instance_bound(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            author = ArtifactStage(root / 'author', 'EXPLICIT_TASK', phase='nl0-authoring', library=False)
            reviewer = ArtifactStage(root / 'reviewer', 'EXPLICIT_TASK', phase='audit-b-semantic-review', library=False)
            try:
                for stage, expected in [(author, 'gpt-6.1-sol'), (reviewer, 'gpt-6.1-sol')]:
                    stage.allowed_user_messages = {'EXPLICIT_TASK'}
                    stage.initial_user_message = 'EXPLICIT_TASK'
                    payload = {'model': expected, 'reasoning': {'effort': 'high'},
                        'input': [{'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'EXPLICIT_TASK'}]}]}
                    self.assertEqual(stage.normalize_request(payload)['model'], expected)
                    other = 'gpt-6-luna' if expected == 'gpt-6.1-sol' else 'gpt-6.1-sol'
                    with self.assertRaises(ValueError): stage.normalize_request({**payload, 'model': other})
                    run_pilot.validate_model_event({'response': {'model': expected}}, strict=True, expected_model=stage.model)
                    with self.assertRaises(PermissionError):
                        run_pilot.validate_model_event({'response': {'model': other}}, strict=True, expected_model=stage.model)
                    manifest = json.loads((stage.logs / 'execution-manifest.json').read_text())
                    self.assertEqual(manifest['model'], expected)
                    self.assertEqual(manifest['model_selection'], stage.model_selection)
                self.assertEqual(author.model, 'gpt-6.1-sol')
                self.assertEqual(reviewer.model, 'gpt-6.1-sol')
            finally:
                shutil.rmtree(author.work)
                shutil.rmtree(reviewer.work)


    def test_sol_native_carrier_config_is_isolated_without_a_model_call(self):
        import io
        import tomllib
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            stage = ArtifactStage(root / 'stage', 'EXPLICIT_TASK', phase='audit-b-mapping', library=False)
            proc = Mock(); proc.stdin = io.StringIO(); proc.stdout = []; proc.pid = 12345
            stage.execution = None
            stage.start_relay = Mock(return_value=12345)
            stage.rpc = Mock(return_value={})
            try:
                with patch.object(run_pilot, 'system_https_proxy', return_value=None), \
                        patch.object(run_pilot.subprocess, 'Popen', return_value=proc), \
                        patch('runtime_config.auth_home', return_value=root / 'empty-auth'), \
                        patch('run_resources.register_child'):
                    stage.start_process()
                config = tomllib.loads((stage.logs / 'effective-config.toml').read_text())
                self.assertEqual(config['model'], 'gpt-6.1-sol')
                self.assertEqual(config['model_reasoning_effort'], 'high')
                self.assertEqual(config['project_doc_max_bytes'], 0)
                self.assertFalse(config['features']['memories'])
                self.assertFalse(config['features']['shell_tool'])
                self.assertFalse(config['features']['multi_agent'])
            finally:
                shutil.rmtree(stage.work)


if __name__ == '__main__': unittest.main()
