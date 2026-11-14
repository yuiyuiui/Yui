"""Actual setup consumer qualification; no provider request or global installation."""
import harness_support
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import local_config
import runtime_config
import setup_checks
from lean_library_fixtures import library


class ActualSetupConsumers(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.selected=runtime_config.require_environment()

    def test_actual_inspector_export_source_query_and_negative_axiom_gate(self):
        checks=setup_checks.native(self.root,self.selected)
        self.assertEqual(set(checks),local_config.rules.LEAN_CHECKS)
        self.assertTrue(all(row['passed'] and row['execution']=='actual' for row in checks.values()))

    def test_generated_library_spec_works_through_real_job_tools_sandbox_and_export(self):
        original=library(self.root/'external')
        data=json.loads(original.read_text())
        specification=setup_checks.library_specification(data['source_root'],data['build_root'],
            data['name'],data['imports'],self.root/'generated.json')
        generated=json.loads(specification.read_text())
        self.assertEqual(generated['modules'],data['modules'])
        import jobs
        original=jobs.input_file
        def outside_installation(path):
            self.assertFalse(Path(path).resolve().is_relative_to(self.root),
                             'Setup task inputs must stay outside the installation/evidence directory')
            return original(path)
        with patch.object(jobs,'input_file',side_effect=outside_installation):
            checked=setup_checks.external_library(self.root/'qualification',specification,self.selected,
                                                  harness_support.PROFILES)
        self.assertTrue(checked['passed'])
        report=json.loads(Path(checked['evidence'][0]['path']).read_text())
        self.assertIn('YUI_LIBRARY_DECLARATION:',report['native']['stdout'])
        self.assertEqual(report['native']['exit_code'],0)
        self.assertTrue(report['read']['lines'])
        self.assertTrue(report['qualification_workspace_removed'])
        self.assertTrue(Path(report['job']['path']).is_file())

    def test_missing_companion_or_unreadable_source_never_becomes_available(self):
        original=library(self.root/'external')
        data=json.loads(original.read_text())
        source=Path(data['source_root'])/'FixtureLib/Leaf.lean'
        with patch.object(Path,'read_text',side_effect=PermissionError('Synthetic public source denial')):
            with self.assertRaises(PermissionError):
                setup_checks.library_specification(data['source_root'],data['build_root'],
                    data['name'],data['imports'],self.root/'denied.json')
        source.unlink()
        with self.assertRaises((OSError,ValueError)):
            setup_checks.external_library(self.root/'missing',original,self.selected,harness_support.PROFILES)

    def test_concurrent_jobs_and_child_context_keep_each_actual_selected_pair(self):
        import jobs
        import lean_environment
        import runtime_snapshot
        from pilot_common import run_lean,native_succeeded
        alternate=os.environ.get('YUI_TEST_ALTERNATE_ENVIRONMENT')
        other=lean_environment.verify(json.loads(Path(alternate).read_text())) if alternate else self.selected
        tools=runtime_config.host_tools()
        host={'codex':tools['codex'],'ripgrep':{'path':tools['tools']['ripgrep']['binary_path'],
            'sha256':tools['tools']['ripgrep']['sha256']},'python':sys.executable,
            'auth_home':str(runtime_config.auth_home())}
        prepared=[]
        for number,selected in enumerate((self.selected,other)):
            root=self.root/str(number);root.mkdir();problem=root/'proof.md';problem.write_text('Given True, conclude True.')
            context={'version':local_config.rules.RUN_VERSION,'host':host,
                     'profiles':harness_support.PROFILES,'lean_environment':selected}
            with local_config.use(context):
                job=jobs.prepare(problem,track='full',profiles=harness_support.PROFILES,lean_environment=selected)
            prepared.append(job)
        def check(job):
            with jobs.scientific_context(job):
                selected=job['lean_environment'];root=Path(job['root'])/'native'
                for name in ('input','output','tmp','home'):(root/name).mkdir(parents=True)
                source=root/'output/Check.lean'
                source.write_text('import Mathlib\nexample : True := True.intro\n#eval Lean.versionString\n')
                compiled=run_lean(source,root,timeout=120)
                self.assertTrue(native_succeeded(compiled),compiled)
                self.assertIn(selected['lean']['version_number'],compiled['stdout'])
                frozen=runtime_snapshot.environment(job)
                self.assertEqual(json.loads(frozen['YUI_LEAN_ENVIRONMENT']),selected)
                self.assertEqual(json.loads(frozen['YUI_FROZEN_LOCAL_CONFIG'])['lean_environment'],selected)
                jobs.validate(job)
                return runtime_config.scientific_pins()['mathlib_commit']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(check,prepared))
        self.assertEqual(results,[row['lean_environment']['mathlib']['rev'] for row in prepared])
        # The later default cannot change the already frozen first job.
        with local_config.use(prepared[1]['local_configuration']),jobs.scientific_context(prepared[0]):
            self.assertEqual(runtime_config.require_environment(),prepared[0]['lean_environment'])


if __name__=='__main__':unittest.main()
