"""Standalone installation, profile and repair-wiring controls. No model is invoked."""
import argparse
from contextvars import copy_context
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
for path in (CORE/'scripts',CORE/'translation/scripts'):
    sys.path.insert(0,str(path))
import jobs
import entrypoint
import runtime_config as config
import nl0_author
import case_runner
import full_workflow
import execution_state
from execution_health import StageFailure

PROFILES={'nl0':{'id':'gpt-6.1-sol','reasoning_effort':'high','speed':'standard','automatic_fallback':False},
          'lean':{'id':'gpt-6-luna','reasoning_effort':'medium','speed':'standard','automatic_fallback':False}}


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
        command=[sys.executable,'-B',str(CORE/'scripts/yui.py'),'prepare',str(self.problem),'--track','full']
        r=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('Ask once',r.stdout)
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
                          '--nl0-model','gpt-6.1-sol','--nl0-effort','high','--nl0-speed','standard']
                else:
                    argv=['execute',self.job()['root']]
                args=parser.parse_args(argv+['--detach','--case-concurrency','3'])
                with patch.object(entrypoint,'launch',return_value={'status':'LAUNCH_CONTROL_ONLY'}) as launcher:
                    self.assertEqual(entrypoint.dispatch(args),{'status':'LAUNCH_CONTROL_ONLY'})
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

    def test_normal_policy_routes_located_a_findings_to_changed_author_revision(self):
        job=self.job();root=Path(job['root'])
        source1=self.root/'source1';source2=self.root/'source2'
        for p in (source1,source2):p.mkdir()
        diagnosis={'issues':[{'id':'one','location':'/graph/inferences/0','note':'Located defect','criterion':'A4'}]}
        with patch.object(case_runner,'source_key',side_effect=['first','second']), \
             patch.object(case_runner,'author_stage',side_effect=[source1,source2]) as author, \
             patch.object(full_workflow,'audit_source',side_effect=[{'full_acceptance':False},{'full_acceptance':True}]) as audit, \
             patch.object(case_runner,'repair_obligations',return_value=diagnosis):
            result=case_runner.nl0_work(job,None,None,lambda *a,**k:None)
        self.assertEqual(Path(result['graph']).parent,source2)
        self.assertEqual(author.call_args.kwargs['baseline'],source1)
        self.assertEqual(audit.call_args.kwargs['reuse_from'],[root/'audit-a/0001'])
        self.assertTrue((root/'repairs/audit-a-0001.json').is_file())

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
             patch.object(case_runner,'nl0_work') as author:
            result=case_runner.execute(job)
        author.assert_not_called();self.assertFalse(result['completion']['acceptance_target_satisfied'])
        self.assertFalse(execution_state.inspect(Path(job['root']))['inspection']['residual_owned_processes'])

    def test_standalone_copy_prepares_and_reports_without_repository_or_test_support(self):
        install=self.root/'installed-skill'
        shutil.copytree(CORE,install,ignore=shutil.ignore_patterns('__pycache__','results','.git'))
        command=[sys.executable,'-B',str(install/'scripts/yui.py')]
        result=subprocess.run(command+['prepare',str(self.problem),'--track','nl0',
            '--nl0-model','gpt-6.1-sol','--nl0-effort','high','--nl0-speed','standard'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        prepared=json.loads(result.stdout);run=Path(prepared['runs'][0])
        status=subprocess.run(command+['status',str(run)],capture_output=True,text=True)
        self.assertEqual(status.returncode,0,status.stderr)
        self.assertEqual(json.loads(status.stdout)[str(run)]['phase'],'PREPARED_NOT_STARTED')
        self.assertFalse((install.parent/'test/support').exists())
        self.assertTrue(all(Path(row['path']).is_relative_to(install) for row in json.loads((run/'job.json').read_text())['runtime']))


if __name__=='__main__':unittest.main()
