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
    def test_workflow_unlimited_with_separate_native_feedback_limit(self):
        config = json.loads((runtime_config.CORE / 'config.json').read_text())
        for scope in ('case', 'stage'):
            self.assertIsNone(runtime_config.configured_timeout(scope))
        self.assertEqual(runtime_config.configured_timeout('native'), 300)
        self.assertIsNone(config['token_budget'])

    def test_limit_representation_rejects_ambiguous_values(self):
        self.assertIsNone(runtime_config.time_limit(None))
        self.assertEqual(runtime_config.time_limit(20), 20)
        for value in (0, -1, True, 'unlimited', float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime_config.time_limit(value)

    def test_native_limit_clamps_explicit_requests_without_changing_workflow_limits(self):
        self.assertEqual(runtime_config.native_timeout(),300)
        self.assertEqual(runtime_config.native_timeout(900),300)
        self.assertEqual(runtime_config.native_timeout(20),20)
        with patch.object(runtime_config,'configured_timeout',return_value=None):
            self.assertIsNone(runtime_config.native_timeout())
            self.assertEqual(runtime_config.native_timeout(20),20)
        with self.assertRaises(ValueError):runtime_config.native_timeout(0)

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
        t.active_turn_id = None
        t.inbox.put({'method': 'turn/completed', 'params': {'turn': {'id': 'done'}}})
        result = t.receive_until(lambda m: m['method'] == 'turn/completed', None)
        self.assertEqual(result['params']['turn']['id'], 'done')

    def test_existing_worker_reads_updated_native_limit_without_restart(self):
        t = Trial.__new__(Trial)
        t.strict = True
        t.started = 10
        t.timeout = None
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);config=root/'config.json'
            config.write_text(json.dumps({'timeouts':{'native_seconds':None}}))
            with patch.object(runtime_config,'CORE',root), patch('run_pilot.time.monotonic',return_value=20):
                self.assertIsNone(t.lean_timeout())
                config.write_text(json.dumps({'timeouts':{'native_seconds':300}}))
                self.assertEqual(t.lean_timeout(),300)
                t.timeout=30
                self.assertEqual(t.lean_timeout(),20)

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
