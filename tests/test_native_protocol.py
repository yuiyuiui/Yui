"""Native protocol, trust and accounting boundaries without model service calls."""
import harness_support
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock,patch

from clean_stage import ArtifactStage
import native_client
import usage
import execution_health
import execution_state


class NativeProtocolTests(unittest.TestCase):
    def test_native_policies_do_not_claim_invisible_partial_stream_guards(self):
        import model_pilot
        self.assertFalse(native_client.OUTPUT_POLICY['partial_argument_deltas_available'])
        self.assertFalse(native_client.OUTPUT_POLICY['automatic_whitespace_interrupt'])
        self.assertFalse(native_client.PROVIDER_WAIT_POLICY['raw_provider_terminal_observer'])
        self.assertIsNone(native_client.PROVIDER_WAIT_POLICY['idle_seconds'])
        self.assertEqual(model_pilot.OUTPUT_POLICY,native_client.OUTPUT_POLICY)
        self.assertFalse(hasattr(self.stage,'argument_guard'))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.stage=ArtifactStage(self.root/'stage','Synthetic native contract.',phase='control',library=False)
        self.addCleanup(shutil.rmtree,self.stage.work,True)
        self.stage.thread_id='thread';self.stage.active_turn_id='turn';self.stage.proc=Mock(stdin=io.StringIO())
        self.stage.proc.poll.return_value=None

    def params(self):
        return {'threadId':'thread','turnId':'turn','callId':'call','tool':'read_yui','arguments':{'path':'SKILL.md'}}

    def test_native_tool_ids_cannot_cross_thread_turn_namespace_or_catalog(self):
        original=self.params()
        for field,value in [('threadId','foreign'),('turnId','old'),('tool','shell'),('namespace','foreign'),('callId',''),('arguments','{}')]:
            p={**original,field:value}
            with self.subTest(field=field),self.assertRaises((ValueError,PermissionError)):
                native_client.validate_tool(self.stage,p)
        native_client.validate_tool(self.stage,original)
        with self.assertRaises(PermissionError):native_client.validate_tool(self.stage,{**original,'arguments':{'path':'foreign'}})

    def test_tool_result_is_immutable_after_actual_delivery_snapshot(self):
        row={'nested':[{'value':1}]};saved=self.stage.snapshot_tool_result('call',row)
        row['nested'][0]['value']=2
        self.assertEqual(json.loads(saved),{'nested':[{'value':1}]})
        self.assertEqual(self.stage.tool_history['call'],json.loads(saved))

    def test_old_terminal_error_and_raw_item_do_not_mutate_current_work(self):
        for method in ('turn/completed','error','rawResponseItem/completed'):
            params={'threadId':'thread','turnId':'old','turn':{'id':'old','status':'failed'},'error':{'code':'server_error'}}
            self.assertFalse(native_client.observe(self.stage,{'method':method,'params':params}))
        self.assertFalse((self.stage.logs/'native-errors.jsonl').exists())

    def test_foreign_thread_and_model_reroute_fail_before_dispatch(self):
        with self.assertRaises(PermissionError):native_client.observe(self.stage,{'method':'item/started','params':{'threadId':'foreign'}})
        with self.assertRaises(PermissionError):native_client.observe(self.stage,{'method':'model/rerouted','params':{'threadId':'thread','toModel':'unexpected'}})

    def test_known_native_error_envelopes_do_not_parse_arbitrary_http_prose(self):
        cases=[('stream disconnected before completion: idle timeout waiting for SSE','model_timeout'),
               ('stream disconnected before completion: Transport error: network error: error decoding response body','model_stream_interrupted'),
               ('stream disconnected before completion: error sending request','model_transport'),
               ('Some quoted paper says HTTP 403 and timeout','model_unknown')]
        import remote_retry
        for text,category in cases:
            value={'codexErrorInfo':'other','message':text}
            self.assertEqual(remote_retry.diagnose(native_client.fault(value))['category'],category)
            self.assertNotIn('code',value)

    def raw(self,item,turn='turn'):
        return native_client.observe(self.stage,{'method':'rawResponseItem/completed',
            'params':{'threadId':'thread','turnId':turn,'item':item}})

    def host_fault(self):
        self.raw({'type':'custom_tool_call','name':'exec','call_id':'code','input':'text(1);'})
        self.raw({'type':'custom_tool_call_output','call_id':'code',
            'output':'failed to spawn code-mode host /fixture/helper: Operation not permitted (os error 1)'})

    def test_only_current_native_exec_failure_latches_and_completion_cannot_erase_it(self):
        for kind,name,call,turn in [('message','exec','code','turn'),
                ('custom_tool_call','not_exec','code','turn'),('custom_tool_call','exec','other','old')]:
            self.raw({'type':kind,'name':name,'call_id':call,'input':'text(1);'},turn)
            self.raw({'type':'custom_tool_call_output','call_id':call,
                'output':'failed to spawn code-mode host /fixture/helper: denied'},turn)
            self.assertFalse(getattr(self.stage,'native_infrastructure_fault',None))
        self.host_fault();fault=self.stage.native_infrastructure_fault.copy()
        native_client.observe(self.stage,{'method':'turn/completed','params':{
            'threadId':'thread','turn':{'id':'turn','status':'completed'}}})
        self.assertEqual(self.stage.native_infrastructure_fault,fault)
        self.assertIsNone(self.stage.last_response_success)
        self.assertEqual((fault['thread_id'],fault['turn_id'],fault['call_id']),('thread','turn','code'))

    def test_host_fault_interrupt_is_once_and_failed_ack_is_reported_without_cleanup(self):
        self.host_fault()
        self.stage.interrupt_active_turn=Mock(side_effect=TimeoutError('no native acknowledgement'))
        self.stage.pause_error=Mock(side_effect=RuntimeError('retained pause'))
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError,'retained pause'):self.stage.check_argument_guard()
        self.stage.interrupt_active_turn.assert_called_once_with(reason='NATIVE_INFRASTRUCTURE_FAULT')
        error=self.stage.pause_error.call_args.args[0]
        self.assertIs(error['current_generation_stop_confirmed'],False)
        self.assertIn('no native acknowledgement',error['interrupt_error'])
        self.stage.proc.terminate.assert_not_called()

    def test_host_fault_interrupt_does_not_dispatch_late_tool(self):
        import time
        self.host_fault();self.stage.dispatch=Mock();self.stage._stopping=True
        self.stage.inbox.put({'id':10,'method':'item/tool/call','params':self.params()})
        self.stage.inbox.put({'method':'turn/completed','params':{'threadId':'thread',
            'turn':{'id':'turn','status':'interrupted'}}})
        self.stage.receive_until(lambda m:m.get('method')=='turn/completed',time.monotonic()+2)
        self.stage.dispatch.assert_not_called()
        self.assertEqual(json.loads(self.stage.proc.stdin.getvalue())['error']['code'],-32800)

    def test_explicit_typed_auth_code_is_not_replaced_by_transport_message(self):
        error={'code':'invalid_api_key','codexErrorInfo':'other',
            'message':'stream disconnected before completion: error sending request'}
        self.assertEqual(native_client.fault(error),error)

    def test_missing_native_helper_prevents_process_launch(self):
        with patch('native_runtime.for_stage',side_effect=ValueError('Bound helper changed')), \
                patch('subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError,'Bound helper changed'):self.stage.start_process()
            launch.assert_not_called()

    def counter(self,total,baseline=None):
        return {'baseline':baseline or {},'token_usage':{'total':{
            'inputTokens':total,'outputTokens':total,'totalTokens':2*total,
            'cachedInputTokens':total//2,'reasoningOutputTokens':total//2}}}

    def usage(self,rows):
        (self.stage.logs/'native-client.json').write_text('{}')
        (self.stage.logs/'native-usage.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        return usage.summarize_stage(self.stage.logs)

    def test_duplicate_cumulative_usage_snapshots_are_not_added(self):
        result=self.usage([self.counter(10),self.counter(10),self.counter(15)])
        self.assertEqual(result['observed_usage']['total_tokens'],30)
        self.assertFalse(result['complete']);self.assertIsNone(result['requests'])
        ledger=json.loads((self.stage.logs/'usage-ledger.jsonl').read_text())
        self.assertIn('record_id',ledger);self.assertNotIn('response_id',ledger)

    def test_retained_thread_usage_subtracts_earlier_role_work(self):
        base=self.counter(10)['token_usage']['total']
        result=self.usage([self.counter(15,base),self.counter(20,base)])
        self.assertEqual(result['observed_usage']['total_tokens'],20)

    def test_decreasing_usage_and_impossible_subsets_remain_invalid(self):
        value=self.counter(8);value['token_usage']['total']['cachedInputTokens']=999
        for rows in ([self.counter(10),self.counter(9)],[value]):
            self.assertTrue(self.usage(rows)['errors'])
            self.assertFalse(self.usage(rows)['complete'])

    def test_missing_usage_and_actual_tier_are_unknown(self):
        result=self.usage([])
        self.assertIsNone(result['observed_usage']);self.assertEqual(result['status'],'NOT_RECORDED')
        self.assertEqual(result['standard_speed_observation'],'UNVERIFIED')

    def test_missing_or_inconsistent_native_usage_does_not_invent_live_counters(self):
        self.stage.execution=Mock();self.stage.execution_task='task'
        invalid=self.counter(8)['token_usage'];invalid['total']['cachedInputTokens']=999
        for value in (None,{},invalid):
            native_client.observe(self.stage,{'method':'thread/tokenUsage/updated',
                'params':{'threadId':'thread','turnId':'turn','tokenUsage':value}})
            self.assertIsNone(self.stage.execution.native_event.call_args.args[-1])
        result=usage.summarize_native(self.stage.logs,'control')
        self.assertFalse(result['complete'])
        self.assertTrue(result['errors']);self.assertIsNone(result['observed_usage'])

    def test_failed_turn_uses_its_native_error_event_when_inline_error_is_absent(self):
        fault={'codexErrorInfo':{'httpConnectionFailed':{'httpStatusCode':403}},'message':'Denied'}
        self.stage.rpc=Mock(return_value={'turn':{'id':'turn'}})
        def completed(*args):
            self.stage.last_native_error=fault
            return {'method':'turn/completed','params':{'turn':{'id':'turn','status':'failed','error':None}}}
        self.stage.receive_until=Mock(side_effect=completed)
        self.stage.pause_error=Mock(side_effect=RuntimeError('retained pause'))
        with self.assertRaisesRegex(RuntimeError,'retained pause'):self.stage.solve_turns('Synthetic work')
        self.assertEqual(self.stage.pause_error.call_args.args[0],fault)

    def test_native_live_usage_and_final_ledger_use_the_same_delta(self):
        recorder=execution_state.Recorder(self.root/'case','native',{})
        self.addCleanup(recorder.close,'CANCELLED')
        counts={'input_tokens':12,'output_tokens':4,'total_tokens':16,'cached_input_tokens':6,'reasoning_tokens':2}
        for _ in range(3):recorder.native_event(None,self.stage.logs,'thread/tokenUsage/updated',counts)
        recorder.flush(force=True)
        self.assertEqual(recorder.state['usage']['confirmed_tokens'],counts)
        self.assertEqual(recorder.state['usage']['status'],'PARTIAL')
        self.assertIsNone(recorder.state['usage']['requests'])

    def test_production_config_has_no_listener_or_custom_endpoint(self):
        text=native_client.configuration(self.stage)
        self.assertNotIn('base_url',text);self.assertNotIn('127.0.0.1',text)
        self.assertIn('request_max_retries = 0',text);self.assertIn('stream_max_retries = 0',text)
        self.assertIn('service_tier = "default"',text)
        params=native_client.thread_parameters(self.stage)
        self.assertNotIn('baseInstructions',params)
        self.assertFalse(params['allowProviderModelFallback'])

    def test_post_submission_new_tool_is_rejected_without_execution(self):
        import time
        self.stage.submission_closed=True;self.stage.dispatch=Mock();self.stage.started=time.monotonic()
        self.stage.inbox.put({'id':10,'method':'item/tool/call','params':self.params()})
        self.stage.inbox.put({'method':'turn/completed','params':{'threadId':'thread','turn':{'id':'turn','status':'interrupted'}}})
        self.stage.receive_until(lambda m:m.get('method')=='turn/completed',time.monotonic()+2)
        self.stage.dispatch.assert_not_called()
        self.assertEqual(json.loads(self.stage.proc.stdin.getvalue())['error']['code'],-32800)

    def test_malformed_native_notification_cannot_silently_continue(self):
        with self.assertRaises(ValueError):native_client.observe(self.stage,{'method':'error','params':['bad']})

    def test_aggregate_excludes_copied_stage_receipts_and_does_not_invent_response_count(self):
        self.usage([self.counter(10)])
        (self.stage.logs/'result.json').write_text(json.dumps({'stage_log_path':str(self.stage.logs)}))
        copied=self.root/'review-evidence/copy';shutil.copytree(self.stage.logs,copied)
        result=usage.aggregate(self.root)
        self.assertEqual(result['observed_usage']['total_tokens'],20)
        self.assertIsNone(result['unique_responses']);self.assertEqual(len(result['stages']),1)

    def test_exposed_thread_model_effort_tier_and_provider_cannot_silently_change(self):
        expected={'model':self.stage.model,'modelProvider':'yui-native',
                  'reasoningEffort':self.stage.model_selection['reasoning_effort'],'serviceTier':'default'}
        native_client.verify_thread(self.stage,expected)
        for key in expected:
            with self.subTest(key=key),self.assertRaises(ValueError):
                native_client.verify_thread(self.stage,{**expected,key:'unexpected'})

    def test_native_work_without_usage_keeps_request_count_unknown_not_zero(self):
        recorder=execution_state.Recorder(self.root/'unreported','native',{})
        self.addCleanup(recorder.close,'CANCELLED')
        recorder.native_event(None,self.stage.logs,'turn/started')
        recorder.flush(force=True)
        self.assertIsNone(recorder.state['usage']['requests'])
        self.assertIsNone(recorder.state['usage']['confirmed_tokens'])

    def test_native_delegation_is_disabled_in_supported_agents_configuration(self):
        import tomllib
        settings=tomllib.loads(native_client.configuration(self.stage))
        self.assertIs(settings['agents']['enabled'],False)
