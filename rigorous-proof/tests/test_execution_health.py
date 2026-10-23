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

    def test_provider_server_error_is_an_execution_fault(self):
        self.http(200)
        (self.root/'response-0001.sse').write_text('data: '+json.dumps({'type':'response.failed','response':{
            'error':{'code':'server_error','message':'service unavailable'}}})+'\n\n')
        self.assertEqual(execution_health.inspect(self.root)['status'],'FAULT')

    def test_rejected_math_candidate_is_not_an_execution_fault(self):
        self.http(200)
        (self.root/'tools.jsonl').write_text('{"result":{"exit_code":1,"accepted":false}}\n')
        self.assertEqual(execution_health.inspect(self.root)['status'],'NO_RECORDED_FAULT')
