import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import execution_health


class ExecutionHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'requests.jsonl').write_text('{"request_number":1}\n')

    def tearDown(self):self.temp.cleanup()

    def submitted(self):
        return {'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT',
            'temporary_workspace_removed':True,'isolation_violation':False,
            'usage':{'complete':True},'exposure':{'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED',
                'actual_model_ids':[__import__('run_pilot').MODEL],'standard_tier_verified':True},
            'transport_health':{'status':'NO_RECORDED_FAULT','faults':[],'uncertainty':[]}}

    def recovered(self):
        row=self.submitted();row.update(execution_health='FAULT',usage={'complete':False},
            transport_health={'status':'FAULT','faults':[{'kind':'RELAY_ERROR','request_number':6}],
                'uncertainty':[{'kind':'HTTP_EVIDENCE_INCOMPLETE','missing_requests':[6]}]})
        return row

    def test_complete_recovered_record_does_not_upgrade_original_health_or_usage(self):
        from copy import deepcopy
        row=self.recovered();before=deepcopy(row)
        checked=execution_health.require_review_execution(row,self.root/'actual-result.json')
        self.assertTrue(checked['submitted_record_qualified'])
        self.assertTrue(checked['recovered_transport'])
        self.assertFalse(checked['execution_qualified'])
        self.assertFalse(checked['measurement_valid'])
        self.assertFalse(checked['measurement_complete'])
        self.assertEqual(row,before)

    def test_partial_unknown_or_other_faults_cannot_claim_completed_recovery(self):
        from copy import deepcopy
        variants=[];base=self.recovered()
        for status in ['UNFINISHED','CANCELLED']:
            row=deepcopy(base);row['status']=status;variants.append(row)
        row=deepcopy(base);row['execution_health']='UNVERIFIED';variants.append(row)
        row=deepcopy(base);row['execution_fault']='controller failed';variants.append(row)
        row=deepcopy(base);row['isolation_violation']=True;variants.append(row)
        row=deepcopy(base);row['transport_health']['faults']=[{'kind':'TOOL_SERVICE_ERROR'}];variants.append(row)
        row=deepcopy(base);row['transport_health']['uncertainty']=[{'kind':'PROVIDER_TERMINAL_WAIT_EXCEEDED'}];variants.append(row)
        row=deepcopy(base);row['transport_health']['uncertainty'][0]['missing_requests']=[7];variants.append(row)
        row=deepcopy(base);row['temporary_workspace_removed']=False;variants.append(row)
        row=deepcopy(base);row['exposure']['actual_model_ids']=['wrong-model'];variants.append(row)
        row=deepcopy(base);row['exposure']['standard_tier_verified']=False;variants.append(row)
        for row in variants:
            self.assertFalse(execution_health.record_qualification(row)['submitted_record_qualified'])

    def test_typed_blocker_is_negative_evidence_and_cannot_complete_a_whole_review(self):
        row=self.submitted();row.update(status='BLOCKED',task_outcome='MATHEMATICAL_REVIEW_FAILED')
        self.assertFalse(execution_health.record_qualification(row)['submitted_record_qualified'])
        self.assertTrue(execution_health.record_qualification(row,allow_blocked=True)['submitted_record_qualified'])
        with self.assertRaises(execution_health.StageFailure) as error:
            execution_health.require_review_execution(row,self.root/'blocking-result.json')
        self.assertEqual(error.exception.result['status'],'MATHEMATICAL_REVIEW_FAILED')

    def test_healthy_budget_and_output_stops_keep_their_task_outcomes(self):
        for outcome in ['MODEL_BUDGET_EXHAUSTED','MODEL_OUTPUT_STALLED','MODEL_OUTPUT_LIMIT']:
            row=self.submitted();row.update(status='UNFINISHED',task_outcome=outcome)
            with self.assertRaises(execution_health.StageFailure) as error:
                execution_health.require_review_execution(row,self.root/'unfinished-result.json')
            self.assertEqual(error.exception.result['status'],outcome)

    def http(self,status):
        (self.root/'http.jsonl').write_text(json.dumps({'path':'/responses','request_number':1,'status':status})+'\n')

    def test_http_error_cannot_become_model_failure(self):
        self.http(503)
        self.assertEqual(execution_health.inspect(self.root)['status'],'FAULT')

    def test_missing_transport_evidence_stays_unverified(self):
        self.assertEqual(execution_health.inspect(self.root)['status'],'UNVERIFIED')

    def test_unverified_review_is_distinct_from_a_located_failure(self):
        self.assertEqual(execution_health.review_outcome(['PASS','UNVERIFIED']),'REVIEW_UNVERIFIED')
        self.assertEqual(execution_health.review_outcome(['FAIL','UNVERIFIED']),'MATHEMATICAL_REVIEW_FAILED')
        self.assertEqual(execution_health.review_outcome([]),'REVIEW_INCOMPLETE')

    def test_provider_server_error_is_an_execution_fault(self):
        self.http(200)
        (self.root/'response-0001.sse').write_text('data: '+json.dumps({'type':'response.failed','response':{
            'error':{'code':'server_error','message':'service unavailable'}}})+'\n\n')
        self.assertEqual(execution_health.inspect(self.root)['status'],'FAULT')

    def test_rejected_math_candidate_is_not_an_execution_fault(self):
        self.http(200)
        (self.root/'tools.jsonl').write_text('{"result":{"exit_code":1,"accepted":false}}\n')
        self.assertEqual(execution_health.inspect(self.root)['status'],'NO_RECORDED_FAULT')

    def test_output_limit_is_not_network_failure_and_does_not_hide_a_real_fault(self):
        self.http(200)
        (self.root/'response-0001.sse').write_text('data: '+json.dumps({
            'type':'response.incomplete','response':{'error':None,
            'incomplete_details':{'reason':'max_output_tokens'}}})+'\n\n')
        (self.root/'model-output-events.jsonl').write_text('{"event":"MODEL_OUTPUT_STALLED"}\n')
        self.assertEqual(execution_health.inspect(self.root)['status'],'NO_RECORDED_FAULT')
        (self.root/'relay-errors.jsonl').write_text('{"error":"TLS EOF"}\n')
        self.assertEqual(execution_health.inspect(self.root)['status'],'FAULT')

    def test_real_relay_and_tool_service_faults_are_separate_from_missing_usage(self):
        self.http(200)
        (self.root/'relay-errors.jsonl').write_text('{"error":"TLS unexpected EOF"}\n')
        report=execution_health.inspect(self.root)
        self.assertEqual(report['status'],'FAULT')
        self.assertIsNone(report['faults'][0]['request_number'])
        (self.root/'relay-errors.jsonl').unlink()
        (self.root/'tools.jsonl').write_text('{"tool":"search_mathlib","result":{"infrastructure_error":true,"error":"missing executable"}}\n')
        self.assertEqual(execution_health.inspect(self.root)['faults'][0]['kind'],'TOOL_SERVICE_ERROR')

    def test_post_tool_wait_stays_uncertain_and_a_real_fault_takes_precedence(self):
        self.http(200)
        (self.root/'model-output-events.jsonl').write_text(json.dumps({
            'event':'PROVIDER_TERMINAL_WAIT_EXCEEDED','request_number':1,
            'call_ids':['actual-call'],'idle_seconds':121})+'\n')
        report=execution_health.inspect(self.root)
        self.assertEqual(report['status'],'UNVERIFIED')
        self.assertEqual(report['uncertainty'][0]['kind'],'PROVIDER_TERMINAL_WAIT_EXCEEDED')
        (self.root/'relay-errors.jsonl').write_text('{"error":"TLS EOF"}\n')
        self.assertEqual(execution_health.inspect(self.root)['status'],'FAULT')
