"""Owned-run cleanup with real neutral processes; no model execution."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
CORE=Path(__file__).resolve().parents[1]
for path in (CORE/'scripts',CORE/'translation/scripts'):sys.path.insert(0,str(path))
import cleanup as c
import jobs
import run_resources
from execution_state import identity
from test_job_entry import PROFILES

class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.problem=self.root/'paper/proof.md';self.problem.parent.mkdir();self.problem.write_text('Preserved original proof')
        self.job=jobs.prepare(self.problem,track='nl0',profiles=PROFILES)
        self.output=Path(self.job['root']);self.processes=[];self.workspaces=[]
    def tearDown(self):
        for p in self.processes:
            if p.poll() is None:p.kill()
            p.wait(timeout=5)
        for p in self.workspaces:
            if p.exists():shutil.rmtree(p)
        self.tmp.cleanup()
    def start_owner(self,stubborn=False):
        ready=self.output/'ready.json'
        script=("import sys,time,json,signal,subprocess,tempfile;from pathlib import Path;sys.path.insert(0,"+repr(str(CORE/'scripts'))+");"
            "from run_resources import register_workspace,register_child;from execution_state import identity;"
            "logs=Path("+repr(str(self.output))+ ");work=Path(tempfile.mkdtemp(prefix='yui-cleanup-control-'));register_workspace(work,logs);"
            "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);register_child(work,child,'neutral-child');"
            +( "signal.signal(signal.SIGTERM,signal.SIG_IGN);" if stubborn else "")+
            "(logs/'case-process.json').write_text(json.dumps({'schema_version':'yui-owned-process-1','process':identity(__import__('os').getpid())}));"
            "(logs/'ready.json').write_text(json.dumps({'work':str(work),'child':child.pid}));time.sleep(60)")
        p=subprocess.Popen([sys.executable,'-B','-c',script],start_new_session=True);self.processes.append(p)
        deadline=time.monotonic()+5
        while not ready.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        self.assertTrue(ready.is_file());row=json.loads(ready.read_text());self.workspaces.append(Path(row['work']))
        return p,row
    def clean(self,**kwargs):return c.clean(outputs=[self.output],**kwargs)

    def test_preview_then_stop_real_owner_and_child_preserving_inputs_and_unrelated_process(self):
        owner,row=self.start_owner()
        unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True);self.processes.append(unrelated)
        self.assertEqual(self.clean()['status'],'PREVIEW');self.assertIsNone(owner.poll())
        result=self.clean(apply=True,grace=.3);self.assertEqual(result['status'],'CLEANED',result)
        owner.wait(timeout=5);self.assertIsNone(unrelated.poll())
        self.assertFalse(self.output.exists());self.assertFalse(Path(row['work']).exists())
        self.assertEqual(self.problem.read_text(),'Preserved original proof')
        self.assertTrue((CORE/'SKILL.md').is_file())

    def test_bad_workspace_marker_blocks_deletion(self):
        owner,row=self.start_owner();(Path(row['work'])/run_resources.MARKER).write_text('{}')
        result=self.clean(apply=True,grace=0)
        self.assertEqual(result['status'],'BLOCKED');self.assertTrue(self.output.exists())
        # Teardown owns both real process handles independently of the bad marker.
        table=c.process_table()
        for pid in (row['child'],):
            if pid in table:os.kill(pid,9)

    def test_unmarked_input_and_symlink_cannot_be_removed(self):
        with self.assertRaises(ValueError):c.clean(outputs=[self.problem.parent],apply=True)
        alias=self.root/'alias';alias.symlink_to(self.output,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):c.clean(outputs=[alias],apply=True)
        self.assertTrue(self.problem.is_file())

    def test_unconfirmed_shutdown_preserves_evidence(self):
        owner,row=self.start_owner()
        with patch.object(c,'signal_owned'):
            result=self.clean(apply=True,grace=0)
        self.assertEqual(result['status'],'BLOCKED');self.assertIn(owner.pid,result['residual_pids'])
        self.assertTrue((self.output/'resources').is_dir())
        for pid in (row['child'],):
            if pid in c.process_table():os.kill(pid,9)

    def test_sigterm_ignoring_owner_is_force_stopped(self):
        owner,_=self.start_owner(stubborn=True)
        self.assertEqual(self.clean(apply=True,grace=.05)['status'],'CLEANED')
        owner.wait(timeout=5);self.assertIsNotNone(owner.returncode)

    def test_expired_pid_identity_does_not_target_unrelated_process(self):
        unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True);self.processes.append(unrelated)
        row=identity(unrelated.pid);row['started']='expired identity'
        (self.output/'case-process.json').write_text(json.dumps({'schema_version':'yui-owned-process-1','process':row}))
        self.assertEqual(self.clean(apply=True,grace=0)['status'],'CLEANED')
        self.assertIsNone(unrelated.poll())

    def test_cleanup_lock_blocks_new_stage_and_unknown_lock_is_preserved(self):
        lock=self.output/'.cleanup.lock';lock.write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'cleanup'):run_resources.check_cleanup_lock(self.output/'stage')
        with self.assertRaises(ValueError):self.clean(apply=True)
        self.assertTrue(lock.is_file())

    def test_cleanup_is_allowed_after_original_input_changes(self):
        self.problem.write_text('User revised their own proof')
        self.assertEqual(self.clean(apply=True,grace=0)['status'],'CLEANED')
        self.assertEqual(self.problem.read_text(),'User revised their own proof')

    def test_no_implicit_global_cleanup(self):
        with self.assertRaisesRegex(ValueError,'Explicit'):c.clean(apply=True)

if __name__=='__main__':unittest.main()
