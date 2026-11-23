"""Native deadlines return directly to the requesting author."""
import harness_support
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import lean_timeout_policy as policy
import pilot_common


WALL = dict(exit_code=124, stdout='partial compiler output', stderr='raw compiler diagnostic',
            timed_out=True, error_kind='LEAN_TIMEOUT', timeout_scope='native_call')


class TranslationTimeouts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = self.root/'output/Proof.lean'
        self.source.parent.mkdir()
        self.source.write_text('example : True := True.intro\n')

    def test_wall_timeout_returns_raw_diagnostic_and_same_source_can_retry(self):
        actual = pilot_common._run_lean
        attempts=[]
        def compile_once(file,work,**options):
            attempts.append(options['timeout'])
            if len(attempts)==1:return WALL.copy()
            return actual(file,work,**options)
        with patch.object(pilot_common,'_run_lean',side_effect=compile_once):
            failure=pilot_common.run_lean(self.source,self.root)
            self.assertEqual(failure,WALL)
            self.assertEqual(attempts,[1200])
            accepted=pilot_common.run_lean(self.source,self.root)
        self.assertEqual(attempts,[1200,1200])
        self.assertTrue(pilot_common.native_succeeded(accepted),accepted)

    def test_type_probe_and_explicit_short_deadline_stay_bounded(self):
        stage=SimpleNamespace(started=time.monotonic(),timeout=7)
        with policy.stage_scope(stage), patch.object(pilot_common,'_run_lean',return_value=WALL) as native:
            pilot_common.run_lean(self.source,self.root,timeout=policy.probe_seconds())
        self.assertTrue(native.call_args.kwargs['stage_limited'])
        self.assertLessEqual(native.call_args.kwargs['timeout'],7)
        self.assertEqual(policy.allowance(policy.probe_seconds()),(60,False))

    def test_actual_compiler_wall_timeout_does_not_prevent_an_unchanged_retry(self):
        self.source.write_text('#eval IO.sleep 1600\nexample : True := True.intro\n')
        interrupted=pilot_common.run_lean(self.source,self.root,timeout=.2)
        self.assertEqual(interrupted['exit_code'],124,interrupted)
        self.assertEqual(interrupted['error_kind'],'LEAN_TIMEOUT')
        self.assertEqual(interrupted['timeout_seconds'],.2)
        rerun=pilot_common.run_lean(self.source,self.root,timeout=15)
        self.assertTrue(pilot_common.native_succeeded(rerun),rerun)
