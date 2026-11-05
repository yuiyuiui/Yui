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

if __name__=='__main__':unittest.main()
