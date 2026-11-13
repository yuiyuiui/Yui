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

    def test_whole_file_starts_at_thirty_and_increases_by_fifteen_to_sixty(self):
        self.assertEqual(lean_limits.limits('whole_file'), (1800, 900, 3600))
        self.assertEqual(lean_limits.decision(1800, 'workload_only', kind='whole_file'), ('retry', 2700))
        self.assertEqual(lean_limits.decision(2700, 'workload_only', kind='whole_file'), ('retry', 3600))
        self.assertEqual(lean_limits.decision(3600, 'workload_only', kind='whole_file'), ('limit', 3600))

    def test_whole_file_code_repair_does_not_increase_time(self):
        for seconds in (1800, 2700, 3600):
            self.assertEqual(lean_limits.decision(seconds, 'code_issue', kind='whole_file'), ('repair', seconds))
            self.assertEqual(lean_limits.decision(seconds, 'uncertain', kind='whole_file'), ('inspect', seconds))

    def test_whole_file_cannot_exceed_sixty_or_a_shorter_ceiling(self):
        with self.assertRaises(ValueError):
            lean_limits.decision(3601, 'workload_only', kind='whole_file')
        self.assertEqual(lean_limits.decision(1800, 'workload_only', ceiling=2000, kind='whole_file'), ('limit', 1800))


if __name__ == '__main__':
    unittest.main()
