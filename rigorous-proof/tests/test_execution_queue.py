"""Deterministic scheduling controls with fake work; no model/claim of proof."""
import harness_support
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import ir
import scheduler
import concurrency
import execution_state as e


class QueueExecutionTests(unittest.TestCase):
    def test_freed_slot_claims_next_job_and_cancelled_pending_job_never_calls_worker(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);contract=root/'contract.json';contract.write_text('{}')
            steps=[{'id':f'T{i:03d}','inputs':[]} for i in range(1,6)]
            nodes={s['id']:s for s in steps};plan={'steps':steps}
            rec=e.Recorder(root/'run','neutral',concurrency.resolve(2))
            calls=[];lock=threading.Lock();first=threading.Event();third=threading.Event();errors=[]
            def worker(sid,packet):
                with lock:calls.append(sid)
                if sid=='T001':
                    first.set()
                    if not third.wait(2):errors.append('A free slot did not take the next pending job')
                if sid=='T002':first.wait(1);time.sleep(.02)
                if sid=='T003':third.set()
                return {'proof':'synthetic-control'}
            # Only the scheduler is under test. Native acceptance is intentionally
            # stubbed and no returned status is published as a mathematical result.
            try:
                with patch.object(ir,'validate',return_value=({},nodes,list(nodes))),patch.object(ir,'check',return_value={'exit_code':0}),patch.object(ir,'local_packet',side_effect=lambda *_:{'synthetic_packet':True}):
                    rec.task('T005');rec.flush(force=True);e.request_cancel(rec.root,'T005')
                    result=scheduler.prove_graph(contract,plan,worker,max_workers=2,execution=rec)
                self.assertFalse(errors)
                self.assertEqual(len(calls),len(set(calls)))
                self.assertNotIn('T005',calls)
                self.assertEqual(set(calls),{'T001','T002','T003','T004'})
                self.assertEqual(result['status'],'GRAPH_UNFINISHED')
                self.assertEqual(rec.state['tasks']['T005']['state'],'CANCELLED')
                slots={r['worker_id'] for r in result['jobs']};self.assertLessEqual(len(slots),2)
            finally:rec.close('SOFTWARE_CONTROL')

    def test_three_case_budgets_can_run_six_workers_without_context_overlap(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);recorders=[e.Recorder(root/str(i),str(i),concurrency.resolve(2)) for i in range(3)]
            budgets=[concurrency.Budget(concurrency.resolve(2),execution=r) for r in recorders]
            barrier=threading.Barrier(6,timeout=3);contexts=[];lock=threading.Lock()
            def work(index):
                case=index//2;task=f'T{index%2+1:03d}'
                with e.activate(recorders[case],task),budgets[case]:
                    with lock:contexts.append((e.current()[0].state['case_id'],e.current()[1]))
                    barrier.wait()
            try:
                with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(work,range(6)))
                self.assertEqual(len(set(contexts)),6)
                self.assertEqual([b.report()['observed_peak_model_stages'] for b in budgets],[2,2,2])
                e.request_cancel(recorders[0].root)
                self.assertFalse(recorders[1].cancelled());self.assertFalse(recorders[2].cancelled())
            finally:
                for r in recorders:r.close('SOFTWARE_CONTROL')


if __name__=='__main__':unittest.main()
