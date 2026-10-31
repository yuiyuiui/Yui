"""Offline progress/escalation controls; no provider or scientific proof runs."""
import harness_support
import copy
import json
from pathlib import Path
import shutil
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import execution_state
import full_workflow as full
import ir
import model_pilot
import proof_diagnosis
import proof_repair
import scheduler
from lean_fixtures import shared_fixture, LIFT


class ProofRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.cpath,self.plan=shared_fixture(self.root/'source');self.stages=[]

    def tearDown(self):
        for stage in self.stages:shutil.rmtree(stage.work,ignore_errors=True)
        self.temp.cleanup()

    def stage(self,*,arm='yui'):
        stage=model_pilot.Stage(self.root/f'worker-{len(self.stages)}',self.cpath,'proof',None,
            self.plan,'T001',instruction_arm=arm)
        self.stages.append(stage);return stage

    def simulate(self,stage,actions=None,finish=None):
        number=[0]
        def rpc(method,params,seconds=30):
            self.assertEqual(method,'turn/start');number[0]+=1
            self.assertLess(number[0],30,'A no-progress loop escaped the controller')
            return {'turn':{'id':str(number[0])}}
        def receive(predicate,deadline):
            n=number[0]
            if actions:actions(stage,n)
            if finish and n==finish:stage.accepted={'proof':'synthetic fixture only'}
            event={'method':'turn/completed','params':{'turn':{'id':str(n),'status':'completed'}}}
            self.assertTrue(predicate(event));return event
        stage.thread_id='offline-control';stage.rpc=rpc;stage.receive_until=receive
        return stage.solve_turns('Synthetic fixed input; no external call'),number[0]

    def report(self):
        return {'layer':'interface','explanation':'Compare the supplied target with its source statement.',
                'locations':['/target','/source_steps/0/text'],'candidates':[]}

    def test_idle_turn_accounting_has_no_automatic_retirement_threshold(self):
        stage=self.stage();_,turns=self.simulate(stage,finish=8)
        self.assertEqual(turns,8);self.assertIsNone(stage.repair_request)
        self.assertGreaterEqual(stage.proof_progress.idle_turns,3)
        self.assertFalse((stage.logs/'proof-repair-request.json').exists())

    def test_many_distinct_failed_checks_have_no_model_call_or_turn_cap(self):
        stage=self.stage()
        def action(stage,n):stage.dispatch('check_transition',{'proof':f'have h{n} := h_H001\nexact h{n}'})
        with patch.object(ir,'check',return_value={'exit_code':1,'status':'LOCAL-REJECTED','stdout':'fixture error'}):
            _,turns=self.simulate(stage,action,finish=18)
        self.assertEqual(turns,18);self.assertIsNone(stage.repair_request)
        self.assertEqual(stage.proof_progress.metadata()['distinct_check_candidates'],18)

    def test_identical_candidates_are_counted_without_forcing_a_control_transition(self):
        stage=self.stage()
        with patch.object(ir,'check',return_value={'exit_code':1,'stdout':'fixture rejection'}):
            _,turns=self.simulate(stage,lambda s,n:s.dispatch('check_transition',{'proof':'exact h_H001'}),finish=7)
        self.assertEqual(turns,7);self.assertEqual(stage.lean_calls,7)
        self.assertEqual(stage.proof_progress.metadata()['distinct_check_candidates'],1)
        self.assertIsNone(stage.repair_request)

    def test_obstruction_is_located_and_never_a_submission(self):
        stage=self.stage()
        result=stage.dispatch('report_proof_obstruction',self.report())
        self.assertFalse(result['accepted']);self.assertFalse(result['stage_complete'])
        self.assertTrue(result['repair_requested'])
        self.assertIsNone(stage.accepted);self.assertEqual(stage.repair_request['step'],'T001')
        self.assertFalse((stage.logs/'accepted.json').exists())

    def test_fabricated_attempt_or_nonresolving_location_cannot_escalate(self):
        stage=self.stage()
        for value in [dict(self.report(),candidates=[{'kind':'proof','candidate':42}]),
                      dict(self.report(),locations=['/unprovided/claim']),
                      dict(self.report(),extra_premise='unproved')]:
            result=stage.dispatch('report_proof_obstruction',value)
            self.assertFalse(result['accepted']);self.assertIsNone(stage.repair_request)

    def test_obstruction_uses_actual_checked_own_draft(self):
        stage=self.stage()
        with patch.object(ir,'check',return_value={'exit_code':1,'stdout':'actual fixture feedback'}):
            stage.dispatch('check_transition',{'proof':'exact h_H001'})
        stage.dispatch('report_proof_obstruction',dict(self.report(),candidates=[{'kind':'proof','candidate':1}]))
        self.assertEqual(stage.repair_request['candidate_evidence'][0]['sha256'],
            proof_repair.digest(stage.own_lean_drafts['proof'][1]))

    def test_reworded_allegations_and_timestamps_do_not_change_evidence_identity(self):
        stage=self.stage();a=proof_repair.obstruction(stage,self.report())
        value=self.report();value['explanation']='Another account of the same evidence.'
        stage.proof_progress.idle_turns=999
        b=proof_repair.obstruction(stage,value)
        self.assertEqual(a['evidence_key'],b['evidence_key'])

    def test_direct_arm_has_neither_report_tool_nor_progress_policy(self):
        stage=self.stage(arm='direct')
        self.assertNotIn('report_proof_obstruction',stage.tool_names)
        self.assertFalse(stage.after_unaccepted_turn());self.assertIsNone(stage.proof_progress)
        _,turns=self.simulate(stage,finish=7)
        self.assertEqual(turns,7);self.assertIsNone(stage.repair_request)

    def test_report_does_not_interrupt_other_nodes_and_user_cancel_has_priority(self):
        stage=self.stage();other=self.stage()
        stage.dispatch('report_proof_obstruction',self.report())
        stage.check_runtime_state()
        other.check_runtime_state()
        other.execution=Mock();other.execution_task='T002'
        other.execution.check.side_effect=execution_state.Cancelled('Actual human stop')
        with self.assertRaises(execution_state.Cancelled):other.check_runtime_state()

    def test_remote_wait_does_not_increment_completed_idle_turns(self):
        stage=self.stage();stage.started=__import__('time').monotonic();stage.remote_retry_count=1
        stage.thread_id='same-thread';stage.execution=None;stage.api_calls=0
        stage.wait_remote_retry(0,{'kind':'synthetic'}, {'id':'failed','error':{'code':'server_is_overloaded'}},None)
        self.assertEqual(stage.proof_progress.idle_turns,0);self.assertIsNone(stage.repair_request)

    def test_scheduler_preserves_checked_bodies_and_does_not_claim_assembly(self):
        request={'step':'T002','acceptance':False,'evidence_key':'fixture'}
        def worker(sid,packet):
            if sid=='T001':return {'proof':LIFT}
            return {'proof':None,'stage':{'status':'REPAIR_REQUESTED','repair_request':request}}
        with patch.object(ir,'check',return_value={'exit_code':0}) as check:
            result=scheduler.prove_graph(self.cpath,self.plan,worker,max_workers=1)
        self.assertEqual(result['status'],'GRAPH_REPAIR_REQUIRED')
        self.assertEqual(result['proofs'],{'T001':LIFT});self.assertIsNone(result['assembly'])
        self.assertEqual(check.call_count,2) # Types and the one completed node, no assembly.

    def test_scheduler_preserves_other_running_workers_after_a_report(self):
        barrier=threading.Barrier(2)
        def worker(sid,packet):
            barrier.wait(timeout=3)
            if sid=='T001':
                request={'step':sid,'acceptance':False,'evidence_key':'fixture'}
                return {'proof':None,'stage':{'repair_request':request}}
            return {'proof':LIFT}
        with patch.object(ir,'check',return_value={'exit_code':0}):
            result=scheduler.prove_graph(self.cpath,self.plan,worker,max_workers=2)
        self.assertEqual({j['status'] for j in result['jobs']},{'REPAIR_REQUESTED','LOCAL_PROOFS_CHECKED'})
        self.assertNotIn('CANCELLED',json.dumps(result))
        self.assertEqual(result['repair_requests']['T001']['evidence_key'],'fixture')

    def test_local_diagnosis_repair_handoff_preserves_prior_round(self):
        import run_graph,workflow
        import run_resources
        budget=SimpleNamespace(execution=None);proof_budget=SimpleNamespace(execution=None)
        frozen={'contract':str(self.cpath),'plan':str(self.root/'plan.json')}
        request={'step':'T001','evidence_key':'one'}
        failure={'status':'GRAPH_REPAIR_REQUIRED','repair_requests':{'T001':request}}
        retained=self.stage()
        failure['jobs']=[{'step':'T001','worker':{'stage':{'status':'REPAIR_REQUESTED',
            'temporary_workspace_removed':False,
            'workspace_retention':run_resources.retention(retained.work,retained.logs)}}}]
        calls=[]
        def run(c,p,out,**kwargs):
            calls.append((out,copy.deepcopy(kwargs)));ir.write(out/'report.json',failure if len(calls)==1 else {'status':'FRAGMENT_ASSEMBLED'})
            return failure if len(calls)==1 else {'status':'FRAGMENT_ASSEMBLED'}
        advice={'route':'LOCAL_PROOF_REPAIR','repair_advice':'Inspect the actual binder type.'}
        with patch.object(run_graph,'run',side_effect=run),patch.object(workflow,'bound'),\
                patch.object(workflow,'select_proof_run') as select,patch.object(full,'stage_seconds',return_value=None),\
                patch.object(proof_diagnosis,'run',return_value=advice) as diagnose:
            result,path=full.prove_with_repair('neutral',frozen,self.root/'workflow',self.root/'interface',
                budget,proof_budget,lambda *a,**k:None)
        self.assertEqual(result['status'],'FRAGMENT_ASSEMBLED');self.assertEqual(diagnose.call_count,1)
        self.assertEqual(calls[1][1]['prior_run'],calls[0][0]);self.assertEqual(calls[1][1]['repair_guidance']['T001'],advice)
        self.assertEqual(ir.load(calls[0][0]/'report.json'),failure);select.assert_called_once()
        history=ir.load(self.root/'workflow/proof-repair-history.json')
        self.assertEqual(len(history['rounds']),2);self.assertEqual(len(history['diagnoses']),1)

    def test_repeated_evidence_retains_the_approved_repair_loop_and_every_prior_round(self):
        import run_graph,workflow
        from role_sessions import Sessions,current
        row={'status':'GRAPH_REPAIR_REQUIRED','repair_requests':{'T001':{'evidence_key':'same'}}}
        calls=[];roles=[];sessions=Sessions()
        def run(c,p,out,**kw):
            calls.append((out,kw));result=row if len(calls)<3 else {'status':'FRAGMENT_ASSEMBLED'}
            ir.write(out/'report.json',result);return result
        def diagnose(*args,**kwargs):roles.append(current());return {'route':'LOCAL_PROOF_REPAIR'}
        with patch.object(run_graph,'run',side_effect=run),patch.object(workflow,'bound'),\
                patch.object(workflow,'select_proof_run'),\
                patch.object(full,'stage_seconds',return_value=None),\
                patch.object(proof_diagnosis,'run',side_effect=diagnose) as diagnostics:
            result,_=full.prove_with_repair('neutral',{'contract':str(self.cpath),'plan':'unused'},self.root/'workflow',
                self.root/'interface',SimpleNamespace(execution=None),None,lambda *a,**k:None,sessions=sessions)
        self.assertEqual(result['status'],'FRAGMENT_ASSEMBLED');self.assertEqual(diagnostics.call_count,2)
        self.assertEqual(roles,[(sessions,'proof-connection')]*2)
        self.assertEqual(calls[2][1]['prior_run'],calls[1][0])
        history=ir.load(self.root/'workflow/proof-repair-history.json')
        self.assertEqual(len(history['rounds']),3);self.assertEqual(len(history['diagnoses']),2)
        self.assertTrue(all(path.is_file() for path in [out/'report.json' for out,kw in calls]))

    def test_source_or_unknown_diagnosis_cannot_weaken_an_interface_or_gain_acceptance(self):
        import run_graph,workflow
        row={'status':'GRAPH_REPAIR_REQUIRED','repair_requests':{'T001':{'evidence_key':'same'}}}
        def run(c,p,out,**kw):ir.write(out/'report.json',row);return row
        for route in ['SOURCE_REVIEW_REQUIRED','UNRESOLVED','INTERFACE_REPAIR_REQUIRED']:
            with patch.object(run_graph,'run',side_effect=run),patch.object(workflow,'bound'),\
                    patch.object(full,'stage_seconds',return_value=None),\
                    patch.object(proof_diagnosis,'run',return_value={'route':route}):
                with self.assertRaises(full.StageFailure) as error:
                    full.prove_with_repair('neutral',{'contract':str(self.cpath),'plan':'unused'},self.root/route,
                        self.root/'interface',SimpleNamespace(execution=None),None,lambda *a,**k:None)
            self.assertEqual(error.exception.result['phase'],'frozen-interface' if route=='INTERFACE_REPAIR_REQUIRED' else 'proof-diagnosis')

    def test_unconfirmed_sibling_cleanup_blocks_interface_repair_and_new_model_dispatch(self):
        import run_graph,workflow
        row={'status':'GRAPH_REPAIR_REQUIRED','repair_requests':{'T001':{'evidence_key':'same'}},
            'jobs':[{'step':'T002','worker':{'stage':{'status':'REPAIR_WAIT','execution_fault':'Model process cleanup unconfirmed'}}}]}
        def run(c,p,out,**kw):ir.write(out/'report.json',row);return row
        with patch.object(run_graph,'run',side_effect=run),patch.object(workflow,'bound'),\
                patch.object(full,'stage_seconds',return_value=None),patch.object(proof_diagnosis,'run') as diagnose:
            with self.assertRaises(full.StageFailure) as error:
                full.prove_with_repair('neutral',{'contract':str(self.cpath),'plan':'unused'},self.root/'cleanup-fault',
                    self.root/'interface',SimpleNamespace(execution=None),None,lambda *a,**k:None)
        diagnose.assert_not_called();self.assertEqual(error.exception.result['status'],'EXECUTION_FAULT')
        self.assertEqual(error.exception.result['affected_steps'],['T002'])

    def test_selected_successful_round_does_not_overwrite_or_accept_old_failures(self):
        import workflow
        root=self.root/'selection';first=root/'proof-run';later=root/'proof-repairs/0002'
        ir.write(first/'report.json',{'status':'GRAPH_REPAIR_REQUIRED'})
        for name,value in [('report.json',{'status':'FRAGMENT_ASSEMBLED'}),('proofs.json',{'fixture':'no scientific proof'})]:
            ir.write(later/name,value)
        for name,path in [('contract.json',self.cpath),('plan.json',self.root/'plan.json')]:
            if name=='plan.json':ir.write(path,self.plan)
            dest=later/'inputs'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(path,dest)
        frozen={'contract':str(self.cpath),'plan':str(self.root/'plan.json')}
        with patch.object(workflow,'bound',return_value=frozen):
            with self.assertRaisesRegex(ValueError,'missing local proof bodies'):workflow.select_proof_run(root,first)
            self.assertEqual(workflow.select_proof_run(root,later),later.resolve())
        self.assertEqual(ir.load(first/'report.json')['status'],'GRAPH_REPAIR_REQUIRED')
        ir.write(later/'proofs.json',{'modified':True})
        with self.assertRaisesRegex(ValueError,'stale'):workflow.proof_run(root)

    def test_artifact_status_reads_selected_repaired_round_instead_of_old_failure(self):
        import case_status,workflow
        source=self.root/'status-source';ir.write(source/'nl0.json',{});ir.write(source/'spec.json',{})
        root=self.root/'status-workflow';old=root/'proof-run';later=root/'proof-repairs/0002'
        ir.write(root/'manifest.json',{'fixture':'scope only; freeze gate mocked'})
        ir.write(old/'report.json',{'status':'GRAPH_REPAIR_REQUIRED'})
        ir.write(later/'report.json',{'status':'FRAGMENT_ASSEMBLED'});ir.write(later/'proofs.json',{})
        ir.write(self.root/'plan.json',self.plan)
        for name,file in [('contract.json',self.cpath),('plan.json',self.root/'plan.json')]:
            dest=later/'inputs'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(file,dest)
        frozen={'contract':str(self.cpath),'plan':str(self.root/'plan.json'),'authority':{'graph':str(source/'nl0.json')}}
        with patch.object(workflow,'bound',return_value=frozen):
            workflow.select_proof_run(root,later)
            with patch.object(case_status.nl0,'validate',return_value=[{'case_id':'neutral'}]):
                status=case_status.project(source,workflow=root)
        self.assertEqual(status['gates']['lean_assembly'],'FRAGMENT_ASSEMBLED')
        self.assertFalse(status['full_acceptance']);self.assertEqual(status['gates']['audit_b'],'NOT_PASSED')

    def test_actual_repair_request_result_is_unaccepted_and_retains_context(self):
        stage=self.stage();stage.start_process=Mock();stage.interrupt_active_turn=Mock()
        stage.rpc=Mock(return_value={'thread':{'id':'offline-thread'}})
        stage.solve_turns=lambda user:stage.dispatch('report_proof_obstruction',self.report())
        result,value=stage._execute()
        self.assertEqual(result['status'],'REPAIR_REQUESTED');self.assertIsNone(value)
        self.assertEqual(result['task_outcome'],'PROOF_DIAGNOSIS_REQUIRED')
        self.assertFalse(result['temporary_workspace_removed']);self.assertTrue(stage.work.exists());self.assertFalse((stage.logs/'accepted.json').exists())

    def test_warm_repair_restores_only_own_drafts_without_inheriting_acceptance(self):
        import proof_reuse,run_graph
        stage=self.stage()
        with patch.object(ir,'check',return_value={'exit_code':1,'stdout':'actual own fixture error'}):
            stage.dispatch('check_transition',{'proof':'exact h_H001'})
        stage.dispatch('report_proof_obstruction',dict(self.report(),candidates=[{'kind':'proof','candidate':1}]))
        previous=self.root/'repair-origin';ir.write(self.root/'plan.json',self.plan)
        run_graph.package(self.cpath,self.root/'plan.json',previous)
        old=previous/'workers/T001';shutil.copytree(stage.logs,old)
        ir.write(old/'prompt.txt',json.loads(stage.prompt()))
        ir.write(old/'result.json',{'status':'REPAIR_REQUESTED','model':stage.model,'model_selection':stage.model_selection,
            'temporary_workspace_removed':True,'isolation_violation':False,'execution_health':'NO_RECORDED_FAULT',
            'exposure':{'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[stage.model],'standard_tier_verified':True}})
        ir.write(previous/'workers/T002/lean-drafts/proof-0001.json',{'proof':'SIBLING_CANARY'})
        current=self.stage();receipt=proof_reuse.restore_repair_drafts(current,previous)
        self.assertIn('Warm own-node repair',receipt['scope']);self.assertIsNone(current.accepted)
        self.assertEqual(current.own_lean_drafts['proof'][1]['proof'],'exact h_H001')
        self.assertEqual(current.own_lean_drafts['proof'][1]['check']['status'],'RETAINED_UNACCEPTED_CANDIDATE')
        self.assertEqual(current.own_lean_drafts['proof'][1]['previous_check']['exit_code'],1)
        self.assertNotIn('SIBLING_CANARY',json.dumps(current.own_lean_drafts))
        self.assertEqual(stage.proof_progress.seen,current.proof_progress.seen)
        self.assertEqual(current.proof_progress.last_turn_revision,current.proof_progress.revision)

    def test_retired_startup_without_drafts_is_not_a_failed_recovery(self):
        import proof_reuse
        previous=self.root/'retired-startup';old=previous/'workers/T001'
        stage=self.stage();ir.write(old/'prompt.txt',json.loads(stage.prompt()))
        ir.write(old/'result.json',{'status':'REPAIR_WAIT','api_calls':0,'execution_health':'UNVERIFIED'})
        self.assertIsNone(proof_reuse.restore_repair_drafts(stage,previous))
        self.assertEqual(stage.own_lean_drafts,{'proof':{},'auxiliary':{}})
        self.assertEqual(ir.load(old/'result.json')['status'],'REPAIR_WAIT')

    def test_old_checked_body_that_fails_current_recheck_is_given_to_own_repair_worker(self):
        import proof_reuse
        stage=self.stage();candidate={'body':'exact h_H001','previous_run':'explicit same-case origin'}
        actual={'exit_code':1,'stdout':'Actual current check: target differs after a reviewed definition repair.'}
        proof_reuse.retain_recheck_failure(stage,candidate,actual)
        row=stage.own_lean_drafts['proof'][1]
        self.assertEqual(row['proof'],candidate['body']);self.assertEqual(row['check'],actual)
        self.assertIsNone(stage.accepted);self.assertIn('No prior proof is accepted',stage.system)
        self.assertEqual(stage.proof_progress.last_turn_revision,stage.proof_progress.revision)

    def test_diagnostic_inputs_include_only_reporting_workers_selected_actual_attempts(self):
        import run_graph
        stage=self.stage()
        with patch.object(ir,'check',return_value={'exit_code':1,'stdout':'located neutral failure'}):
            stage.dispatch('check_transition',{'proof':'exact h_H001'})
        value=dict(self.report(),candidates=[{'kind':'proof','candidate':1}])
        stage.dispatch('report_proof_obstruction',value)
        previous=self.root/'prior';ir.write(self.root/'plan.json',self.plan)
        run_graph.package(self.cpath,self.root/'plan.json',previous)
        destination=previous/'workers/T001';shutil.copytree(stage.logs,destination)
        model=stage.model
        ir.write(destination/'result.json',{'status':'REPAIR_REQUESTED','repair_request':stage.repair_request,
            'model':model,'temporary_workspace_removed':True,'isolation_violation':False,
            'execution_health':'NO_RECORDED_FAULT','usage':{'complete':False},
            'exposure':{'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[model],'standard_tier_verified':True}})
        ir.write(previous/'report.json',{'repair_requests':{'T001':stage.repair_request}})
        (previous/'workers/T002').mkdir();(previous/'workers/T002/foreign.txt').write_text('SIBLING_PRIVATE_CANARY')
        author=self.root/'author';ir.write(author/'inputs/spec.json',{'conclusion':'a neutral source target'})
        shutil.copyfile(self.cpath.parent/'source.json',author/'inputs/nl0.json')
        (author/'inputs/author-history.txt').write_text('OLD_VERDICT_CANARY')
        out=self.root/'diagnosis';proof_diagnosis.prepare(previous,'T001',author,out)
        text=''.join(p.read_text() for p in (out/'inputs').iterdir())
        self.assertNotIn('SIBLING_PRIVATE_CANARY',text);self.assertNotIn('OLD_VERDICT_CANARY',text)
        attempts=ir.load(out/'inputs/own-attempts.json')
        self.assertEqual(attempts[0]['actual_attempt']['proof'],'exact h_H001')
        diagnosis={'route':'LOCAL_PROOF_REPAIR','explanation':'Inspect this actual binder.',
            'repair_advice':'Check the local binder type before applying it.',
            'locations':[{'document':'local-packet.json','pointer':'/inputs/0/type'}],'comparison':None}
        proof_diagnosis.validate(diagnosis,out)
        diagnosis['route']='INTERFACE_REPAIR_REQUIRED'
        with self.assertRaises(ValueError):proof_diagnosis.validate(diagnosis,out)
        record=destination/'lean-drafts/proof-0001.json';ir.write(record,{'tampered':True})
        with self.assertRaisesRegex(ValueError,'Changed own-attempt'):
            proof_diagnosis.prepare(previous,'T001',author,self.root/'tampered-diagnosis')


if __name__=='__main__':unittest.main()
