"""Real process-family regressions; no model, production worker or foreign signal."""
import harness_support
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import execution_state as execution


class GroupCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yui-group-control-')
        self.root = Path(self.temp.name)
        self.recorder = execution.Recorder(self.root/'run', 'synthetic-family', {})
        self.parents = []
        self.children = []

    def tearDown(self):
        for child in self.children:
            if execution.same_process(child):
                try: os.kill(child['pid'], signal.SIGKILL)
                except ProcessLookupError: pass
        for process in self.parents:
            if process.poll() is None: process.kill()
            process.wait(timeout=3)
        if not self.recorder.done.is_set(): self.recorder.close('CANCELLED')
        self.temp.cleanup()

    def family(self, *, resistant=False):
        ready = self.root/('ready-'+str(len(self.parents))+'.json')
        child = ('import os,sys,time,signal,json;from pathlib import Path;'
                 'signal.signal(signal.SIGTERM,signal.SIG_IGN if sys.argv[2]=="yes" else signal.SIG_DFL);'
                 'Path(sys.argv[1]).write_text(json.dumps({"pid":os.getpid()}));time.sleep(60)')
        parent = ('import subprocess,sys,time;'
                  'subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2],sys.argv[3]]);time.sleep(60)')
        process = subprocess.Popen([sys.executable, '-B', '-c', parent, child, str(ready),
                                    'yes' if resistant else 'no'], start_new_session=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.parents.append(process)
        until = time.monotonic()+5
        while not ready.exists() and time.monotonic() < until: time.sleep(.01)
        self.assertTrue(ready.exists())
        member = execution.identity(json.loads(ready.read_text())['pid'])
        self.assertIsNotNone(member)
        self.children.append(member)
        self.recorder.register_process(process, 'synthetic-family')
        return process, member

    def live(self, record):
        result = subprocess.run(['ps', '-p', str(record['pid']), '-o', 'stat='],
                                capture_output=True, text=True, timeout=2)
        return bool(result.stdout.strip() and not result.stdout.strip().startswith('Z'))

    def test_exited_leader_does_not_hide_registered_surviving_child(self):
        parent, child = self.family()
        parent.terminate(); parent.wait(timeout=3)
        self.assertTrue(self.live(child))
        self.assertTrue(self.recorder.stop_process(parent))
        self.assertFalse(self.live(child))
        self.recorder.close('CANCELLED')
        self.assertEqual(self.recorder.state['cancellation']['cleanup'], 'CONFIRMED_NO_OWNED_PROCESSES')

    def test_completed_pid_only_child_does_not_become_unconfirmed_cleanup(self):
        for private in (False,True):
            with self.subTest(private_group=private):
                child=subprocess.Popen([sys.executable,'-B','-c','pass'],start_new_session=private)
                self.parents.append(child);child.wait(timeout=3)
                self.recorder.register_process(child,'synthetic-already-reaped-child',private_group=private)
                self.assertTrue(self.recorder.stop_process(child))
        self.recorder.close('CANCELLED')
        self.assertEqual(self.recorder.state['cancellation']['cleanup'],'CONFIRMED_NO_OWNED_PROCESSES')

    def test_term_exits_parent_but_resistant_child_requires_group_followup(self):
        parent, child = self.family(resistant=True)
        self.assertTrue(self.recorder.stop_process(parent))
        self.assertFalse(self.live(child))
        self.assertTrue(self.recorder.stop_process(parent), 'Repeated cleanup must remain idempotent')

    def test_close_inspects_exited_handles_and_foreign_bystander_survives(self):
        parent, child = self.family()
        other = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(60)'],
                                 start_new_session=True)
        self.parents.append(other)
        parent.terminate(); parent.wait(timeout=3)
        self.recorder.close('CANCELLED')
        self.assertFalse(self.live(child))
        self.assertIsNone(other.poll())

    def test_lost_process_query_cannot_confirm_empty_exited_group(self):
        parent, child = self.family()
        parent.terminate(); parent.wait(timeout=3)
        with patch.object(execution.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ps', 2)):
            confirmed = self.recorder.stop_process(parent)
        self.assertFalse(confirmed)
        self.assertTrue(self.live(child))

    def test_unrecognized_orphan_is_reported_without_an_unproven_signal(self):
        parent, child = self.family()
        parent.terminate();parent.wait(timeout=3)
        self.recorder.state['processes'][str(parent.pid)].pop('group_members',None)
        self.recorder.process_finished(parent);self.recorder.flush(force=True)
        with patch.object(execution.os,'kill',side_effect=AssertionError('Unproven orphan must not be signalled')):
            self.assertFalse(self.recorder.stop_process(parent))
            # A private leader first captured after exit must still inspect its group.
            late=execution.capture_process(parent,private_group=True)
            self.assertFalse(execution.terminate_owned(parent,late))
        inspected=execution.inspect(self.recorder.root)
        self.assertEqual(len(inspected['inspection']['residual_owned_processes']),1)
        self.assertTrue(self.live(child))

    def test_reused_group_leader_identity_does_not_signal_a_foreign_group(self):
        other=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'],start_new_session=True)
        self.parents.append(other)
        record=execution.capture_process(other,private_group=True)
        record['started']='Mon Jan 1 00:00:00 1990';record['group_members']=[]
        class ExitedOldHandle:
            def poll(self):return 0
        with patch.object(execution.os,'kill',side_effect=AssertionError('Reused group is foreign')):
            self.assertTrue(execution.terminate_owned(ExitedOldHandle(),record))
        self.assertIsNone(other.poll())

    def test_nonleader_cleanup_signals_only_its_own_pid_in_a_shared_group(self):
        own=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'])
        bystander=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'])
        self.parents.extend([own,bystander])
        self.recorder.register_process(own,'synthetic-shared-group-child')
        self.assertNotEqual(os.getpgid(own.pid),own.pid)
        self.assertTrue(self.recorder.stop_process(own))
        self.assertIsNone(bystander.poll())

    def test_foreign_reused_nonleader_pid_is_not_reported_as_an_old_owned_process(self):
        bystander=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'])
        self.parents.append(bystander)
        record=execution.capture_process(bystander)
        record['started']='Mon Jan 1 00:00:00 1990'
        members,authorized=execution.remaining_processes(record,execution.process_table())
        self.assertFalse(members);self.assertTrue(authorized)
        self.assertIsNone(bystander.poll())

    def test_standalone_stage_refuses_workspace_deletion_if_group_ownership_is_unknown(self):
        from clean_stage import ArtifactStage
        parent,child=self.family()
        record=dict(self.recorder.state['processes'][str(parent.pid)])
        record.pop('group_members',None)
        parent.terminate();parent.wait(timeout=3)
        stage=ArtifactStage(self.root/'standalone-stage','Synthetic resource control.',phase='control',library=False)
        stage.proc=parent;stage.process_owner=record
        try:
            with self.assertRaisesRegex(RuntimeError,'cleanup unconfirmed'):
                stage.release_resources('USER_CANCELLED')
            self.assertTrue(stage.work.exists());self.assertTrue(self.live(child))
        finally:
            if execution.same_process(child):os.kill(child['pid'],signal.SIGKILL)
            until=time.monotonic()+3
            while self.live(child) and time.monotonic()<until:time.sleep(.01)
            stage.release_resources('USER_CANCELLED')


if __name__ == '__main__': unittest.main()
