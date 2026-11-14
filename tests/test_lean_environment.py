"""Per-run host selection, frozen authority and actual native compatibility."""
import harness_support
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import jobs
import lean_environment as environments
import runtime_config
import runtime_snapshot
from controller_common import bind


OLD = Path.home() / 'formalization-tools/lean-mathlib-v4.32.2'


class SelectedEnvironment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selected = environments.resolve(lean_root=OLD/'lean', mathlib_root=OLD/'mathlib')

    def test_descriptor_records_the_actual_pair_and_successful_native_probe(self):
        selected = self.selected
        self.assertEqual(selected['lean']['version_number'], '4.32.2')
        self.assertEqual(selected['mathlib']['rev'], '905b95818eb32af7874a58b427f50c1711a5e96c')
        self.assertTrue(selected['compatibility']['accepted'])
        self.assertEqual(selected['compatibility']['exit_code'], 0)
        self.assertEqual(selected['lean']['binary_sha256'],
                         bind(Path(selected['lean']['local_path'])/'bin/lean')['sha256'])
        environments.verify(selected)

    def test_explicit_pair_is_not_replaced_by_a_discovered_version(self):
        with patch.object(environments, 'discover', side_effect=AssertionError('unexpected discovery')):
            self.assertEqual(environments.resolve(lean_root=OLD/'lean', mathlib_root=OLD/'mathlib'),
                             self.selected)

    def test_context_and_child_environment_keep_the_frozen_pair(self):
        original = deepcopy(self.selected)
        with runtime_config.use_environment(original):
            self.assertEqual(runtime_config.load_lock()['mathlib']['rev'], original['mathlib']['rev'])
            exposed = runtime_config.load_lock()
            exposed['mathlib']['rev'] = 'altered returned copy'
            self.assertEqual(runtime_config.load_lock()['mathlib']['rev'], original['mathlib']['rev'])
        with patch.dict(os.environ, {'YUI_LEAN_IMPORT_ROOT': '/unrelated-case/imported-lean'}):
            env = runtime_snapshot.environment({'lean_environment': original})
        self.assertNotIn('YUI_LEAN_IMPORT_ROOT', env)
        self.assertEqual(json.loads(env['YUI_LEAN_ENVIRONMENT']), original)
        command = [sys.executable, '-B', '-c',
                   'import json,runtime_config;print(json.dumps(runtime_config.scientific_pins()))']
        env['PYTHONPATH'] = str(harness_support.CORE/'nl0/scripts')
        observed = json.loads(subprocess.check_output(command, env=env, text=True))
        self.assertEqual(observed['lean_version'], '4.32.2')
        self.assertEqual(original, self.selected)

    def test_natural_language_job_needs_only_the_host_carrier(self):
        with tempfile.TemporaryDirectory() as raw:
            problem = Path(raw)/'problem.md'
            problem.write_text('If P then P.')
            with patch.object(environments, 'resolve', side_effect=AssertionError('NL0 must not select Lean')):
                job = jobs.prepare(problem, track='nl0', profiles=harness_support.PROFILES)
                self.assertIsNone(job['lean_environment'])
                jobs.validate(job)
                with runtime_config.use_environment(None):
                    self.assertIsNone(runtime_config.load_lock()['lean'])
                    self.assertEqual(runtime_config.scientific_pins()['lean_version'], 'NOT_SELECTED')
                    runtime_config.verify()
        env=dict(os.environ,YUI_LEAN_ROOT='/missing/lean',YUI_MATHLIB_ROOT='/missing/mathlib')
        env.pop('YUI_LEAN_ENVIRONMENT',None)
        cp=subprocess.run([sys.executable,'-B',str(harness_support.CORE/'nl0/scripts/yui.py'),
                           'doctor','--no-lean'],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertIsNone(json.loads(cp.stdout)['resolved_environment']['lean'])

    def test_formal_job_freezes_selected_authority_before_runtime_snapshot(self):
        with tempfile.TemporaryDirectory() as raw:
            problem = Path(raw)/'problem.md'
            problem.write_text('If P then P.')
            job = jobs.prepare(problem, track='full', profiles=harness_support.PROFILES,
                               lean_environment=self.selected)
            self.assertEqual(job['version'],'yui-case-job-5')
            self.assertEqual(job['lean_environment'], self.selected)
            jobs.validate(job)
            with patch.object(environments, 'resolve', side_effect=AssertionError('no reselection')):
                jobs.validate(job)
            altered = deepcopy(job)
            altered['lean_environment']['mathlib']['rev'] = '0' * 40
            with self.assertRaises(ValueError):
                jobs.validate(altered)
            missing=deepcopy(job)
            missing.pop('lean_environment')
            with self.assertRaises(ValueError):
                jobs.validate(missing)

    def test_v3_frozen_jobs_remain_readable_without_an_attachment_field(self):
        with tempfile.TemporaryDirectory() as raw:
            problem=Path(raw)/'proof.md';problem.write_text('If P then P.')
            job=jobs.prepare(problem,track='full',profiles=harness_support.PROFILES,lean_environment=self.selected)
            job['version']='yui-case-job-3';job.pop('lean_libraries')
            root=Path(job['root']);(root/'job.json').write_text(json.dumps(job))
            marker=json.loads((root/jobs.MARKER).read_text());marker.update(version=job['version'],job=bind(root/'job.json'))
            (root/jobs.MARKER).write_text(json.dumps(marker));jobs.validate(job)

    def test_translate_and_audit_tracks_freeze_the_same_explicit_pair(self):
        import source_preparation
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve()
            problem=root/'proof.md';problem.write_text('Given P, conclude P.')
            source=root/'source';source.mkdir()
            for name in ('Proof.lean','compiler.json','mechanical.json','mapping.json'):
                (source/name).write_text('example : True := by trivial\n' if name.endswith('.lean') else '{}')
            authority=[{'current_standard_receipt_valid':True},{},
                       {'inputs':[{'sha256':bind(problem)['sha256']}]}]
            with patch.object(source_preparation,'read_source',return_value=(authority,[])):
                for track,option in (('translate',{'source':source}),('audit-b',{'audit':source})):
                    job=jobs.prepare(problem,track=track,profiles=harness_support.PROFILES,
                                     lean_environment=self.selected,**option)
                    self.assertEqual(job['lean_environment'],self.selected)
                    jobs.validate(job)

    def test_resume_preparation_inherits_prior_selection_without_discovery(self):
        import basis
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve()
            problem=root/'proof.md';problem.write_text('Given P, conclude P.')
            old=jobs.prepare(problem,track='full',profiles=harness_support.PROFILES,
                             lean_environment=self.selected)
            with patch.object(environments,'resolve',side_effect=AssertionError('no new selection')), \
                    patch.object(basis,'recovery_bindings',return_value=[]):
                continued=jobs.prepare(problem,track='full',profiles=harness_support.PROFILES,
                    resume={'mode':'basis-revision','prior_run':old['root']})
            self.assertEqual(continued['lean_environment'],old['lean_environment'])

    def test_binary_or_manifest_drift_cannot_reuse_a_frozen_environment(self):
        for section, key in (('lean', 'binary_sha256'), ('mathlib', 'manifest_sha256'),
                             ('mathlib', 'rev')):
            changed = deepcopy(self.selected)
            changed[section][key] = '0' * len(changed[section][key])
            with self.subTest(field=key), self.assertRaises(ValueError):
                environments.verify(changed)

    def test_audited_nl0_without_lean_gets_current_interface_pins_without_rewriting_the_source(self):
        import ir
        import workflow
        from final_acceptance_fixtures import frozen_case
        selected_file=os.environ.get('YUI_TEST_ALTERNATE_ENVIRONMENT')
        selected=json.loads(Path(selected_file).read_text()) if selected_file else self.selected
        def natural_only(source):
            spec=ir.load(source/'spec.json')
            spec['pins']=dict.fromkeys(('lean_version','mathlib_commit','mathlib_root'),'NOT_SELECTED')
            ir.write(source/'spec.json',spec)
            graph=ir.load(source/'nl0.json');graph['spec_sha256']=ir.digest(source/'spec.json')
            ir.write(source/'nl0.json',graph)
        with tempfile.TemporaryDirectory() as raw,runtime_config.use_environment(selected):
            root=Path(raw).resolve()
            directory=frozen_case(root,prepare_source=natural_only)
            contract=ir.contract(workflow.bound(directory)['contract'])
            self.assertEqual(contract['pins'],environments.rules.pins(selected))
            self.assertEqual(ir.load(root/'source/spec.json')['pins']['lean_version'],'NOT_SELECTED')

    def test_real_public_entry_uses_its_selected_pair_through_delivery_and_cleanup(self):
        import delivery
        import cleanup
        from basis_fixtures import TARGET
        selected_file=os.environ.get('YUI_TEST_ALTERNATE_ENVIRONMENT')
        selected=json.loads(Path(selected_file).read_text()) if selected_file else self.selected
        for goal,mode,scope in (('conditional','direct','CONDITIONAL_LEAN'),
                                ('unconditional','planned-closed','UNCONDITIONAL_LEAN')):
            with self.subTest(goal=goal),tempfile.TemporaryDirectory() as raw:
                root=Path(raw).resolve()
                problem=root/'proof.md'
                problem.write_bytes((harness_support.FIXTURES/'closed-addition/problem.txt').read_bytes())
                run=root/'run'
                bridge=harness_support.TESTS/'tooling/public_entry_control.py'
                command=[sys.executable,'-B',str(bridge),mode+'+reference','run',str(problem),
                         '--track','full','--formalization',goal,'--target',TARGET,
                         '--use-config-profiles','--nl0-effort','max','--lean-effort','xhigh',
                         '--max-concurrency','1','--output',str(run),
                         '--lean-root',selected['lean']['local_path'],
                         '--mathlib-root',selected['mathlib']['local_path']]
                if goal=='unconditional':
                    from lean_library_fixtures import library
                    with runtime_config.use_environment(selected):
                        specification=library(root/'external-library',modern=True)
                    command+=['--lean-library',str(specification)]
                    imported=root/'imported.lean'
                    imported.write_text('import Mathlib\nimport FixtureLib.Leaf\nnamespace ImportedExample\n'
                        'theorem add_zero (n : Nat) : n + 0 = n := by\n'
                        '  have _ : True := FixtureLib.witness\n  rfl\nend ImportedExample\n')
                    command[3]=mode+'+imported-lean+reference'
                    command+=['--material',str(imported)]
                result=subprocess.run(command,capture_output=True,text=True,timeout=300)
                self.assertEqual(result.returncode,0,(result.stdout+'\n'+result.stderr)[-12000:])
                job=json.loads((run/'job.json').read_text())
                record=json.loads((run/'delivery/run.json').read_text())
                references=[]
                for path in run.rglob('tools.jsonl'):
                    for line in path.read_text().splitlines():
                        event=json.loads(line)
                        if event.get('tool')=='consult_strategy':references.append(event['result'])
                self.assertTrue(references)
                complete=[r for r in references if r.get('status')=='cards']
                self.assertTrue(complete)
                reference_environment={'lean_version':self.selected['lean']['version_number'],
                    'mathlib_commit':self.selected['mathlib']['rev'],'basis':'historical_configuration'}
                for reply in references:
                    self.assertIn(reply.get('status'),{'catalog','cards'},reply)
                    self.assertTrue(reply['reference_only'])
                    self.assertTrue(reply['current_environment_verification_required'])
                    for item in reply[reply['status']]:
                        self.assertEqual(item['reference_environments'],[reference_environment])
                self.assertTrue(any(r['cards'] for r in complete))
                self.assertEqual(job['lean_environment']['lean']['version_number'],selected['lean']['version_number'])
                self.assertEqual(record['lean_environment'],job['lean_environment'])
                if goal=='unconditional':
                    self.assertEqual(job['lean_libraries'][0]['name'],'FixtureLib')
                    self.assertTrue((run/'delivery/formalization/lean-libraries/FixtureLib/source/FixtureLib/Leaf.lean').is_file())
                    self.assertFalse(list((run/'delivery').rglob('*.olean')))
                    endpoints=json.loads((run/'delivery/nl0/lean-endpoints.json').read_text())
                    self.assertEqual(endpoints['lean_libraries'][0]['manifest_sha256'],
                                     job['lean_libraries'][0]['manifest']['sha256'])
                    self.assertEqual(len(endpoints['lean_libraries']),2)
                    self.assertTrue(any(row['name'].startswith('YuiImported') for row in endpoints['lean_libraries']))
                    imports=list(run.glob('2basis/*/stage/imported-lean/request-*/result.json'))
                    self.assertTrue(imports)
                    imported_check=json.loads(imports[0].read_text())
                    self.assertEqual(imported_check['status'],'LOCAL_REUSED')
                    self.assertFalse(imported_check['semantic_acceptance'])
                self.assertEqual(delivery.verify(run/'delivery')['scope'],scope)
                profiles=[]
                for path in run.rglob('execution-manifest.json'):
                    manifest=json.loads(path.read_text())
                    if manifest.get('phase')=='control':continue
                    profile=manifest.get('model_selection')
                    if profile:
                        profiles.append(profile)
                        self.assertEqual(profile['selection_origin'],'explicit_run')
                        self.assertEqual(profile['reasoning_effort'],
                                         'xhigh' if profile['profile_key']=='nl0_to_lean' else 'max')
                self.assertTrue(profiles)
                for path in run.rglob('compiler.json'):
                    compiler=json.loads(path.read_text())
                    if 'selected_environment' in compiler:
                        self.assertEqual(compiler['selected_environment']['mathlib_commit'],selected['mathlib']['rev'])
                report=cleanup.clean(apply=True,grace=1,outputs=[run])
                self.assertEqual(report['status'],'CLEANED',report)
                self.assertEqual(delivery.verify(run/'delivery')['scope'],scope)
                if goal=='unconditional':
                    # Rebuild only public delivered sources after controller and
                    # worker cleanup; no copied olean from the imported registry.
                    package=root/'fresh-package';shutil.copytree(run/'delivery/formalization',package)
                    packages=package/'.lake/packages';packages.mkdir(parents=True)
                    ml=Path(selected['mathlib']['local_path'])
                    (packages/'mathlib').symlink_to(ml,target_is_directory=True)
                    for row in json.loads((ml/'lake-manifest.json').read_text())['packages']:
                        (packages/row['name']).symlink_to(ml/'.lake/packages'/row['name'],target_is_directory=True)
                    binary=Path(selected['lean']['local_path'])/'bin/lake'
                    built=subprocess.run([str(binary),'build','+Solution:olean'],cwd=package,
                        capture_output=True,text=True,timeout=120,
                        env={**os.environ,'PATH':str(binary.parent)+os.pathsep+os.environ.get('PATH',''),'LEAN_NUM_THREADS':'2'})
                    self.assertEqual(built.returncode,0,(built.stdout+built.stderr)[-6000:])


if __name__ == '__main__':
    unittest.main()
