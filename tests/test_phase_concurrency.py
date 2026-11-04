"""Phase-sized defaults through real queues; model replies are synthetic."""
import harness_support
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from audit_a_fixtures import synthetic_stage, canonical_propositional_case
from lean_fixtures import shared_fixture, LIFT, SUP
import audit_a_campaign as campaign
import concurrency
import ir
import run_graph
import scheduler


class AuditPhaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        source=canonical_propositional_case(self.root/'source')
        self.out=self.root/'audit'
        self.plan=campaign.prepare(source,source,self.out)

    def tearDown(self):self.tmp.cleanup()

    def run_campaign(self, *, requested=None, only=None, global_verdict='PASS', empty=False):
        if empty:
            self.plan['jobs']=[job for job in self.plan['jobs'] if job['library']]
            ir.write(self.out/'campaign.json',self.plan)
        barrier=(threading.Barrier(3,timeout=5) if requested in (None,'auto')
                 and only is None and global_verdict=='PASS' and not empty else None)
        events=[];lock=threading.Lock()
        class Stage:
            def __init__(self,logs,prompt,**kwargs):
                self.directory=logs.parent;self.name=logs.parent.name;self.budget=kwargs['budget']
            def execute(self):
                with self.budget:
                    with lock:events.append(('start',self.name))
                    if self.name!='global' and barrier:barrier.wait()
                    result=synthetic_stage(self.directory,global_verdict=global_verdict)
                    with lock:events.append(('end',self.name))
                    return result
        kwargs={} if requested is None else {
            'audit_budget':concurrency.Budget(concurrency.resolve(requested),role='audit_r')}
        with patch.object(campaign,'ArtifactStage',Stage):
            report=campaign.run(self.out,only=only,**kwargs)
        return report,events

    def test_default_campaign_runs_all_three_r_reviews_after_global_pass(self):
        report,events=self.run_campaign()
        self.assertEqual(report['r_concurrency']['effective'],3)
        self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],3)
        self.assertLess(events.index(('end','global')),
            min(events.index(('start',rid)) for rid in ('R001','R002','R003')))
        self.assertEqual(report['concurrency']['observed_peak_model_stages'],1)

    def test_explicit_one_worker_keeps_three_reviews_serial(self):
        report,events=self.run_campaign(requested=1)
        self.assertEqual(report['r_concurrency']['effective'],1)
        self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],1)
        self.assertLess(events.index(('end','R001')),events.index(('start','R002')))

    def test_single_packet_dispatch_retains_the_full_phase_node_count(self):
        self.run_campaign(only='global')
        report,_=self.run_campaign(requested='auto',only='R001')
        self.assertEqual(report['r_concurrency']['effective'],3)
        self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],1)
        self.assertEqual([row['id'] for row in report['results']],['R001'])

    def test_global_fail_still_dispatches_no_local_models_under_auto(self):
        report,events=self.run_campaign(global_verdict='FAIL')
        self.assertEqual(report['r_concurrency']['effective'],3)
        self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],0)
        self.assertEqual(events,[('start','global'),('end','global')])

    def test_empty_local_queue_records_zero_and_constructs_no_executor(self):
        with patch('concurrent.futures.ThreadPoolExecutor') as executor:
            report,_=self.run_campaign(empty=True)
        executor.assert_not_called()
        self.assertEqual(report['r_concurrency']['effective'],0)
        self.assertEqual(report['r_concurrency']['model_stages'],[])


class LeanPhaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.cpath,self.plan=shared_fixture(self.root/'input',objects=True)
        root=self.plan['steps'][1]
        for index in range(3,6):
            step=deepcopy(root)
            step.update(id=f'T{index:03d}',inputs=[f'T{index-1:03d}'])
            step.pop('bridges',None)
            self.plan['steps'].append(step)
        self.plan['terminal']='T005'
        self.ppath=self.cpath.parent/'plan.json';ir.write(self.ppath,self.plan)
        ir.validate(self.cpath,self.plan)
        self.bodies={'T001':LIFT,'T002':SUP,**{
            f'T{i:03d}':f'exact h_T{i-1:03d}' for i in range(3,6)}}

    def tearDown(self):self.tmp.cleanup()

    def test_default_runner_really_overlaps_all_five_t_nodes_and_checks_lean(self):
        barrier=threading.Barrier(5,timeout=10);seen=[];lock=threading.Lock()
        bodies=self.bodies
        def execute(stage):
            with lock:seen.append(stage.step)
            barrier.wait()
            shutil.rmtree(stage.work)
            return {'status':'SYNTHETIC_MODEL_REPLY','api_calls':0},{'proof':bodies[stage.step]}
        out=self.root/'run'
        with patch.object(run_graph.pilot.Stage,'_execute',execute):
            report=run_graph.run(self.cpath,self.ppath,out)
        self.assertEqual(report['status'],'FRAGMENT_ASSEMBLED',report)
        self.assertEqual(sorted(seen),sorted(self.bodies))
        self.assertEqual(report['concurrency']['requested'],'auto')
        self.assertEqual(report['concurrency']['effective'],5)
        self.assertEqual(report['concurrency']['observed_peak_model_stages'],5)
        self.assertEqual(report['fresh_verifier']['exit_code'],0)
        state=ir.load(out/'execution-status.json')['concurrency']
        self.assertEqual(state['roles']['proof']['configuration']['node_count'],5)
        self.assertEqual(state['roles']['proof']['observed_peak'],5)
        # T001 is a shared lemma and T002 owns an explicit representation bridge.
        self.assertIn('shared_lemma',self.plan['steps'][0])
        self.assertTrue(self.plan['steps'][1]['bridges'])

    def test_direct_scheduler_default_is_all_five_nodes(self):
        barrier=threading.Barrier(5,timeout=5)
        def worker(sid,packet):
            barrier.wait()
            return {'proof':self.bodies[sid]}
        # Exercise the real executor and its omitted argument independently of
        # run_graph. Kernel acceptance is covered by the runner test above.
        with patch.object(ir,'check',return_value={'exit_code':0}):
            report=scheduler.prove_graph(self.cpath,self.plan,worker)
        self.assertEqual(report['max_workers'],5)
        self.assertEqual(report['status'],'FRAGMENT_ASSEMBLED')

    def test_explicit_runner_limit_survives_a_larger_phase(self):
        bodies=self.bodies
        def execute(stage):
            shutil.rmtree(stage.work)
            return {'status':'SYNTHETIC_MODEL_REPLY','api_calls':0},{'proof':bodies[stage.step]}
        with patch.object(run_graph.pilot.Stage,'_execute',execute),patch.object(
                ir,'check',return_value={'exit_code':0}):
            report=run_graph.run(self.cpath,self.ppath,self.root/'serial-run',max_concurrency=1)
        self.assertEqual(report['concurrency']['requested'],1)
        self.assertEqual(report['concurrency']['node_count'],5)
        self.assertEqual(report['concurrency']['effective'],1)
        self.assertEqual(report['concurrency']['observed_peak_model_stages'],1)


if __name__=='__main__':unittest.main()
