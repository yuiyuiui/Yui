"""Request audit iteration must not load concatenated semantic histories."""
import harness_support
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from clean_stage import ArtifactStage
import execution_health
import exposure
import usage
import phase_metrics


class StreamingAuditTests(unittest.TestCase):
    def test_all_request_records_are_checked_without_read_text_on_jsonl(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);stage=ArtifactStage(root/'stage','Declared neutral input.',phase='control',library=False)
            try:
                stage.allowed_user_messages={'Declared neutral input.'};stage.initial_user_message='Declared neutral input.'
                model=stage.model
                payload={'model':model,'reasoning':{'effort':stage.model_selection['reasoning_effort']},
                    'input':[{'type':'message','role':'user','content':[{'type':'input_text','text':'Declared neutral input.'}]}]}
                for _ in range(12):stage.normalize_request(payload)
                (stage.logs/'system.txt').write_text(stage.system+'\n')
                (stage.logs/'tools.json').write_text(json.dumps(stage.tools))
                (stage.logs/'execution-manifest.json').write_text(json.dumps({'model':model}))
                (stage.logs/'result.json').write_text('{"status":"SYNTHETIC_SOFTWARE_CONTROL"}')
                (stage.logs/'http.jsonl').write_text(''.join(json.dumps({'request_number':n,'path':'/responses','status':200})+'\n' for n in range(1,13)))
                (stage.logs/'response-0001.sse').write_text('data: '+json.dumps({'type':'response.completed',
                    'response':{'model':model,'service_tier':'default'}})+'\n\n')
                original=Path.read_text
                def guarded(path,*a,**k):
                    if path.suffix=='.jsonl':raise AssertionError('No eager JSONL history loading')
                    return original(path,*a,**k)
                with patch.object(Path,'read_text',guarded):
                    result=exposure.audit_stage(stage.logs);health=execution_health.inspect(stage.logs)
                    accounting=usage.summarize_stage(stage.logs)
                    metrics=phase_metrics.summarize(root)
                self.assertEqual(result['requests_checked'],12);self.assertEqual(result['errors'],[])
                self.assertEqual(result['status'],'TRANSMITTED-EXPOSURE-CHECK-PASSED')
                self.assertEqual(health['status'],'NO_RECORDED_FAULT')
                self.assertEqual(accounting['requests'],12);self.assertIsNone(accounting['total_usage'])
                self.assertEqual(metrics['stages'][0]['requests'],12)
                # A late malformed record must still fail explicitly.
                with (stage.logs/'requests.jsonl').open('a') as stream:stream.write('{bad-json}\n')
                with self.assertRaises(ValueError):exposure.audit_stage(stage.logs)
            finally:shutil.rmtree(stage.work,ignore_errors=True)


if __name__=='__main__':unittest.main()
