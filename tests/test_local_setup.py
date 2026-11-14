"""Local adaptation publication and frozen-context controls without live services."""
import harness_support
from copy import deepcopy
from contextlib import ExitStack
import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import jobs
import local_config
import local_setup
import runtime_config
import runtime_snapshot
import setup_checks
from controller_common import write
from local_setup_fixtures import configuration


def arguments(**overrides):
    p=argparse.ArgumentParser();local_setup.parsers(p.add_subparsers(dest='command'))
    value=p.parse_args(['setup','--mode','nl0'])
    for key,item in overrides.items():setattr(value,key,item)
    return value


class LocalSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()/'renamed installation with spaces';self.root.mkdir()
        (self.root/'config.json').write_bytes((harness_support.CORE/'config.json').read_bytes())
        (self.root/'SKILL.md').write_text('---\nname: rigorous-proof\ndescription: Synthetic registration fixture.\n---\n')
        for name in ('nl0/scripts/local_setup.py','nl0/scripts/setup_checks.py','nl0/scripts/local_config.py',
                     'nl0/scripts/runtime_config.py','nl0/scripts/lean_environment.py','nl0/scripts/native_runtime.py',
                     'nl0/scripts/pilot_common.py','nl02lean/scripts/audit_probe.lean','nl02lean/scripts/basis_export.lean'):
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((harness_support.CORE/name).read_bytes())
        self.value=configuration(self.root)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(local_config,'CORE',self.root))
        self.stack.enter_context(patch.object(local_setup,'CORE',self.root))
        self.stack.enter_context(local_config.use(None))
        self.args=arguments(skill_root=self.root/'registered skill')

    def checks(self):
        self.stack.enter_context(patch.object(local_setup,'host_check',side_effect=lambda out:
            (deepcopy(self.value['host']),setup_checks.record(out,'host',{'fixture':'software control'}))))
        return self.stack.enter_context(patch.object(setup_checks,'provider',side_effect=lambda out,profiles:
            setup_checks.record(out,'provider',{'fixture':'software control, no model request'})))

    def test_success_publishes_one_validated_config_and_repeat_setup_reuses_registration(self):
        provider=self.checks()
        for _ in range(2):
            result=local_setup.run(self.args)
            self.assertEqual(result['status'],'READY',result)
            local_config.verify(json.loads(local_config.path().read_text()))
        self.assertEqual(provider.call_count,2)
        self.assertTrue(self.args.skill_root.is_symlink())
        self.assertEqual(self.args.skill_root.resolve(),self.root)

    def test_failed_switch_keeps_previous_configuration_bytes(self):
        self.checks();self.assertEqual(local_setup.run(self.args)['status'],'READY')
        before=local_config.path().read_bytes()
        with patch.object(setup_checks,'provider',side_effect=ValueError('Synthetic service failure')):
            result=local_setup.run(self.args)
        self.assertEqual(result['status'],'FAILED')
        self.assertFalse(result['configuration_published'])
        self.assertEqual(local_config.path().read_bytes(),before)

    def test_atomic_configuration_write_failure_keeps_previous_default(self):
        self.checks();self.assertEqual(local_setup.run(self.args)['status'],'READY')
        before=local_config.path().read_bytes();original=local_setup.write
        def denied(path,value):
            if Path(path)==local_config.path():raise PermissionError('Synthetic configuration write denial')
            return original(path,value)
        with patch.object(local_setup,'write',side_effect=denied):
            report=local_setup.run(self.args)
        self.assertEqual(report['status'],'FAILED')
        self.assertEqual(local_config.path().read_bytes(),before)

    def test_saved_default_is_read_without_shell_exports_and_detects_changed_code(self):
        self.value['profiles']=deepcopy(self.value['profiles'])
        self.value['profiles']['nl0']['reasoning_effort']='max'
        local_config.path().parent.mkdir()
        write(local_config.path(),self.value)
        with patch.dict(__import__('os').environ,{},clear=False):
            for name in ('YUI_FROZEN_LOCAL_CONFIG','YUI_CODEX_BINARY','YUI_RG_BINARY','YUI_CODEX_HOME'):
                __import__('os').environ.pop(name,None)
            token=local_config._selected.set(local_config._UNSET)
            try:
                self.assertEqual(runtime_config.model_profile('nl0-authoring')['reasoning_effort'],'max')
                self.assertEqual(runtime_config.host_tools()['codex'],self.value['host']['codex'])
                local_config.verify(local_config.current())
                (self.root/'program.py').write_text('Changed after qualification')
                with self.assertRaisesRegex(ValueError,'changed'):local_config.verify(local_config.current())
            finally:local_config._selected.reset(token)

    def test_missing_authentication_is_actionable_without_publishing(self):
        with patch.object(local_setup,'host_check',side_effect=local_config.rules.SetupRequired(
                'Log in first',[{'kind':'login'}])):
            result=local_setup.run(self.args)
        self.assertEqual(result['status'],'NEEDS_USER_ACTION')
        self.assertFalse(local_config.path().exists())

    def test_public_entry_uses_previously_selected_profiles_without_asking_again(self):
        import entrypoint
        parser=argparse.ArgumentParser();entrypoint.parsers(parser.add_subparsers(dest='command'))
        args=parser.parse_args(['prepare','/explicit/proof.md','--track','full'])
        self.value['profiles']['lean']['reasoning_effort']='max'
        with local_config.use(self.value):
            self.assertEqual(entrypoint.profiles(args),self.value['profiles'])

    def test_conflicting_skill_is_preserved(self):
        self.checks();self.args.skill_root.mkdir();file=self.args.skill_root/'user.txt';file.write_text('Keep this')
        result=local_setup.run(self.args)
        self.assertEqual(result['status'],'NEEDS_USER_ACTION')
        self.assertEqual(file.read_text(),'Keep this')
        self.assertFalse(local_config.path().exists())

    def test_lean_setup_cannot_pass_when_a_core_consumer_check_is_omitted(self):
        self.checks();self.args.mode='lean'
        with patch.object(local_setup,'select_environment',return_value={'fixture':'not a real environment'}), \
             patch.object(setup_checks,'native',return_value={}), \
             patch.object(runtime_config,'use_environment',return_value=__import__('contextlib').nullcontext()):
            # The actual coordinator imports use_environment at module scope.
            with patch.object(local_setup,'use_environment',return_value=__import__('contextlib').nullcontext()):
                result=local_setup.run(self.args)
        self.assertEqual(result['status'],'FAILED')
        self.assertFalse(local_config.path().exists())

    def test_frozen_job_ignores_later_default_and_original_setup_evidence_removal(self):
        problem=self.root.parent/'proof.md';problem.write_text('Given P, conclude P.')
        with local_config.use(self.value):
            job=jobs.prepare(problem,track='nl0',profiles=harness_support.PROFILES)
        self.assertEqual(job['local_configuration']['version'],local_config.rules.RUN_VERSION)
        other=configuration(self.root.parent/'other configuration')
        with local_config.use(other):
            with jobs.scientific_context(job):
                self.assertEqual(runtime_config.host_tools()['codex'],self.value['host']['codex'])
                self.assertEqual(runtime_config.auth_home(),Path(self.value['host']['auth_home']))
                self.assertIsNone(runtime_config.selected_environment())
            jobs.validate(job)
        child=runtime_snapshot.environment(job)
        self.assertEqual(json.loads(child['YUI_FROZEN_LOCAL_CONFIG']),job['local_configuration'])
        for row in self.value['checks'].values():
            for evidence in row['evidence']:Path(evidence['path']).unlink()
        jobs.validate(job)

    def test_frozen_run_context_cannot_gain_unreviewed_fields(self):
        value=local_config.for_job(self.value,harness_support.PROFILES,None)
        local_config.rules.validate_runtime(value)
        value['auth_token']='never copied'
        with self.assertRaises(ValueError):local_config.rules.validate_runtime(value)

    def test_new_job_freezes_the_actual_explicit_host_choice(self):
        other=configuration(self.root.parent/'explicit host choice')['host']
        tools={'codex':other['codex'],'tools':{'ripgrep':{'binary_path':other['ripgrep']['path'],
               'sha256':other['ripgrep']['sha256']},'python':{'binary_path':other['python']}}}
        problem=self.root.parent/'explicit.md';problem.write_text('Given P, conclude P.')
        with local_config.use(self.value),patch.object(runtime_config,'host_tools',return_value=tools), \
                patch.object(runtime_config,'auth_home',return_value=Path(other['auth_home'])):
            job=jobs.prepare(problem,track='nl0',profiles=harness_support.PROFILES)
        self.assertEqual(job['local_configuration']['host'],other)
        self.assertEqual(job['native_components'],other['codex'])
        jobs.validate(job)

    def test_installation_configuration_path_cannot_be_a_symlink(self):
        storage=self.root/'.runtime';storage.mkdir()
        elsewhere=self.root/'other.json';write(elsewhere,self.value)
        local_config.path().symlink_to(elsewhere)
        with patch.dict(__import__('os').environ,{},clear=False):
            # Escape the intentional test-local scope to exercise the disk reader.
            token=local_config._selected.set(local_config._UNSET)
            try:
                with patch.dict(__import__('os').environ,{'YUI_FROZEN_LOCAL_CONFIG':''}):
                    __import__('os').environ.pop('YUI_FROZEN_LOCAL_CONFIG')
                    with self.assertRaises(local_config.rules.SetupRequired):local_config.current()
            finally:local_config._selected.reset(token)





class ProviderMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.secret = 'synthetic-secret-that-must-never-be-logged'
        (self.root/'auth.json').write_text(json.dumps({'tokens': {
            'access_token': self.secret, 'account_id': 'synthetic-account'}}))
        self.profiles={role:{'id':'fixture-model','reasoning_effort':'high','speed':'standard'} for role in ('nl0','lean')}
        self.model = {'slug': 'fixture-model', 'supported_reasoning_levels': [{'effort': 'high'}]}
        self.connection = Mock(); self.response = Mock(status=200)
        self.response.getheader.side_effect = lambda k: {'Content-Type': 'application/json',
                                                       'x-request-id': 'synthetic-request'}.get(k)
        self.response.read.return_value = json.dumps({'models': [self.model]}).encode()
        self.connection.getresponse.return_value = self.response
        self.stack = ExitStack(); self.addCleanup(self.stack.close); self.addCleanup(self.temp.cleanup)
        self.stack.enter_context(patch.object(setup_checks, 'auth_home', return_value=self.root))
        self.stack.enter_context(patch.object(setup_checks, 'host_tools', return_value={'codex': {'version': 'codex-cli 0.1.0'}}))
        self.proxy = self.stack.enter_context(patch('run_pilot.system_https_proxy', return_value=None))
        self.factory = self.stack.enter_context(patch.object(setup_checks.http.client, 'HTTPSConnection', return_value=self.connection))


    def test_authenticated_metadata_get_preserves_profiles_and_redacts_credentials(self):
        receipt = setup_checks.provider_metadata(self.profiles)
        self.assertEqual(receipt['verified_profiles'], self.profiles)
        self.assertEqual(receipt['inference_calls'], 0)
        self.assertNotIn(self.secret, json.dumps(receipt))
        self.assertNotIn('synthetic-account', json.dumps(receipt))
        self.connection.request.assert_called_once()
        args, kwargs = self.connection.request.call_args
        self.assertEqual(args[:2], ('GET', '/backend-api/codex/models?client_version=0.1.0'))
        self.assertNotIn('body', kwargs)
        self.response.read.assert_called_once_with(setup_checks.METADATA_MAX_BYTES+1)
        self.connection.close.assert_called_once()

    def test_same_system_proxy_and_tls_tunnel_as_the_carrier(self):
        self.proxy.return_value = ('synthetic-proxy', 7890)
        setup_checks.provider_metadata(self.profiles)
        self.factory.assert_called_once_with('synthetic-proxy', 7890, timeout=25)
        self.connection.set_tunnel.assert_called_once_with('chatgpt.com', 443)

    def test_denial_redirect_and_service_failure_never_infer_or_follow_redirects(self):
        for status in [301, 302, 400, 401, 403, 429, 503]:
            with self.subTest(status=status):
                self.response.status = status; self.connection.request.reset_mock(); self.response.read.reset_mock()
                with self.assertRaisesRegex(ValueError, 'metadata HTTP '+str(status)):
                    setup_checks.provider_metadata(self.profiles)
                self.connection.request.assert_called_once(); self.response.read.assert_not_called()

    def test_html_malformed_oversized_and_wrong_model_catalogs_are_rejected(self):
        cases = [b'invalid json', b'[]', b'{"models":[]}',
                 json.dumps({'models': [{**self.model, 'slug': 'another-model'}]}).encode(),
                 json.dumps({'models': [{**self.model, 'supported_reasoning_levels': [{'effort': 'low'}]}]}).encode(),
                 json.dumps({'models': [self.model, self.model]}).encode(), b'x'*(setup_checks.METADATA_MAX_BYTES+1)]
        for body in cases:
            with self.subTest(bytes=len(body)):
                self.response.read.return_value = body
                with self.assertRaises(ValueError): setup_checks.provider_metadata(self.profiles)
        self.response.getheader.side_effect = lambda k: 'text/html' if k == 'Content-Type' else None
        with self.assertRaisesRegex(ValueError, 'model JSON'): setup_checks.provider_metadata(self.profiles)

    def test_network_failure_does_not_leak_tokens_and_closes_the_connection(self):
        self.connection.getresponse.side_effect = OSError(self.secret)
        with self.assertRaisesRegex(ValueError, 'OSError') as caught: setup_checks.provider_metadata(self.profiles)
        self.assertNotIn(self.secret, str(caught.exception)); self.connection.close.assert_called_once()

    def test_provider_uses_the_installation_metadata_check_before_a_model_probe(self):
        with patch.object(setup_checks,'provider_metadata',side_effect=ValueError('metadata unavailable')) as metadata, \
                patch('clean_stage.ArtifactStage',side_effect=AssertionError('No model probe before metadata')):
            with self.assertRaisesRegex(ValueError,'metadata unavailable'):
                setup_checks.provider(self.root,self.profiles)
        metadata.assert_called_once_with(self.profiles)

    def test_malformed_credentials_are_rejected_before_network_access(self):
        (self.root/'auth.json').write_text(json.dumps({'tokens':{'access_token':'invalid\nsecret','account_id':'test'}}))
        with self.assertRaisesRegex(ValueError,'Malformed subscription') as error:
            setup_checks.provider_metadata(self.profiles)
        self.assertNotIn('secret',str(error.exception));self.factory.assert_not_called()


if __name__=='__main__':unittest.main()
