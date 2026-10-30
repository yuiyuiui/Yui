"""An incomplete mock must fail before any live model carrier can start."""
import harness_support
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from clean_stage import ArtifactStage


class OfflineGuardTests(unittest.TestCase):
    def test_unmocked_entry_cannot_launch_or_pause_a_real_model_carrier(self):
        with tempfile.TemporaryDirectory() as raw:
            stage=ArtifactStage(Path(raw)/'stage','Synthetic missed-mock regression.',phase='control',library=False)
            try:
                with patch.object(stage,'start_relay') as relay:
                    with self.assertRaises(harness_support.LiveModelAttemptBlocked):stage.execute()
                relay.assert_not_called();self.assertIsNone(stage.proc)
                self.assertEqual(stage.api_calls,0)
                self.assertFalse((stage.work/'state/auth.json').exists())
                self.assertFalse((stage.logs/'error-state.json').exists())
            finally:stage.release_resources('USER_CANCELLED');shutil.rmtree(stage.work,ignore_errors=True)


if __name__=='__main__':unittest.main()
