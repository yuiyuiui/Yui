"""Remote-failure continuation and cancellation controls; no provider calls."""
import harness_support
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import queue
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

CORE=Path(__file__).resolve().parents[1]
import remote_retry as retry
import run_pilot
import execution_state
import execution_health
import full_workflow


def terminal(number, error=None):
    return {'method':'turn/completed','params':{'turn':{
        'id':'turn-'+str(number),'status':'failed' if error else 'completed','error':error}}}


class RemoteRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def trial(self):
        t=run_pilot.Trial.__new__(run_pilot.Trial)
        t.logs=self.root;t.thread_id='same-isolated-thread';t.timeout=None;t.strict=True
        t.model_selection={'id':'gpt-6.1-sol','reasoning_effort':'high','speed':'standard'}
        t.allowed_user_messages=set();t.continuation_count=0;t.turn_results=[];t.accepted=None
        t.api_calls=0;t.proc=Mock();t.proc.poll.return_value=None
        t.tool_history={};t.model_calls={};t.inbox=queue.Queue();t.pending_turn_start_id=None
        t.last_turn_event=None;t.active_turn_id=None;t.check_argument_guard=Mock();t.execution=None
        t.pause_error=Mock(side_effect=RuntimeError('Explicit retained pause software fixture'))
        t.execution_task='neutral-task'
        return t

    def turns(self, errors):
        t=self.trial();events=[terminal(i+1,error) for i,error in enumerate(errors)]+[terminal(len(errors)+1)]
        def start(*args,**kwargs):return {'turn':{'id':'turn-'+str(t.rpc.call_count)}}
        t.rpc=Mock(side_effect=start)
        def receive(predicate, deadline):
            event=events.pop(0);self.assertTrue(predicate(event));return event
        t.receive_until=Mock(side_effect=receive);t.wait_remote_retry=Mock()
        return t

    def test_real_overload_code_continues_same_thread_profile_and_existing_history(self):
        error={'message':'Selected model is at capacity.','codexErrorInfo':'serverOverloaded'}
        t=self.turns([error]);t.tool_history['old-call']={'actual_result':'retained'}
        result=t.solve_turns('Original frozen task.',smoke=True)
        self.assertEqual(result,terminal(2));self.assertEqual(t.remote_retry_count,1)
        self.assertEqual(t.turn_results[0]['params']['turn']['error'],error)
        self.assertEqual(t.tool_history['old-call'],{'actual_result':'retained'})
        for call in t.rpc.call_args_list:
            self.assertEqual(call.args[1]['threadId'],'same-isolated-thread')
            self.assertEqual(call.args[1]['model'],'gpt-6.1-sol')
            self.assertEqual(call.args[1]['effort'],'high')
        self.assertEqual(t.rpc.call_args_list[1].args[1]['input'][0]['text'],run_pilot.CONTINUE_PROMPT)
        self.assertEqual(t.continuation_count,0);t.wait_remote_retry.assert_called_once()

    def test_transient_retries_stop_at_ten_and_enter_pause(self):
        t=self.turns([{'code':'server_is_overloaded'}]*16)
        with self.assertRaisesRegex(RuntimeError,'retained pause'):t.solve_turns('Frozen task',smoke=True)
        self.assertEqual(t.remote_retry_count,10)
        self.assertEqual(t.rpc.call_count,11)
        t.pause_error.assert_called_once()

    def test_permanent_unknown_and_local_failures_do_not_retry(self):
        errors=[{'code':code} for code in ['invalid_request','insufficient_quota','usage_limit_exceeded',
            'context_length_exceeded','max_output_tokens','authentication_error','proof_invalid']]
        errors.append({'message':'server is overloaded','codexErrorInfo':'unrecognized'})
        for error in errors:
            with self.subTest(error=error):
                t=self.turns([error])
                with self.assertRaises(RuntimeError):t.solve_turns('Frozen task',smoke=True)
                t.wait_remote_retry.assert_not_called()
        for flag in ['local_protocol_fault','non_remote_relay_fault']:
            t=self.turns([{'codexErrorInfo':'serverOverloaded'}]);setattr(t,flag,True)
            with self.assertRaises(RuntimeError):t.solve_turns('Frozen task',smoke=True)
            t.wait_remote_retry.assert_not_called()

    def test_retry_classification_vetoes_auth_and_quota_even_with_server_status(self):
        for error in [
            {'code':'insufficient_quota','httpStatusCode':503},
            {'codexErrorInfo':{'httpConnectionFailed':{'httpStatusCode':401}}},
            {'code':'server_error','error':{'code':'organization_usage_limit_exceeded'}}]:
            self.assertIsNone(retry.classify(error))
        for error in [{'code':'server_is_overloaded'},
                      {'codexErrorInfo':{'responseStreamDisconnected':{'httpStatusCode':None}}},
                      {'codexErrorInfo':{'httpConnectionFailed':{'httpStatusCode':502}}}]:
            self.assertIsNotNone(retry.classify(error))

    def test_delay_is_fixed_at_one_minute(self):
        self.assertEqual(retry.delay(1),60);self.assertEqual(retry.delay(2),60)
        self.assertEqual(retry.delay(999),60)
        self.assertEqual(retry.delay(1,retry_after_seconds=600),60)
        self.assertEqual(retry.retry_after('30'),30)
        self.assertEqual(retry.retry_after('Wed, 21 Oct 2026 07:01:00 GMT',
            at=datetime(2026,10,21,7,tzinfo=timezone.utc)),60)
        for value in ['invalid','nan','inf',True]:self.assertIsNone(retry.retry_after(value))

    def test_cancellation_and_explicit_deadline_interrupt_the_wait(self):
        reason={'kind':'REMOTE_SERVICE_TRANSIENT'}
        t=self.trial();t.remote_retry_count=1;t.execution=Mock()
        t.execution.check.side_effect=execution_state.Cancelled('User stopped this case')
        started=time.monotonic()
        with self.assertRaises(execution_state.Cancelled):
            t.wait_remote_retry(300,reason,{'id':'failed-turn'},None)
        self.assertLess(time.monotonic()-started,1)
        t=self.trial();t.remote_retry_count=1
        with self.assertRaises(TimeoutError):
            t.wait_remote_retry(300,reason,{'id':'failed-turn'},time.monotonic()-1)

    def test_stale_terminal_event_does_not_finish_the_new_turn(self):
        t=self.trial();t.rpc=Mock(return_value={'turn':{'id':'turn-2'}})
        t.receive_until=run_pilot.Trial.receive_until.__get__(t)
        t.inbox.put(terminal(1,{'codexErrorInfo':'serverOverloaded'}));t.inbox.put(terminal(2))
        self.assertEqual(t.solve_turns('Frozen task',smoke=True),terminal(2))
        self.assertEqual(t.remote_retry_count,0)

    def test_duplicate_tool_delivery_keeps_exact_receipt_without_reexecuting(self):
        t=self.trial();t.proc.stdin=io.StringIO();t.dispatch=Mock(return_value={'actual':{'value':1}})
        t.model_calls={'call':{'name':'neutral','arguments':'{"x":1}'}}
        for number in [1,2]:t.inbox.put({'method':'item/tool/call','id':number,
            'params':{'callId':'call','tool':'neutral','arguments':{'x':1}}})
        t.inbox.put(terminal(1));t.receive_until=run_pilot.Trial.receive_until.__get__(t)
        t.receive_until(lambda m:m.get('method')=='turn/completed',None)
        self.assertEqual(t.dispatch.call_count,1)
        replies=[json.loads(line) for line in t.proc.stdin.getvalue().splitlines()]
        self.assertEqual(replies[0]['result'],replies[1]['result'])
        self.assertEqual(t.tool_history['call'],{'actual':{'value':1}})

    def test_duplicate_tool_id_still_rejects_changed_arguments(self):
        t=self.trial();t.proc.stdin=io.StringIO();t.dispatch=Mock()
        t.model_calls={'call':{'name':'neutral','arguments':'{"x":1}'}}
        t.tool_history={'call':{'actual_result':'retained'}}
        t.inbox.put({'method':'item/tool/call','id':2,
            'params':{'callId':'call','tool':'neutral','arguments':{'x':2}}})
        with self.assertRaises(PermissionError):
            run_pilot.Trial.receive_until(t,lambda m:False,None)
        t.dispatch.assert_not_called();self.assertEqual(t.proc.stdin.getvalue(),'')

    def test_a_new_model_event_cannot_reassign_an_already_completed_tool_id(self):
        t=self.trial();t.tool_names={'neutral'};t.model_history={}
        t.model_calls={'call':{'name':'neutral','arguments':'{"x":1}'}}
        t.tool_history={'call':{'actual_result':'retained'}}
        with self.assertRaises(PermissionError):
            t.observe_model_event({'type':'response.output_item.done','item':{
                'type':'function_call','id':'new-item','call_id':'call','name':'neutral','arguments':'{"x":2}'}})
        self.assertEqual(t.model_calls['call']['arguments'],'{"x":1}')

    def test_structured_remote_error_type_is_also_recognized_by_execution_health(self):
        (self.root/'requests.jsonl').write_text('{"request_number":1}\n')
        (self.root/'http.jsonl').write_text('{"path":"/responses","request_number":1,"status":200}\n')
        (self.root/'response-0001.sse').write_text('data: '+json.dumps({'type':'response.failed',
            'response':{'error':{'type':'service_unavailable_error','message':'capacity'}}})+'\n\n')
        health=execution_health.inspect(self.root)
        self.assertEqual(health['status'],'FAULT');self.assertFalse(health['uncertainty'])

    def test_recovered_overload_is_disclosed_and_never_a_healthy_measurement(self):
        (self.root/'requests.jsonl').write_text('{"request_number":1}\n')
        (self.root/'http.jsonl').write_text('{"path":"/responses","request_number":1,"status":200}\n')
        (self.root/'response-0001.sse').write_text('data: '+json.dumps({'type':'response.failed',
            'response':{'error':{'code':'server_is_overloaded','message':'capacity'}}})+'\n\n')
        health=execution_health.inspect(self.root)
        self.assertEqual(health['status'],'FAULT');self.assertEqual(health['faults'][0]['request_number'],1)
        row={'model':'gpt-6.1-sol','status':'ACCEPTED','execution_health':'FAULT',
            'transport_health':health,'temporary_workspace_removed':True,'usage':{'complete':False},
            'exposure':{'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED',
                'actual_model_ids':['gpt-6.1-sol'],'standard_tier_verified':True}}
        (self.root/'stage').mkdir();(self.root/'stage/result.json').write_text(json.dumps(row))
        self.assertEqual(full_workflow.accepted(self.root),row)
        checked=execution_health.require_review_execution(row,self.root/'stage/result.json')
        self.assertTrue(checked['submitted_record_qualified'])
        self.assertFalse(checked['measurement_valid']);self.assertFalse(checked['execution_qualified'])


if __name__=='__main__':unittest.main()
