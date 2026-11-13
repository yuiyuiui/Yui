"""Independent whole-file allowance and failed-compilation controls; no live model."""
import harness_support
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import lean_timeout_policy as policy
import pilot_common


OK = {'exit_code': 0, 'stdout': 'checked', 'stderr': ''}
WALL = {'exit_code': 124, 'stdout': 'partial output', 'stderr': 'native wall limit',
        'timed_out': True, 'error_kind': 'LEAN_TIMEOUT', 'timeout_scope': 'native_call'}


def diagnosis(category):
    return {'category': category, 'line': 1, 'quote': 'example',
            'reason': 'The actual example was inspected for avoidable elaboration.',
            'next_action': 'Repair the located code or retry the unchanged workload.'}


class WholeFileTimeouts(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root/'Proof.lean'
        self.source.write_text('example : True := by trivial\n')
        self.calls = []

    @contextmanager
    def native(self, results):
        results = iter(results)
        def invoke(file, work, **kwargs):
            self.calls.append((kwargs['timeout'], kwargs['reviewed_policy'], file.read_text()))
            return deepcopy(next(results))
        with patch.object(pilot_common, '_run_lean', side_effect=invoke):
            yield

    def check(self, key='assembly-export', **kwargs):
        with policy.whole_file_scope(self.root/'whole-checks', key=key):
            return pilot_common.run_lean(self.source, self.root, **kwargs)

    def test_first_whole_file_check_is_thirty_minutes_not_the_local_six(self):
        with self.native([OK, OK]), policy.scope(self.root/'translation', None):
            self.assertEqual(self.check()['exit_code'], 0)
            self.assertEqual(pilot_common.run_lean(self.source, self.root)['exit_code'], 0)
        self.assertEqual([row[0] for row in self.calls], [1800, 360])

    def test_whole_file_workload_uses_thirty_forty_five_sixty_and_never_more(self):
        with self.native([WALL]*3), patch.object(policy, 'inspect_source', return_value=diagnosis('workload_only')) as review:
            result = self.check(timeout=10000)
        self.assertEqual([row[0] for row in self.calls], [1800, 2700, 3600])
        self.assertEqual(review.call_count, 3)
        self.assertEqual(result['exit_code'], 124)
        self.assertTrue(result['timed_out'])
        self.assertEqual(result['timeout_reviews'][-1]['action'], 'limit')
        for row in result['timeout_reviews']:
            directory = Path(row['evidence'])
            self.assertEqual((directory/'inputs/Candidate.lean').read_text(), self.source.read_text())

    def test_code_repair_keeps_the_current_allowance_and_unchanged_failure_is_not_retried(self):
        with self.native([WALL, WALL, OK, OK]), patch.object(policy, 'inspect_source',
                side_effect=[diagnosis('workload_only'), diagnosis('code_issue')]):
            failed = self.check()
            self.assertEqual(failed['timeout_reviews'][-1]['action'], 'repair')
            repeated = self.check()
            self.assertTrue(repeated['timeout_replayed'])
            self.assertEqual(len(self.calls), 2)
            self.source.write_text('example : True := True.intro\n')
            self.assertEqual(self.check()['exit_code'], 0)
            self.assertEqual(self.check(key='audit-inspection')['exit_code'], 0)
        self.assertEqual([row[0] for row in self.calls], [1800, 2700, 2700, 1800])

    def test_incomplete_diagnosis_does_not_authorize_more_time(self):
        with self.native([WALL]), patch.object(policy, 'inspect_source', return_value=diagnosis('uncertain')):
            result = self.check()
        self.assertEqual([row[0] for row in self.calls], [1800])
        self.assertEqual(result['timeout_reviews'][-1]['action'], 'inspect')
        self.assertEqual(result['exit_code'], 124)

    def test_shorter_explicit_stage_and_case_limits_remain_binding(self):
        with self.native([WALL]), patch.object(policy, 'inspect_source', return_value=diagnosis('workload_only')):
            result = self.check(timeout=20)
        self.assertEqual(self.calls[-1][0], 20)
        self.assertEqual(result['timeout_reviews'][-1]['action'], 'limit')
        with self.native([WALL]), policy.scope(self.root/'stage', None, deadline=time.monotonic()+5), \
                patch.object(policy, 'inspect_source', side_effect=AssertionError('Stage expiry is not a native timeout')):
            result = self.check(key='stage-limited')
        self.assertLessEqual(self.calls[-1][0], 5)
        self.assertEqual(result['error_kind'], 'STAGE_DEADLINE')
        case = dict(WALL, error_kind='CASE_DEADLINE', timeout_scope='whole_case')
        with self.native([case]), patch.object(policy, 'inspect_source', side_effect=AssertionError):
            self.assertEqual(self.check(key='case-limited'), case)

    def test_disabled_or_diagnostic_context_cannot_inject_adaptive_whole_file_work(self):
        with self.native([WALL]), policy.scope(None, None), \
                patch.object(policy, 'inspect_source', side_effect=AssertionError):
            self.assertEqual(self.check(), WALL)
        self.assertFalse(self.calls[-1][1])

    def test_timeout_flag_cannot_be_accepted_even_with_zero_exit_and_successful_output(self):
        for result in (dict(OK, timed_out=True), dict(OK, cancelled=True),
                       dict(OK, error_kind='LEAN_TIMEOUT'), dict(OK, error_kind='STAGE_DEADLINE')):
            with self.subTest(result=result):
                self.assertFalse(pilot_common.native_succeeded(result))
        self.assertTrue(pilot_common.native_succeeded(OK))

    def test_actual_native_diagnostic_then_real_lean_retry_uses_the_same_single_lane(self):
        import concurrency
        from native_fixture import NativeFixture
        from fault_control import Gate
        def respond(fixture, handler, number, payload):
            fixture.tool(handler, number, 'submit_draft', diagnosis('workload_only'))
        original = pilot_common._run_lean
        def controlled(file, work, **kwargs):
            self.calls.append((kwargs['timeout'], kwargs['reviewed_policy'], file.read_text()))
            return deepcopy(WALL) if len(self.calls) == 1 else original(file, work, **kwargs)
        lane = concurrency.Budget(concurrency.resolve(1), role='proof')
        work = self.root/'native'
        (work/'output').mkdir(parents=True)
        self.source = work/'output/Proof.lean'
        self.source.write_text('example : True := True.intro\n')
        with NativeFixture(self.root/'fixture', responder=respond) as fixture, \
                patch.object(Gate, 'pause', side_effect=AssertionError('Unexpected review pause')), \
                patch.object(pilot_common, '_run_lean', side_effect=controlled), \
                policy.scope(self.root/'reviews', lane), lane, \
                policy.whole_file_scope(self.root/'unused', key='assembly-export'):
            result = pilot_common.run_lean(self.source, work)
            self.assertFalse(fixture.failures)
        self.assertEqual([row[0] for row in self.calls], [1800, 2700])
        self.assertTrue(pilot_common.native_succeeded(result))
        self.assertEqual(result['native_limits']['timeout_seconds'], 2700)
        self.assertEqual(lane.report()['observed_peak_model_stages'], 1)


if __name__ == '__main__':
    unittest.main()
