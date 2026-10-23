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

    def test_real_relay_and_tool_service_faults_are_separate_from_missing_usage(self):
        self.http(200)
        (self.root/'relay-errors.jsonl').write_text('{"error":"TLS unexpected EOF"}\n')
        report=execution_health.inspect(self.root)
        self.assertEqual(report['status'],'FAULT')
        self.assertIsNone(report['faults'][0]['request_number'])
        (self.root/'relay-errors.jsonl').unlink()
        (self.root/'tools.jsonl').write_text('{"tool":"search_mathlib","result":{"infrastructure_error":true,"error":"missing executable"}}\n')
        self.assertEqual(execution_health.inspect(self.root)['faults'][0]['kind'],'TOOL_SERVICE_ERROR')
