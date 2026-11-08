"""I/O continuation rejects unsafe replay and never manufactures acceptance."""
import harness_support
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import proof_io_recovery as recovery
import proof_reuse
from controller_common import write


class ProofIORecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = (Path(self.tmp.name)/'old').resolve(); self.root.mkdir()
        self.workflow = self.root/'nl0-to-lean/0001/workflow'
        self.prior = self.workflow/'proof-run'
        self.interface = self.workflow.parent/'interface'
        self.profile = {'id': 'test-model', 'reasoning_effort': 'xhigh', 'speed': 'standard'}
        self.job = {'root': str(self.root), 'track': 'full', 'formalization': 'unconditional',
                    'policy': 'normal', 'time_budget_seconds': None, 'profiles': {'lean': self.profile}}
        write(self.root/'job.json', self.job)
        self.tasks = {}
        for sid, state in [('T001', 'LOCAL_CHECKED'), ('T002', 'PAUSED_ERROR')]:
            stage = self.prior/'workers'/sid
            self.tasks[sid] = {'id': sid, 'role': 'proof', 'state': state, 'log_path': str(stage)}
            write(stage/'prompt.txt', {'packet': {'step': sid}})
            write(stage/'native-client.json', {'profile': self.profile})
        self.submission = {'status': 'ACCEPTED', 'identity_and_input_boundary_verified': True,
                           'isolation_violation': False, 'submission_completion': {},
                           'execution_health': 'NO_RECORDED_FAULT'}
        write(self.prior/'workers/T001/result.json', self.submission)
        write(self.prior/'workers/T001/accepted.json', {'proof': 'synthetic candidate only'})
        write(self.prior/'workers/T002/error-state.json', {
            'state': 'PAUSED_ERROR', 'incident': 'disk-incident', 'fault': {'category': 'harness_bug'},
            'error': {'exception_type': 'OSError', 'message': '[Errno 28] No space left on device'}})
        self.state = {'phase': 'proof', 'tasks': self.tasks}
        write(self.root/'execution-status.json', self.state)
        for p in [self.workflow/'manifest.json', self.workflow/'freeze-seal.json',
                  self.interface/'accepted-interface-paths.json', self.prior/'inputs/contract.json']:
            write(p, {})
        write(self.prior/'inputs/plan.json', {'steps': [{'id': sid} for sid in self.tasks]})
        (self.root/'logs').mkdir(); (self.root/'logs/controller.log').write_text(
            'OSError: [Errno 28] No space left on device')
        self.patches = [
            patch('jobs.validate', side_effect=lambda value, **kw: value),
            patch('owner_observation.snapshot', return_value={'all_process_exits_verified': True}),
            patch('full_workflow.workflow.bound', return_value={
                'bindings': [], 'frozen_input_bindings': [],
                'interface_binding': str(self.interface/'accepted-interface-paths.json'),
                'authority': {'graph': 'synthetic-source'}}),
            patch('ir.validate'), patch('ir.render'),
            patch('ir.local_packet', side_effect=lambda c, p, sid: {'step': sid}),
            patch('native_client.audit', return_value={'status': 'NATIVE-CODEX-CONTEXT-CHECK-PASSED'}),
            patch('execution_health.record_qualification', return_value={'record_context_qualified': True})]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def test_exited_checkpoint_binds_actual_artifacts_without_writing_old_run(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        _, descriptor, files = recovery.qualify(self.root)
        self.assertEqual(descriptor['completed_steps'], ['T001'])
        self.assertEqual(descriptor['unfinished_steps'], ['T002'])
        self.assertIn(str(self.prior/'workers/T001/accepted.json'), {r['path'] for r in files})
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertFalse((self.prior/'report.json').exists())

    def test_live_processes_and_actual_queue_results_block_replay(self):
        with patch('owner_observation.snapshot', return_value={'all_process_exits_verified': False}):
            with self.assertRaisesRegex(ValueError, 'must have exited'): recovery.qualify(self.root)
        write(self.prior/'report.json', {'status': 'ACTUAL_NONPASS'})
        with self.assertRaisesRegex(ValueError, 'actual completed queue'): recovery.qualify(self.root)

    def test_non_io_failure_and_changed_profile_block_replay(self):
        p = self.prior/'workers/T002/error-state.json'; value = json.loads(p.read_text())
        value['error']['message'] = 'different failure'; write(p, value)
        with self.assertRaisesRegex(ValueError, 'non-ENOSPC'): recovery.qualify(self.root)
        value['error']['message'] = '[Errno 28] No space left on device'; write(p, value)
        write(self.prior/'workers/T002/native-client.json', {'profile': {**self.profile, 'id': 'different'}})
        with self.assertRaisesRegex(ValueError, 'profile changed'): recovery.qualify(self.root)

    def test_profile_and_target_cannot_change_in_new_job(self):
        old, descriptor, files = recovery.qualify(self.root)
        new = {**old, 'root': str(self.root.parent/'new'), 'resume': descriptor, 'authority_bindings': files}
        recovery.validate_descriptor(new)
        new['target_selection'] = {'full_target': 'changed'}
        with self.assertRaisesRegex(ValueError, 'target_selection'): recovery.validate_descriptor(new)

    def test_stored_diagnostic_cannot_be_rerolled_after_protected_objection(self):
        review = self.prior/'workers/T002/diagnosis-requests/one/review'
        write(review/'stage/accepted.json', {'route': 'SOURCE_REVIEW_REQUIRED'})
        write(review/'stage/result.json', self.submission)
        with patch('proof_diagnosis.validate'):
            with self.assertRaisesRegex(ValueError, 'Preserve the actual diagnostic route'):
                recovery.qualify(self.root)

    def test_completed_body_is_only_candidate_and_own_scope_is_fixed(self):
        _, descriptor, _ = recovery.qualify(self.root)
        view = self.root.parent/'view'; view.mkdir()
        write(view/'io-recovery.json', {'version': recovery.VERSION, 'checkpoint': descriptor, 'origins': []})
        with patch.object(recovery, 'view', return_value=descriptor), patch('proof_reuse.same_port', return_value=True):
            value = proof_reuse.candidate(view, self.prior/'inputs/contract.json', {}, 'T001')
            self.assertEqual(value['body'], 'synthetic candidate only')
            self.assertIn('recheck required', value['scope'])
            self.assertIsNone(proof_reuse.candidate(view, self.prior/'inputs/contract.json', {}, 'T002'))
        with patch.object(recovery, 'view', return_value=descriptor), patch('proof_reuse.same_port', return_value=False):
            with self.assertRaisesRegex(ValueError, 'obligation changed'):
                recovery.candidate(view, self.prior/'inputs/contract.json', {}, 'T001')

    def test_candidate_context_does_not_silently_accept_faulted_or_foreign_records(self):
        self.assertTrue(recovery.candidate_context(self.submission))
        for change in [{'execution_fault': 'unknown'}, {'isolation_violation': True},
                       {'identity_and_input_boundary_verified': False}, {'status': 'BLOCKED'}]:
            self.assertFalse(recovery.candidate_context({**self.submission, **change}))


if __name__ == '__main__': unittest.main()
