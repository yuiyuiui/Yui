"""Explicit job-schema/path controls; no model or mathematical acceptance."""
from pathlib import Path
import tempfile
import subprocess
import sys
import json
import threading
import time
import unittest
from unittest.mock import patch

import queue_controller as q


class QueueControllerTests(unittest.TestCase):
    def test_jobs_keep_the_frozen_case_and_explicit_result_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);case=root/'test/results/neutral/case';case.mkdir(parents=True)
            for name in ['spec.json','nl0.json']:(case/name).write_text('{}')
            job={'id':'neutral-control','kind':'translate','case':'lie-module-irreducibility',
                 'source':'neutral/case','interface':'neutral-interface','workflow':'neutral-workflow'}
            with patch.object(q.a,'ROOT',root):
                q.validate_job(job)
                with self.assertRaisesRegex(ValueError,'exact staged case'):
                    q.validate_job({**job,'source':'../../outside'})
                with self.assertRaisesRegex(ValueError,'frozen exercise'):
                    q.validate_job({**job,'case':'a-substituted-easy-theorem'})
                with self.assertRaisesRegex(ValueError,'schema'):
                    q.validate_job({**job,'shell_command':'not-permitted'})

    def test_nl0_jobs_name_every_next_gate(self):
        job={'id':'neutral-control','kind':'nl0','case':'wave-map-energy','run':'neutral-nl0',
             'audit':'neutral-audit','interface':'neutral-interface','workflow':'neutral-workflow'}
        q.validate_job(job)
        with self.assertRaisesRegex(ValueError,'schema'):
            q.validate_job({k:v for k,v in job.items() if k!='audit'})

    def test_audit_a_only_job_has_no_lean_phase_names(self):
        job={'id':'neutral-control','kind':'nl0','case':'wave-map-energy','run':'neutral-nl0',
             'audit':'neutral-audit','stop_after':'audit_a','audit_controls':'fresh-controls'}
        q.validate_job(job)
        with self.assertRaisesRegex(ValueError,'requires an NL0/Audit A job'):
            q.validate_job({**job,'kind':'translate'})
        with self.assertRaisesRegex(ValueError,'plain unique'):
            q.validate_job({**job,'audit_controls':'../foreign-control'})

    def test_submitted_interface_gets_a_new_review_without_reauthoring(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);case=root/'test/results/neutral/case';case.mkdir(parents=True)
            for name in ['spec.json','nl0.json']:(case/name).write_text('{}')
            job={'id':'neutral-control','kind':'submitted_interface','case':'lie-module-irreducibility',
                 'source':'neutral/case','interface':'existing-interface','review':'fresh-review',
                 'workflow':'neutral-workflow','max_concurrency':5}
            with patch.object(q.a,'ROOT',root):
                q.validate_job(job)
                with self.assertRaisesRegex(ValueError,'plain unique'):
                    q.validate_job({**job,'review':'../overwrite'})

    def test_checked_interface_recovery_requires_an_explicit_real_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);case=root/'test/results/neutral/case';case.mkdir(parents=True)
            for name in ['spec.json','nl0.json']:(case/name).write_text('{}')
            job={'id':'neutral-control','kind':'checked_interface','case':'lie-module-irreducibility',
                'source':'neutral/case','interface':'neutral-interface','workflow':'neutral-workflow','candidate':1}
            with patch.object(q.a,'ROOT',root):
                q.validate_job(job)
                with self.assertRaisesRegex(ValueError,'positive candidate'):
                    q.validate_job({**job,'candidate':True})

    def run_fake_batch(self,stop):
        """Three real case processes; serial reviews and fifteen fake proof jobs."""
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);queue=root/'queue';(queue/'pending').mkdir(parents=True)
            source=root/'test/results/neutral/case';source.mkdir(parents=True)
            for name in ['spec.json','nl0.json']:(source/name).write_text('{}')
            for i,case in enumerate(sorted(q.CASES)):
                job={'id':f'control-{i}','kind':'translate','case':case,'source':'neutral/case',
                    'interface':f'interface-{i}','workflow':f'workflow-{i}','max_concurrency':5}
                (queue/'pending'/f'{i}.json').write_text(json.dumps(job))
            helper=root/'fake_case.py';scripts=q.a.CORE/'scripts';translation=q.a.CORE/'translation/scripts'
            helper.write_text('''import sys,json,time,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path[:0]=[sys.argv[4],sys.argv[5]]
import execution_state as e
import concurrency
job=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);shared=Path(sys.argv[3])
r=e.Recorder(out,job['case'],concurrency.resolve(5));budgets=concurrency.CaseBudgets(5,execution=r);b=budgets.proof
with budgets.serial:
 (shared/('review-'+job['id'])).touch()
 deadline=time.monotonic()+5
 while len(list(shared.glob('review-control-*')))<3 and time.monotonic()<deadline:r.check();time.sleep(.01)
def work(n):
 try:
  with e.activate(r,str(n)),b:
   (shared/(job['id']+'-'+str(n))).touch()
   deadline=time.monotonic()+5
   while len(list(shared.glob('control-*')))<15 and time.monotonic()<deadline:r.check();time.sleep(.01)
   if sys.argv[6]=='stop':
    while True:r.check();time.sleep(.01)
 except e.Cancelled:pass
try:
 with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(work,range(5)))
finally:
 status='CANCELLED' if r.cancelled() else 'PROOF_UNFINISHED'
 r.close(status)
 e.atomic(out/'case-result.json',{'job':job,'result':{'status':status},'concurrency':b.report(),'roles':budgets.report()})
''')
            shared=root/'barrier';shared.mkdir();handles=[];errors=[]
            def launch(job_file,out):
                out.mkdir(parents=True)
                p=subprocess.Popen([sys.executable,str(helper),str(job_file),str(out/'nl0-to-lean'),str(shared),str(scripts),str(translation),'stop' if stop else 'finish'],start_new_session=True)
                handles.append(p);return p
            def serve():
                try:q.serve(queue)
                except Exception as error:errors.append(error)
            with patch.object(q.a,'ROOT',root),patch.object(q,'launch_case',side_effect=launch):
                thread=threading.Thread(target=serve);thread.start()
                try:
                    deadline=time.monotonic()+8
                    while len(list(shared.glob('control-*')))<15 and time.monotonic()<deadline:time.sleep(.02)
                    self.assertEqual(len(list(shared.glob('control-*'))),15)
                    if stop:q.cancel_batch(queue)
                    thread.join(8);self.assertFalse(thread.is_alive());self.assertFalse(errors)
                    reports=[json.loads(p.read_text()) for p in (queue/'results').glob('*.json')]
                    self.assertEqual(len(reports),3)
                    self.assertEqual([r['concurrency']['observed_peak_model_stages'] for r in reports],[5,5,5])
                    self.assertEqual([r['roles']['preparation_review']['observed_peak_model_stages'] for r in reports],[1,1,1])
                    self.assertEqual({r['result']['status'] for r in reports},{'CANCELLED' if stop else 'PROOF_UNFINISHED'})
                    self.assertTrue((queue/'final-concurrency.json').exists())
                    final=json.loads((queue/'final-concurrency.json').read_text())
                    self.assertFalse(final['all_cases_accepted'])
                    self.assertEqual(final['status'],'CANCELLED' if stop else 'FINITE_BATCH_FINISHED')
                    self.assertEqual(len(final['case_outcomes']),3)
                    self.assertEqual(len({p.pid for p in handles}),3)
                    self.assertTrue(all(p.poll() is not None for p in handles))
                finally:
                    q.cancel_batch(queue);thread.join(5)
                    for process in handles:
                        if process.poll() is None:process.kill();process.wait()

    def test_failed_finite_batch_exits_and_has_three_independent_case_processes(self):
        self.run_fake_batch(False)

    def test_batch_stop_propagates_to_all_three_cases(self):
        self.run_fake_batch(True)


if __name__=='__main__':unittest.main()
