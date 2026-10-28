"""Unlimited execution controls; no model calls or mathematical verdicts."""
import harness_support
import json
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import Mock, patch

import runtime_config
from output_guard import ProviderWaitGuard
from run_pilot import Trial


class UnlimitedExecutionTests(unittest.TestCase):
    def test_default_limits_are_explicitly_unlimited(self):
        config = json.loads((runtime_config.CORE / 'config.json').read_text())
        for scope in ('case', 'stage', 'native'):
            self.assertIsNone(runtime_config.configured_timeout(scope))
        self.assertIsNone(config['token_budget'])

    def test_limit_representation_rejects_ambiguous_values(self):
        self.assertIsNone(runtime_config.time_limit(None))
        self.assertEqual(runtime_config.time_limit(20), 20)
        for value in (0, -1, True, 'unlimited', float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime_config.time_limit(value)

    def test_unlimited_stage_continues_after_long_elapsed_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            t = Trial.__new__(Trial)
            t.logs = Path(temporary)
            t.timeout = None
            t.strict = True
            t.allowed_user_messages = set()
            t.thread_id = 'synthetic'
            t.accepted = None
            t.turn_results = []
            t.continuation_count = 0
            t.rpc = Mock(return_value={'turn': {'id': 'synthetic'}})
            deadlines = []

            def receive(predicate, deadline):
                deadlines.append(deadline)
                if len(deadlines) == 2:
                    t.accepted = {'synthetic': True}
                return {'method': 'turn/completed', 'params': {'turn': {
                    'id': 'synthetic', 'status': 'completed'}}}

            t.receive_until = receive
            with patch('run_pilot.time.monotonic', side_effect=[1, 99999999]):
                t.solve_turns('Synthetic explicit task')
            self.assertEqual(deadlines, [None, None])
            self.assertEqual(t.continuation_count, 1)

    def test_unlimited_receive_still_processes_terminal_events(self):
        t = Trial.__new__(Trial)
        t.inbox = queue.Queue()
        t.pending_turn_start_id = None
        t.inbox.put({'method': 'turn/completed', 'params': {'turn': {'id': 'done'}}})
        result = t.receive_until(lambda m: m['method'] == 'turn/completed', None)
        self.assertEqual(result['params']['turn']['id'], 'done')

    def test_native_limit_inherits_only_explicit_case_or_stage_limit(self):
        t = Trial.__new__(Trial)
        t.strict = True
        t.started = 10
        t.timeout = None
        with patch('run_pilot.time.monotonic', return_value=20):
            self.assertIsNone(t.lean_timeout())
            t.timeout = 30
            self.assertEqual(t.lean_timeout(), 20)

    def test_long_post_tool_wait_is_not_an_automatic_stop(self):
        clock = [0]
        guard = ProviderWaitGuard(clock=lambda: clock[0])
        guard.normalized(1)
        guard.observe({'type': 'response.output_item.done', 'item': {
            'type': 'function_call', 'id': 'item', 'call_id': 'call', 'name': 'check_draft'}}, 1)
        self.assertIsNotNone(guard.delivered('call', 'synthetic-delivery'))
        clock[0] = 99999999
        self.assertIsNone(guard.check())
        self.assertIn(1, guard.waits)


if __name__ == '__main__':
    unittest.main()
