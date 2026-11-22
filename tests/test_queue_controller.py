"""Independent finite process scheduling; executors below are synthetic controls."""
import harness_support
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
CORE=Path(__file__).resolve().parents[1]
import jobs
from execution_state import Cancelled
import queue_controller as q
from harness_support import PROFILES

class QueueControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def job(self,index):
        p=self.root/f'arbitrary-{index}/proof.md';p.parent.mkdir();p.write_text('Explicit proof '+str(index))
        return jobs.prepare(p,track='nl0',profiles=PROFILES)

    def test_arbitrary_names_are_allowed_and_frozen_job_mutation_is_rejected(self):
        job=self.job(0);q.validate_job(job)
        with self.assertRaises(ValueError):q.validate_job({**job,'case':'silently changed'})

    def test_duplicate_case_output_cannot_be_dispatched(self):
        job=self.job(0)
        with self.assertRaisesRegex(ValueError,'Duplicate'):q.serve([job,job])

    def test_three_actual_nonpass_processes_pause_until_explicit_cancel_without_retry(self):
        selected=[self.job(i) for i in range(3)]
        def launch(job_file,out):
            script=("import json,time,os;from pathlib import Path; p=Path("+repr(str(out))+");"
                "(p/'started').write_text(str(time.monotonic()));time.sleep(.3);"
                "(p/'case-result.json').write_text(json.dumps({'result':{'status':'SYNTHETIC_NONPASS','pid':os.getpid()}}))")
            return subprocess.Popen([sys.executable,'-B','-c',script],start_new_session=True)
        with patch.object(q,'launch_case',side_effect=launch) as called, \
             patch('fault_control.Gate.pause',side_effect=Cancelled('Synthetic explicit user cancellation')):
            result=q.serve(selected,case_concurrency=3)
        self.assertEqual(called.call_count,3);self.assertEqual(len({r['retained_case_outcome']['pid'] for r in result.values()}),3)
        starts=[float((Path(j['root'])/'started').read_text()) for j in selected]
        self.assertLess(max(starts)-min(starts),.3)
        for job in selected:
            final=json.loads((Path(job['root'])/'batch-result.json').read_text())
            self.assertFalse(final['all_cases_accepted']);self.assertTrue(final['children_exited'])

    def test_malformed_or_unbound_stops_remain_case_process_errors_and_free_the_slot_after_cancel(self):
        selected=[self.job(i) for i in range(5)]
        payloads=['{', '[]', '{"result":[]}', '{"result":{"status":["STOPPED_BY_USER"]}}',
                  '{"job":{"sha256":"foreign"},"result":{"status":"STOPPED_BY_USER"}}']
        by_root={j['root']:payload for j,payload in zip(selected,payloads)}
        incidents=[]
        def launch(job_file,out):
            script="import sys;from pathlib import Path;Path(sys.argv[1]).write_text(sys.argv[2]);sys.exit(3)"
            return subprocess.Popen([sys.executable,'-B','-c',script,str(out/'case-result.json'),by_root[str(out)]],
                                    start_new_session=True)
        def cancel(gate,error,**kwargs):
            incidents.append((gate.stage,error['exit_code']))
            raise Cancelled('Explicit fixture cancel after inspection')
        with patch.object(q,'launch_case',side_effect=launch),patch('fault_control.Gate.pause',cancel):
            result=q.serve(selected,case_concurrency=1)
        self.assertEqual(incidents,[('case-process-exited',3)]*len(selected))
        for j in selected:
            self.assertEqual(result[j['id']]['status'],'CANCELLED')
            batch=json.loads((Path(j['root'])/'batch-result.json').read_text())
            self.assertTrue(batch['children_exited'])
            self.assertFalse(batch['all_cases_accepted'])

    def test_pending_cancellation_does_not_launch_or_cancel_another_case(self):
        selected=[self.job(i) for i in range(2)];q.cancel_batch([selected[0]['root']])
        def launch(job_file,out):
            script="import json;from pathlib import Path;p=Path("+repr(str(out))+");(p/'case-result.json').write_text(json.dumps({'result':{'status':'SYNTHETIC_NONPASS'}}))"
            return subprocess.Popen([sys.executable,'-B','-c',script],start_new_session=True)
        with patch.object(q,'launch_case',side_effect=launch) as called, \
             patch('fault_control.Gate.pause',side_effect=Cancelled('Synthetic explicit user cancellation')):
            result=q.serve(selected,case_concurrency=1)
        self.assertEqual(called.call_count,1)
        self.assertEqual(result[selected[0]['id']]['status'],'CANCELLED')
        self.assertEqual(result[selected[1]['id']]['retained_case_outcome']['status'],'SYNTHETIC_NONPASS')

    def test_unidentified_short_exit_reports_failure_and_frees_the_slot(self):
        first, second = [self.job(i) for i in range(2)]
        children, incidents = [], []
        lookup = q.identity

        def launch(job_file, out):
            if not children:
                program = 'import time;time.sleep(.08);raise SystemExit(7)'
            else:
                program = ('from pathlib import Path;import sys;'
                           'Path(sys.argv[1]).write_text(\'{"result":{"status":"CANCELLED"}}\')')
            child = subprocess.Popen([sys.executable, '-B', '-c', program, str(out/'case-result.json')],
                                     start_new_session=True)
            children.append(child)
            return child

        def miss_first(pid):
            return None if children and pid == children[0].pid else lookup(pid)

        def incident(gate, error, **options):
            incidents.append((gate.stage, error, options.get('wait_for_control', True)))

        try:
            with patch.object(q, 'launch_case', side_effect=launch), patch.object(q, 'identity', side_effect=miss_first), \
                    patch('fault_control.Gate.pause', incident):
                results = q.serve([first, second], case_concurrency=1)
            self.assertEqual(len(children), 2)
            self.assertEqual(results[first['id']]['exit_code'], 7)
            self.assertEqual(results[second['id']]['status'], 'CANCELLED')
            self.assertEqual([(stage, error['exit_code'], waits) for stage, error, waits in incidents],
                             [('case-process-exited', 7, False)])
        finally:
            for child in children:
                child.wait(timeout=5)

    def test_live_unconfirmed_child_is_fenced_while_sibling_runs(self):
        import cleanup
        first, second = [self.job(i) for i in range(2)]
        first_root = Path(first['root'])
        release = self.root/'release-child'
        children, observed = [], []
        lookup = q.identity

        def launch(job_file, out):
            self.assertTrue((out/'case-launch-pending.json').is_file())
            if out == first_root:
                program = ('import sys,time\nfrom pathlib import Path\n'
                           'while not Path(sys.argv[1]).exists(): time.sleep(.02)\n'
                           'Path(sys.argv[2]).write_text(\'{"result":{"status":"CANCELLED"}}\')')
                args = [str(release), str(out/'case-result.json')]
            else:
                observed.append(children[0].poll() is None)
                with patch.object(cleanup, 'signal_owned') as signals:
                    result = cleanup.clean(apply=True, grace=0, outputs=[first_root])
                self.assertEqual(result['status'], 'BLOCKED')
                signals.assert_not_called()
                self.assertTrue(first_root.is_dir())
                program = ('from pathlib import Path;import sys;'
                           'Path(sys.argv[1]).write_text(\'{"result":{"status":"CANCELLED"}}\');'
                           'Path(sys.argv[2]).touch()')
                args = [str(out/'case-result.json'), str(release)]
            child = subprocess.Popen([sys.executable, '-B', '-c', program, *args], start_new_session=True)
            children.append(child)
            return child

        def miss_first(pid):
            return None if children and pid == children[0].pid else lookup(pid)

        try:
            with patch.object(q, 'launch_case', side_effect=launch), patch.object(q, 'identity', side_effect=miss_first), \
                    patch.object(q, 'terminate_owned') as terminate, patch('fault_control.Gate.pause') as pause:
                results = q.serve([first, second], case_concurrency=2)
            self.assertEqual(observed, [True])
            self.assertEqual(set(results), {first['id'], second['id']})
            terminate.assert_not_called()
            pause.assert_not_called()
        finally:
            release.touch()
            for child in children:
                child.wait(timeout=5)

    def test_cleanup_never_signals_a_child_discovered_between_scans_without_identity(self):
        import cleanup
        from controller_common import write

        job = self.job(0)
        root = Path(job['root'])
        release = self.root/'release-late-child'
        signals = []
        process = None

        def signal_attempt(candidates, signal_kind):
            nonlocal process
            if signal_kind == __import__('signal').SIGTERM:
                program = ('import sys,time\nfrom pathlib import Path\n'
                           'while not Path(sys.argv[1]).exists(): time.sleep(.02)\n')
                worker = str(CORE/'nl0/scripts/case_runner.py')
                process = subprocess.Popen([sys.executable, '-B', '-c', program, str(release), worker,
                                            '--job', str(root/'job.json')], start_new_session=True)
                write(root/'case-process.json', {'schema_version':'yui-owned-process-1',
                                                 'process':{'pid':process.pid,'pgid':process.pid,'started':None}})
            signals.extend(candidates)

        try:
            with patch.object(cleanup, 'signal_owned', signal_attempt):
                result = cleanup.clean(apply=True, grace=0, outputs=[root])
            self.assertIsNotNone(process)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertNotIn(process.pid, signals)
            self.assertTrue(root.is_dir())
            self.assertIsNone(process.poll())
        finally:
            release.touch()
            if process is not None:
                process.wait(timeout=5)

if __name__=='__main__':unittest.main()
