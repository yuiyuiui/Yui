"""Automatic test cleanup under success, failure, interruption and orphan children."""
import harness_support
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import run_tests as runner
import cleanup


class AutomaticTestCleanupTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def command(self,extra=''):
        result=self.root/'result.json'
        code=('import os,json,sys,subprocess,time;from pathlib import Path;'
            'root=Path(os.environ["YUI_TEST_CLEANUP_ROOT"]);'
            'scratch=Path(os.environ["TMPDIR"]);'
            '(scratch/".lake/build").mkdir(parents=True);'
            '(scratch/".lake/build/Test.olean").write_text("disposable compiled output");'
            '(root/".hidden").write_text("test-only hidden state");'
            f'Path({str(result)!r}).write_text(json.dumps({{"root":str(root)}}));'+extra)
        return [sys.executable,'-B','-c',code],result

    def test_success_and_failure_remove_hidden_build_and_temporary_files(self):
        for status in (0,7):
            command,result=self.command(f'sys.exit({status})')
            self.assertEqual(runner.run(command=command),status)
            owned=Path(json.loads(result.read_text())['root']);self.assertFalse(owned.exists())

    def test_keyboard_and_termination_exit_cleanup(self):
        for sig in (signal.SIGINT,signal.SIGTERM):
            command,result=self.command(f'os.kill(os.getppid(),{int(sig)});time.sleep(60)')
            self.assertEqual(runner.run(command=command),128+int(sig))
            self.assertFalse(Path(json.loads(result.read_text())['root']).exists())

    def test_exception_before_child_start_cleans_owned_root(self):
        original=runner.tempfile.mkdtemp;created=[]
        def allocate(*args,**kwargs):
            path=original(*args,**kwargs);created.append(Path(path));return path
        with patch.object(runner.tempfile,'mkdtemp',side_effect=allocate),self.assertRaises(FileNotFoundError):
            runner.run(command=['/nonexistent/yui-cleanup-test-command'])
        self.assertTrue(created);self.assertTrue(all(not path.exists() for path in created))

    def test_detached_child_after_parent_exit_is_reaped_and_unrelated_survives(self):
        unrelated=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'],start_new_session=True)
        child_file=self.root/'child.json'
        try:
            code=(f'sys.path.insert(0,{str(runner.TESTS)!r});import test_resources;'
                'child=subprocess.Popen([sys.executable,"-B","-c","import time;time.sleep(60)"],start_new_session=True);'
                f'sys.path.insert(0,{str(runner.CORE/"nl0/scripts")!r});from execution_state import identity;'
                f'Path({str(child_file)!r}).write_text(json.dumps(identity(child.pid)))')
            command,result=self.command(code)
            self.assertEqual(runner.run(command=command),0)
            row=json.loads(child_file.read_text())
            self.assertFalse(cleanup.matching(row,cleanup.process_table()))
            self.assertIsNone(unrelated.poll())
        finally:
            unrelated.kill();unrelated.wait(timeout=5)

    def owned_root(self):
        root=self.root/'owned';root.mkdir()
        (root/'.test-owner.json').write_text(json.dumps({'owner':runner.owner_identity(),'root':str(root.resolve())}))
        return root

    def test_symlink_contents_and_unrelated_paths_are_preserved(self):
        root=self.owned_root();outside=self.root/'user-data';outside.mkdir()
        (outside/'keep').write_text('preserve');(root/'alias').symlink_to(outside,target_is_directory=True)
        self.assertEqual(runner.cleanup(root,{})['status'],'CLEANED')
        self.assertEqual((outside/'keep').read_text(),'preserve')
        self.assertEqual(runner.cleanup(root,{})['status'],'CLEANED')

    def test_unknown_marker_and_foreign_owner_are_rejected(self):
        root=self.owned_root();marker=root/'.test-owner.json'
        marker.unlink()
        with self.assertRaises(ValueError):runner.cleanup(root,{})
        marker.write_text(json.dumps({'owner':-1,'root':str(root)}))
        with self.assertRaises(ValueError):runner.cleanup(root,{})

    def test_reused_owner_pid_and_symlink_marker_cannot_authorize_deletion(self):
        root=self.owned_root();marker=root/'.test-owner.json';value=json.loads(marker.read_text())
        value['owner']['started']='expired';marker.write_text(json.dumps(value))
        with self.assertRaises(ValueError):runner.cleanup(root,{})
        marker.unlink();target=self.root/'foreign-marker';target.write_text(json.dumps(value))
        marker.symlink_to(target)
        with self.assertRaises(ValueError):runner.cleanup(root,{})
        self.assertTrue(target.exists());self.assertTrue(root.exists())

    def test_interrupt_during_cleanup_is_not_reported_as_success(self):
        original=runner.cleanup;command,result=self.command()
        def interrupted(*args,**kwargs):
            os.kill(os.getpid(),signal.SIGTERM)
            return original(*args,**kwargs)
        with patch.object(runner,'cleanup',side_effect=interrupted):
            self.assertEqual(runner.run(command=command),128+int(signal.SIGTERM))

    def test_reused_pid_identity_does_not_kill_unrelated_process(self):
        root=self.owned_root();process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
        try:
            row=cleanup.process_table()[process.pid];row['started']='expired'
            (root/'processes.jsonl').write_text(json.dumps(row)+'\n')
            self.assertEqual(runner.cleanup(root,{})['status'],'CLEANED')
            self.assertIsNone(process.poll())
        finally:process.kill();process.wait(timeout=5)

    def test_unconfirmed_shutdown_preserves_evidence_and_reports_failure(self):
        root=self.owned_root();process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
        row=cleanup.process_table()[process.pid];records={(row['pid'],row['started']):row}
        try:
            with patch.object(runner,'signal_owned'):
                report=runner.cleanup(root,records)
            self.assertEqual(report['status'],'CLEANUP_FAILED');self.assertTrue(root.exists())
            self.assertTrue((root/'cleanup-failure.json').is_file())
        finally:process.kill();process.wait(timeout=5)
        self.assertEqual(runner.cleanup(root,records)['status'],'CLEANED')

    def test_process_query_failure_retains_cleanup_diagnostic(self):
        root=self.owned_root()
        with patch.object(runner,'observe',side_effect=OSError('process inventory unavailable')):
            report=runner.cleanup(root,{})
        self.assertEqual(report['status'],'CLEANUP_FAILED');self.assertIsNone(report['residual_pids'])
        self.assertTrue((root/'cleanup-failure.json').exists())
        self.assertEqual(runner.cleanup(root,{})['status'],'CLEANED')

    def test_setup_failure_before_process_launch_rolls_back_empty_owned_root(self):
        original=runner.tempfile.mkdtemp;created=[]
        def allocate(*args,**kwargs):
            path=original(*args,**kwargs);created.append(Path(path));return path
        with patch.object(runner.tempfile,'mkdtemp',side_effect=allocate), \
             patch.object(runner,'owner_identity',side_effect=OSError('owner query unavailable')),self.assertRaises(OSError):
            runner.run(command=['/not-started'])
        self.assertTrue(created);self.assertTrue(all(not p.exists() for p in created))


if __name__=='__main__':unittest.main()
