"""Observable accounting controls; no inference-speed claim or model call."""
import harness_support
import json
from pathlib import Path
import tempfile
import unittest
import shutil

from phase_metrics import summarize


class MetricsTests(unittest.TestCase):
    def test_retained_review_copies_do_not_duplicate_stage_wall_time(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);stage=root/'stage';stage.mkdir()
            (stage/'result.json').write_text(json.dumps({'status':'ACCEPTED','wall_seconds':10,'stage_log_path':str(stage)}))
            (stage/'execution-manifest.json').write_text('{"phase":"audit-a-global"}')
            shutil.copytree(stage,root/'review-evidence/copy')
            rows=summarize(root)['stages']
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['wall_seconds'],10)
    def test_tools_are_nested_and_missing_usage_stays_unknown(self):
        with tempfile.TemporaryDirectory() as raw:
            stage=Path(raw)/'stage';stage.mkdir()
            (stage/'result.json').write_text(json.dumps({'status':'UNFINISHED','wall_seconds':10,'queue_seconds':2}))
            (stage/'execution-manifest.json').write_text('{"phase":"proof"}')
            (stage/'tools.jsonl').write_text('{"tool":"check_transition","wall_seconds":3}\n')
            (stage/'request-lifecycle.jsonl').write_text(
                '{"event":"FORWARDED","request_number":1,"at_utc":"2026-01-01T09:00:00"}\n'
                '{"event":"TOOL_RESULT_DELIVERED","call_id":"a"}\n'
                '{"event":"PROVIDER_TERMINAL","request_number":1,"at_utc":"2026-01-01T09:00:02"}\n')
            value=summarize(raw);row=value['stages'][0]
            self.assertEqual(row['request_observations'],[])
            self.assertIsNone(row['requests'])
            self.assertEqual(row['wall_seconds'],10)
            self.assertEqual(row['tool_wall_seconds_by_name']['check_transition'],3)
            self.assertIsNone(row['usage']);self.assertIsNone(value['pure_internal_model_reasoning_seconds'])
            self.assertFalse(row['measurement_valid'])


if __name__=='__main__':unittest.main()
