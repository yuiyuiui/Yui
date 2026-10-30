"""New-run service recovery controls; synthetic fixtures are not audits."""
import harness_support
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, ExitStack
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
import jobs
import interrupted
import case_runner
import full_workflow
import audit_a_campaign
import entrypoint

PROFILES={phase:{'id':'gpt-6.1-sol','reasoning_effort':'high','speed':'standard',
                  'automatic_fallback':False} for phase in ['nl0','lean']}
EXITED={'inspection':{'controller_identity_matches':False,'residual_owned_processes':[]}}


class InterruptedResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.problem=self.root/'arbitrary-problem/problem.md';self.problem.parent.mkdir()
        self.problem.write_text('SYNTHETIC continuation fixture, not a mathematical result.\n')
        self.old=jobs.prepare(self.problem,track='full',profiles=PROFILES)
        self.run=Path(self.old['root']);self.author=self.run/'nl0/0001';self.stage=self.author/'stage'
        self.stage.mkdir(parents=True)
        self.failure={'status':'UNFINISHED','execution_health':'FAULT','isolation_violation':False,
            'execution_fault':'SYNTHETIC provider interruption',
            'transport_health':{'status':'FAULT','faults':[{'kind':'PROVIDER_ERROR',
                'details':{'code':'server_is_overloaded'}}],'uncertainty':[]}}
        self.write(self.stage/'result.json',self.failure)
        self.failed_turn(self.stage)
        self.write(self.run/'case-result.json',{'result':{'status':'AUTHOR_ARTIFACT_INELIGIBLE',
            'evidence':str(self.stage/'result.json'),'completion':{'acceptance_target_satisfied':False}}})
    def tearDown(self):self.temp.cleanup()
    def write(self,path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
    def failed_turn(self,stage,*,status='failed',error=None):
        self.write(stage/'events.jsonl',{'method':'turn/completed','params':{'turn':{
            'id':'synthetic-failed-turn','status':status,
            'error':{'codexErrorInfo':'serverOverloaded'} if error is None else error}}})
    def prepare(self):
        with patch.object(interrupted,'inspect',return_value=EXITED):return interrupted.prepare(self.run)

    def test_new_job_preserves_input_profiles_and_old_fault_without_mutation(self):
        before=(self.run/'job.json').read_bytes();job=self.prepare();jobs.validate(job)
        self.assertNotEqual(job['root'],self.old['root']);self.assertEqual(job['profiles'],PROFILES)
        self.assertEqual(job['documents'][0]['sha256'],self.old['documents'][0]['sha256'])
        self.assertEqual(job['resume']['mode'],'author');self.assertEqual((self.run/'job.json').read_bytes(),before)
        self.assertEqual(json.loads((self.stage/'result.json').read_text()),self.failure)
        self.assertIsNone(job['time_budget_seconds'])

    def test_resume_preserves_selected_target_without_repeating_the_original_material(self):
        import target_selection
        selected=target_selection.select(self.problem,[{'id':'chosen','label':'Selected claim',
            'statement':'Synthetic target that must not change on continuation.','start_line':1}])
        extra=self.root/'secondary.txt';extra.write_text('Explicit additional source.')
        old=jobs.prepare(self.problem,track='full',profiles=PROFILES,target=selected,materials=[extra])
        run=Path(old['root']);stage=run/'nl0/0001/stage'
        self.write(stage/'result.json',self.failure);self.failed_turn(stage)
        self.write(run/'case-result.json',{'result':{'status':'AUTHOR_ARTIFACT_INELIGIBLE',
            'evidence':str(stage/'result.json'),'completion':{'acceptance_target_satisfied':False}}})
        with patch.object(interrupted,'inspect',return_value=EXITED):new=interrupted.prepare(run)
        self.assertEqual(new['target_selection'],selected)
        self.assertEqual(len(new['documents']),3)
        self.assertEqual([r['extraction'] for r in new['documents']].count('target-selection'),1)
        del new['target_selection']
        with self.assertRaisesRegex(ValueError,'selected target'):interrupted.validate_descriptor(new)

    def test_active_owner_or_residual_child_blocks_resumption(self):
        for inspection in [{'controller_identity_matches':True,'residual_owned_processes':[]},
                           {'controller_identity_matches':False,'residual_owned_processes':[{'pid':123}]}]:
            with patch.object(interrupted,'inspect',return_value={'inspection':inspection}):
                with self.assertRaisesRegex(ValueError,'still active'):interrupted.prepare(self.run)

    def test_original_input_drift_and_permanent_failures_are_not_silently_retried(self):
        self.problem.write_text('Changed problem')
        with self.assertRaisesRegex(ValueError,'changed'):self.prepare()
        self.problem.write_text('SYNTHETIC continuation fixture, not a mathematical result.\n')
        self.failure['transport_health']['faults'][0]['details']['code']='insufficient_quota'
        self.write(self.stage/'result.json',self.failure)
        with self.assertRaisesRegex(ValueError,'not a positively identified'):self.prepare()

    def test_isolation_fault_cannot_be_reclassified_as_remote(self):
        self.failure['isolation_violation']=True;self.write(self.stage/'result.json',self.failure)
        with self.assertRaisesRegex(ValueError,'not a positively identified'):self.prepare()

    def test_earlier_remote_error_does_not_bless_a_later_local_or_permanent_stop(self):
        for status,error in [('completed',{}),('failed',{'code':'insufficient_quota'}),
                             ('failed',{'code':'local_protocol_rejected'})]:
            self.failed_turn(self.stage,status=status,error=error)
            with self.assertRaisesRegex(ValueError,'not a positively identified'):self.prepare()

    def test_new_job_binds_the_prior_result_and_cannot_hide_later_changes(self):
        job=self.prepare();self.write(self.stage/'result.json',{})
        with self.assertRaisesRegex(ValueError,'changed'):jobs.validate(job)

    def audit_boundary(self):
        source=self.stage/'case';shutil.copytree(CORE/'tests/fixtures/closed-addition',source)
        self.write(source/'author-check-progress.json',{'synthetic_fixture_only':True})
        self.write(self.stage/'accepted.json',{'synthetic_fixture_only':True})
        (self.stage/'tools.jsonl').write_text('')
        campaign=self.run/'audit-a/0001'
        audit_a_campaign.prepare(source,self.run/'inputs',campaign)
        failed=campaign/'R001/stage/result.json';self.write(failed,self.failure)
        self.failed_turn(failed.parent)
        self.write(self.run/'case-result.json',{'result':{'status':'EXECUTION_UNQUALIFIED',
            'phase':'audit-a','evidence':str(failed),'completion':{'acceptance_target_satisfied':False}}})
        return source,campaign

    def test_resume_dispatch_and_prepare_only_use_the_unified_entry(self):
        parser=argparse.ArgumentParser();entrypoint.parsers(parser.add_subparsers(dest='command'))
        new=self.prepare()
        for prepare_only in [False,True]:
            argv=['resume',str(self.run),'--detach','--case-concurrency','3']
            if prepare_only:argv+=['--prepare-only']
            with patch.object(interrupted,'prepare',return_value=new) as prepare, \
                 patch.object(entrypoint,'launch',return_value={'status':'DISPATCH_CONTROL_ONLY'}) as launch:
                result=entrypoint.dispatch(parser.parse_args(argv))
            prepare.assert_called_once_with(self.run)
            if prepare_only:
                launch.assert_not_called();self.assertEqual(result['runs'],[new['root']])
            else:
                launch.assert_called_once_with([new],detached=True,case_concurrency=3)
                self.assertEqual(result['status'],'DISPATCH_CONTROL_ONLY')

    def test_public_cli_routes_resume_before_the_generic_stage_branch(self):
        self.write(self.run/'execution-status.json',{'controller':{
            'pid':2147483647,'pgid':2147483647,'started':'SYNTHETIC exited owner','state':'EXITED'},
            'processes':{}})
        result=subprocess.run([sys.executable,'-B',str(CORE/'nl0/scripts/yui.py'),'resume',
            str(self.run),'--prepare-only'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        prepared=json.loads(result.stdout)
        self.assertEqual(prepared['status'],'PREPARED_NOT_STARTED')
        self.assertNotEqual(Path(prepared['runs'][0]),self.run)

    def test_evidence_repair_is_an_explicit_guarded_resume_mode(self):
        parser=argparse.ArgumentParser();entrypoint.parsers(parser.add_subparsers(dest='command'))
        args=parser.parse_args(['resume',str(self.run),'--repair-evidence','--prepare-only'])
        with patch.object(interrupted,'prepare',return_value=self.old) as prepare:
            result=entrypoint.dispatch(args)
        prepare.assert_called_once_with(self.run,repair_evidence=True)
        self.assertEqual(result['status'],'PREPARED_NOT_STARTED')
        with self.assertRaisesRegex(ValueError,'known recoverable evidence-index'):
            with patch.object(interrupted,'inspect',return_value=EXITED):
                interrupted.prepare(self.run,repair_evidence=True)

    def local_fixture(self):
        """Synthetic path/repair records; mathematical source gates stay mocked."""
        import nl0_author
        source=self.stage/'case';shutil.copytree(CORE/'tests/fixtures/closed-addition',source)
        probe=source/'library/M021-0001/library-sources.json'
        self.write(probe,{'synthetic_receipt_only':True})
        self.write(self.stage/'result.json',{'status':'ACCEPTED','synthetic_fixture_only':True})
        self.write(self.stage/'accepted.json',{'synthetic_fixture_only':True})
        self.write(source/'author-check-progress.json',{'synthetic_fixture_only':True})
        (self.stage/'tools.jsonl').write_text('')
        campaign=self.run/'audit-a/0001';audit_a_campaign.prepare(source,self.run/'inputs',campaign)
        reviewed=campaign/'R001/stage';reviewed.mkdir()
        self.write(reviewed/'accepted.json',{'findings':[{'verdict':'FAIL',
            'notes':'SYNTHETIC located repair obligation, not an audit.',
            'locations':['/inference/argument/0/text']}]})
        self.write(reviewed/'result.json',{'synthetic_fixture_only':True})
        obligations=case_runner.repair_obligations(source,campaign)
        repair=self.run/'nl0/0002'
        nl0_author.prepare(self.run/'inputs',repair,baseline=source,obligations=obligations)
        stage=repair/'stage';copied=stage/'case/library/M021-0001/library-sources.json'
        self.write(copied,json.loads(probe.read_text()))
        error='FileExistsError: [Errno 17] File exists: '+repr(str(copied.parent))
        self.write(stage/'result.json',{'status':'UNFINISHED','execution_fault':error,
            'temporary_workspace_removed':True,'isolation_violation':False,'execution_health':'FAULT',
            'exposure':{'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED',
                'actual_model_ids':['gpt-6.1-sol'],'standard_tier_verified':True}})
        self.write(stage/'events.jsonl',{'method':'item/tool/call','params':{
            'tool':'probe_library','arguments':{'id':'M021','declaration':'Synthetic.query'}}})
        (stage/'tools.jsonl').write_text('')
        self.write(self.run/'case-result.json',{'result':{'status':'AUTHOR_ARTIFACT_INELIGIBLE',
            'evidence':str(stage/'result.json'),'usage':{'status':'PARTIAL'},
            'completion':{'acceptance_target_satisfied':False}}})
        self.write(self.run/'execution-status.json',{'controller':{
            'pid':2147483647,'pgid':2147483647,'started':'SYNTHETIC exited owner','state':'FINALIZED'},'processes':{}})
        return source,probe,repair,campaign

    @contextmanager
    def local_source_gates(self,source,probe):
        # This fixture exercises recovery wiring, not synthetic proof acceptance.
        import source_preparation
        import owner_observation
        with ExitStack() as stack:
            stack.enter_context(patch.object(interrupted,'inspect',return_value=EXITED))
            stack.enter_context(patch.object(owner_observation,'process_table',return_value={}))
            stack.enter_context(patch.object(full_workflow,'nl0_artifact_for_audit',return_value={'synthetic_control_only':True}))
            stack.enter_context(patch.object(source_preparation,'read_source',return_value=([],[source/'spec.json',source/'nl0.json',probe])))
            stack.enter_context(patch.object(source_preparation,'evidence_paths',return_value=[probe]))
            yield

    def test_probe_collision_resume_restores_the_recorded_repair_without_replaying_authoring(self):
        source,probe,repair,campaign=self.local_fixture()
        old=(self.run/'case-result.json').read_bytes()
        with self.local_source_gates(source,probe):
            job=interrupted.prepare(self.run,repair_local_tool=True);jobs.validate(job)
            self.assertEqual(job['resume']['mode'],'author-repair')
            restored,obligations,prior=interrupted.restore_repair(job)
            self.assertEqual(restored,source);self.assertEqual(prior,[str(campaign)])
            self.assertEqual(obligations,json.loads((repair/'inputs/repair-obligations.json').read_text()))
            patched=self.root/'changed-source';shutil.copytree(source,patched)
            graph=json.loads((patched/'nl0.json').read_text())
            graph['inferences'][0]['argument'][0]['text']+=' Synthetic repair edit.'
            self.write(patched/'nl0.json',graph)
            import nl0_review_loop
            with patch.object(nl0_review_loop,'run',return_value={'graph':str(patched/'nl0.json')}) as review:
                case_runner.nl0_work(job,None,None,lambda *args,**kwargs:None)
            self.assertEqual(review.call_args.kwargs['restored'],source)
            self.assertEqual(review.call_args.kwargs['initial_issues'],obligations)
            self.assertEqual(review.call_args.kwargs['prior'],prior)
        self.assertEqual((self.run/'case-result.json').read_bytes(),old)
        self.assertEqual(job['profiles'],self.old['profiles'])
        self.assertEqual(job['max_concurrency'],self.old['max_concurrency'])

    def test_probe_recovery_rejects_modified_obligations_and_missing_or_changed_inherited_evidence(self):
        source,probe,repair,_=self.local_fixture()
        copied=repair/'stage/case/library/M021-0001/library-sources.json'
        before=copied.read_bytes();copied.write_text('Changed evidence')
        with self.local_source_gates(source,probe):
            with self.assertRaisesRegex(ValueError,'intact inherited'):interrupted.prepare(self.run,repair_local_tool=True)
            copied.write_bytes(before)
            obligations=repair/'inputs/repair-obligations.json';value=json.loads(obligations.read_text())
            value['issues'][0]['note']='Injected different review';self.write(obligations,value)
            with self.assertRaisesRegex(ValueError,'input binding changed'):interrupted.prepare(self.run,repair_local_tool=True)

    def test_probe_recovery_rejects_unknown_faults_submitted_drafts_and_live_process_groups(self):
        source,probe,repair,_=self.local_fixture();path=repair/'stage/result.json'
        original=json.loads(path.read_text())
        with self.local_source_gates(source,probe):
            changed={**original,'execution_fault':'OSError: Unknown local failure'};self.write(path,changed)
            with self.assertRaisesRegex(ValueError,'verified inherited'):interrupted.prepare(self.run,repair_local_tool=True)
            self.write(path,original);candidate=repair/'stage/case/candidate-0001.json';candidate.write_text('{}')
            with self.assertRaisesRegex(ValueError,'draft checkpoint'):interrupted.prepare(self.run,repair_local_tool=True)
            candidate.unlink()
            import owner_observation
            with patch.object(owner_observation,'process_table',return_value={1:{'pid':1,'pgid':2147483647,'started':'Unrelated group member'}}):
                with self.assertRaisesRegex(ValueError,'process and group exits'):interrupted.prepare(self.run,repair_local_tool=True)

    def test_local_recovery_public_prepare_only_preserves_its_explicit_boundary(self):
        source,probe,repair,_=self.local_fixture()
        parser=argparse.ArgumentParser();entrypoint.parsers(parser.add_subparsers(dest='command'))
        args=parser.parse_args(['resume',str(self.run),'--repair-local-tool','--prepare-only'])
        with self.local_source_gates(source,probe),patch.object(entrypoint,'launch') as launch:
            result=entrypoint.dispatch(args)
            job=json.loads((Path(result['runs'][0])/'job.json').read_text())
            self.assertEqual(job['resume']['repair_directory'],str(repair));launch.assert_not_called()
            job['max_concurrency']=17
            with self.assertRaisesRegex(ValueError,'worker count'):interrupted.validate_descriptor(job)

    def test_author_lineage_remains_exact_across_multiple_continuations(self):
        first=self.prepare()
        outcome=Path(first['root'])/'case-result.json';self.write(outcome,{'result':{'status':'EXECUTION_FAULT'}})
        new=jobs.prepare(self.problem,track='full',profiles=PROFILES,
            resume={**first['resume'],'prior_run':first['root']},
            resume_bindings=[__import__('controller_common').bind(Path(first['root'])/'job.json'),
                __import__('controller_common').bind(outcome),
                __import__('controller_common').bind(self.stage/'result.json')])
        jobs.validate(new)
        new['resume']['author_directory']=str(self.root/'unrelated-author')
        with self.assertRaisesRegex(ValueError,'bound authority lineage'):interrupted.validate_descriptor(new)

    def test_released_source_resumes_only_its_same_case_audit_without_author_replay(self):
        source,campaign=self.audit_boundary();before=(source/'nl0.json').read_bytes()
        with patch.object(full_workflow,'nl0_artifact_for_audit',return_value={'synthetic_control_only':True}) as release:
            job=self.prepare()
            self.assertEqual(job['resume']['mode'],'audit-a')
            import nl0_review_loop
            def restored_result(*args,**kwargs):return {'graph':str(kwargs['restored']/'nl0.json')}
            with patch.object(case_runner,'author_stage') as author, \
                 patch.object(nl0_review_loop,'run',side_effect=restored_result) as audit:
                authority=case_runner.nl0_work(job,None,None,lambda *args,**kwargs:None)
            author.assert_not_called();self.assertEqual(release.call_count,2)
        self.assertEqual(audit.call_args.kwargs['prior'],[str(campaign)])
        self.assertEqual(Path(authority['graph']).read_bytes(),before)
        self.assertEqual((source/'nl0.json').read_bytes(),before)
        origin=json.loads((Path(job['root'])/'resumed-source/source-origin.json').read_text())
        self.assertFalse(origin['new_author_model_called'])

    def test_unreleased_author_cannot_be_promoted_to_audit_recovery(self):
        self.audit_boundary()
        with self.assertRaises(Exception) as result:self.prepare()
        self.assertNotIsInstance(result.exception,FileNotFoundError)

    def test_explicit_time_budget_is_never_reset_by_resume(self):
        bounded=jobs.prepare(self.problem,track='full',profiles=PROFILES,time_budget_seconds=10)
        run=Path(bounded['root']);stage=run/'nl0/0001/stage/result.json';self.write(stage,self.failure)
        self.failed_turn(stage.parent)
        self.write(run/'case-result.json',{'result':{'evidence':str(stage)}})
        self.write(run/'execution-status.json',{'time_budget':{'seconds':10}})
        with patch.object(interrupted,'inspect',return_value=EXITED):
            with self.assertRaisesRegex(ValueError,'cannot reset'):interrupted.prepare(run)


if __name__=='__main__':unittest.main()
