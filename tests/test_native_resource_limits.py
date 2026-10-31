"""The configured resource policy reaches the actual Lean executable."""
import harness_support
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ir
import runtime_config
import pilot_common


class NativeResourceTests(unittest.TestCase):
    def test_heartbeat_config_rejects_unlimited_bool_negative_and_noninteger(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            for value in [0,-1,True,False,None,'20000000',2.5]:
                ir.write(root/'config.json',{'lean':{'max_heartbeats':value}})
                with self.subTest(value=value),patch.object(runtime_config,'CORE',root),self.assertRaises(ValueError):
                    runtime_config.native_heartbeats()
            ir.write(root/'config.json',{'lean':{'max_heartbeats':20000000}})
            with patch.object(runtime_config,'CORE',root):self.assertEqual(runtime_config.native_heartbeats(),20000000)

    def test_real_lean_reads_20m_and_shorter_call_deadline_is_recorded(self):
        with tempfile.TemporaryDirectory(prefix='native-limit-test-') as raw:
            work=Path(raw);(work/'output').mkdir()
            path=work/'output/Policy.lean'
            path.write_text('import Lean\nopen Lean Elab Command\nrun_cmd logInfo m!"actualHeartbeats={maxHeartbeats.get (← getOptions)}"\n')
            result=pilot_common.run_lean(path,work,timeout=20)
            self.assertEqual(result['exit_code'],0,result)
            self.assertIn('actualHeartbeats=20000000',result['stdout'])
            self.assertEqual(result['native_limits'],{'timeout_seconds':20,'max_heartbeats':20000000})

    def test_real_lean_deadline_reaps_process_and_preserves_policy(self):
        with tempfile.TemporaryDirectory(prefix='native-limit-timeout-') as raw:
            work=Path(raw);(work/'output').mkdir()
            path=work/'output/Slow.lean'
            path.write_text('import Lean\n#eval IO.sleep 5000\n')
            result=pilot_common.run_lean(path,work,timeout=.05)
            self.assertEqual(result['exit_code'],124,result)
            self.assertTrue(result['timed_out'])
            self.assertEqual(result['native_limits'],{'timeout_seconds':.05,'max_heartbeats':20000000})
            self.assertEqual(result['timeout_scope'],'native_call')


if __name__=='__main__':unittest.main()
