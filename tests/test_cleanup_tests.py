"""Owned-run cleanup with real neutral processes; no model execution."""
import harness_support
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
import cleanup as c
import jobs
import run_resources
import execution_state
from execution_state import identity
from harness_support import PROFILES

class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.problem=self.root/'paper/proof.md';self.problem.parent.mkdir();self.problem.write_text('Preserved original proof')
        self.job=jobs.prepare(self.problem,track='nl0',profiles=PROFILES)
        self.output=Path(self.job['root']);self.processes=[];self.workspaces=[]
    def tearDown(self):
        for p in self.processes:
            if p.stdin:p.stdin.close()
            if p.poll() is None:p.kill()
            p.wait(timeout=5)
        for p in self.workspaces:
            if p.exists():shutil.rmtree(p)
        self.tmp.cleanup()
    def start_owner(self,stubborn=False):
        ready=self.output/'ready.json'
        script=("import sys,time,json,signal,subprocess,tempfile;from pathlib import Path;sys.path.insert(0,"+repr(str(CORE/'nl0/scripts'))+");"
            "from run_resources import register_workspace,register_child;from execution_state import identity;"
            "logs=Path("+repr(str(self.output))+ ");work=Path(tempfile.mkdtemp(prefix='yui-cleanup-control-'));register_workspace(work,logs);"
            "child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()']);register_child(work,child,'neutral-child');"
            +( "signal.signal(signal.SIGTERM,signal.SIG_IGN);" if stubborn else "")+
            "(logs/'case-process.json').write_text(json.dumps({'schema_version':'yui-owned-process-1','process':identity(__import__('os').getpid())}));"
            "from execution_state import atomic;atomic(logs/'ready.json',{'work':str(work),'child':child.pid});sys.stdin.buffer.read()")
        p=subprocess.Popen([sys.executable,'-B','-c',script],stdin=subprocess.PIPE,start_new_session=True);self.processes.append(p)
        deadline=time.monotonic()+5
        while not ready.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        self.assertTrue(ready.is_file());row=json.loads(ready.read_text());self.workspaces.append(Path(row['work']))
        return p,row
    def clean(self,**kwargs):return c.clean(outputs=[self.output],**kwargs)

    def idle_process(self,cwd=None):
        process=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()','app-server'],
                                 stdin=subprocess.PIPE,start_new_session=True,cwd=cwd)
        self.processes.append(process)
        return process

    def test_preview_then_stop_real_owner_and_child_preserving_inputs_and_unrelated_process(self):
        owner,row=self.start_owner()
        unrelated=self.idle_process()
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

    def copied_workspace(self):
        import tempfile
        work=Path(tempfile.mkdtemp(prefix='yui-cleanup-copy-')).resolve();self.workspaces.append(work)
        original=self.output/'assembly/candidate/native-workspaces'
        program='from pathlib import Path;import sys;sys.path.insert(0,'+repr(str(CORE/'nl0/scripts'))+');from run_resources import register_workspace;register_workspace(Path(sys.argv[1]),Path(sys.argv[2]))'
        subprocess.run([sys.executable,'-B','-c',program,str(work),str(original)],check=True)
        source=next((original/'resources').glob('workspace-*'))
        copy=self.output/'audit-b/native-workspaces/resources'/source.name
        copy.parent.mkdir(parents=True);shutil.copyfile(source,copy)
        return work,source,copy

    def test_released_assembly_copy_uses_its_exact_same_run_original(self):
        work,source,copy=self.copied_workspace();shutil.rmtree(work)
        self.assertEqual(c.inventory(CORE,[self.output])['errors'],[])
        self.assertEqual(self.clean(apply=True,grace=0)['status'],'CLEANED')
        self.assertFalse(self.output.exists())

    def test_live_changed_missing_and_foreign_workspace_copies_block_cleanup(self):
        work,source,copy=self.copied_workspace()
        def errors():return c.inventory(CORE,[self.output])['errors']
        self.assertTrue(errors())
        shutil.rmtree(work)
        self.assertEqual(errors(),[])
        original=source.read_bytes()
        copy.write_text('{}');self.assertTrue(errors())
        copy.write_bytes(original);source.unlink();self.assertTrue(errors())
        source.write_bytes(original)
        row=json.loads(original);row['logs']=str(self.root/'foreign')
        copy.write_text(json.dumps(row));self.assertTrue(errors())
        self.assertEqual(self.clean(apply=True,grace=0)['status'],'BLOCKED')
        self.assertTrue(copy.is_file())

    def test_cwd_discovery_batches_real_candidates_and_preserves_unrelated_process(self):
        work=self.root/'workspace with spaces'
        (work/'input').mkdir(parents=True)
        owner=self.idle_process(work/'input')
        unrelated=self.idle_process(self.root)
        table=c.process_table()
        pids=[owner.pid,unrelated.pid]
        errors=[]
        with patch.object(c.subprocess,'run',wraps=subprocess.run) as query:
            self.assertEqual(c.workspace_cwd_pids(pids,[work],table,errors),{owner.pid})
        query.assert_called_once()
        self.assertEqual(errors,[])
        self.assertIsNone(unrelated.poll())

    def test_incomplete_cwd_query_preserves_uncertainty_for_same_live_identity(self):
        row={'pid':41,'pgid':41,'started':'previous start','stat':'S'}
        exited={**row,'pid':42,'pgid':42}
        table={41:row,42:exited}
        errors=[]
        with patch.object(c.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'')), \
                patch.object(c,'process_table',return_value={41:row}):
            self.assertEqual(c.workspace_cwd_pids([41,42],[],table,errors),set())
        self.assertEqual(errors,['Unconfirmed working directory for live process 41'])

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
        unrelated=self.idle_process()
        row=identity(unrelated.pid);row['started']='expired identity'
        (self.output/'case-process.json').write_text(json.dumps({'schema_version':'yui-owned-process-1','process':row}))
        self.assertEqual(self.clean(apply=True,grace=0)['status'],'CLEANED')
        self.assertIsNone(unrelated.poll())

    def test_orphan_group_without_member_identity_blocks_manual_deletion(self):
        owner,row=self.start_owner()
        child=identity(row['child'])
        # Emulate historical records that knew only the leader, not its helper.
        for path in (self.output/'resources').glob('process-*.json'):path.unlink()
        owner.terminate();owner.wait(timeout=5)
        try:
            result=self.clean(apply=True,grace=0)
            self.assertEqual(result['status'],'BLOCKED',result)
            self.assertTrue(self.output.exists());self.assertTrue(Path(row['work']).exists())
            self.assertTrue(execution_state.same_process(child))
        finally:
            if execution_state.same_process(child):os.kill(child['pid'],9)

    def test_saved_group_members_allow_manual_cleanup_after_leader_exit(self):
        owner,row=self.start_owner()
        record=execution_state.capture_process(owner,private_group=True)
        child=identity(row['child'])
        (self.output/'case-process.json').write_text(json.dumps({'schema_version':'yui-owned-process-1','process':record}))
        for path in (self.output/'resources').glob('process-*.json'):path.unlink()
        owner.terminate();owner.wait(timeout=5)
        try:
            self.assertEqual(self.clean(apply=True,grace=.05)['status'],'CLEANED')
            self.assertFalse(self.output.exists());self.assertFalse(Path(row['work']).exists())
            table=c.process_table()
            self.assertFalse(c.matching(child,table))
        finally:
            if execution_state.same_process(child):os.kill(child['pid'],9)

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
