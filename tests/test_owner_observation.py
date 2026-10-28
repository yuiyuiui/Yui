"""Owner handoffs and bounded metadata checks never launch mathematical work."""
import harness_support
from harness_support import PROFILES
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import entrypoint
import jobs
import owner_observation as owner
from controller_common import write


class OwnerObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        paper = self.root/'proof.md'; paper.write_text('Synthetic operator control.')
        self.job = jobs.prepare(paper, track='nl0', profiles=PROFILES, max_concurrency=2)
        self.run = Path(self.job['root'])
        self.identity = {'pid': 73100, 'pgid': 73100, 'started': 'Wed Oct 28 02:39:13 2026'}

    def tearDown(self):
        self.temp.cleanup()

    def state(self, *, final=False):
        write(self.run/'execution-status.json', {'phase': 'proof',
            'controller': {**self.identity, 'state': 'FINALIZED' if final else 'RUNNING'},
            'processes': {}, 'proof_counts': {'LOCAL_CHECKED': 3, 'RUNNING': 2},
            'tasks': {'T001': {'argument': 'UNFINISHED_ARGUMENT_MUST_NOT_BE_DISPLAYED'}},
            'usage': {'status': 'PARTIAL', 'confirmed_tokens': {'total_tokens': 123},
                      'in_flight_or_unreported_requests': 2}})

    def test_pending_handoff_groups_cases_without_claiming_a_real_schedule(self):
        before = {p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('No scheduler/model process')):
            result = owner.handoff([self.run, self.run])
        self.assertEqual(result['runs'], [str(self.run)])
        self.assertEqual(result['interval_seconds'], 600)
        self.assertEqual(result['registration'], 'HOST_REGISTRATION_REQUIRED')
        self.assertIsNone(result['automation_id'])
        self.assertEqual(result['foreground'], 'end_turn_after_handoff')
        self.assertEqual(result['observe_command'][-2:], ['observe', str(self.run)])
        self.assertEqual(before, {p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()})

    def test_detached_dispatch_persists_the_pending_owner_handoff(self):
        with patch.object(entrypoint, 'preflight_profiles'), patch('runtime_config.verify'), \
                patch.object(subprocess, 'Popen') as launch, \
                patch('execution_state.identity', return_value=self.identity):
            launch.return_value.pid = self.identity['pid']
            result = entrypoint.launch([self.job], detached=True)
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(result['status'], 'DISPATCHED')
        saved = json.loads((self.run/'launch.json').read_text())
        self.assertEqual(saved['owner_observation'], result['owner_observation'])
        self.assertEqual(saved['owner_observation']['registration'], 'HOST_REGISTRATION_REQUIRED')

    def test_finalized_status_never_establishes_process_exit(self):
        self.state(final=True)
        write(self.run/'case-result.json', {'result': {'status': 'WORKFLOW-PASSED'}})
        with patch.object(owner, 'process_table', return_value={73100: self.identity}):
            result = owner.snapshot([self.run])
        self.assertTrue(result['all_terminal'])
        self.assertFalse(result['all_process_exits_verified'])
        self.assertEqual(result['next_check_seconds'], 600)

    def test_terminal_exit_retains_partial_usage_and_only_compact_metadata(self):
        self.state(final=True)
        write(self.run/'case-result.json', {'result': {'status': 'WORKFLOW-PASSED'}})
        before = {p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        with patch.object(owner, 'process_table', return_value={}) as ps:
            result = owner.snapshot([self.run])
        self.assertEqual(ps.call_count, 1)
        self.assertTrue(result['all_terminal'])
        self.assertTrue(result['all_process_exits_verified'])
        self.assertIsNone(result['next_check_seconds'])
        self.assertEqual(result['cases'][0]['usage']['in_flight_or_unreported_requests'], 2)
        self.assertNotIn('UNFINISHED_ARGUMENT', json.dumps(result))
        self.assertEqual(before, {p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()})

    def test_reused_pid_or_surviving_group_is_not_a_verified_owned_exit(self):
        self.state(final=True)
        reused = {**self.identity, 'started': 'Wed Oct 28 08:00:00 2026'}
        with patch.object(owner, 'process_table', return_value={73100: reused}):
            result = owner.snapshot([self.run])['cases'][0]
        self.assertFalse(result['controller_identity_matches'])
        self.assertFalse(result['process_exit_verified'])
        self.assertEqual(result['registered_groups_still_present'], [73100])

    def test_unavailable_process_inspection_cannot_claim_exit(self):
        self.state(final=True)
        with patch.object(owner, 'process_table', side_effect=OSError('OS inspection unavailable')):
            result = owner.snapshot([self.run])
        self.assertFalse(result['all_process_exits_verified'])
        self.assertIn('OSError', result['process_inspection_error'])

    def test_altered_job_or_unmarked_directory_is_rejected(self):
        with self.assertRaises(OSError):
            owner.snapshot([self.root/'unmarked'])
        (self.run/'job.json').write_text('{}')
        with self.assertRaises((KeyError, ValueError)):
            owner.handoff([self.run])

    def test_public_observe_command_reports_a_prepared_job_without_model_calls(self):
        result = subprocess.run([sys.executable, '-B', str(harness_support.CORE/'nl0/scripts/yui.py'),
            'observe', str(self.run)], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['cases'][0]['phase'], 'PREPARED_NOT_STARTED')
        self.assertFalse(data['all_terminal'])
        self.assertEqual(data['next_check_seconds'], 600)

    def test_invalid_interval_is_rejected_before_any_host_scheduling(self):
        fake = self.root/'config'; fake.mkdir()
        data = json.loads((harness_support.CORE/'config.json').read_text())
        for value in (0, True, 30, 1.5):
            data['owner_observation']['interval_seconds'] = value
            (fake/'config.json').write_text(json.dumps(data))
            with self.subTest(value=value), patch.object(owner, 'CORE', fake), self.assertRaises(ValueError):
                owner.policy()


if __name__ == '__main__':
    unittest.main()
