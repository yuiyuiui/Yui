"""Explicit access recovery controls; synthetic metadata, no model/Lean calls."""
import harness_support
import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

import access_recovery as access
import entrypoint
import interrupted
import jobs
import owner_observation
import remote_retry

PROFILES = {p: {'id': 'gpt-6.1-sol', 'reasoning_effort': 'high', 'speed': 'standard',
                'automatic_fallback': False} for p in ['nl0', 'lean']}
DENIAL = {'message': 'Synthetic provider denial; not a mathematical judgment.',
          'codexErrorInfo': {'httpConnectionFailed': {'httpStatusCode': 403}}}


def restored():
    return {'at_utc': datetime.now(timezone.utc).isoformat(), 'method': 'GET',
            'host': 'chatgpt.com', 'path': '/backend-api/codex/models?client_version=0.1.0',
            'http_status': 200, 'catalog_sha256': 'a'*64, 'verified_profiles': PROFILES,
            'inference_calls': 0, 'credential_values_logged': False}


class ProviderMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.secret = 'synthetic-secret-that-must-never-be-logged'
        (self.root/'auth.json').write_text(json.dumps({'tokens': {
            'access_token': self.secret, 'account_id': 'synthetic-account'}}))
        self.model = {'slug': 'gpt-6.1-sol', 'supported_reasoning_levels': [{'effort': 'high'}]}
        self.connection = Mock(); self.response = Mock(status=200)
        self.response.getheader.side_effect = lambda k: {'Content-Type': 'application/json',
                                                       'x-request-id': 'synthetic-request'}.get(k)
        self.response.read.return_value = json.dumps({'models': [self.model]}).encode()
        self.connection.getresponse.return_value = self.response
        self.stack = ExitStack(); self.addCleanup(self.stack.close); self.addCleanup(self.temp.cleanup)
        self.stack.enter_context(patch.object(access, 'auth_home', return_value=self.root))
        self.stack.enter_context(patch.object(access, 'load_lock', return_value={'codex': {'version': 'codex-cli 0.1.0'}}))
        self.proxy = self.stack.enter_context(patch('run_pilot.system_https_proxy', return_value=None))
        self.factory = self.stack.enter_context(patch.object(access.http.client, 'HTTPSConnection', return_value=self.connection))

    def test_structured_denial_is_explicit_only_not_an_automatic_retry(self):
        self.assertTrue(access.denied(DENIAL)); self.assertIsNone(remote_retry.classify(DENIAL))
        for error in [dict(DENIAL, code='insufficient_quota'), dict(DENIAL, type='authentication_error'),
                      dict(DENIAL, reason='proof_invalid'), {'message': '403 Forbidden'},
                      {'codexErrorInfo': {'httpConnectionFailed': {'httpStatusCode': 403.0}}},
                      {'codexErrorInfo': {'httpConnectionFailed': {'httpStatusCode': 401}}}]:
            with self.subTest(error=error): self.assertFalse(access.denied(error))

    def test_authenticated_metadata_get_preserves_profiles_and_redacts_credentials(self):
        receipt = access.check(PROFILES)
        self.assertEqual(receipt['verified_profiles'], PROFILES)
        self.assertEqual(receipt['inference_calls'], 0)
        self.assertNotIn(self.secret, json.dumps(receipt))
        self.assertNotIn('synthetic-account', json.dumps(receipt))
        self.connection.request.assert_called_once()
        args, kwargs = self.connection.request.call_args
        self.assertEqual(args[:2], ('GET', '/backend-api/codex/models?client_version=0.1.0'))
        self.assertNotIn('body', kwargs)
        self.response.read.assert_called_once_with(access.MAX_BYTES+1)
        self.connection.close.assert_called_once()

    def test_same_system_proxy_and_tls_tunnel_as_the_carrier(self):
        self.proxy.return_value = ('synthetic-proxy', 7890)
        access.check(PROFILES)
        self.factory.assert_called_once_with('synthetic-proxy', 7890, timeout=25)
        self.connection.set_tunnel.assert_called_once_with('chatgpt.com', 443)

    def test_denial_redirect_and_service_failure_never_infer_or_follow_redirects(self):
        for status in [301, 302, 400, 401, 403, 429, 503]:
            with self.subTest(status=status):
                self.response.status = status; self.connection.request.reset_mock(); self.response.read.reset_mock()
                with self.assertRaisesRegex(ValueError, 'metadata HTTP '+str(status)):
                    access.check(PROFILES)
                self.connection.request.assert_called_once(); self.response.read.assert_not_called()

    def test_html_malformed_oversized_and_wrong_model_catalogs_are_rejected(self):
        cases = [b'invalid json', b'[]', b'{"models":[]}',
                 json.dumps({'models': [{**self.model, 'slug': 'another-model'}]}).encode(),
                 json.dumps({'models': [{**self.model, 'supported_reasoning_levels': [{'effort': 'low'}]}]}).encode(),
                 json.dumps({'models': [self.model, self.model]}).encode(), b'x'*(access.MAX_BYTES+1)]
        for body in cases:
            with self.subTest(bytes=len(body)):
                self.response.read.return_value = body
                with self.assertRaises(ValueError): access.check(PROFILES)
        self.response.getheader.side_effect = lambda k: 'text/html' if k == 'Content-Type' else None
        with self.assertRaisesRegex(ValueError, 'model JSON'): access.check(PROFILES)

    def test_network_failure_does_not_leak_tokens_and_closes_the_connection(self):
        self.connection.getresponse.side_effect = OSError(self.secret)
        with self.assertRaisesRegex(ValueError, 'OSError') as caught: access.check(PROFILES)
        self.assertNotIn(self.secret, str(caught.exception)); self.connection.close.assert_called_once()


class ManualResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)
        self.problem = self.root/'proof/problem.md'; self.problem.parent.mkdir()
        self.problem.write_text('SYNTHETIC access recovery fixture; not proof evidence.\n')
        self.old = jobs.prepare(self.problem, track='full', profiles=PROFILES, max_concurrency=7,
                                output=self.root/'results/old')
        self.run = Path(self.old['root']); self.stage = self.run/'nl0/0001/stage'
        self.failure = {'status': 'UNFINISHED', 'execution_health': 'FAULT', 'isolation_violation': False,
            'identity_and_input_boundary_verified': True, 'execution_fault': 'SYNTHETIC HTTP403',
            'transport_health': {'status': 'FAULT', 'faults': [
                {'kind': 'HTTP_ERROR', 'request_number': 2, 'status': 403}], 'uncertainty': []}}
        self.stage_records(self.stage)
        self.write(self.run/'case-result.json', {'result': {'status': 'EXECUTION_FAULT',
            'evidence': str(self.stage/'result.json'), 'elapsed_case_seconds': 10,
            'usage': {'status': 'PARTIAL', 'confirmed_tokens': {'total_tokens': 17}},
            'completion': {'acceptance_target_satisfied': False}}})
        self.write(self.run/'execution-status.json', {'phase': 'NL0_AUTHORING', 'controller': {
            'pid': 2147483647, 'pgid': 2147483647, 'started': 'Synthetic exited process', 'state': 'FINALIZED'},
            'processes': {}})
        self.probe = patch.object(access, 'check', return_value=restored()).start()
        self.addCleanup(patch.stopall)

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value)+'\n')

    def stage_records(self, stage):
        self.write(stage/'result.json', self.failure)
        self.write(stage/'events.jsonl', {'method': 'turn/completed', 'params': {'turn': {
            'id': 'synthetic-denied-turn', 'status': 'failed', 'error': DENIAL}}})
        self.write(stage/'http.jsonl', {'path': '/responses', 'status': 403, 'request_number': 2})

    def test_plain_resume_still_rejects_access_denial_without_probe(self):
        with self.assertRaisesRegex(ValueError, 'not a positively identified'):
            interrupted.prepare(self.run)
        self.probe.assert_not_called()

    def test_manual_preparation_preserves_lineage_inputs_profiles_workers_costs_and_output_root(self):
        old = {p: p.read_bytes() for p in [self.run/'job.json', self.stage/'result.json', self.stage/'events.jsonl']}
        job = interrupted.prepare(self.run, after_access_restored=True)
        root = Path(job['root']); self.assertEqual(root.parent, self.run.parent)
        self.assertEqual(job['profiles'], PROFILES); self.assertEqual(job['max_concurrency'], 7)
        self.assertEqual(job['documents'][0]['sha256'], self.old['documents'][0]['sha256'])
        self.assertEqual(job['resume']['mode'], 'author'); self.assertIsNone(job['time_budget_seconds'])
        self.assertFalse((root/'resumed-source').exists())
        meta = json.loads((root/'resumption.json').read_text())
        self.assertEqual(meta['access_recovery']['old_partial_usage']['confirmed_tokens']['total_tokens'], 17)
        self.assertFalse(meta['access_recovery']['automatic_http403_retry'])
        for p, content in old.items(): self.assertEqual(p.read_bytes(), content)
        with patch.object(access, 'check', side_effect=AssertionError('Static validation must be offline')):
            jobs.validate(job)

    def test_failed_access_creates_no_new_run(self):
        self.probe.side_effect = ValueError('Provider access is not restored')
        before = list(self.run.parent.iterdir())
        with self.assertRaisesRegex(ValueError, 'not restored'):
            interrupted.prepare(self.run, after_access_restored=True)
        self.assertEqual(list(self.run.parent.iterdir()), before)

    def test_actual_last_error_and_http_evidence_are_required(self):
        for event in [
            {'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}},
            {'method': 'turn/completed', 'params': {'turn': {'status': 'failed', 'error': dict(DENIAL, code='insufficient_quota')}}}]:
            with self.subTest(event=event):
                self.write(self.stage/'events.jsonl', event)
                with self.assertRaisesRegex(ValueError, 'actual final'):
                    interrupted.prepare(self.run, after_access_restored=True)
        self.stage_records(self.stage)
        self.write(self.stage/'http.jsonl', {'path': '/responses', 'status': 401})
        with self.assertRaisesRegex(ValueError, 'matching terminal'):
            interrupted.prepare(self.run, after_access_restored=True)
        self.probe.assert_not_called()

    def test_local_unknown_mathematical_and_unqualified_records_cannot_resume(self):
        original = json.loads(json.dumps(self.failure))
        variants = [dict(original, status='BLOCKED'), dict(original, isolation_violation=True),
                    dict(original, identity_and_input_boundary_verified=False),
                    dict(original, transport_health={'faults': [{'kind': 'TOOL_SERVICE_ERROR'}]}),
                    dict(original, transport_health={'faults': original['transport_health']['faults'],
                         'uncertainty': [{'kind': 'PROVIDER_TERMINAL_WAIT_EXCEEDED'}]})]
        for failure in variants:
            with self.subTest(failure=failure):
                self.write(self.stage/'result.json', failure)
                with self.assertRaises(ValueError): interrupted.prepare(self.run, after_access_restored=True)
        self.probe.assert_not_called()

    def test_only_recorded_remote_relay_classes_can_accompany_a_denial(self):
        self.failure['transport_health']['faults'].insert(0, {'kind': 'RELAY_ERROR', 'request_number': 1})
        self.write(self.stage/'result.json', self.failure)
        self.write(self.stage/'relay-errors.jsonl', {'request_number': 1, 'error_type': 'FileNotFoundError', 'upstream_opened': False})
        with self.assertRaisesRegex(ValueError, 'Unknown/local relay'):
            interrupted.prepare(self.run, after_access_restored=True)
        self.write(self.stage/'relay-errors.jsonl', {'request_number': 1, 'error_type': 'IncompleteRead', 'upstream_opened': True})
        job = interrupted.prepare(self.run, after_access_restored=True); jobs.validate(job)

    def test_live_group_or_later_phase_cannot_be_overridden(self):
        with patch.object(owner_observation, 'snapshot', return_value={'all_terminal': True, 'all_process_exits_verified': False}):
            with self.assertRaisesRegex(ValueError, 'group exits'):
                interrupted.prepare(self.run, after_access_restored=True)
        later = self.run/'nl0-to-lean/tasks/T001/stage'; self.stage_records(later)
        self.write(self.run/'case-result.json', {'result': {'status': 'EXECUTION_FAULT', 'evidence': str(later/'result.json')}})
        with self.assertRaisesRegex(ValueError, 'later-stage recovery'):
            interrupted.prepare(self.run, after_access_restored=True)
        self.probe.assert_not_called()

    def test_receipt_or_transport_mutation_invalidates_static_authority(self):
        job = interrupted.prepare(self.run, after_access_restored=True)
        for path in [Path(job['resume']['access_recovery_receipt']), self.stage/'http.jsonl', self.stage/'events.jsonl']:
            content = path.read_bytes()
            try:
                path.write_bytes(content+b'\nchanged')
                with self.assertRaisesRegex(ValueError, 'changed'): jobs.validate(job)
            finally: path.write_bytes(content)

    def test_a_released_source_keeps_the_audit_boundary_without_author_replay(self):
        import audit_a_campaign
        import full_workflow
        core = Path(__file__).resolve().parents[1]
        source = self.stage/'case'; shutil.copytree(core/'tests/fixtures/closed-addition', source)
        self.write(source/'author-check-progress.json', {'synthetic_control_only': True})
        self.write(self.stage/'accepted.json', {'synthetic_control_only': True})
        (self.stage/'tools.jsonl').write_text('')
        campaign = self.run/'audit-a/0001'; audit_a_campaign.prepare(source, self.run/'inputs', campaign)
        failed = campaign/'R001/stage'; self.stage_records(failed)
        self.write(self.run/'case-result.json', {'result': {'status': 'EXECUTION_FAULT',
            'evidence': str(failed/'result.json'), 'completion': {'acceptance_target_satisfied': False}}})
        before = (source/'nl0.json').read_bytes()
        with patch.object(full_workflow, 'nl0_artifact_for_audit', return_value={'synthetic_control_only': True}):
            job = interrupted.prepare(self.run, after_access_restored=True)
            self.assertEqual(job['resume']['mode'], 'audit-a')
            self.assertEqual(job['resume']['author_directory'], str(self.stage.parent))
            self.assertEqual(job['resume']['campaigns'], [str(campaign)])
        self.assertEqual((source/'nl0.json').read_bytes(), before)

    def test_provenance_rejection_file_cannot_be_overridden(self):
        path = self.stage/'tool-provenance-rejections.jsonl'; path.write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'Local/provenance'):
            interrupted.prepare(self.run, after_access_restored=True)
        self.probe.assert_not_called()

    def test_finite_deadline_is_preserved_and_never_reset(self):
        # Bind a separately prepared bounded fixture rather than editing its ownership marker.
        original = jobs.prepare(self.problem, track='full', profiles=PROFILES, time_budget_seconds=100)
        run = Path(original['root']); stage = run/'nl0/0001/stage'; self.stage_records(stage)
        self.write(run/'case-result.json', {'result': {'status': 'EXECUTION_FAULT', 'evidence': str(stage/'result.json')}})
        self.write(run/'execution-status.json', {'controller': {'pid': 2147483647, 'pgid': 2147483647,
            'started': 'Synthetic exited owner', 'state': 'FINALIZED'}, 'processes': {}, 'time_budget': {
            'deadline_at_utc': (datetime.now(timezone.utc)+timedelta(seconds=70)).isoformat()}})
        job = interrupted.prepare(run, after_access_restored=True)
        self.assertGreater(job['time_budget_seconds'], 0); self.assertLessEqual(job['time_budget_seconds'], 70)
        self.write(run/'execution-status.json', {'controller': {'pid': 2147483647, 'pgid': 2147483647,
            'started': 'Synthetic exited owner', 'state': 'FINALIZED'}, 'processes': {}, 'time_budget': {}})
        with self.assertRaisesRegex(ValueError, 'cannot reset'):
            interrupted.prepare(run, after_access_restored=True)

    def test_prepare_only_cli_is_explicit_single_run_and_mutually_exclusive(self):
        parser = argparse.ArgumentParser(); entrypoint.parsers(parser.add_subparsers(dest='command'))
        output = self.run.parent/'new-explicit-output'
        args = parser.parse_args(['resume', str(self.run), '--after-access-restored', '--prepare-only', '--output', str(output)])
        with patch.object(entrypoint, 'launch') as launch:
            result = entrypoint.dispatch(args); launch.assert_not_called()
        self.assertEqual(result['runs'], [str(output)])
        with patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(['resume', str(self.run), '--after-access-restored', '--repair-evidence'])
        for argv in [['resume', str(self.run), str(self.run), '--after-access-restored'],
                     ['resume', str(self.run), '--output', str(output)]]:
            with self.subTest(argv=argv), self.assertRaises(ValueError): entrypoint.dispatch(parser.parse_args(argv))

    def test_access_is_rechecked_at_actual_launch_without_a_model_start(self):
        job = interrupted.prepare(self.run, after_access_restored=True)
        with patch.object(entrypoint, 'preflight_profiles'), patch('runtime_config.verify'), \
             patch.object(access, 'confirm_exit', return_value={'process_exit_verified': True}), \
             patch.object(access, 'check', side_effect=ValueError('Provider access failed again')), \
             patch.object(entrypoint.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(ValueError, 'failed again'): entrypoint.launch([job], detached=True)
            process.assert_not_called()
        self.assertFalse((Path(job['root'])/'launch.json').exists())


if __name__ == '__main__':
    unittest.main()
