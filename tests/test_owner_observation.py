"""Owner handoffs and bounded metadata checks never launch mathematical work."""
import harness_support
from harness_support import PROFILES
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import Future
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import entrypoint
import jobs
import owner_observation as owner
import owner_reports
import execution_state
import queue_controller
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
            'updated_at_utc': '2026-10-28T03:00:00+00:00',
            'processes': {}, 'proof_counts': {'LOCAL_CHECKED': 3, 'RUNNING': 2},
            'tasks': {'T001': {'argument': 'UNFINISHED_ARGUMENT_MUST_NOT_BE_DISPLAYED'}},
            'usage': {'status': 'PARTIAL', 'confirmed_tokens': {'total_tokens': 123},
                      'in_flight_or_unreported_requests': 2}})

    def test_handoff_routes_reports_to_the_bound_owner(self):
        write(self.run/'owner-context.json', {'thread_id':'owner-task'})
        before = {p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('No scheduler/model process')):
            result = owner.handoff([self.run, self.run])
        self.assertEqual(result['runs'], [str(self.run)])
        self.assertEqual(result['routed_runs'], [str(self.run)])
        self.assertEqual(result['interval_seconds'], 600)
        self.assertEqual(result['registration'], 'CONTROLLER_REPORTS')
        self.assertEqual(result['scheduler'], 'controller')
        self.assertEqual(result['notifications'], 'every_interval')
        self.assertEqual(result['foreground'], 'end_turn_after_handoff')
        self.assertIn('end the foreground turn', result['next_action'])
        self.assertEqual(result['observe_command'][-2:], ['observe', str(self.run)])
        self.assertEqual(before, {p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()})

    def test_controller_reports_unchanged_status_and_persists_failed_delivery(self):
        write(self.run/'owner-context.json', {'thread_id':'owner-task'})
        self.state()
        path = self.run/owner.REPORT_LOG
        sent = threading.Event()
        snapshots = []

        def notify(thread, message, *, resume):
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            snapshots.append((thread, resume, message, rows[-1]['report']))
            if len(snapshots) == 2:
                sent.set()
            return {'status':'PENDING' if len(snapshots) == 1 else 'QUEUED'}

        with patch('fault_control.queue_notification', side_effect=notify), \
                patch.object(owner_reports, 'policy', return_value={'interval_seconds':.02}):
            with owner_reports.controller_reports([self.run]):
                self.assertTrue(sent.wait(2))
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual([r['delivery']['status'] for r in rows if 'delivery' in r][:2], ['PENDING', 'QUEUED'])
        for thread, resume, message, report in snapshots[:2]:
            self.assertEqual(thread, 'owner-task')
            self.assertTrue(resume)
            self.assertEqual(report['phase'], 'proof')
            self.assertIn('longest_blocker', report['progress'])
            self.assertIn('[Yui STATUS]', message)
            self.assertNotIn('UNFINISHED_ARGUMENT_MUST_NOT_BE_DISPLAYED', message)

    def test_nonproof_task_counts_are_not_hidden_by_zero_proof_counts(self):
        recorder=execution_state.Recorder(self.run,'synthetic-case',{})
        try:
            recorder.update(proof_total=10)
            for state in ('RUNNING','WAITING_REVIEW','PAUSED_ERROR'):
                recorder.task('review-'+state,role='audit',state=state)
            recorder.flush(force=True)
            with patch.object(owner,'process_table',return_value={}):
                row=owner.snapshot([self.run])['cases'][0]
            self.assertEqual(row['counts']['RUNNING'],1)
            self.assertEqual(row['counts']['WAITING_REVIEW'],1)
            self.assertEqual(row['counts']['PAUSED_ERROR'],1)
            self.assertTrue(all(value==0 for value in row['proof_counts'].values()))
            self.assertEqual(row['proof_total'],10)
        finally:recorder.close('CANCELLED')

    def test_detached_dispatch_persists_and_starts_controller_reporting(self):
        write(self.run/'owner-context.json', {'thread_id':'owner-task'})
        self.assertIsNone(owner.snapshot([self.run])['cases'][0]['proof_total'])
        with patch.object(entrypoint, 'preflight_profiles'), patch('runtime_config.verify'), \
                patch.object(subprocess, 'Popen') as launch, \
                patch('execution_state.identity', return_value=self.identity):
            launch.return_value.pid = self.identity['pid']
            launch.return_value.poll.return_value = None
            result = entrypoint.launch([self.job], detached=True)
        self.assertEqual(launch.call_count, 1)
        self.assertIn('--controller-reports', launch.call_args.args[0])
        self.assertEqual(result['status'], 'DISPATCHED')
        saved = json.loads((self.run/'launch.json').read_text())
        self.assertEqual(saved['owner_observation'], result['owner_observation'])
        self.assertEqual(saved['owner_observation']['registration'], 'CONTROLLER_REPORTS')

    def test_legacy_frozen_controller_keeps_its_launch_contract(self):
        legacy_files = [row for row in jobs.runtime_bindings() if Path(row['path']).name!='owner_reports.py']
        with patch.object(jobs,'runtime_bindings',return_value=legacy_files):
            legacy = jobs.prepare(self.job['problem'],track='nl0',profiles=PROFILES,
                                  output=self.root/'legacy-run',max_concurrency=2)
        with patch.object(entrypoint, 'preflight_profiles'), patch('runtime_config.verify'), \
                patch('runtime_snapshot.environment'), patch.object(subprocess, 'Popen') as launch, \
                patch('execution_state.identity', return_value=self.identity):
            launch.return_value.pid = self.identity['pid']
            launch.return_value.poll.return_value = None
            result = entrypoint.launch([legacy], detached=True)
        self.assertNotIn('--controller-reports', launch.call_args.args[0])
        self.assertEqual(result['owner_observation']['registration'], 'HOST_REGISTRATION_REQUIRED')

    def test_detached_short_exit_observes_the_held_child_result(self):
        import sys
        from types import SimpleNamespace

        children, launch_was_reserved = [], []

        def start_detached(*args, **kwargs):
            launch_was_reserved.append((self.run/'batch-launch-pending.json').is_file())
            child = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(.08);raise SystemExit(17)'],
                                     start_new_session=True)
            children.append(child)
            return child

        try:
            with patch.object(entrypoint, 'preflight_profiles'), patch('runtime_config.verify'), \
                    patch.object(entrypoint, 'subprocess', SimpleNamespace(Popen=start_detached)), \
                    patch('execution_state.identity', return_value=None):
                result = entrypoint.launch([self.job], detached=True)
            self.assertEqual(launch_was_reserved, [True])
            self.assertEqual((result['status'], result['exit_code']), ('CONTROLLER_EXITED', 17))
            self.assertFalse((self.run/'batch-launch-pending.json').exists())
        finally:
            for child in children:
                child.wait(timeout=5)

    def test_controller_reports_completion_after_persisting_batch_result(self):
        write(self.run/'owner-context.json', {'thread_id': 'owner-task'})
        status = 'DRAFT-AUDIT-PASSED'

        def complete_case(_job, root):
            write(root/'case-result.json', {'result': {'status': status}})
            return SimpleNamespace(pid=self.identity['pid'], poll=lambda: 0)

        def notify(_thread, _message, *, resume):
            batch = json.loads((self.run/'batch-result.json').read_text())
            self.assertTrue(batch['children_exited'])
            self.assertTrue(resume)
            return {'status': 'QUEUED'}

        with patch.object(queue_controller, 'launch_case', side_effect=complete_case), \
                patch.object(queue_controller, 'identity', return_value=self.identity), \
                patch.object(queue_controller.case_outcomes, 'terminal', return_value=True), \
                patch('fault_control.queue_notification', side_effect=notify) as queued:
            queue_controller.serve([self.job], report_progress=True)
        rows = [json.loads(line) for line in (self.run/owner.REPORT_LOG).read_text().splitlines()]
        self.assertEqual(rows[0]['report']['result'], status)
        self.assertEqual(rows[1]['delivery']['status'], 'QUEUED')
        queued.assert_called_once()

    def test_revised_plan_counts_shared_aliases_once_and_excludes_retired_workers_and_diagnosis(self):
        recorder=execution_state.Recorder(self.run,'neutral-plan',{})
        try:
            recorder.task('T009',role='proof',state='FINISHED')
            recorder.task('T001',role='proof',state='LOCAL_CHECKED')
            recorder.task('T002',role='proof',state='RUNNING')
            recorder.task('diagnosis',role='diagnosis',state='RUNNING')
            recorder.update(proof_total=3,proof_group_sizes={'T001':2,'T002':1})
            recorder.flush(force=True)
            row=owner.snapshot([self.run])['cases'][0]
            self.assertEqual(row['proof_total'],sum(row['proof_counts'].values()))
            self.assertEqual(row['proof_counts']['LOCAL_CHECKED'],2)
            self.assertEqual(row['proof_counts']['RUNNING'],1)
            self.assertEqual(row['counts']['RUNNING'],2)
        finally:
            recorder.close('CANCELLED')

    def test_current_round_report_tracks_exact_passes_waits_and_retries(self):
        instant = datetime.now(timezone.utc)
        def ago(seconds):
            return (instant - timedelta(seconds=seconds)).isoformat()
        tasks = {
            'T035': {'state':'RUNNING','activity':'WAITING_FOR_HELPER','activity_since_utc':ago(720),
                'waiting_for_helpers':['private-working'],'last_target_check':{'at_utc':ago(2520),'candidate':5,'exit_code':1},
                'last_helper_result':{'at_utc':ago(1500),'task_id':'previous-helper','status':'checked'}},
            'private-working': {'state':'RUNNING','helper_id':'H003','parent_task':'T035',
                'current_lean_check':{'started_at_utc':ago(91)}},
            'T006': {'state':'RUNNING','activity':'REMOTE_RETRY_WAIT','activity_since_utc':ago(12)},
            'T007': {'state':'RUNNING','activity':'TOOL_RESULT_DELIVERED','repair_route':'INTERNAL_INTERFACE_REPAIR',
                'repair_requested_at_utc':ago(15)},
            'T012': {'state':'PENDING','activity':'WAITING_FOR_MODEL_SLOT','activity_since_utc':ago(45)},
            'T040': {'state':'LOCAL_CHECKED','finished_at_utc':ago(79)},
            'T041': {'state':'LOCAL_CHECKED','finished_at_utc':ago(601)},
            'T099': {'state':'REPAIR_WAIT','consumers':['T099'],'activity_since_utc':ago(2000),
                'last_target_check':{'at_utc':ago(0),'candidate':20}},
        }
        groups = {'T035':1,'T006':1,'T007':1,'T012':1,'T040':2,'T041':1}
        state = {'phase':'proof','controller':{**self.identity,'state':'RUNNING'},'tasks':tasks,
            'updated_at_utc':ago(0),'controller_heartbeat_at_utc':ago(1),
            'proof_round':2,'bindings':{'plan_sha256':'a'*64},'proof_total':7,
            'proof_group_sizes':groups,'proof_counts':{'LOCAL_CHECKED':3}}
        write(self.run/'execution-status.json',state)
        with patch.object(owner,'process_table',return_value={self.identity['pid']:self.identity}):
            row = owner.snapshot([self.run])['cases'][0]
        progress = row['progress']
        self.assertEqual((row['phase'],progress['status']),('proof','FRESH'))
        self.assertEqual((progress['plan_sha256'],progress['proof_round']),('a'*64,2))
        self.assertEqual((progress['passed'],progress['passed_last_10m']),(3,2))
        self.assertEqual(progress['activity_counts'],{kind:1 for kind in (
            'WAITING_FOR_HELPER','LEAN_CHECKING','REMOTE_RETRY_WAIT','INTERFACE_REPAIR','WAITING_FOR_MODEL_SLOT')})
        self.assertEqual(progress['last_target_check']['candidate'],5)
        self.assertEqual(progress['last_helper_result']['task_id'],'previous-helper')
        blocker = progress['longest_blocker']
        self.assertEqual((blocker['task'],blocker['seconds'],blocker['last_target_check_age_seconds']),('T035',720,2520))
        self.assertEqual(blocker['waiting_on'],[{'task_id':'H003','activity':'LEAN_CHECKING'}])
        self.assertIn('collect',blocker['next_action'])
        del tasks['T040']['finished_at_utc']
        self.assertIsNone(owner.progress(state,observed=instant,identity_matches=True,
            process_error=None,state_error=None)['passed_last_10m'])

    def test_stale_or_unreadable_snapshot_exposes_a_gap(self):
        old = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        path = self.run/'execution-status.json'
        write(path,{'controller':{**self.identity,'state':'RUNNING'},'updated_at_utc':old,
            'controller_heartbeat_at_utc':old,'tasks':{'T001':{'activity':'LEAN_CHECKING'}}})
        with patch.object(owner,'process_table',return_value={self.identity['pid']:self.identity}):
            row = owner.snapshot([self.run])['cases'][0]['progress']
        self.assertEqual((row['status'],row['observation_gap']),('STALE','CONTROLLER_HEARTBEAT_EXPIRED'))
        self.assertEqual(row['activity_counts'],{})
        self.assertIsNone(row['longest_blocker'])
        path.write_text('{')
        with patch.object(owner,'process_table',return_value={}):
            row = owner.snapshot([self.run])['cases'][0]
        self.assertFalse(row['process_exit_verified'])
        self.assertEqual(row['progress']['observation_gap'],'UNREADABLE_EXECUTION_STATUS')

    def test_target_check_and_helper_receipt_record_only_the_observed_events(self):
        from proof_obligations import HelperWork
        recorder = execution_state.Recorder(self.run,'synthetic-observation',{})
        try:
            recorder.task('T035',activity='WAITING_FOR_HELPER')
            since = recorder.state['tasks']['T035']['activity_since_utc']
            recorder.task('T035',activity='WAITING_FOR_HELPER')
            self.assertEqual(recorder.state['tasks']['T035']['activity_since_utc'],since)
            recorder.target_checked('T035',{'candidate':2,'exit_code':1,'stdout':'PRIVATE_PROOF'},source='check_transition')
            work = HelperWork(SimpleNamespace(budget=SimpleNamespace(execution=recorder),execution_task='T035'))
            future = Future()
            work.jobs['H003'] = ('child',self.run/'request.json',future)
            work.collect('H003')
            self.assertNotIn('last_helper_result',recorder.state['tasks']['T035'])
            future.set_result(self.run/'result.json')
            with patch('proof_obligations.receive',return_value={'status':'checked','result':{},'helper':{'name':'localLemma'}}):
                work.collect('H003')
                row = recorder.state['tasks']['T035']
                received = row['last_helper_result']
                work.collect('H003')
                self.assertIs(row['last_helper_result'],received)
            self.assertEqual(received['task_id'],'H003')
            self.assertNotIn('stdout',row['last_target_check'])
        finally:
            recorder.close('CANCELLED')

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
        self.assertEqual(result['cases'][0]['progress']['status'],'TERMINAL')
        self.assertEqual(result['cases'][0]['usage']['in_flight_or_unreported_requests'], 2)
        self.assertNotIn('UNFINISHED_ARGUMENT', json.dumps(result))
        self.assertEqual(before, {p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()})

    def test_positively_reused_group_leader_is_unrelated_to_old_run(self):
        self.state(final=True)
        reused = {**self.identity, 'started': 'Wed Oct 28 08:00:00 2026'}
        with patch.object(owner, 'process_table', return_value={73100: reused}):
            result = owner.snapshot([self.run])['cases'][0]
        self.assertFalse(result['controller_identity_matches'])
        self.assertTrue(result['process_exit_verified'])
        self.assertEqual(result['registered_groups_still_present'], [])

    def test_surviving_orphan_group_still_blocks_an_exit_claim(self):
        self.state(final=True)
        orphan={'pid':73101,'pgid':73100,'started':'Wed Oct 28 02:39:14 2026'}
        with patch.object(owner,'process_table',return_value={73101:orphan}):
            result=owner.snapshot([self.run])['cases'][0]
        self.assertFalse(result['process_exit_verified'])
        self.assertEqual(result['registered_groups_still_present'],[73100])

    def test_unknown_group_start_is_not_positive_reuse_evidence(self):
        self.state(final=True)
        with patch.object(owner,'process_table',return_value={73100:{**self.identity,'started':'-'}}):
            result=owner.snapshot([self.run])['cases'][0]
        self.assertFalse(result['process_exit_verified'])

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
        self.assertEqual(data['cases'][0]['progress']['observation_gap'],'MISSING_EXECUTION_STATUS')
        self.assertFalse(data['all_terminal'])
        self.assertEqual(data['next_check_seconds'], 600)

    def test_invalid_interval_is_rejected_before_any_host_scheduling(self):
        fake = self.root/'config'; fake.mkdir()
        data = json.loads((harness_support.CORE/'nl0/templates/yui-config.json').read_text())
        for value in (0, True, 30, 1.5):
            data['owner_observation']['interval_seconds'] = value
            (fake/'yui-config.json').write_text(json.dumps(data))
            with self.subTest(value=value), patch.object(owner, 'CORE', fake), self.assertRaises(ValueError):
                owner.policy()


if __name__ == '__main__':
    unittest.main()
