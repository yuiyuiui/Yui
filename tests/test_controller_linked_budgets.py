"""Native A/proof/pool/retained-role deadline regressions with local providers."""
import harness_support
from contextvars import copy_context
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import audit_a_campaign as campaign
from clean_stage import ArtifactStage
import concurrency
import execution_state as execution
import ir
from lean_fixtures import shared_fixture, LIFT
import model_pilot
from native_fault_fixtures import NativeFaultFixture
from native_fixture import NativeFixture
from role_sessions import Sessions
import scheduler


class LinkedBudgetTests(unittest.TestCase):
    def test_two_native_local_auditors_unwind_through_real_campaign_at_one_deadline(self):
        with tempfile.TemporaryDirectory(prefix='yui-local-a-budget-') as raw:
            root=Path(raw);source=root/'source'
            shutil.copytree(harness_support.FIXTURES/'closed-addition',source)
            (source/'audit-a.json').unlink()
            out=root/'campaign';campaign.prepare(source,source,out)
            def respond(f,handler,number,payload):
                f.code(handler,number,'text(await tools.read_review_progress({}));')
            with NativeFixture(root/'native',responder=respond) as fixture:
                fixture.stage.release_resources('USER_CANCELLED')
                budgets=concurrency.CaseBudgets(2,execution=fixture.recorder)
                original=ArtifactStage._execute;stages={};guard=threading.Lock()
                barrier=threading.Barrier(2,action=lambda:setattr(fixture.recorder,'deadline',time.monotonic()-1))
                def execute(stage):
                    with guard:
                        if not stages:fixture.stage=stage
                        stages[stage.logs.parent.name]=stage
                    dispatch=stage.dispatch
                    def expire(name,args):
                        result=dispatch(name,args)
                        if name=='read_review_progress':barrier.wait(timeout=8)
                        return result
                    with patch.object(stage,'dispatch',side_effect=expire):return original(stage)
                def target():
                    try:
                        with execution.activate(fixture.recorder), \
                             patch.object(ArtifactStage,'_execute',execute), \
                             patch.object(campaign,'global_acceptance',return_value={'accepted':True}):
                            # The preceding global judgment is an explicit synthetic boundary.
                            campaign.run(out,budget=budgets.serial,audit_budget=budgets.audit,only='local')
                    except BaseException as error:fixture.exceptions.append(error)
                fixture.worker=threading.Thread(target=copy_context().run,args=(target,),daemon=True)
                fixture.worker.start();fixture.worker.join(18)
                self.assertFalse(fixture.worker.is_alive())
                self.assertEqual(len(fixture.exceptions),1)
                self.assertIsInstance(fixture.exceptions[0],execution.CaseDeadlineExceeded)
                self.assertEqual(set(stages),{'R001','R002'})
                self.assertEqual(len(fixture.calls),2)
                report=ir.load(out/'execution.json')
                self.assertEqual(report['r_concurrency']['observed_peak_model_stages'],2)
                self.assertEqual(report['r_concurrency']['active_model_stages'],0)
                self.assertTrue(all(row['error_type']=='CaseDeadlineExceeded' for row in report['results']))
                for stage in stages.values():
                    self.assertEqual(ir.load(stage.logs/'result.json')['task_outcome'],'MODEL_BUDGET_EXHAUSTED')
                    self.assertFalse((stage.logs/'accepted.json').exists())
                    self.assertTrue(stage.work.exists() and stage.proc.poll() is None)
                self.assertFalse((source/'audit-a.json').exists())
            self.assertTrue(all(not stage.work.exists() for stage in stages.values()))

    def test_actual_global_a_deadline_preserves_coverage_and_never_dispatches_local_review(self):
        with tempfile.TemporaryDirectory(prefix='yui-a-budget-') as raw:
            root=Path(raw);source=root/'source'
            shutil.copytree(harness_support.FIXTURES/'closed-addition',source)
            (source/'audit-a.json').unlink()
            out=root/'campaign';campaign.prepare(source,source,out)
            recorder=execution.Recorder(root/'run','synthetic-a-budget',concurrency.resolve(2))
            budgets=concurrency.CaseBudgets(2,execution=recorder)
            original=ArtifactStage._execute;seen=[]
            def execute(stage):
                seen.append(stage.mode)
                def respond(f,handler,number,payload):
                    f.code(handler,number,'text(await tools.read_review_progress({}));')
                with NativeFixture(root/'native',responder=respond) as fixture:
                    unused=fixture.stage;fixture.stage=stage;unused.release_resources('USER_CANCELLED')
                    dispatch=stage.dispatch
                    def expire(name,args):
                        result=dispatch(name,args)
                        if name=='read_review_progress':recorder.deadline=time.monotonic()-1
                        return result
                    with patch.object(stage,'dispatch',side_effect=expire):
                        try:return original(stage)
                        except execution.CaseDeadlineExceeded:
                            saved=ir.load(stage.logs/'result.json')
                            self.assertEqual(saved['stop_reason'],'CASE_DEADLINE')
                            self.assertFalse((stage.logs/'accepted.json').exists())
                            self.assertIsNone(stage.proc.poll())
                            raise
            try:
                with patch.object(ArtifactStage,'_execute',execute):
                    with self.assertRaises(execution.CaseDeadlineExceeded):
                        campaign.run(out,budget=budgets.serial,audit_budget=budgets.audit)
                self.assertEqual(seen,['audit-a-global'])
                self.assertFalse((source/'audit-a.json').exists())
                self.assertEqual(recorder.state['concurrency']['active_model_stages'],0)
            finally:recorder.close('CANCELLED')

    def test_actual_lean_check_then_native_proof_deadline_keeps_checked_work(self):
        with tempfile.TemporaryDirectory(prefix='yui-proof-budget-') as raw:
            root=Path(raw);cp,plan=shared_fixture(root/'source')
            def respond(f,handler,number,payload):
                f.code(handler,number,'text(await tools.check_transition('+json.dumps({'proof':LIFT})+'));')
            with NativeFixture(root/'native',responder=respond) as fixture:
                unused=fixture.stage
                stage=model_pilot.Stage(root/'proof-stage',cp,'proof',None,plan=plan,step='T001',
                    budget=concurrency.Budget(concurrency.resolve(1),execution=fixture.recorder,role='proof'))
                fixture.stage=stage;unused.release_resources('USER_CANCELLED')
                dispatch=stage.dispatch
                def expire(name,args):
                    result=dispatch(name,args)
                    if name=='check_transition':
                        self.assertTrue(result['accepted'],result)
                        fixture.recorder.deadline=time.monotonic()-1
                    return result
                with patch.object(stage,'dispatch',side_effect=expire):
                    fixture.start();fixture.worker.join(12)
                self.assertFalse(fixture.worker.is_alive())
                self.assertEqual(len(fixture.exceptions),1)
                self.assertIsInstance(fixture.exceptions[0],execution.CaseDeadlineExceeded)
                result=ir.load(stage.logs/'result.json')
                self.assertEqual(result['task_outcome'],'MODEL_BUDGET_EXHAUSTED')
                draft=ir.load(stage.logs/'lean-drafts/proof-0001.json')
                self.assertEqual(draft['check']['exit_code'],0)
                self.assertIsNone(stage.accepted,'A successful check is not a submitted final proof')
                self.assertTrue(stage.work.exists())

    def test_two_native_workers_and_queued_node_leave_real_scheduler_at_one_deadline(self):
        with tempfile.TemporaryDirectory(prefix='yui-pool-budget-') as raw:
            root=Path(raw);cp,plan=shared_fixture(root/'source')
            plan['steps'].append({'id':'T003','statement':plan['steps'][-1]['statement'],
                'inputs':['T002'],'source_steps':['S002'],'explanation':'Synthetic redundant linked obligation.'})
            plan['terminal']='T003'
            def respond(f,handler,number,payload):
                f.code(handler,number,'text(await tools.check_transition('+json.dumps({'proof':LIFT})+'));')
            stages={};guard=threading.Lock()
            with NativeFixture(root/'native',responder=respond) as fixture:
                unused=fixture.stage;unused.release_resources('USER_CANCELLED')
                budget=concurrency.Budget(concurrency.resolve(2),execution=fixture.recorder,role='proof')
                barrier=threading.Barrier(2,action=lambda:setattr(fixture.recorder,'deadline',time.monotonic()-1))
                def worker(sid,packet):
                    stage=model_pilot.Stage(root/sid,cp,'proof',None,plan=plan,step=sid,budget=budget)
                    with guard:
                        if not stages:fixture.stage=stage
                        stages[sid]=stage
                    dispatch=stage.dispatch
                    def expire(name,args):
                        if name=='check_transition':barrier.wait(timeout=8)
                        return dispatch(name,args)
                    with patch.object(stage,'dispatch',side_effect=expire):return stage.execute()
                def target():
                    try:
                        with execution.activate(fixture.recorder):
                            scheduler.prove_graph(cp,plan,worker,max_workers=2,out=root/'graph',execution=fixture.recorder)
                    except BaseException as error:fixture.exceptions.append(error)
                fixture.worker=threading.Thread(target=copy_context().run,args=(target,),daemon=True)
                fixture.worker.start();fixture.worker.join(18)
                self.assertFalse(fixture.worker.is_alive())
                self.assertEqual(len(fixture.exceptions),1)
                self.assertIsInstance(fixture.exceptions[0],execution.CaseDeadlineExceeded)
                self.assertEqual(set(stages),{'T001','T002'},'Queued third node must not construct/dispatch a carrier')
                self.assertEqual(len(fixture.calls),2)
                self.assertEqual(budget.report()['observed_peak_model_stages'],2)
                self.assertEqual(budget.report()['active_model_stages'],0)
                report=ir.load(root/'graph/scheduler-report.json')
                self.assertEqual(report['status'],'GRAPH_UNFINISHED')
                self.assertIsNone(report['assembly'])
                self.assertTrue(all(stage.work.exists() and stage.proc.poll() is None for stage in stages.values()))
            self.assertTrue(all(not stage.work.exists() for stage in stages.values()))

    def test_recovered_fault_and_healthy_role_revision_both_survive_case_attribution(self):
        with tempfile.TemporaryDirectory(prefix='yui-role-health-') as raw:
            root=Path(raw);sessions=Sessions()
            with NativeFaultFixture(root/'native',503) as fixture:
                fixture.start(sessions,'author');fixture.wait()
                first=fixture.outcomes[0][0]
                self.assertEqual(first['execution_health'],'FAULT')
                template=ArtifactStage(root/'revision','Submit the synthetic fixture object using submit_draft.',
                    phase='control',library=False,validator=fixture.validate)
                with execution.activate(fixture.recorder),sessions.use('author'):
                    second,_=template.execute()
                self.assertEqual(second['execution_health'],'NO_RECORDED_FAULT')
                self.assertTrue(second['identity_and_input_boundary_verified'])
                result=fixture.recorder.deadline_result(execution.CaseDeadlineExceeded('Synthetic later case deadline'))
                self.assertEqual(result['task_outcome'],'UNFINISHED_WITH_EXECUTION_FAULT')
                self.assertEqual(len(result['stage_health_evidence']),2)
                self.assertEqual({entry['summary']['execution_health'] for entry in result['stage_health_evidence']},
                                 {'FAULT','NO_RECORDED_FAULT'})


if __name__=='__main__':unittest.main()
