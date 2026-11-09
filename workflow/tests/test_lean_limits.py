"""Independent examples of the private native-check contract inside translate."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'blocks'))
import lean_limits


class LeanLimits(unittest.TestCase):
    def test_only_volume_moves_up_one_rung(self):
        actual = []
        seconds = 360
        for _ in range(5):
            action, seconds = lean_limits.decision(seconds, 'workload_only')
            actual.append((action, seconds))
        self.assertEqual(actual, [('retry', 720), ('retry', 1080), ('retry', 1440),
                                  ('retry', 1800), ('limit', 1800)])

    def test_fix_or_inspect_at_current_limit(self):
        for seconds in (360, 720, 1080, 1440, 1800):
            self.assertEqual(lean_limits.decision(seconds, 'code_issue'), ('repair', seconds))
            self.assertEqual(lean_limits.decision(seconds, 'uncertain'), ('inspect', seconds))

    def test_stop_for_a_shorter_explicit_ceiling(self):
        self.assertEqual(lean_limits.decision(360, 'workload_only', ceiling=400), ('limit', 360))


if __name__ == '__main__':
    unittest.main()
