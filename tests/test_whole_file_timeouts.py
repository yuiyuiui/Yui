"""Preserve actual whole-file resource and acceptance boundaries."""
import harness_support
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lean_timeout_policy as policy
import pilot_common
from test_translation_timeout_policy import WALL


class WholeFileTimeouts(unittest.TestCase):
    def test_whole_file_has_one_call_and_preserves_raw_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            source=root/'Proof.lean'
            source.write_text('example : True := trivial\n')
            with policy.whole_file_scope(), patch.object(pilot_common,'_run_lean',return_value=WALL) as native:
                self.assertEqual(pilot_common.run_lean(source,root),WALL)
                native.assert_called_once()
                self.assertEqual(native.call_args.kwargs['timeout'],1800)
                self.assertEqual(pilot_common.run_lean(source,root,timeout=2),WALL)
                self.assertEqual(native.call_args.kwargs['timeout'],2)
            self.assertEqual(policy.allowance(),(1200,False))

    def test_timeout_flag_cannot_be_accepted_even_with_zero_exit(self):
        for flag in ({'timed_out':True},{'cancelled':True},{'error_kind':'LEAN_TIMEOUT'}, {'error_kind':'STAGE_DEADLINE'}):
            with self.subTest(flag=flag):
                self.assertFalse(pilot_common.native_succeeded({'exit_code':0,**flag}))
        self.assertTrue(pilot_common.native_succeeded({'exit_code':0}))
