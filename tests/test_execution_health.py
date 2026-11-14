import harness_support
import json
from pathlib import Path
import tempfile
import unittest

import execution_health


class ExecutionHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def submitted(self):
        return {'transport':'native-codex-stdio-v1','status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT',
            'temporary_workspace_removed':True,'isolation_violation':False,
            'usage':{'complete':True},'exposure':{'status':'NATIVE-CODEX-CONTEXT-CHECK-PASSED','configured_model':__import__('native_carrier').MODEL,'errors':[]},
            'transport_health':{'status':'NO_RECORDED_FAULT','faults':[],'uncertainty':[]}}

    def recovered(self):
        row=self.submitted();row.update(execution_health='FAULT',usage={'complete':False},
            transport_health={'status':'FAULT','faults':[{'kind':'NATIVE_PROVIDER_ERROR','details':{'codexErrorInfo':'serverOverloaded'}}],
                'uncertainty':[]})
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
        row=deepcopy(base);row['transport_health']['faults'][0]['details']={'codexErrorInfo':'unknown'};variants.append(row)
        row=deepcopy(base);row['temporary_workspace_removed']=False;variants.append(row)
        row=deepcopy(base);row['exposure']['configured_model']='wrong-model';variants.append(row)
        row=deepcopy(base);row['exposure']['errors']=['configuration mismatch'];variants.append(row)
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



    def test_native_reader_failure_is_not_remote_provider_recovery(self):
        (self.root/'native-client.json').write_text('{}')
        (self.root/'carrier-reader-errors.jsonl').write_text(json.dumps({'message':'invalid native frame'})+'\n')
        health=execution_health.inspect(self.root)
        self.assertEqual(health['status'],'FAULT')
        self.assertEqual(health['faults'][0]['kind'],'CARRIER_READER_ERROR')
        result=self.submitted();result.update(execution_health='FAULT',transport_health=health)
        self.assertFalse(execution_health.known_transport_recovery(result))

    def test_missing_transport_evidence_stays_unverified(self):
        self.assertEqual(execution_health.inspect(self.root)['status'],'UNVERIFIED')

    def test_old_transport_receipt_cannot_qualify_current_execution(self):
        row=self.submitted()
        row['exposure']={'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED',
                         'actual_model_ids':['gpt-6.1-sol'],'standard_tier_verified':True}
        self.assertFalse(execution_health.qualification(row)['identity_and_input_boundary_verified'])
        row=self.recovered();row['transport']='obsolete-http'
        self.assertFalse(execution_health.known_transport_recovery(row))

    def test_unverified_review_is_distinct_from_a_located_failure(self):
        self.assertEqual(execution_health.review_outcome(['PASS','UNVERIFIED']),'REVIEW_UNVERIFIED')
        self.assertEqual(execution_health.review_outcome(['FAIL','UNVERIFIED']),'MATHEMATICAL_REVIEW_FAILED')
        self.assertEqual(execution_health.review_outcome([]),'REVIEW_INCOMPLETE')
