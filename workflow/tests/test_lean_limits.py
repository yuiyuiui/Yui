"""The compiler keeps its configured, caller and stage limits."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'blocks'))
import lean_limits


class LeanLimits(unittest.TestCase):
    def test_native_and_probe_deadlines(self):
        self.assertEqual(lean_limits.allowance(1200,None),(1200,False))
        self.assertEqual(lean_limits.allowance(1200,lean_limits.PROBE_SECONDS),(60,False))
        self.assertEqual(lean_limits.allowance(1200,60,20),(20,True))

    def test_whole_file_uses_its_configured_limit(self):
        self.assertEqual(lean_limits.allowance(lean_limits.WHOLE_FILE_SECONDS,None),(1800,False))
        self.assertEqual(lean_limits.allowance(1800,60),(60,False))
        self.assertEqual(lean_limits.allowance(None,None),(None,False))


if __name__=='__main__':
    unittest.main()
