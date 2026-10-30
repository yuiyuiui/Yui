"""Exercise real scheduling with controlled isolated-stage stand-ins, not models."""
import harness_support
from harness_support import PROFILES
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import shutil
from audit_a_fixtures import synthetic_stage
from unittest.mock import patch
import audit_a_campaign as campaign
import concurrency
import execution_state
from runtime_config import use_profiles,model_profile


class ParallelAuditTests(unittest.TestCase):
    def test_real_packet_stage_accepts_only_its_parallel_review_budget(self):
        from clean_stage import ArtifactStage
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);case=harness_support.CORE/'tests/fixtures/closed-addition'
            campaign.prepare(case,case,root/'campaign')
            local=concurrency.Budget(concurrency.resolve(3),role='audit_r')
            stage=ArtifactStage(root/'stage','Synthetic constructor control.',phase='audit-a-packet-replay',
                inputs=root/'campaign/R001/inputs.json',budget=local,library=False)
            try:
                self.assertIs(stage.budget,local)
                self.assertNotIn('search_external_sources',stage.tool_names)
            finally:shutil.rmtree(stage.work)
            with self.assertRaisesRegex(ValueError,'serial'):
                ArtifactStage(root/'bad','Synthetic.',phase='audit-a-global',budget=local)

    def exercise(self,n,failed=None,global_verdict='PASS'):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        case=harness_support.CORE/'tests/fixtures/closed-addition';out=root/'audit'
        campaign.prepare(case,case,out)
        serial=concurrency.Budget(concurrency.resolve(1),role='preparation_review')
        local=concurrency.Budget(concurrency.resolve(n),role='audit_r')
        events=[];lock=threading.Lock();barrier=threading.Barrier(2) if n>1 else None
        class Stage:
            def __init__(self,logs,prompt,**kwargs):self.name=logs.parent.name;self.budget=kwargs['budget'];self.directory=logs.parent
            def execute(self):
                with self.budget:
                    with lock:events.append(('start',self.name,model_profile('audit-a-packet-replay')['id']))
                    if self.name!='global' and barrier:barrier.wait(timeout=3)
                    time.sleep(.015)
                    if self.name==failed:raise RuntimeError('Controlled stage fault')
                    with lock:events.append(('end',self.name,None))
                return synthetic_stage(self.directory,global_verdict=global_verdict)
        with use_profiles(PROFILES),patch.object(campaign,'ArtifactStage',Stage):
            if failed:
                with self.assertRaisesRegex(RuntimeError,'Controlled'):campaign.run(out,budget=serial,audit_budget=local)
                report=json.loads((out/'execution.json').read_text())
            else:report=campaign.run(out,budget=serial,audit_budget=local)
        return events,report

    def test_global_barrier_parallel_limit_order_and_context_propagation(self):
        events,report=self.exercise(2)
        self.assertEqual([r['id'] for r in report['results']],['global','R001','R002'])
        self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],2)
        self.assertLess(events.index(('end','global',None)),next(i for i,e in enumerate(events) if e[:2]==('start','R001')))
        self.assertTrue(all(e[2]==PROFILES['nl0']['id'] for e in events if e[0]=='start'))

    def test_one_worker_stays_serial(self):
        _,report=self.exercise(1)
        self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],1)

    def test_local_failure_retains_other_completed_results_and_releases_slots(self):
        _,report=self.exercise(2,failed='R001')
        self.assertEqual(report['results'][1]['status'],'REVIEW_EXECUTION_FAILED')
        self.assertEqual(report['results'][2]['id'],'R002')
        self.assertTrue(report['results'][2]['artifact_present'])
        self.assertEqual(report['r_concurrency']['active_model_stages'],0)

    def test_global_execution_failure_is_recorded_before_any_local_dispatch(self):
        events,report=self.exercise(2,failed='global')
        self.assertEqual([row['id'] for row in report['results']],['global'])
        self.assertEqual(report['results'][0]['status'],'REVIEW_EXECUTION_FAILED')
        self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],0)
        self.assertEqual([e[1] for e in events],['global'])

    def test_actual_stage_wrapper_uses_distinct_task_ids_and_case_roles(self):
        from clean_stage import ArtifactStage
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);out=root/'campaign';case=harness_support.CORE/'tests/fixtures/closed-addition'
            campaign.prepare(case,case,out)
            recorder=execution_state.Recorder(root/'state','parallel-control',concurrency.resolve(2))
            budgets=concurrency.CaseBudgets(2,execution=recorder)
            barrier=threading.Barrier(2)
            def execute(stage):
                try:
                    if stage.mode=='audit-a-packet-replay':barrier.wait(timeout=3)
                    return synthetic_stage(stage.logs.parent)
                finally:shutil.rmtree(stage.work)
            try:
                with execution_state.activate(recorder),use_profiles(PROFILES),patch.object(ArtifactStage,'_execute',execute):
                    campaign.run(out,budget=budgets.serial,audit_budget=budgets.audit)
                tasks=recorder.state['tasks']
                self.assertEqual(len(tasks),3)
                self.assertEqual(len({r['log_path'] for r in tasks.values()}),3)
                self.assertEqual(sorted(r['role'] for r in tasks.values()),['audit_r','audit_r','preparation_review'])
                self.assertEqual(recorder.state['concurrency']['roles']['audit_r']['observed_peak'],2)
            finally:recorder.close('SYNTHETIC_CONTROL_FINISHED')

    def test_audit_and_proof_phases_cannot_overlap(self):
        with tempfile.TemporaryDirectory() as raw:
            recorder=execution_state.Recorder(Path(raw),'test',concurrency.resolve(2))
            budgets=concurrency.CaseBudgets(2,execution=recorder)
            try:
                with budgets.audit:
                    for lane in [budgets.serial,budgets.proof]:
                        with self.assertRaisesRegex(ValueError,'cannot overlap'):
                            with lane:pass
            finally:recorder.close('TEST_FINISHED')

    def test_complete_global_fail_dispatches_no_local_workers(self):
        events,report=self.exercise(3,global_verdict='FAIL')
        self.assertEqual([r['id'] for r in report['results']],['global'])
        self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],0)
        self.assertEqual([e[1] for e in events],['global','global'])


if __name__=='__main__':unittest.main()
