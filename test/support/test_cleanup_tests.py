"""Real-process reclamation and deletion-boundary tests; no model calls."""
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

import cleanup_tests as c
from execution_state import identity
from run_resources import MARKER, register_workspace


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)/'repo'
        self.output = self.repo/'test/results/neutral/stage'
        self.output.mkdir(parents=True)
        self.input = self.repo/'test/neutral/problem.md'
        self.input.parent.mkdir(); self.input.write_text('fixed mathematical input')
        self.code = self.repo/'rigorous-proof/scripts/keep.py'
        self.code.parent.mkdir(parents=True); self.code.write_text('runtime')
        self.processes = []; self.workspaces = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        for work in self.workspaces:
            __import__('shutil').rmtree(work, ignore_errors=True)
        self.tmp.cleanup()

    def start_owner(self):
        helper = self.repo/'owner.py'
        scripts = c.REPO/'rigorous-proof/scripts'
        helper.write_text('''import sys,signal,subprocess,tempfile,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from run_resources import register_workspace,register_child
from execution_state import atomic
out=Path(sys.argv[2]);work=Path(tempfile.mkdtemp(prefix='yui-cleanup-control-'))
register_workspace(work,out)
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'],start_new_session=True)
register_child(work,child,'synthetic-worker')
atomic(out/'ready.json',{'work':str(work),'child':child.pid})
def finish(*_):
 child.terminate();child.wait();raise SystemExit(0)
signal.signal(signal.SIGTERM,finish)
while True:time.sleep(.1)
''')
        process = subprocess.Popen([sys.executable, '-B', str(helper), str(scripts), str(self.output)],
                                   start_new_session=True)
        self.processes.append(process)
        deadline = time.monotonic()+5
        while not (self.output/'ready.json').exists():
            if process.poll() is not None or time.monotonic()>deadline:
                self.fail('Ownership helper did not initialize')
            time.sleep(.02)
        row = json.loads((self.output/'ready.json').read_text())
        self.workspaces.append(Path(row['work']))
        return process, row

    def test_preview_then_stop_real_owner_child_and_delete_only_outputs(self):
        owner, row = self.start_owner()
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(120)'])
        self.processes.append(unrelated)
        stale = {**identity(unrelated.pid), 'started': 'different OS start identity'}
        (self.output/'case-process.json').write_text(json.dumps({
            'schema_version':'yui-owned-process-1','process':stale}))
        preview = c.clean(self.repo)
        self.assertEqual(preview['status'], 'PREVIEW')
        self.assertIsNone(owner.poll())
        self.assertTrue(self.output.exists())
        result = c.clean(self.repo, apply=True, grace=.2)
        self.assertEqual(result['status'], 'CLEANED', result)
        owner.wait(timeout=5)
        self.assertNotIn(row['child'], {p for p,r in c.process_table().items() if not r['stat'].startswith('Z')})
        self.assertIsNone(unrelated.poll())
        self.assertFalse(Path(row['work']).exists())
        self.assertFalse((self.repo/'test/results').exists())
        self.assertEqual(self.input.read_text(), 'fixed mathematical input')
        self.assertEqual(self.code.read_text(), 'runtime')
        self.assertFalse((self.repo/'test/.cleanup.lock').exists())
        self.assertEqual(c.clean(self.repo, apply=True)['status'], 'CLEANED')

    def test_bad_workspace_marker_blocks_deletion(self):
        work = Path(tempfile.mkdtemp(prefix='yui-cleanup-control-')); self.workspaces.append(work)
        register_workspace(work, self.output)
        (work/MARKER).write_text('{}')
        result = c.clean(self.repo, apply=True)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertTrue(self.output.exists()); self.assertTrue(work.exists())

    def test_selected_cleanup_preserves_frozen_source_and_rejects_outside(self):
        preserved = self.repo/'test/results/accepted-nl0/stage'
        preserved.mkdir(parents=True)
        (preserved/'audit-a.json').write_text('frozen receipt')
        result = c.clean(self.repo, apply=True, outputs=[self.output.parent])
        self.assertEqual(result['status'], 'CLEANED', result)
        self.assertFalse(self.output.exists())
        self.assertEqual((preserved/'audit-a.json').read_text(), 'frozen receipt')
        with self.assertRaisesRegex(ValueError, 'must be a child'):
            c.clean(self.repo, apply=True, outputs=[self.repo/'test'])

    def test_output_root_symlink_cannot_delete_an_outside_directory(self):
        __import__('shutil').rmtree(self.repo/'test/results')
        outside = Path(self.tmp.name)/'outside'; outside.mkdir()
        (outside/'keep').write_text('unrelated')
        (self.repo/'test/results').symlink_to(outside, target_is_directory=True)
        self.assertEqual(c.clean(self.repo, apply=True)['status'], 'BLOCKED')
        self.assertEqual((outside/'keep').read_text(), 'unrelated')

    def test_unconfirmed_shutdown_keeps_ownership_and_outputs(self):
        owner, _ = self.start_owner()
        with patch.object(c, 'signal_owned'):
            result = c.clean(self.repo, apply=True, grace=0)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertIn(owner.pid, result['residual_pids'])
        self.assertTrue((self.output/'resources').is_dir())
        owner.terminate(); owner.wait(timeout=5)

    def test_single_digit_day_start_identity_is_normalized(self):
        record = {'pid':123,'pgid':123,'started':'Sat Nov  7 01:02:03 2026'}
        table = {123:{**record,'started':'Sat Nov 7 01:02:03 2026','stat':'S'}}
        self.assertTrue(c.matching(record, table))

    def test_sigterm_ignoring_owned_worker_is_force_stopped(self):
        ready = self.output/'stubborn-ready'
        process = subprocess.Popen([sys.executable, '-c',
            'import signal,time,pathlib,sys;signal.signal(signal.SIGTERM,signal.SIG_IGN);'
            'pathlib.Path(sys.argv[1]).touch();time.sleep(120)', str(ready)], start_new_session=True)
        self.processes.append(process)
        deadline = time.monotonic()+5
        while not ready.exists():
            if time.monotonic()>deadline:self.fail('Worker did not initialize')
            time.sleep(.02)
        (self.output/'case-process.json').write_text(json.dumps({
            'schema_version':'yui-owned-process-1','process':identity(process.pid)}))
        result = c.clean(self.repo, apply=True, grace=.1)
        self.assertEqual(result['status'], 'CLEANED', result)
        self.assertEqual(process.wait(timeout=5), -signal.SIGKILL)

    def test_unknown_or_live_cleanup_lock_is_preserved(self):
        lock = self.repo/'test/.cleanup.lock'; lock.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'ownership is unknown'):
            c.clean(self.repo, apply=True)
        self.assertTrue(self.output.exists()); self.assertTrue(lock.exists())

    def test_new_test_stage_is_rejected_while_cleanup_holds_lock(self):
        from run_resources import check_cleanup_lock, REPO
        with patch('run_resources.REPO', self.repo), patch('run_resources.GENERATED', (self.repo/'test/results',)):
            with c.cleanup_lock(self.repo):
                with self.assertRaisesRegex(RuntimeError, 'cleanup is in progress'):
                    check_cleanup_lock(self.output)


if __name__ == '__main__':
    unittest.main()
