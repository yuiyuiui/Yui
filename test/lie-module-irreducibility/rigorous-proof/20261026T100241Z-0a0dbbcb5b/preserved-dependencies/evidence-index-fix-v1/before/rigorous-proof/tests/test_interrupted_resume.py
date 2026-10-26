"""New-run service recovery controls; synthetic fixtures are not audits."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CORE/'scripts'),str(CORE/'translation/scripts')]
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
        result=subprocess.run([sys.executable,'-B',str(CORE/'scripts/yui.py'),'resume',
            str(self.run),'--prepare-only'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        prepared=json.loads(result.stdout)
        self.assertEqual(prepared['status'],'PREPARED_NOT_STARTED')
        self.assertNotEqual(Path(prepared['runs'][0]),self.run)

    def test_released_source_resumes_only_its_same_case_audit_without_author_replay(self):
        source,campaign=self.audit_boundary();before=(source/'nl0.json').read_bytes()
        with patch.object(full_workflow,'nl0_artifact_for_audit',return_value={'synthetic_control_only':True}) as release:
            job=self.prepare()
            self.assertEqual(job['resume']['mode'],'audit-a')
            with patch.object(case_runner,'author_stage') as author, \
                 patch.object(full_workflow,'audit_source',return_value={'full_acceptance':True}) as audit:
                authority=case_runner.nl0_work(job,None,None,lambda *args,**kwargs:None)
            author.assert_not_called();self.assertEqual(release.call_count,2)
        self.assertEqual(audit.call_args.kwargs['reuse_from'],[str(campaign)])
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
