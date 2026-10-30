"""Controller checks with synthetic stream events; no model or proof verdict."""
import harness_support
import json
from pathlib import Path
import queue
import threading
import time
import unittest
from unittest.mock import Mock

from output_guard import (ArgumentGuard, ModelOutputLimit, ModelOutputStalled,
                          ProviderWaitGuard, ProviderTerminalWaitExceeded)
from run_pilot import Trial


class OutputGuardTests(unittest.TestCase):
    def added(self, guard, request=1):
        guard.observe({'type':'response.output_item.added', 'item':{
            'id':'fc1', 'type':'function_call', 'name':'check_draft', 'call_id':'call1'}}, request)

    def delta(self, guard, text, request=1):
        return guard.observe({'type':'response.function_call_arguments.delta',
                              'item_id':'fc1', 'delta':text}, request)

    def test_actual_outside_whitespace_across_chunks_triggers_once(self):
        g=ArgumentGuard(8);self.added(g)
        self.assertIsNone(self.delta(g,'{"artifact":{'+ ' '*5))
        notice=self.delta(g,'\n\t  ')
        self.assertEqual(notice['outside_string_whitespace'],8)
        self.assertEqual((notice['request_number'],notice['tool']),(1,'check_draft'))
        self.assertIsNone(self.delta(g,' '*100))

    def test_quoted_mathematical_text_and_split_escapes_are_not_a_stall(self):
        g=ArgumentGuard(8);self.added(g)
        value=json.dumps({'text':'x " '+ ' '*10000+' \\ LaTeX\nend'})
        for char in value:self.assertIsNone(self.delta(g,char))

    def test_nonwhitespace_resets_and_other_requests_do_not_accumulate(self):
        g=ArgumentGuard(8);self.added(g);self.added(g,2)
        for text,request in [(' '*7,1),(' '*7,2),('x'+' '*7,1),('x',2)]:
            self.assertIsNone(self.delta(g,text,request))
        self.assertIsNotNone(self.delta(g,' ',1))

    def test_only_actual_function_items_are_tracked_and_terminal_clears(self):
        g=ArgumentGuard(8)
        self.assertIsNone(self.delta(g,' '*100))
        self.added(g)
        g.observe({'type':'response.completed'},1)
        self.assertIsNone(self.delta(g,' '*100))
        self.assertFalse(g.states)

    def test_guard_never_dispatches_a_partial_tool_call(self):
        t=Trial.__new__(Trial);t.output_guard_notice={'request_number':2}
        t.dispatch=Mock();t.inbox=queue.Queue()
        t.inbox.put({'method':'item/tool/call','id':9,'params':{'tool':'check_draft'}})
        with self.assertRaises(ModelOutputStalled):
            t.receive_until(lambda x:True,time.monotonic()+1)
        t.dispatch.assert_not_called()

    def test_output_limit_requires_actual_provider_terminal_evidence(self):
        for actual in [False,True]:
            t=Trial.__new__(Trial);t.allowed_user_messages=set();t.timeout=5;t.strict=True
            t.request_lock=threading.Lock();t.native_turn_generation=0;t.request_turns={};t.last_response_success=None
            t.thread_id='neutral-thread'
            t.accepted=None;t.turn_results=[];t.continuation_count=0
            t.pause_error=Mock(side_effect=RuntimeError('Retained software-control pause'))
            t.rpc=Mock(return_value={'turn':{'id':'turn1'}})
            t.receive_until=Mock(return_value={'method':'turn/completed','params':{'turn':{
                'id':'turn1','status':'failed','error':{'message':'Incomplete response returned, reason: max_output_tokens'}}}})
            if actual:t.provider_output_limit={'request_number':7,'response_id':'r7','reason':'max_output_tokens'}
            with self.assertRaises(ModelOutputLimit if actual else RuntimeError) as result:
                t.solve_turns('Neutral fixed task')
            if actual:self.assertEqual(result.exception.evidence['response_id'],'r7')
            else:self.assertNotIsInstance(result.exception,ModelOutputLimit)


