"""Bound external Lean files never become implicit trust or mutable inputs."""
import harness_support
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import subprocess
from unittest.mock import patch

import lean_libraries as libraries
import pilot_common
from controller_common import bind
from runtime_config import load_lock


class LeanLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root/'source';self.build = self.root/'build'
        for folder in (self.source, self.build):(folder/'FixtureLib').mkdir(parents=True)
        (self.source/'FixtureLib/Leaf.lean').write_text('theorem fixture : True := True.intro\n')
        (self.build/'FixtureLib/Leaf.olean').write_bytes(b'synthetic identity fixture; not a Lean proof')
        lock = load_lock()
        self.value = dict(version=libraries.VERSION, name='FixtureLib',
            lean_version=lock['lean']['toolchain'].rsplit(':v', 1)[-1], mathlib_commit=lock['mathlib']['rev'],
            source_root=str(self.source), build_root=str(self.build), imports=['FixtureLib.Leaf'],
            modules=[dict(module='FixtureLib.Leaf',
                source_sha256=bind(self.source/'FixtureLib/Leaf.lean')['sha256'],
                olean_sha256=bind(self.build/'FixtureLib/Leaf.olean')['sha256'])])
        self.spec = self.root/'spec.json'

    def capture(self, value=None):
        self.spec.write_text(json.dumps(self.value if value is None else value))
        return libraries.capture(self.spec, self.root/'run')

    def test_capture_is_independent_of_later_original_changes(self):
        descriptor = self.capture()
        (self.source/'FixtureLib/Leaf.lean').write_text('changed original')
        libraries.validate([descriptor], full=True)
        path = Path(descriptor['root'])/'source/FixtureLib/Leaf.lean'
        self.assertIn('True.intro', path.read_text())
        self.assertFalse(path.is_symlink())

    def test_explicit_scope_survives_worker_context_and_restores(self):
        descriptor = self.capture()
        with libraries.use([descriptor]):
            with ThreadPoolExecutor(1) as pool:
                answer = pool.submit(copy_context().run, libraries.binding).result()
            self.assertEqual(answer, [descriptor])
            self.assertIn(str(Path(descriptor['root'])/'lib'), pilot_common.lean_paths())
            self.assertEqual(libraries.permitted_imports(), {'FixtureLib.Leaf'})
        self.assertEqual(libraries.binding(), [])

    def test_header_import_is_allowed_only_in_bound_scope(self):
        descriptor = self.capture();header='import Mathlib\nimport FixtureLib.Leaf\ndef x := 1\n'
        with self.assertRaises(ValueError):libraries.strip_attached_imports(header)
        with libraries.use([descriptor]):
            self.assertEqual(libraries.strip_attached_imports(header),'import Mathlib\ndef x := 1\n')
            with self.assertRaises(ValueError):libraries.strip_attached_imports(header.replace('Leaf','Other'))
            with self.assertRaises(ValueError):libraries.strip_attached_imports(header.replace('def x', 'import FixtureLib.Leaf\ndef x'))

    def test_original_missing_changed_and_wrong_version_inputs_fail(self):
        for field in ('lean_version','mathlib_commit'):
            value=deepcopy(self.value);value[field]='wrong'
            with self.subTest(field=field),self.assertRaises(ValueError):self.capture(value)
        (self.source/'FixtureLib/Leaf.lean').write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.capture()

    def test_semantic_version_uses_the_frozen_toolchain_pin(self):
        self.assertEqual(self.value['lean_version'], load_lock()['lean']['version_number'])
        value=deepcopy(self.value);value['lean_version']=load_lock()['lean']['version']
        with self.assertRaisesRegex(ValueError, 'Lean/Mathlib|environment identity'):
            self.capture(value)
        self.capture()

    def test_namespace_and_import_escape_rejected(self):
        for change in ({'name':'Mathlib'}, {'imports':['Other.Entry']},
                       {'name':'../Outside'}, {'imports':[]}, {'version':'unknown'}):
            value=deepcopy(self.value);value.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.capture(value)

    def test_duplicate_modules_rejected(self):
        value=deepcopy(self.value);value['modules']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.capture(value)

    def test_input_symlink_cannot_copy_a_file_outside_the_declared_library(self):
        path=self.source/'FixtureLib/Leaf.lean';external=self.root/'outside.lean'
        external.write_bytes(path.read_bytes());path.unlink();path.symlink_to(external)
        with self.assertRaisesRegex(ValueError,'symlink'):self.capture()

    def test_input_parent_symlink_cannot_escape_the_declared_library(self):
        import shutil
        folder=self.source/'FixtureLib';external=self.root/'outside';shutil.copytree(folder,external)
        shutil.rmtree(folder);folder.symlink_to(external,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):self.capture()

    def test_recovery_clones_frozen_library_bytes_without_reading_changed_originals(self):
        import jobs
        import basis
        problem=self.root/'problem.md';problem.write_text('Given P, conclude P.')
        self.spec.write_text(json.dumps(self.value))
        selected=__import__('runtime_config').require_environment()
        old=jobs.prepare(problem,track='full',profiles=harness_support.PROFILES,
            lean_libraries=[self.spec],lean_environment=selected,output=self.root/'old')
        (self.source/'FixtureLib/Leaf.lean').write_text('Changed upstream source is not a recovery input.')
        with patch.object(basis,'recovery_bindings',return_value=[]):
            continued=jobs.prepare(problem,track='full',profiles=harness_support.PROFILES,
                resume={'mode':'basis-revision','prior_run':old['root']},output=self.root/'continued')
        self.assertNotEqual(continued['lean_libraries'][0]['root'],old['lean_libraries'][0]['root'])
        self.assertEqual(continued['lean_libraries'][0]['manifest']['sha256'],old['lean_libraries'][0]['manifest']['sha256'])
        self.assertEqual([r['sha256'] for r in continued['documents']],[r['sha256'] for r in old['documents']])
        with libraries.use(continued['lean_libraries']):self.assertIn('True.intro',libraries.read_source('FixtureLib.Leaf')['lines'])

    def test_same_header_with_different_library_content_cannot_share_native_caches(self):
        import helper_modules
        import shared_lemmas
        from lean_fixtures import shared_fixture
        cp,plan=shared_fixture(self.root/'case')
        first=self.capture()
        with libraries.use([first]):
            key1=shared_lemmas.signature_key(shared_lemmas.obligation(cp,plan,'T001'))
            helper1=helper_modules.context(cp,plan,'T001')[0]
        path=self.source/'FixtureLib/Leaf.lean';path.write_text(path.read_text()+'\n-- Distinct public source revision.\n')
        value=deepcopy(self.value);value['modules'][0]['source_sha256']=bind(path)['sha256']
        spec=self.root/'second.json';spec.write_text(json.dumps(value));second=libraries.capture(spec,self.root/'second')
        with libraries.use([second]):
            key2=shared_lemmas.signature_key(shared_lemmas.obligation(cp,plan,'T001'))
            helper2=helper_modules.context(cp,plan,'T001')[0]
        self.assertNotEqual(key1,key2);self.assertNotEqual(helper1,helper2)

    def test_snapshot_source_and_olean_drift_are_rejected(self):
        descriptor=self.capture();root=Path(descriptor['root'])
        for relative in ('source/FixtureLib/Leaf.lean','lib/FixtureLib/Leaf.olean'):
            path=root/relative;old=path.read_bytes();path.write_bytes(old+b'changed')
            with self.subTest(relative=relative),self.assertRaisesRegex(ValueError,'changed'):
                libraries.validate([descriptor])
            path.write_bytes(old)
        libraries.validate([descriptor],full=True)

    def test_undeclared_files_and_symlinks_rejected(self):
        descriptor=self.capture();root=Path(descriptor['root']);extra=root/'extra'
        extra.write_text('unbound')
        with self.assertRaisesRegex(ValueError,'Undeclared'):libraries.validate([descriptor])
        extra.unlink();extra.symlink_to(self.spec)
        with self.assertRaisesRegex(ValueError,'Nonportable'):libraries.validate([descriptor])

    def test_source_queries_are_scoped_and_bounded(self):
        descriptor=self.capture()
        with libraries.use([descriptor]):
            self.assertIn('True.intro',libraries.read_source('FixtureLib.Leaf')['lines'])
            self.assertEqual(len(libraries.search_source('fixture')['matches']),1)
            for module in ('Mathlib.Init','FixtureLib.Missing','../../secret'):
                with self.subTest(module=module),self.assertRaises(ValueError):libraries.read_source(module)
            with self.assertRaises(ValueError):libraries.read_source('FixtureLib.Leaf',1,9999)
        with self.assertRaises(ValueError):libraries.read_source('FixtureLib.Leaf')

    def test_job_freezes_attachment_and_declares_the_environment(self):
        import jobs
        import runtime_snapshot
        problem=self.root/'problem.md';problem.write_text('Prove True.')
        self.spec.write_text(json.dumps(self.value))
        job=jobs.prepare(problem,track='nl0',profiles=harness_support.PROFILES,
                         output=self.root/'job',lean_libraries=[self.spec],lean_environment=__import__('runtime_config').require_environment())
        jobs.validate(job)
        self.assertEqual(job['lean_libraries'][0]['name'],'FixtureLib')
        self.assertIn('lean-library-001.json',[r['id'] for r in job['documents']])
        env=runtime_snapshot.environment(job)
        self.assertEqual(json.loads(env['YUI_LEAN_LIBRARIES']),job['lean_libraries'])
        bound=Path(job['lean_libraries'][0]['root'])/'lib/FixtureLib/Leaf.olean'
        bound.write_bytes(b'changed frozen binary')
        with self.assertRaisesRegex(ValueError,'changed'):jobs.validate(job)

    def test_source_export_is_portable_and_excludes_compiler_binaries(self):
        descriptor=self.capture();delivery=self.root/'export';delivery.mkdir()
        with libraries.use([descriptor]):index=libraries.export_sources(delivery)
        self.assertEqual(libraries.verify_export(delivery,index),['FixtureLib'])
        self.assertFalse(list(delivery.rglob('*.olean')))
        exported=delivery/'lean-libraries/FixtureLib/source/FixtureLib/Leaf.lean'
        exported.write_text('changed source')
        with self.assertRaisesRegex(ValueError,'source changed'):libraries.verify_export(delivery,index)

    def test_real_native_import_in_offline_sandbox(self):
        source=self.source/'FixtureLib/Leaf.lean'
        source.write_text('namespace FixtureLib\ntheorem witness : True := True.intro\nend FixtureLib\n')
        target=self.build/'FixtureLib/Leaf.olean'
        binary=Path(load_lock()['lean']['local_path'])/'bin/lean'
        compiled=subprocess.run([str(binary),'-R',str(self.source),'-o',str(target),str(source)],capture_output=True,text=True,timeout=60)
        self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
        self.value['modules'][0].update(source_sha256=bind(source)['sha256'],olean_sha256=bind(target)['sha256'])
        descriptor=self.capture();work=self.root/'native'
        (work/'input').mkdir(parents=True);(work/'output').mkdir()
        probe=work/'output/Probe.lean'
        probe.write_text('import Mathlib\nimport FixtureLib.Leaf\nexample : True := FixtureLib.witness\n#print axioms FixtureLib.witness\n')
        with libraries.use([descriptor]):result=pilot_common.run_lean(probe,work)
        self.assertEqual(result['exit_code'],0,result['stdout']+result['stderr'])
        self.assertRegex(result['stdout'],r'does not depend on any axioms|depends on axioms: \[\]')
        failed=pilot_common.run_lean(probe,work)
        self.assertNotEqual(failed['exit_code'],0)
        import delivery
        package=self.root/'portable';package.mkdir()
        solution=self.root/'Solution.lean'
        solution.write_text('import Mathlib\nimport FixtureLib.Leaf\nnamespace AuditBExport\n'
                            'theorem P : True := FixtureLib.witness\nend AuditBExport\n')
        contract={'parameters':[],'header':'import Mathlib\nimport FixtureLib.Leaf\n',
                  'conclusion':{'type':'True'}}
        with libraries.use([descriptor]):delivery.lean_project(package,contract,[],'AuditBExport.P',solution)
        (package/'.lake').mkdir()
        (package/'.lake/packages').symlink_to(Path(load_lock()['mathlib']['local_path']).parent/'packages',target_is_directory=True)
        built=subprocess.run([str(binary.parent/'lake'),'build','+Solution:olean'],cwd=package,
            capture_output=True,text=True,timeout=90,env={**os.environ,'LEAN_NUM_THREADS':'2'})
        self.assertEqual(built.returncode,0,built.stdout[-4000:]+built.stderr[-4000:])

    def test_actual_isolated_worker_imports_a_selected_library_and_uses_its_declaration(self):
        import runtime_config
        import model_pilot
        import ir
        from native_fixture import NativeFixture
        from audit_b_fixtures import fixture
        from lean_library_fixtures import library
        selected_file=os.environ.get('YUI_TEST_ALTERNATE_ENVIRONMENT')
        selected=json.loads(Path(selected_file).read_text()) if selected_file else runtime_config.require_environment()
        with runtime_config.use_environment(selected):
            spec=library(self.root/'real-library',modern=True)
            descriptor=libraries.capture(spec,self.root/'worker-run')
            cp,pp,_,_=fixture(self.root/'worker-case')
            contract=ir.load(cp);contract.update(header='import Mathlib\nimport FixtureLib.Leaf\n',
                pins=runtime_config.scientific_pins(),parameters=[],premises=[],conclusion={'statement':'Truth.','type':'True'})
            ir.write(cp,contract);plan=ir.load(pp);plan.update(contract_sha256=ir.digest(cp))
            plan['steps'][0].update(statement='True',inputs=[])
            def respond(f,handler,number,payload):
                code=('text(await tools.read_lean_library({module:"FixtureLib.Leaf",start:1,end:20}));'
                      if number==1 else 'text(await tools.submit_transition({proof:"exact FixtureLib.witness"}));')
                if number>2:raise AssertionError('Unexpected extra worker request')
                f.code(handler,number,code)
            with libraries.use([descriptor]),NativeFixture(self.root/'native-worker',responder=respond) as f:
                f.stage.release_resources('USER_CANCELLED')
                f.stage=model_pilot.Stage(self.root/'proof-worker',cp,'proof',None,plan,'T001')
                f.start();f.wait(seconds=45)
                self.assertEqual(f.outcomes[0][0]['status'],'ACCEPTED',f.outcomes)
                self.assertEqual(f.outcomes[0][1],{'proof':'exact FixtureLib.witness'})
                rows=[json.loads(line) for line in (f.stage.logs/'tools.jsonl').read_text().splitlines()]
                self.assertEqual([r['tool'] for r in rows],['read_lean_library','submit_transition'])
                self.assertIn('theorem witness',rows[0]['result']['lines'])
                self.assertTrue((f.stage.logs/rows[0]['result']['evidence']['path']).is_file())
                self.assertFalse(f.failures);self.assertFalse(f.notifications)


if __name__=='__main__':unittest.main()
