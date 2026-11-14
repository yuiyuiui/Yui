"""An installed skill may change without changing an owned job's executable."""
import harness_support
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from controller_common import bind
import queue_controller
import runtime_snapshot as snapshots


class RuntimeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.core=self.root/'installation';self.run=self.root/'run'
        self.core.mkdir();self.run.mkdir()
        for name,text in [('SKILL.md','Declared rules'),('config.json','{}'),
                ('nl0/scripts/case_runner.py','print("PINNED_RUNTIME")\n')]:
            p=self.core/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        self.rows=[bind(p) for p in sorted(self.core.rglob('*')) if p.is_file()]

    def tearDown(self):self.temp.cleanup()

    def capture(self):
        descriptor,rows=snapshots.capture(self.run,self.rows,core=self.core)
        return dict(root=str(self.run),runtime_snapshot=descriptor,runtime=rows)

    def test_installed_updates_or_removal_do_not_change_the_prepared_runtime(self):
        job=self.capture();before=list(job['runtime'])
        shutil.rmtree(self.core)
        self.assertEqual(snapshots.validate(job),job['runtime_snapshot'])
        self.assertEqual(job['runtime'],before)
        result=subprocess.check_output([sys.executable,'-B',str(snapshots.root_for(job)/'nl0/scripts/case_runner.py')],text=True)
        self.assertEqual(result.strip(),'PINNED_RUNTIME')

    def test_snapshot_tampering_and_escape_are_rejected(self):
        job=self.capture();p=self.run/'runtime/SKILL.md';p.write_text('modified')
        with self.assertRaisesRegex(ValueError,'changed'):snapshots.validate(job)
        job['runtime_snapshot']['root']=str(self.core)
        with self.assertRaisesRegex(ValueError,'escapes'):snapshots.validate(job)

    def test_new_snapshot_ignores_retired_catalog_configuration(self):
        catalog=self.root/'catalog';catalog.mkdir()
        (catalog/'foundations.json').write_text('Obsolete personal data must never be read.')
        with patch.dict(os.environ,{'YUI_LIBRARY_ROOT':str(catalog)}):
            job=self.capture()
            self.assertNotIn('YUI_LIBRARY_ROOT',snapshots.environment(job))
        self.assertEqual(set(job['runtime_snapshot']),{'root','manifest'})
        self.assertEqual(json.loads((self.run/'runtime-manifest.json').read_text())['version'],
                         'yui-runtime-snapshot-3')
        self.assertFalse((self.run/'runtime/library').exists())






    def test_snapshot_schema_and_descriptor_cannot_mix_versions(self):
        job=self.capture();job['runtime_snapshot']['library_root']=str(self.run/'runtime/library')
        with self.assertRaisesRegex(ValueError,'escapes'):snapshots.validate(job)

    def test_case_launcher_uses_the_retained_executable(self):
        job=self.capture();path=self.run/'job.json';path.write_text(json.dumps(job))
        with patch.object(queue_controller.subprocess,'Popen') as start:
            queue_controller.launch_case(path,self.run)
        argv=start.call_args.args[0]
        self.assertEqual(Path(argv[3]),self.run/'runtime/nl0/scripts/case_runner.py')
        self.assertNotIn('YUI_LIBRARY_ROOT',start.call_args.kwargs['env'])

    def test_capture_rejects_a_changed_or_undeclared_external_file(self):
        (self.core/'SKILL.md').write_text('not the collected source')
        with self.assertRaisesRegex(ValueError,'changed'):self.capture()
        shutil.rmtree(self.run/'runtime')
        p=self.root/'foreign.json';p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'outside'):
            snapshots.capture(self.run,[bind(p)],core=self.core)


if __name__=='__main__':unittest.main()