class ProviderWaitTests(unittest.TestCase):
    def setUp(self):
        self.mono=0.;self.g=ProviderWaitGuard(idle_seconds=120,clock=lambda:self.mono)
        self.g.normalized(1)

    def completed_call(self,number=1,call='c1'):
        self.g.observe({'type':'response.output_item.done','item':{
            'id':'item-'+call,'type':'function_call','name':'read_task_input','call_id':call}},number)

    def test_requires_both_completed_call_and_real_tool_result(self):
        self.mono=1000
        self.assertIsNone(self.g.check())
        self.assertIsNone(self.g.delivered('not-completed','actual-delivery'))
        self.completed_call();self.mono=2000
        self.assertIsNone(self.g.check())
        self.g.delivered('c1','actual-delivery');self.mono=2119
        self.assertIsNone(self.g.check());self.mono=2120
        notice=self.g.check()
        self.assertEqual(notice['request_number'],1)
        self.assertEqual(notice['call_ids'],['c1'])
        self.assertEqual(notice['attribution'],'UNVERIFIED')

    def test_terminal_before_result_does_not_start_a_wait(self):
        self.completed_call();self.g.observe({'type':'response.completed'},1)
        self.assertIsNone(self.g.delivered('c1','actual-delivery'))
        self.mono=10000;self.assertIsNone(self.g.check())

    def test_terminal_or_next_request_clears_the_wait(self):
        for clear in ['terminal','next_request']:
            self.setUp();self.completed_call();self.g.delivered('c1','actual-delivery')
            if clear=='terminal':self.g.observe({'type':'response.incomplete'},1)
            else:self.g.normalized(2)
            self.mono=1000;self.assertIsNone(self.g.check())
            self.assertIsNone(self.g.delivered('c1','late-old-delivery'))

    def test_keepalive_does_not_reset_but_real_output_does(self):
        self.completed_call();self.g.delivered('c1','actual-delivery')
        self.mono=100;self.g.observe({'type':'keepalive'},1)
        self.g.observe({'type':'response.in_progress'},1)
        self.mono=120;self.assertIsNotNone(self.g.check())
        self.g.observe({'type':'response.reasoning_text.delta','delta':'actual output'},1)
        self.mono=239;self.assertIsNone(self.g.check())
        self.mono=240;self.assertIsNotNone(self.g.check())

    def test_local_tool_runtime_and_new_tool_result_do_not_consume_wait_budget(self):
        self.completed_call();self.mono=10000
        self.assertIsNone(self.g.check())
        self.g.delivered('c1','first-result');self.mono=10010
        self.completed_call(call='c2');self.mono=11000
        self.g.delivered('c2','second-result')
        self.assertIsNone(self.g.check())
        self.mono=11120;self.assertEqual(self.g.check()['call_ids'],['c1','c2'])

    def test_real_controller_raises_without_executing_waiting_tool(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.completed_call();self.g.delivered('c1','actual-result');self.mono=121
            t=Trial.__new__(Trial);t.provider_wait_guard=self.g;t.logs=Path(tmp)
            t.dispatch=Mock();t.inbox=queue.Queue()
            t.inbox.put({'method':'item/tool/call','id':9,'params':{'tool':'read_task_input'}})
            with self.assertRaises(ProviderTerminalWaitExceeded):
                t.receive_until(lambda x:True,time.monotonic()+1)
            t.dispatch.assert_not_called()
            row=json.loads((Path(tmp)/'model-output-events.jsonl').read_text())
            self.assertEqual(row['event'],'PROVIDER_TERMINAL_WAIT_EXCEEDED')
            self.assertEqual(row['call_ids'],['c1'])

    def test_accepted_submission_and_interrupt_cleanup_are_not_reclassified(self):
        self.completed_call();self.g.delivered('c1','actual-result');self.mono=1000
        t=Trial.__new__(Trial);t.provider_wait_guard=self.g;t.submission_closed=True
        t.check_argument_guard()
        t.submission_closed=False;t._stopping=True;t.check_argument_guard()


if __name__=='__main__':unittest.main()
