"""Independent finite process scheduling; executors below are synthetic controls."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
CORE=Path(__file__).resolve().parents[1]
for path in (CORE/'scripts',CORE/'translation/scripts'):sys.path.insert(0,str(path))
import jobs
import queue_controller as q
from test_job_entry import PROFILES

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

    def test_three_actual_independent_processes_finish_with_nonpass_without_retry(self):
        selected=[self.job(i) for i in range(3)]
        def launch(job_file,out):
            script=("import json,time,os;from pathlib import Path; p=Path("+repr(str(out))+");"
                "(p/'started').write_text(str(time.monotonic()));time.sleep(.3);"
                "(p/'case-result.json').write_text(json.dumps({'result':{'status':'SYNTHETIC_NONPASS','pid':os.getpid()}}))")
            return subprocess.Popen([sys.executable,'-B','-c',script],start_new_session=True)
        with patch.object(q,'launch_case',side_effect=launch) as called:
            result=q.serve(selected,case_concurrency=3)
        self.assertEqual(called.call_count,3);self.assertEqual(len({r['pid'] for r in result.values()}),3)
        starts=[float((Path(j['root'])/'started').read_text()) for j in selected]
        self.assertLess(max(starts)-min(starts),.3)
        for job in selected:
            final=json.loads((Path(job['root'])/'batch-result.json').read_text())
            self.assertFalse(final['all_cases_accepted']);self.assertTrue(final['children_exited'])

    def test_pending_cancellation_does_not_launch_or_cancel_another_case(self):
        selected=[self.job(i) for i in range(2)];q.cancel_batch([selected[0]['root']])
        def launch(job_file,out):
            script="import json;from pathlib import Path;p=Path("+repr(str(out))+");(p/'case-result.json').write_text(json.dumps({'result':{'status':'SYNTHETIC_NONPASS'}}))"
            return subprocess.Popen([sys.executable,'-B','-c',script],start_new_session=True)
        with patch.object(q,'launch_case',side_effect=launch) as called:
            result=q.serve(selected,case_concurrency=1)
        self.assertEqual(called.call_count,1)
        self.assertEqual(result[selected[0]['id']]['status'],'CANCELLED')
        self.assertEqual(result[selected[1]['id']]['status'],'SYNTHETIC_NONPASS')

if __name__=='__main__':unittest.main()
