"""Real Lean local/upstream/port checks with source and environment bindings."""
import harness_support
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from controller_common import bind,manifest,write
import lean_environment
import lean_imports
import lean_libraries
import pilot_common
import runtime_config

GOOD='import Mathlib\nnamespace ImportedExample\ntheorem witness : True := by trivial\nend ImportedExample\n'
BAD=GOOD.replace('by trivial','by exact nonexistentOriginalProof')


class ImportedLeanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current=runtime_config.require_environment()
        path=os.environ.get('YUI_TEST_UPSTREAM_ENVIRONMENT')
        cls.comparison=lean_environment.verify(json.loads(Path(path).read_text())) if path else None
        cls.old=cls.comparison or cls.current  # Ordinary source-error checks also work within one pair.

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.use_fixture_root(self.temp.name)

    def use_fixture_root(self, root):
        self.root=Path(root).resolve();self.logs=self.root/'stage';self.logs.mkdir()
        # These controls test native routing, with room for concurrent suite load.
        self.stage=SimpleNamespace(logs=self.logs,task_inputs={'original.lean':GOOD},lean_timeout=lambda:120)
        context=runtime_config.use_environment(self.current);context.__enter__();self.addCleanup(context.__exit__,None,None,None)
        scope=lean_libraries.use([]);scope.__enter__();self.addCleanup(scope.__exit__,None,None,None)
        clear=lean_libraries.generated(None);clear.__enter__();self.addCleanup(clear.__exit__,None,None,None)

    def upstream(self):return {'lean_version':self.old['lean']['version_number'],'mathlib_ref':self.old['mathlib']['rev']}

    def check(self,**kwargs):return lean_imports.check(self.stage,{'document':'original.lean'},**kwargs)

    def test_actual_local_pass_reuses_exact_code_without_upstream_and_hits_bound_cache(self):
        with patch.object(lean_imports,'original_environment',side_effect=AssertionError('Do not check upstream after a local pass')):
            first=self.check(upstream=self.upstream())
            with patch.object(lean_imports,'run_lean',side_effect=AssertionError('Do not rerun a checked unchanged unit')):
                again=self.check(upstream=self.upstream())
        self.assertEqual(first['status'],'LOCAL_REUSED');self.assertTrue(first['accepted_for_native_reuse'])
        self.assertFalse(first['semantic_acceptance']);self.assertTrue(again['current_cache_reused'])
        self.assertEqual(Path(first['checked_source']['path']).read_text(),GOOD)
        self.assertEqual(Path(first['original_source']['path']).read_bytes(),GOOD.encode())

    def test_valid_lean_literals_do_not_turn_comment_or_placeholder_text_into_code(self):
        self.stage.task_inputs['original.lean']=('import Mathlib\n'
            'def quoteChar : Char := \'"\'\n'
            'def quotedText : String := r#"contains "sorry" /- harmless text"#\n'
            'theorem witness\' : True := by trivial\n')
        result=self.check();self.assertEqual(result['status'],'LOCAL_REUSED',result)

    def test_actual_large_import_and_range_have_no_arbitrary_document_size_limit(self):
        self.stage.lean_timeout=lambda:120
        padding='/-'+'x'*5_500_000+'-/\n'
        original=padding+GOOD;self.stage.task_inputs['original.lean']=original
        raw,selected,_=lean_imports.source_bytes(self.stage,{'document':'original.lean','start':2,'end':5})
        self.assertEqual(raw,original.encode());self.assertEqual(selected,GOOD)
        checked=self.check()
        self.assertEqual(checked['status'],'LOCAL_REUSED',checked)
        self.assertEqual(Path(checked['checked_source']['path']).read_text(),original)
        self.assertFalse(checked['semantic_acceptance'])

    def test_actual_original_failure_in_working_upstream_routes_correction_then_checks_port(self):
        self.stage.task_inputs['original.lean']=BAD
        with patch.object(lean_imports,'original_environment',return_value=self.old):
            failed=self.check(upstream=self.upstream())
            bad_port=self.check(upstream=self.upstream(),candidate=BAD+'\n-- Still broken.\n')
            fixed=self.check(upstream=self.upstream(),candidate=GOOD)
        self.assertEqual(failed['status'],'CORRECTION_AND_PORT_REQUIRED',failed)
        self.assertEqual(bad_port['status'],'PORT_CHECK_FAILED',bad_port);self.assertFalse(bad_port['accepted_for_native_reuse'])
        self.assertEqual(fixed['status'],'PORTED_CHECKED',fixed);self.assertTrue(fixed['accepted_for_native_reuse'])
        self.assertEqual(fixed['original_route'],'CORRECTION_AND_PORT_REQUIRED')
        self.assertEqual(Path(fixed['selected_source']['path']).read_text(),BAD)
        self.assertEqual(Path(fixed['checked_source']['path']).read_text(),GOOD)
        original=json.loads(Path(fixed['upstream_check']['path']).read_text())
        context=json.loads(Path(fixed['upstream_context_check']['path']).read_text())
        self.assertEqual(original['native']['exit_code'],1);self.assertEqual(context['native']['exit_code'],0)

    def test_actual_version_specific_original_passes_old_and_requires_current_port(self):
        if self.comparison is None:
            self.skipTest('SKIPPED_COMPARISON_ENVIRONMENT_REQUIRED: supply --comparison-environment with another Lean version')
        if self.current['lean']['version_number']==self.comparison['lean']['version_number']:
            self.skipTest('SKIPPED_COMPARISON_NOT_DISTINCT: this Lean-version guard needs two different Lean versions')
        version=self.old['lean']['version_number']
        self.stage.task_inputs['original.lean']='import Mathlib\nimport Lean\n#guard Lean.versionString == '+json.dumps(version)+'\n'+GOOD.removeprefix('import Mathlib\n')
        with patch.object(lean_imports,'original_environment',return_value=self.old):
            result=self.check(upstream=self.upstream(),candidate=GOOD)
        self.assertEqual(result['status'],'PORTED_CHECKED');self.assertEqual(result['original_route'],'COMPATIBILITY_PORT_REQUIRED')
        old=json.loads(Path(result['upstream_check']['path']).read_text())
        self.assertEqual(old['environment']['lean_version'],version)
        self.assertEqual(old['native']['exit_code'],0)

    def test_upstream_selection_uses_declared_versions_instead_of_ambient_current_paths(self):
        with patch.object(lean_environment,'discover',return_value=([self.old,self.current] if self.old!=self.current else [self.old],[])), \
                patch.dict(os.environ,{'YUI_LEAN_ROOT':self.current['lean']['local_path'],'YUI_MATHLIB_ROOT':self.current['mathlib']['local_path']}):
            self.assertEqual(lean_imports.original_environment(self.upstream()),self.old)

    def test_missing_upstream_installation_or_project_import_does_not_blame_original_source(self):
        self.stage.task_inputs['original.lean']=BAD
        with patch.object(lean_imports,'original_environment',side_effect=lean_environment.SelectionRequired(reason='Original pair not installed')):
            missing=self.check(upstream=self.upstream())
        self.assertEqual(missing['status'],'UPSTREAM_ENVIRONMENT_REQUIRED');self.assertIn('selection_request',missing)
        self.stage.task_inputs['original.lean']='import MissingOriginalProject.Entry\n'+BAD
        with patch.object(lean_imports,'original_environment',return_value=self.old):
            result=self.check(upstream=self.upstream(),candidate=GOOD)
        self.assertEqual(result['status'],'UPSTREAM_CONTEXT_REQUIRED');self.assertFalse(result['accepted_for_native_reuse'])
        self.assertIsNone(result['upstream_check']);self.assertNotIn('candidate_check',result)

    def test_timed_out_or_cancelled_current_check_never_attempts_upstream(self):
        for flag in ('timed_out','cancelled'):
            record={'receipt':{'path':'retained-native.json','sha256':'a'*64},'cache_reused':False,
                    'native':{'exit_code':0,flag:True},'source_policy_passed':True}
            with self.subTest(flag=flag),patch.object(lean_imports,'compile_unit',return_value=record), \
                    patch.object(lean_imports,'original_environment',side_effect=AssertionError('Incomplete check is not a source error')):
                value=self.check(upstream=self.upstream())
            self.assertEqual(value['status'],'LOCAL_CHECK_INCOMPLETE');self.assertFalse(value['accepted_for_native_reuse'])

    def test_source_scope_hash_and_exact_range_are_enforced(self):
        source=self.logs/'external-sources/original.lean';source.parent.mkdir();source.write_text(GOOD)
        selection={'evidence':{'path':'external-sources/original.lean','sha256':bind(source)['sha256']},'start':2,'end':4}
        raw,text,origin=lean_imports.source_bytes(self.stage,selection)
        self.assertEqual(raw,GOOD.encode());self.assertEqual(text,''.join(GOOD.splitlines(keepends=True)[1:4]))
        self.assertEqual(origin['start'],2)
        for bad in ({'document':'foreign.lean'},{'document':'original.lean','start':0},
                    {'evidence':{'path':'../outside.lean','sha256':'a'*64}},
                    {'evidence':{'path':'external-sources/original.lean','sha256':'0'*64}}):
            with self.subTest(selection=bad),self.assertRaises(ValueError):lean_imports.source_bytes(self.stage,bad)
        external=self.root/'outside.lean';external.write_text(GOOD);source.unlink();source.symlink_to(external)
        with self.assertRaisesRegex(ValueError,'symlink'):lean_imports.source_bytes(self.stage,selection)

    def test_tampered_checked_artifact_cannot_be_reused_or_published(self):
        result=self.check();checked=json.loads(Path(result['current_check']['path']).read_text())
        artifact=Path(checked['artifacts'][0]['path']);artifact.write_bytes(artifact.read_bytes()+b'changed')
        with self.assertRaises(ValueError):self.check()

    def test_explicit_unproved_original_and_malformed_import_context_are_not_accepted(self):
        self.stage.task_inputs['original.lean']=GOOD.replace('by trivial','by sorry')
        with patch.object(lean_imports,'original_environment',return_value=self.old):result=self.check(upstream=self.upstream())
        self.assertEqual(result['status'],'CORRECTION_AND_PORT_REQUIRED');self.assertFalse(result['accepted_for_native_reuse'])
        self.assertIsNone(lean_imports.preamble('import\n Missing.Entry\ntheorem witness : True := by trivial\n'))
        self.assertEqual(lean_imports.preamble('/- import Hidden -/\nimport Mathlib\ntheorem witness : True := by trivial\n'),
                         '/- import Hidden -/\nimport Mathlib\n')

    def test_pre_freeze_publication_uses_owned_library_and_survives_recovery_copy(self):
        import jobs
        import basis
        problem=self.root/'proof.md';problem.write_text('Prove True.')
        job=jobs.prepare(problem,track='full',profiles=harness_support.PROFILES,lean_environment=self.current,output=self.root/'case')
        run=Path(job['root']);self.stage.logs=run/'import-stage';self.stage.logs.mkdir()
        with lean_libraries.generated(run/'imported-lean'):
            result=self.check(publish=True,allow_publish=True)
            self.assertEqual(result['status'],'LOCAL_REUSED');self.assertIn(result['module'],lean_libraries.permitted_imports())
            self.assertIn('theorem witness',lean_libraries.read_source(result['module'])['lines'])
            probe=self.root/'probe';(probe/'input').mkdir(parents=True);(probe/'output').mkdir()
            file=probe/'output/Use.lean';file.write_text(result['import']+'\nexample : True := ImportedExample.witness\n')
            native=pilot_common.run_lean(file,probe,timeout=120);self.assertEqual(native['exit_code'],0,native)
            self.assertFalse(result['semantic_acceptance']);self.assertEqual(len(lean_libraries.current()),1)
            with patch.object(basis,'recovery_bindings',return_value=[]):
                continued=jobs.prepare(problem,track='full',profiles=harness_support.PROFILES,
                    resume={'mode':'basis-revision','prior_run':job['root']},output=self.root/'continued')
            self.assertEqual(continued['lean_libraries'][0]['manifest']['sha256'],result['library']['manifest']['sha256'])
            self.assertEqual([r['sha256'] for r in continued['documents']],[r['sha256'] for r in job['documents']])
            write(run/'basis-selection.json',{'frozen':'Synthetic freeze guard.'})
            with self.assertRaisesRegex(ValueError,'frozen'):self.check(publish=True,allow_publish=True)
        self.assertEqual(lean_libraries.current(),[])

    def test_missing_public_import_builds_and_binds_real_modules_in_the_same_job(self):
        import public_lean

        run=self.public_job()
        job_before=bind(run/'job.json')
        repository=self.git_source('lean-lib',{
            'PublicExample/Leaf.lean':
                'import Mathlib\nnamespace PublicExample\ntheorem leaf : True := by trivial\nend PublicExample\n',
            'PublicExample/Entry.lean':
                'import PublicExample.Leaf\nnamespace PublicExample\ntheorem witness : True := leaf\nend PublicExample\n',
        })
        source=self.read_pinned(repository,'PublicExample/Entry.lean','original')
        calls,transport=self.local_git_transport(repository)
        error=public_lean.BuildFailure('PUBLIC_SOURCE_FETCH_FAILED','Synthetic interrupted fetch.')
        with lean_libraries.generated(run/'imported-lean'):
            with patch.object(public_lean,'checkout',side_effect=error):
                first=lean_imports.check(self.stage,source,allow_publish=True)
            self.assertEqual(first['public_library']['status'],'PUBLIC_SOURCE_FETCH_FAILED')
            self.assertEqual(lean_libraries.current(),[])
            with transport:
                result=lean_imports.check(self.stage,source,allow_publish=True)
                again=lean_imports.check(self.stage,source,allow_publish=True)
            self.assertEqual(result['public_library']['status'],'PUBLIC_LEAN_READY',result)
            self.assertEqual(result['status'],'LOCAL_REUSED',result)
            self.assertFalse(result['semantic_acceptance'])
            self.assertIn('PublicExample.Entry',lean_libraries.permitted_imports())
            descriptor=lean_libraries.current()[0]
            manifest=json.loads(Path(descriptor['manifest']['path']).read_text())
            self.assertEqual([row['module'] for row in manifest['modules']],['PublicExample.Leaf','PublicExample.Entry'])
            self.assertEqual(bind(run/'job.json'),job_before)
            self.assertTrue(again['current_cache_reused'])
            self.assertEqual(calls,[(repository[0],repository[2])])

    def test_compiled_dependency_does_not_enter_the_text_material_wait(self):
        from clean_stage import ArtifactStage
        import fault_control
        import material_exchange

        run = self.public_job()
        inputs = self.root/'inputs'; inputs.mkdir()
        (inputs/'original.lean').write_text('import PublicExample.Leaf\n')
        manifest(inputs)
        stage=ArtifactStage(run/'routing','Dependency routing control.',phase='basis-authoring',
                            inputs=inputs/'inputs.json')
        self.assertTrue(stage.material_requests)
        value={'status':'SOURCE_UNAVAILABLE','location':'',
               'explanation':'The module dependency was not yet available.',
               'basis':'The real compiler reported a missing import.','partial_progress':'The source was read.'}
        try:
            check=stage.dispatch('check_imported_lean',{'source':{'document':'original.lean'}})
            self.assertEqual(check['status'],'UPSTREAM_ENVIRONMENT_REQUIRED',check)
            self.assertTrue(Path(check['receipt']['path']).is_file())
            with patch.object(material_exchange,'request',return_value={'status':'WAITING'}) as wait:
                for location in ('PublicExample.Leaf','B052 → B120 → R018'):
                    with self.subTest(location=location):
                        reply=stage.dispatch('report_obstacle',{**value,'location':location})
                        self.assertIn('LEAN_DEPENDENCY_ACTION_REQUIRED',reply.get('error',''),reply)
                        self.assertIn(check['receipt'],[row['receipt'] for row in reply['dependency_followup'].values()])
                        wait.assert_not_called()
                book=stage.dispatch('report_obstacle',{**value,'status':'MISSING_SOURCE_STATEMENT',
                      'location':'An inaccessible public reference, Theorem 2',
                      'explanation':'The complete theorem statement is absent from accessible text.'})
                self.assertEqual(book['status'],'WAITING');wait.assert_called_once()

            def recheck(gate):
                self.assertEqual(gate.stage,'lean-dependency')
                self.assertEqual(gate.state['checkpoint']['import_diagnostic'],check['receipt'])
                self.assertEqual(fault_control.resume(run,gate.state['incident'])['status'],'RESUME_REQUESTED')

            with patch.object(fault_control.Gate,'report',recheck):
                resumed=stage.dispatch('wait_for_lean_dependency',{'receipt':check['receipt']})
            self.assertEqual(resumed['status'],'RETRY_LEAN_DEPENDENCY',resumed)
            self.assertEqual(resumed['dependency_followup']['receipt'],check['receipt'])
            self.assertFalse(resumed['stage_complete'])
        finally:
            stage.release_resources('USER_CANCELLED')

    def public_job(self, *, unconditional=False):
        import jobs
        from basis_fixtures import TARGET
        problem = self.root/'problem.md'
        problem.write_text(TARGET if unconditional else 'Prove True.')
        target = __import__('target_selection').resolve(problem,requested=TARGET) if unconditional else None
        job = jobs.prepare(problem, track='full', profiles=harness_support.PROFILES,
                           formalization='unconditional' if unconditional else 'conditional',
                           target=target,lean_environment=self.current,output=self.root/'case',max_concurrency=1)
        run = Path(job['root'])
        self.stage.logs = run/'public-stage'; self.stage.logs.mkdir()
        (self.stage.logs/'external-sources').mkdir()
        return run

    def git_source(self, repo, files):
        repository = self.root/repo; repository.mkdir()
        for name, text in files.items():
            path = repository/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text)
        subprocess.run(['git','init','-q',str(repository)],check=True)
        subprocess.run(['git','-C',str(repository),'config','uploadpack.allowFilter','true'],check=True)
        subprocess.run(['git','-C',str(repository),'add','.'],check=True)
        subprocess.run(['git','-C',str(repository),'-c','user.name=Yui Test','-c','user.email=test@example.invalid',
                        '-c','commit.gpgsign=false','-c','core.hooksPath=/dev/null','commit','-qm','Pinned fixture'],check=True)
        revision = subprocess.check_output(['git','-C',str(repository),'rev-parse','HEAD'],text=True).strip()
        return f'https://github.com/example/{repo}.git', repository, revision

    def read_pinned(self, source, relative, identifier):
        _, repository, revision = source
        path = self.stage.logs/'external-sources'/f'{identifier}.lean'
        shutil.copyfile(repository/relative,path)
        binding = bind(path)
        write(path.with_name('access-'+identifier+'.json'),{'status':'READABLE','document':binding,
              'final_url':f'https://raw.githubusercontent.com/example/{repository.name}/{revision}/{relative}'})
        return {'evidence':{**binding,'path':str(path.relative_to(self.stage.logs))}}

    def local_git_transport(self, *repositories, first_timeout=False):
        import public_lean
        real_git = public_lean.git
        fixtures = {url:(path,revision) for url,path,revision in repositories}
        calls = []
        configured = {}

        def git(work, cwd, args, deadline):
            # Only substitute the transport. Checkout, revision verification,
            # Lake metadata resolution, Lean compilation and binding all run.
            if args[:3]==['remote','add','origin']:
                url=args[-1]; configured[cwd]=url
                path,_=fixtures[url]
                args=[*args[:-1],path.as_uri()]
            if args[0]=='fetch':
                url=configured[cwd]; pin=args[-1]
                _,revision=fixtures[url]
                self.assertEqual(pin,revision); self.assertIn('--depth=1',args)
                self.assertIn('--filter=blob:none',args)
                calls.append((url,pin))
                if first_timeout and len(calls)==1:
                    raise public_lean.BuildFailure('PUBLIC_SOURCE_FETCH_FAILED', 'Injected Git transport timeout')
            return real_git(work,cwd,['-c','protocol.file.allow=always',*args],deadline)

        return calls, patch.object(public_lean,'git',side_effect=git)

    def basis_stage(self, run, *, name='2basis/0001'):
        from basis import BasisContract, PROMPT
        from basis_author import BasisStage
        from basis_fixtures import TARGET
        out = run/name
        inputs = out/'inputs'
        inputs.mkdir(parents=True)
        (inputs/'problem.md').write_text(TARGET)
        manifest(inputs)
        stage = BasisStage(out/'stage', PROMPT, phase='basis-authoring',
                           validator=BasisContract(out, TARGET), inputs=inputs/'inputs.json', library=True)
        self.addCleanup(stage.release_resources, 'USER_CANCELLED')
        return stage

    def save_basis_route(self, stage, header, proof):
        from basis_fixtures import artifact, dependency
        full = artifact(dependency(category=2, proof=proof))
        full['lean_header'] += header
        route = deepcopy(full)
        route['dependencies'][0]['lean']['proof'] = None
        saved = stage.dispatch('save_basis_draft', {'artifact': route})
        return full, saved['candidate']

    def test_public_library_increment_preserves_old_consumer_and_rechecks_basis(self):
        import basis_native
        import public_lean
        run = self.public_job()
        stage = self.basis_stage(run)
        source = self.git_source('increment',{
            'lakefile.toml':'name = "fixture"\n[[lean_lib]]\nname = "Lib"\n',
            'Lib/A.lean':'import Init\nnamespace Lib\ntheorem a (n : Nat) : n + 0 = n := rfl\nend Lib\n',
            'Lib/B.lean':'import Lib.A\nnamespace Lib\ntheorem b : 0 + 0 = 0 := a 0\nend Lib\n',
            'Lib/C.lean':'import Lib.B\nexample : False := Lib.b\n',
            'other/Lib/A.lean':'import Init\nnamespace Lib\ntheorem a : True := trivial\nend Lib\n',
            'other/Lib/D.lean':'import Lib.A\nexample : 0 + 0 = 0 := Lib.a 0\n',
        })
        registry = run/'imported-lean'
        _, transport = self.local_git_transport(source)
        with transport, lean_libraries.generated(registry):
            def bind_module(path, module):
                evidence = self.read_pinned(source, path, path.replace('/', '-'))
                return lean_imports.check(self.stage, evidence, bind_public=True,
                                          allow_publish=True, module=module)

            first = bind_module('Lib/A.lean', 'Lib.A')
            self.assertEqual(first['public_library']['status'], 'PUBLIC_LEAN_READY', first)
            old = lean_libraries.binding()[0]
            old_manifest = json.loads(Path(old['manifest']['path']).read_bytes())
            proof = 'import Lib.A\ntheorem beforeIncrement : 0 + 0 = 0 := Lib.a 0\n'
            consumer = lean_imports.compile_unit(proof, self.current, run/'old-consumer',
                                                  attachments=lean_libraries.binding())
            consumer_lib = lean_imports.publish_checked(consumer, registry)
            self.assertIn(old['manifest']['sha256'], {row['manifest_sha256'] for row in consumer['libraries']})
            artifact, route = self.save_basis_route(stage, 'import Lib.A\n', 'exact Lib.a')
            self.assertTrue(stage.dispatch('prepare_basis_graph', {'candidate': route, 'prove': False})['route_ready'])
            with patch.object(basis_native, 'check', wraps=basis_native.check) as compile_basis:
                checked = stage.dispatch('check_draft', {'artifact': artifact})
                self.assertTrue(checked['accepted'], checked)
                candidate = stage.validator.last_checked
                with patch.object(public_lean, 'run_lean', wraps=public_lean.run_lean) as build:
                    appended = bind_module('Lib/B.lean', 'Lib.B')
                self.assertEqual(appended['public_library']['status'], 'PUBLIC_LEAN_READY', appended)
                self.assertEqual([call.args[0].name for call in build.call_args_list], ['B.lean'])
                selected = stage.dispatch('submit_draft', {'artifact': {'accept_candidate': candidate}})
                self.assertTrue(selected['stage_complete'], selected)
                self.assertEqual(compile_basis.call_count, 2)
                self.assertEqual(stage.accepted, artifact)
            active = lean_libraries.binding()
            libraries = [row for row in active if row['name']=='Lib']
            self.assertEqual(len(libraries), 1)
            [latest] = libraries
            self.assertNotEqual(old['manifest']['sha256'], latest['manifest']['sha256'])
            lean_libraries.validate([old], full=True)
            metadata = json.loads(Path(latest['manifest']['path']).read_bytes())
            self.assertEqual(metadata['modules'][0], old_manifest['modules'][0])
            self.assertIn(consumer_lib, active)
            def import_all():
                unit = lean_imports.compile_unit(
                    f'import Lib.A\nimport Lib.B\nimport {consumer_lib["name"]}\n'
                    'example : 0 + 0 = 0 := beforeIncrement.trans Lib.b\n',
                    self.current, self.root/'verify-all', attachments=lean_libraries.binding())
                self.assertTrue(pilot_common.native_succeeded(unit['native']), unit['diagnostic'])
            import_all()
            index = (registry/'index.json').read_bytes()
            failed = bind_module('Lib/C.lean', 'Lib.C')
            self.assertEqual(failed['public_library']['status'], 'PUBLIC_LEAN_BUILD_FAILED', failed)
            conflict = bind_module('other/Lib/A.lean', 'Lib.A')
            self.assertEqual(conflict['public_library']['status'], 'PUBLIC_LEAN_CONFLICT', conflict)
            dependency_conflict = bind_module('other/Lib/D.lean', 'Lib.D')
            self.assertEqual(dependency_conflict['public_library']['status'], 'PUBLIC_LEAN_CONFLICT', dependency_conflict)
            self.assertEqual((registry/'index.json').read_bytes(), index)
            lean_libraries.validate(lean_libraries.binding(), full=True)
            import_all()

    def test_selecting_pending_imports_leaves_both_lean_entries_strict(self):
        run = self.public_job()
        stage = self.basis_stage(run)
        repository = self.git_source('pending',{
            'Lib/Pending.lean':'import Init\nnamespace Lib\ntheorem pending (n : Nat) : n + 0 = n := rfl\nend Lib\n',
        })
        _, transport = self.local_git_transport(repository)
        with transport, lean_libraries.generated(run/'imported-lean'):
            full, number = self.save_basis_route(stage, 'import Lib.Pending\n', 'exact Lib.pending')
            planned = stage.dispatch('prepare_basis_graph', {'candidate':number,'prove':False})
            self.assertTrue(planned.get('route_ready'), planned)
            self.assertEqual(json.loads(Path(planned['route']['path']).read_text())['pending_imports'], ['Lib.Pending'])
            saved = stage.dispatch('save_basis_draft', {'artifact':full})
            for tool,args in [('prepare_basis_graph',{'candidate':saved['candidate'],'prove':True}),
                              ('submit_draft',{'artifact':full})]:
                refused = stage.dispatch(tool,args)
                self.assertIn('Lib.Pending',refused['error'],refused)
                self.assertIsNone(stage.accepted)
            evidence = self.read_pinned(repository, 'Lib/Pending.lean', 'pending')
            bound = lean_imports.check(self.stage, evidence, bind_public=True, allow_publish=True)
            self.assertEqual(bound['public_library']['status'],'PUBLIC_LEAN_READY',bound)
            ready = stage.dispatch('prepare_basis_graph', {'candidate':saved['candidate'],'prove':True})
            self.assertTrue(ready.get('route_ready'),ready)
            checked = stage.dispatch('submit_draft', {'artifact':full})
            self.assertTrue(checked['stage_complete'],checked)

    def prepare_port_delivery(self):
        import basis_review
        import delivery
        run = self.public_job(unconditional=True)
        stage = self.basis_stage(run, name='port-probe')
        (stage.logs/'external-sources').mkdir()
        self.stage = stage
        candidate = ('import Lean\nnamespace Lib\n'
                     'theorem base (n : Nat) : n + 0 = n := rfl\nend Lib\n')
        original = candidate.replace('import Lean\n',
                    'import Lean\n#guard Lean.versionString == '+json.dumps(self.old['lean']['version_number'])+'\n')
        source = self.git_source('port',{
            'Lib/Base.lean': original,
            'Lib/Consumer.lean': ('import Lib.Base\nnamespace Lib\n'
                                 'theorem consumer (n : Nat) : n + 0 = n := base n\nend Lib\n'),
        })
        _, transport = self.local_git_transport(source)
        # Supply only the two fixtures already verified against real installations.
        # Version selection and every native build still run.
        with (transport, patch.object(lean_environment,'discover',return_value=([self.old,self.current],[])),
              lean_libraries.generated(run/'imported-lean')):
            _, number = self.save_basis_route(stage,'import Lib.Consumer\n','exact Lib.consumer')
            selected = stage.dispatch('prepare_basis_graph',{'candidate':number,'prove':False})
            self.assertTrue(selected.get('route_ready'),selected)
            evidence = self.read_pinned(source,'Lib/Base.lean','base')
            options = {'source':evidence,'module':'Lib.Base','bind_public':True,'upstream':self.upstream()}
            original_check = stage.dispatch('check_imported_lean',options)
            self.assertEqual(original_check.get('status'),'COMPATIBILITY_PORT_REQUIRED',original_check)
            fragment = stage.dispatch('check_imported_lean',{
                **options,'source':{**evidence,'start':1,'end':2},'candidate':candidate,'publish':True})
            self.assertIn('complete pinned source',fragment['error'],fragment)
            self.assertNotIn('Lib.Base',lean_libraries.permitted_imports())
            port = stage.dispatch('check_imported_lean',{**options,'candidate':candidate,'publish':True})
            self.assertEqual(port.get('status'),'PORTED_CHECKED',port)
            self.assertEqual(port['import'],'import Lib.Base')
            consumer = stage.dispatch('check_imported_lean',{
                'source':self.read_pinned(source,'Lib/Consumer.lean','consumer'),
                'bind_public':True,'module':'Lib.Consumer'})
            self.assertEqual(consumer['public_library']['status'],'PUBLIC_LEAN_READY',consumer)
            replacement = stage.dispatch('check_imported_lean',{
                **options,'candidate':candidate+'\n-- another port\n','publish':True})
            self.assertIn('already registered',replacement['error'],replacement)
            [active] = lean_libraries.binding()
            snapshot = Path(active['root'])
            metadata = json.loads((snapshot/'manifest.json').read_text())
            effective = next(row for row in metadata['modules'] if row['module']=='Lib.Base')
            port_root = snapshot/'ports/Lib.Base'
            receipt = json.loads((port_root/'receipt.json').read_text())
            self.assertEqual(metadata['ports']['Lib.Base'],bind(port_root/'receipt.json')['sha256'])
            self.assertEqual(receipt['original_sha256'],hashlib.sha256(original.encode()).hexdigest())
            self.assertEqual(receipt['ported_sha256'],effective['source_sha256'])
            self.assertEqual(receipt['origin']['revision'],source[2])
            self.assertEqual((snapshot/'source/Lib/Base.lean').read_text(),candidate)

        program=harness_support.TESTS/'tooling/basis_path_control.py'
        process=subprocess.run([sys.executable,'-B',str(program),str(run/'job.json'),'planned-closed+port'],
                               capture_output=True,text=True,timeout=900)
        self.assertEqual(process.returncode,0,(process.stdout+process.stderr)[-5000:])
        review_dir=run/'2basis/0001/review/inputs'
        packet=json.loads((review_dir/basis_review.PACKET).read_text())
        review_port=packet['ports']['Lib.Base']
        self.assertEqual(review_port['receipt_sha256'],metadata['ports']['Lib.Base'])
        self.assertEqual((review_dir/review_port['files']['original']['input']).read_text(),original)
        self.assertEqual((review_dir/review_port['files']['ported']['input']).read_text(),candidate)
        for key,code in {'upstream':0,'target_original':1,'target_ported':0}.items():
            data=json.loads((review_dir/review_port['files'][key]['input']).read_text())
            self.assertEqual(data['exit_code'],code)
        changed=deepcopy(packet)
        changed['ports']['Lib.Base']['files']['upstream']['sha256']='0'*64
        self.assertNotEqual(basis_review.item_keys(packet),basis_review.item_keys(changed))
        delivered=run/'delivery'
        self.assertEqual(delivery.verify(delivered)['scope'],'UNCONDITIONAL_LEAN')
        return {'receipt':receipt,'original':original}

    def test_pinned_original_name_port_reaches_consumer_review_and_retained_delivery(self):
        if not self.comparison or self.old['lean']['version_number']==self.current['lean']['version_number']:
            self.skipTest('Supply a distinct --comparison-environment for the two native environments')
        import cleanup
        import delivery
        fixture=self.root/'port-delivery';fixture.mkdir()
        # The preparer itself takes part in real native executions. Let those
        # owner identities exit before a separate process requests cleanup.
        process=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--prepare-port-fixture',str(fixture)],
                               capture_output=True,text=True,timeout=1200)
        self.assertEqual(process.returncode,0,(process.stdout+process.stderr)[-7000:])
        expected=json.loads((fixture/'expected-port.json').read_text())
        run=fixture/'case'
        delivered=run/'delivery'
        cleaned=cleanup.clean(outputs=[run],apply=True,grace=0)
        self.assertEqual(cleaned['status'],'CLEANED',cleaned)
        self.assertEqual({p.name for p in run.iterdir()},{'delivery'})
        self.assertEqual(delivery.verify(delivered)['scope'],'UNCONDITIONAL_LEAN')
        directory=delivered/'formalization/lean-libraries/Lib/ports/Lib.Base'
        endpoint=json.loads((delivered/'nl0/lean-endpoints.json').read_text())
        self.assertEqual(json.loads((directory/'receipt.json').read_text()),expected['receipt'])
        self.assertEqual((directory/'original.lean').read_text(),expected['original'])
        for path in directory.iterdir():
            with self.subTest(delivered_file=path.name):
                saved=path.read_bytes()
                path.unlink()
                with self.assertRaises(ValueError):delivery.verify(delivered)
                path.write_bytes(saved+b'changed')
                with self.assertRaises(ValueError):
                    lean_libraries.verify_export(delivered/'formalization',endpoint['lean_libraries'])
                with self.assertRaises(ValueError):delivery.verify(delivered)
                path.write_bytes(saved)
        self.assertEqual(delivery.verify(delivered)['scope'],'UNCONDITIONAL_LEAN')

    def test_vendored_hyphenated_source_path_builds_declared_library(self):
        run = self.public_job()
        package = 'vendor/class-field-theory/'
        path = package+'Lean4/ClassFieldTheory/Ray.lean'
        source = self.git_source('vendored',{
            package+'lakefile.toml':'name = "reciprocity"\n[[lean_lib]]\nname = "ClassFieldTheory.All"\nsrcDir = "Lean4"\nglobs = ["ClassFieldTheory.+"]\n',
            package+'Lean4/ClassFieldTheory/Leaf.lean':'import Init\nnamespace ClassFieldTheory\ntheorem leaf : True := trivial\nend ClassFieldTheory\n',
            path:'import ClassFieldTheory.Leaf\nnamespace ClassFieldTheory\ntheorem ray : True := leaf\nend ClassFieldTheory\n',
        })
        _, transport = self.local_git_transport(source)
        with transport, lean_libraries.generated(run/'imported-lean'):
            result = lean_imports.check(self.stage,self.read_pinned(source,path,'ray'),bind_public=True,allow_publish=True)
            self.assertEqual(result['public_library']['status'],'PUBLIC_LEAN_READY',result)
            self.assertIn('ClassFieldTheory.Ray',lean_libraries.permitted_imports())
            proof = lean_imports.compile_unit('import ClassFieldTheory.Ray\nexample : True := ClassFieldTheory.ray\n',
                       self.current,self.root/'verify-vendored',attachments=lean_libraries.current())
            self.assertTrue(pilot_common.native_succeeded(proof['native']), proof['diagnostic'])

    def test_nested_lean_package_compiles_and_satisfies_a_cross_repository_import(self):
        run = self.public_job()
        dependency_path = 'lean/OAI/Menu.lean'
        child = self.git_source('upstream',{
            'lean/lakefile.lean':'import Lake\nopen Lake DSL\npackage OAI\n@[default_target] lean_lib OAI\n',
            dependency_path:'import Init\nnamespace OAI\ntheorem menu : True := trivial\nend OAI\n',
        })
        parent_path = 'Hindman/Main.lean'
        parent = self.git_source('consumer',{
            'lakefile.toml':'name = "hindman"\n[[lean_lib]]\nname = "Hindman"\n',
            parent_path:'import OAI.Menu\nnamespace Hindman\ntheorem witness : True := OAI.menu\nend Hindman\n',
        })
        calls, transport = self.local_git_transport(child,parent)
        with transport, lean_libraries.generated(run/'imported-lean'):
            consumer = self.read_pinned(parent,parent_path,'parent')
            before = lean_imports.check(self.stage,consumer,bind_public=True,allow_publish=True)
            self.assertEqual(before['public_library']['status'],'PUBLIC_LEAN_DEPENDENCY_REQUIRED',before)
            built = lean_imports.check(self.stage,self.read_pinned(child,dependency_path,'child'),bind_public=True,allow_publish=True)
            self.assertEqual(built['public_library']['status'],'PUBLIC_LEAN_READY',built)
            self.assertIn('OAI.Menu',lean_libraries.permitted_imports())
            ready = lean_imports.check(self.stage,consumer,bind_public=True,allow_publish=True)
            self.assertEqual(ready['public_library']['status'],'PUBLIC_LEAN_READY',ready)
            self.assertEqual(set(lean_libraries.permitted_imports()),{'OAI.Menu','Hindman.Main'})
            self.assertEqual(calls,[(parent[0],parent[2]),(child[0],child[2])])
            proof = lean_imports.compile_unit('import Hindman.Main\nexample : True := Hindman.witness\n',
                       self.current,self.root/'verify-cross-repo',attachments=lean_libraries.current())
            self.assertTrue(pilot_common.native_succeeded(proof['native']),proof['diagnostic'])

    def test_pinned_git_fetch_retries_without_refetching_a_verified_commit(self):
        run = self.public_job()
        source = self.git_source('cache-control',{
            'Alpha/Entry.lean':'import Init\nnamespace Alpha\ntheorem witness : True := trivial\nend Alpha\n',
            'Beta/Entry.lean':'import Init\nnamespace Beta\ntheorem witness : True := trivial\nend Beta\n',
            'Examples/Unused.lean':'def unrelated : Nat := 42\n',
        })
        calls, transport = self.local_git_transport(source,first_timeout=True)
        with transport, lean_libraries.generated(run/'imported-lean'):
            for name in ('Alpha','Beta'):
                result = lean_imports.check(self.stage,self.read_pinned(source,name+'/Entry.lean',name),
                            bind_public=True,allow_publish=True)
                self.assertEqual(result['public_library']['status'],'PUBLIC_LEAN_READY',result)
            self.assertEqual(calls,[(source[0],source[2])]*2)
            [cached] = [path for path in (run/'imported-lean/public-sources').iterdir() if path.is_dir()]
            self.assertFalse((cached/'Examples/Unused.lean').exists())
            inspect_blob = ['git','--no-lazy-fetch','-C',str(cached),'cat-file','-e']
            subprocess.run([*inspect_blob,'HEAD:Alpha/Entry.lean'],capture_output=True,check=True)
            blob = subprocess.run([*inspect_blob,'HEAD:Examples/Unused.lean'],capture_output=True)
            self.assertNotEqual(blob.returncode,0, 'An unrelated blob was downloaded with the pinned revision.')

    @contextmanager
    def git_identity_gap(self, repository, arguments):
        import execution_state

        spawn, identity = subprocess.Popen, execution_state.identity
        children = []

        def launch(command, *args, **kwargs):
            if (command[0] != '/usr/bin/git' or kwargs.get('cwd') != repository
                    or command[-len(arguments):] != arguments):
                return spawn(command, *args, **kwargs)
            # Keep the real command pending through poll(); release it when the
            # held child handle is actually waited on, without a timing sleep.
            child = spawn(['/bin/sh', '-c', 'read -r gate; exec "$@"', 'git-fixture', *command],
                          *args, **{**kwargs, 'stdin': subprocess.PIPE})
            wait = child.wait

            def release_and_wait(*args, **kwargs):
                if child.stdin is not None:
                    child.stdin.close()
                    child.stdin = None
                return wait(*args, **kwargs)

            child.wait = release_and_wait
            children.append(child.pid)
            self.addCleanup(child.stdout.close)
            self.addCleanup(child.stderr.close)
            return child

        with patch.object(subprocess, 'Popen', side_effect=launch), \
                patch.object(execution_state, 'identity', side_effect=lambda pid: None if pid in children else identity(pid)):
            yield children

    def test_cached_git_identity_gap_still_binds_real_lean_module(self):
        import public_lean

        run = self.public_job()
        source = self.git_source('short-git', {
            'Lib/Entry.lean': 'import Init\nnamespace Lib\ntheorem witness : True := trivial\nend Lib\n',
        })
        url, _, revision = source
        origin = {'repository': url, 'revision': revision}
        registry = run/'imported-lean'
        work = self.root/'seed-cache'; work.mkdir()
        fetches, transport = self.local_git_transport(source)
        with transport, lean_libraries.generated(registry):
            with public_lean.cached_checkout(work, origin, registry/'public-sources', time.monotonic()+30) as cached:
                self.assertTrue((cached/'.git').is_dir())
            with self.git_identity_gap(cached, ['rev-parse', 'HEAD']) as children:
                result = lean_imports.check(self.stage, self.read_pinned(source, 'Lib/Entry.lean', 'entry'),
                                            bind_public=True, allow_publish=True, module='Lib.Entry')
            self.assertEqual(len(children), 1)
            self.assertEqual(fetches, [(url, revision)])
            self.assertEqual(result['public_library']['status'], 'PUBLIC_LEAN_READY', result)
            consumer = lean_imports.compile_unit('import Lib.Entry\nexample : True := Lib.witness\n',
                         self.current, self.root/'consumer', attachments=lean_libraries.current())
            self.assertTrue(pilot_common.native_succeeded(consumer['native']), consumer['diagnostic'])

    def test_short_git_failure_keeps_original_stderr(self):
        import native_workspace
        import public_lean

        _, repository, _ = self.git_source('failed-git', {'file': 'pinned\n'})
        arguments = ['rev-parse', '--verify', 'refs/heads/missing']
        expected = subprocess.run(['/usr/bin/git', *arguments], cwd=repository, capture_output=True, text=True)
        self.assertNotEqual(expected.returncode, 0)
        self.assertTrue(expected.stderr)
        with native_workspace.temporary('yui-git-failure-', logs=self.logs) as work:
            with self.git_identity_gap(repository, arguments) as children:
                with self.assertRaises(public_lean.BuildFailure) as failed:
                    public_lean.git(work, repository, arguments, time.monotonic()+10)
            self.assertEqual(len(children), 1)
            self.assertEqual(failed.exception.status, 'PUBLIC_SOURCE_FETCH_FAILED')
            self.assertEqual(str(failed.exception), expected.stderr)
            cleanup = native_workspace.read_cleanup(work)
            self.assertTrue(cleanup['cleanup_confirmed'])
            self.assertEqual(cleanup['exit_code'], expected.returncode)

    def test_public_git_respects_host_proxy_without_global_git_configuration(self):
        import public_lean

        proxy = 'http://127.0.0.1:9123'
        with (patch('urllib.request.getproxies',return_value={'https':proxy}),
              patch('urllib.request.proxy_bypass',return_value=False),
              patch.dict(os.environ,{'GH_TOKEN':'unused-test-token'}),
              patch.object(public_lean.subprocess,'Popen',wraps=subprocess.Popen) as child):
            version = public_lean.git(self.root,self.root,['--version'],time.monotonic()+5)
        self.assertIn('git version',version)
        launched = next(call for call in child.call_args_list if call.args[0][0]=='/usr/bin/git')
        env = launched.kwargs['env']
        self.assertEqual(env.get('https_proxy'),proxy)
        self.assertEqual(env['GIT_CONFIG_GLOBAL'],'/dev/null')
        self.assertNotIn('GH_TOKEN',env)


if __name__=='__main__':
    if sys.argv[1:2]==['--prepare-port-fixture']:
        fixture=ImportedLeanTests()
        fixture.setUpClass()
        fixture.use_fixture_root(sys.argv[2])
        try:
            write(fixture.root/'expected-port.json',fixture.prepare_port_delivery())
        finally:
            fixture.doCleanups()
    else:
        unittest.main()
