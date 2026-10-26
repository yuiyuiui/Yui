"""Observable accounting controls; no inference-speed claim or model call."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from phase_metrics import summarize


class MetricsTests(unittest.TestCase):
    def test_tools_are_nested_and_missing_usage_stays_unknown(self):
        with tempfile.TemporaryDirectory() as raw:
            stage=Path(raw)/'stage';stage.mkdir()
            (stage/'result.json').write_text(json.dumps({'status':'UNFINISHED','wall_seconds':10,'queue_seconds':2}))
            (stage/'execution-manifest.json').write_text('{"phase":"proof"}')
            (stage/'tools.jsonl').write_text('{"tool":"check_transition","wall_seconds":3}\n')
            value=summarize(raw);row=value['stages'][0]
            self.assertEqual(row['wall_seconds'],10)
            self.assertEqual(row['tool_wall_seconds_by_name']['check_transition'],3)
            self.assertIsNone(row['usage']);self.assertIsNone(value['pure_internal_model_reasoning_seconds'])
            self.assertFalse(row['measurement_valid'])


if __name__=='__main__':unittest.main()
