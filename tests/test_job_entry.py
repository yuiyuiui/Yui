"""Standalone installation, profile and repair-wiring controls. No model is invoked."""
import harness_support
from harness_support import PROFILES
import argparse
from contextvars import copy_context
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
import jobs
import entrypoint
import runtime_config as config
import nl0_author
import case_runner
import full_workflow
import execution_state
from execution_health import StageFailure



class JobEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.problem=self.root/'arbitrary-paper/proof.md';self.problem.parent.mkdir();self.problem.write_text('An explicitly supplied proof.\n')
    def tearDown(self):self.temp.cleanup()
    def job(self,track='nl0',**kwargs):return jobs.prepare(self.problem,track=track,profiles=PROFILES,**kwargs)

    def test_default_output_is_beside_arbitrary_problem_not_installed_skill(self):
        job=self.job();root=Path(job['root']);jobs.validate(job)
        self.assertEqual(root.parent,self.problem.parent/'rigorous-proof')
        self.assertEqual(self.problem.read_text(),'An explicitly supplied proof.\n')
        self.assertEqual((root/'inputs/problem.md').read_bytes(),self.problem.read_bytes())
        self.assertEqual(job['policy'],'normal');self.assertIsNone(job['time_budget_seconds'])

    def test_only_explicit_materials_are_staged(self):
        secret=self.problem.parent/'personal-memory.md';secret.write_text('DO NOT EXPOSE')
        extra=self.root/'allowed.tex';extra.write_text('Supplied external theorem statement.')
        job=self.job(materials=[extra]);root=Path(job['root'])
        self.assertEqual(len(job['documents']),2)
        self.assertNotIn('DO NOT EXPOSE',''.join(p.read_text() for p in (root/'inputs').iterdir()))

    def test_job_binds_optional_library_selection_even_when_absent(self):
        import os
        with patch.dict(os.environ,{'YUI_LIBRARY_ROOT':str(self.root/'catalog-one')}):
            job=self.job();jobs.validate(job)
            self.assertEqual(job['library_catalog']['files'],[])
            with patch.dict(os.environ,{'YUI_LIBRARY_ROOT':str(self.root/'catalog-two')}):
                jobs.validate(job) # A later installation/environment change is not an active-job change.
            catalog=self.root/'catalog-one';catalog.mkdir()
            (catalog/'foundations.json').write_text('{"version":1,"entries":[]}')
            jobs.validate(job)
            frozen=Path(job['runtime_snapshot']['library_root'])
            (frozen/'foundations.json').write_text('{"version":1,"entries":[]}')
            with self.assertRaisesRegex(ValueError,'library selection|undeclared'):jobs.validate(job)

    def test_job_binds_original_inputs_and_cannot_write_into_installation(self):
        job=self.job();self.problem.write_text('Changed after freeze')
        with self.assertRaisesRegex(ValueError,'changed'):jobs.validate(job)
        with self.assertRaises(ValueError):self.job(output=CORE/'not-a-run')
        with self.assertRaises(ValueError):self.job(output=self.problem.parent)

    def test_altering_the_staging_manifest_cannot_add_undeclared_files(self):
        job=self.job();path=Path(job['root'])/'inputs/inputs.json'
        path.write_text(json.dumps({'inputs':[{'id':'secret','path':'../../outside','sha256':'0'*64}]}))
        with self.assertRaisesRegex(ValueError,'manifest changed'):jobs.validate(job)

    def test_freezing_rejects_unknown_tracks_and_missing_authority(self):
        for track in ('unknown','translate','audit-b'):
            with self.assertRaises(ValueError):self.job(track)
        with self.assertRaises(ValueError):self.job(time_budget_seconds=0)
        with self.assertRaises(ValueError):self.job(max_concurrency=0)

    def test_accepted_source_cannot_be_attached_to_a_different_supplied_problem(self):
        source=self.root/'other-source';source.mkdir()
        data=[{'current_standard_receipt_valid':True},{},{'inputs':[{'sha256':'0'*64}]}]
        with patch.object(case_runner.source_preparation,'read_source',return_value=(data,[])):
            with self.assertRaisesRegex(ValueError,'differs from the accepted'):
                self.job('translate',source=source)

    def test_run_profiles_are_phase_local_and_survive_worker_thread_context(self):
        original=(CORE/'config.json').read_bytes()
        with config.use_profiles(PROFILES):
            self.assertEqual(config.model_profile('audit-a-global')['id'],'gpt-6.1-sol')
            self.assertEqual(config.model_profile('audit-b-review')['id'],'gpt-6-luna')
            with ThreadPoolExecutor(1) as pool:
                result=pool.submit(copy_context().run,config.model_profile,'proof').result()
            self.assertEqual(result['reasoning_effort'],'medium')
        self.assertEqual((CORE/'config.json').read_bytes(),original)
        self.assertEqual(config.model_profile('proof')['selection_origin'],'installation_defaults')

    def test_missing_profiles_request_configuration_without_model_or_output(self):
        command=[sys.executable,'-B',str(CORE/'nl0/scripts/yui.py'),'prepare',str(self.problem),'--track','full']
        r=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('Ask once',r.stdout)
        self.assertFalse((self.problem.parent/'rigorous-proof').exists())

    def test_new_proof_runs_require_numeric_worker_confirmation_before_preparation(self):
        parser=argparse.ArgumentParser()
        entrypoint.parsers(parser.add_subparsers(dest='command'))
        for command in ('prepare','run'):
            for track in ('full','translate'):
                for count in (None,'auto','0','-1','2.5'):
                    argv=[command,str(self.problem),'--track',track,'--use-config-profiles']
                    if count is not None:argv+=['--max-concurrency',count]
                    with self.subTest(command=command,track=track,count=count), \
                         patch.object(jobs,'prepare') as prepare, \
                         patch.object(entrypoint,'launch') as launch:
                        with self.assertRaisesRegex(ValueError,'proof-worker count|concurrency'):
                            entrypoint.dispatch(parser.parse_args(argv))
                        prepare.assert_not_called();launch.assert_not_called()
        self.assertFalse((self.problem.parent/'rigorous-proof').exists())

    def test_nl0_public_entry_needs_its_profile_and_local_review_capacity(self):
        parser=argparse.ArgumentParser()
        entrypoint.parsers(parser.add_subparsers(dest='command'))
        args=parser.parse_args(['prepare',str(self.problem),'--track','nl0',
            '--nl0-model','gpt-6.1-sol','--nl0-effort','high','--nl0-speed','standard',
            '--max-concurrency','3','--target','An explicit synthetic target.'])
        result=entrypoint.dispatch(args)
        self.assertIsNone(result['proof_concurrency'])
        job=json.loads((Path(result['runs'][0])/'job.json').read_text())
        self.assertEqual(job['track'],'nl0')
        self.assertEqual(job['profiles']['nl0'],PROFILES['nl0'])
        self.assertEqual(result['audit_r_concurrency']['effective'],3)

    def test_full_public_entry_freezes_both_profiles_and_confirmed_workers(self):
        parser=argparse.ArgumentParser()
        entrypoint.parsers(parser.add_subparsers(dest='command'))
        args=parser.parse_args(['prepare',str(self.problem),'--track','full',
            '--nl0-model','gpt-6.1-sol','--nl0-effort','high','--nl0-speed','standard',
            '--lean-model','gpt-6-luna','--lean-effort','medium','--lean-speed','standard',
            '--max-concurrency','5','--target','An explicit synthetic target.'])
        result=entrypoint.dispatch(args)
        job=json.loads((Path(result['runs'][0])/'job.json').read_text())
        self.assertEqual(job['profiles'],PROFILES)
        self.assertEqual(job['max_concurrency'],5)
        self.assertEqual(result['proof_concurrency']['effective'],5)
        import concurrency
        budgets=concurrency.CaseBudgets(job['max_concurrency'])
        self.assertEqual(budgets.proof.configuration['effective'],5)
        self.assertEqual(budgets.serial.configuration['effective'],1)

    def test_translation_public_entry_needs_only_lean_profile_and_workers(self):
        source=self.root/'accepted';source.mkdir()
        from controller_common import bind
        parser=argparse.ArgumentParser()
        entrypoint.parsers(parser.add_subparsers(dest='command'))
        args=parser.parse_args(['prepare',str(self.problem),'--track','translate',
            '--source',str(source),'--lean-model','gpt-6-luna','--lean-effort','medium',
            '--lean-speed','standard','--max-concurrency','3'])
        with patch.object(case_runner.source_preparation,'read_source',return_value=([
            {'current_standard_receipt_valid':True},{},{'inputs':[{'sha256':bind(self.problem)['sha256']}]}],[])):
            result=entrypoint.dispatch(args)
        job=json.loads((Path(result['runs'][0])/'job.json').read_text())
        self.assertEqual(job['track'],'translate')
        self.assertEqual(job['profiles']['lean'],PROFILES['lean'])
        self.assertEqual(job['max_concurrency'],3)
        self.assertEqual(result['proof_concurrency']['effective'],3)

    def test_public_cli_model_defaults_do_not_supply_missing_workers(self):
        result=subprocess.run([sys.executable,'-B',str(CORE/'nl0/scripts/yui.py'),
            'prepare',str(self.problem),'--track','full','--use-config-profiles'],
            capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('--max-concurrency N',json.loads(result.stdout)['error'])
        self.assertFalse((self.problem.parent/'rigorous-proof').exists())

    def test_backend_checks_selected_model_and_effort_without_fallback(self):
        job=self.job();home=self.root/'auth';home.mkdir()
        (home/'models_cache.json').write_text(json.dumps({'models':[{'slug':'gpt-6.1-sol','supported_reasoning_levels':[{'effort':'low'}]}]}))
        with patch.object(entrypoint,'auth_home',return_value=home):
            with self.assertRaisesRegex(ValueError,'does not advertise'):entrypoint.preflight_profiles(job)
        with self.assertRaisesRegex(ValueError,'Standard speed only'):
            config.validate_profile({**PROFILES['nl0'],'speed':'unsupported'})

    def test_run_and_execute_dispatch_to_the_actual_launcher(self):
        parser=argparse.ArgumentParser()
        entrypoint.parsers(parser.add_subparsers(dest='command'))
        for command in ('run','execute'):
            with self.subTest(command=command):
                if command=='run':
                    argv=['run',str(self.problem),'--track','nl0',
                          '--nl0-model','gpt-6.1-sol','--nl0-effort','high','--nl0-speed','standard',
                          '--max-concurrency','2','--target','An explicit synthetic target.']
                else:
                    argv=['execute',self.job()['root']]
                args=parser.parse_args(argv+['--detach','--case-concurrency','3'])
                with patch.object(entrypoint,'launch',return_value={'status':'LAUNCH_CONTROL_ONLY'}) as launcher:
                    result=entrypoint.dispatch(args)
                    self.assertEqual(result['status'],'LAUNCH_CONTROL_ONLY')
                    if command=='run':self.assertIn('source_policy_notice',result)
                launcher.assert_called_once()
                self.assertEqual(launcher.call_args.kwargs,{'detached':True,'case_concurrency':3})
                self.assertEqual(len(launcher.call_args.args[0]),1)
                jobs.validate(launcher.call_args.args[0][0])

    def test_author_and_reviewer_inputs_do_not_include_sibling_or_prior_verdict(self):
        job=self.job();root=Path(job['root']);out=root/'nl0/0001'
        (self.problem.parent/'old-verdict.json').write_text('{"verdict":"PASS"}')
        nl0_author.prepare(root/'inputs',out)
        docs=json.loads((out/'inputs/inputs.json').read_text())['inputs']
        self.assertEqual([r['id'] for r in docs],['problem.md'])

    def test_normal_public_entry_dispatches_the_retained_role_controller(self):
        import nl0_review_loop
        import concurrency
        job=self.job();root=Path(job['root']);serial=concurrency.serial_budget()
        local=concurrency.Budget(concurrency.resolve(2),role='audit_r')
        expected={'graph':str(root/'nl0/current/nl0.json'),'spec':str(root/'nl0/current/spec.json'),'audit_a':str(root/'nl0/current/audit-a.json')}
        with patch.object(nl0_review_loop,'run',return_value=expected) as runner,patch.object(full_workflow,'audit_source') as legacy:
            result=case_runner.nl0_work(job,None,serial,lambda *a,**k:None,audit_budget=local)
        self.assertEqual(result,expected);self.assertEqual(runner.call_count,1);legacy.assert_not_called()
        self.assertIs(runner.call_args.args[1],serial);self.assertIs(runner.call_args.args[2],local)
        self.assertEqual(runner.call_args.kwargs,{'restored':None,'prior':[],'initial_issues':None})

    def test_first_pass_policy_stops_after_actual_first_nonpass(self):
        job=self.job(policy='first-pass')
        with patch.object(case_runner,'source_key',return_value='source'), \
             patch.object(case_runner,'author_stage',return_value=self.root/'source') as author, \
             patch.object(full_workflow,'audit_source',return_value={'full_acceptance':False}), \
             patch.object(case_runner,'repair_obligations') as repair:
            with self.assertRaises(StageFailure):case_runner.nl0_work(job,None,None,lambda *a,**k:None)
        self.assertEqual(author.call_count,1);repair.assert_not_called()

    def test_case_has_separate_serial_and_five_proof_slots_and_no_new_a_for_translation(self):
        source=self.root/'accepted';source.mkdir()
        from controller_common import bind
        with patch.object(case_runner.source_preparation,'read_source',return_value=([
            {'current_standard_receipt_valid':True},{},{'inputs':[{'sha256':bind(self.problem)['sha256']}]}],[])):
            job=self.job('translate',source=source,max_concurrency=5)
        def translate(job,authority,budgets,progress):
            self.assertEqual(budgets.serial.configuration['effective'],1)
            self.assertEqual(budgets.proof.configuration['effective'],5)
            self.assertEqual(config.model_profile('proof')['id'],'gpt-6-luna')
            return {'status':'SYNTHETIC_CONTROL_ONLY'}
        with patch.object(case_runner.source_preparation,'read_source'), \
             patch.object(case_runner,'translation_work',side_effect=translate), \
             patch.object(case_runner,'nl0_work') as author, \
             patch('fault_control.Gate.pause',side_effect=execution_state.Cancelled('Synthetic user cancellation')):
            result=case_runner.execute(job)
        author.assert_not_called();self.assertFalse(result['completion']['acceptance_target_satisfied'])
        self.assertFalse(execution_state.inspect(Path(job['root']))['inspection']['residual_owned_processes'])

    def test_standalone_copy_prepares_and_reports_without_repository_or_test_support(self):
        elsewhere=self.root/'unrelated working directory';elsewhere.mkdir()
        env=os.environ.copy();env.pop('YUI_LIBRARY_ROOT',None)
        for include_catalog in (True,False):
            with self.subTest(include_catalog=include_catalog):
                parent=self.root/('with catalog' if include_catalog else 'without catalog')
                install=parent/'renamed skill root'
                ignored=['__pycache__','results','.git','tests']
                if not include_catalog:ignored.append('library')
                shutil.copytree(CORE,install,ignore=shutil.ignore_patterns(*ignored))
                foreign=parent/'library';foreign.mkdir()
                (foreign/'foundations.json').write_text('Unrelated sibling; must never be read.')
                command=[sys.executable,'-B',str(install/'nl0/scripts/yui.py')]
                result=subprocess.run(command+['prepare',str(self.problem),'--track','nl0',
                    '--nl0-model','gpt-6.1-sol','--nl0-effort','high','--nl0-speed','standard',
                    '--max-concurrency','2','--target','An explicit synthetic target.'],
                    cwd=elsewhere,env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr+result.stdout)
                prepared=json.loads(result.stdout);run=Path(prepared['runs'][0])
                status=subprocess.run(command+['status',str(run)],cwd=elsewhere,env=env,capture_output=True,text=True)
                self.assertEqual(status.returncode,0,status.stderr)
                self.assertEqual(json.loads(status.stdout)[str(run)]['phase'],'PREPARED_NOT_STARTED')
                self.assertFalse((install/'tests').exists())
                self.assertFalse((install/'rigorous-proof').exists())
                job=json.loads((run/'job.json').read_text())
                frozen=run/'runtime'
                self.assertTrue(all(Path(row['path']).is_relative_to(frozen) for row in job['runtime']))
                catalog=job['library_catalog']
                self.assertEqual(Path(catalog['path']),frozen/'library/foundations.json')
                self.assertEqual(bool(catalog['files']),include_catalog)
                self.assertTrue(all(Path(row['path']).is_relative_to(frozen) for row in catalog['files']))


if __name__=='__main__':unittest.main()
