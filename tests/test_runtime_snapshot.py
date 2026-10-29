"""An installed skill may change without changing an owned job's executable."""
import harness_support
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from controller_common import bind
import library_catalog
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
        descriptor,rows,catalog=snapshots.capture(self.run,self.rows,core=self.core)
        return dict(root=str(self.run),runtime_snapshot=descriptor,runtime=rows,library_catalog=catalog)

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

    def test_external_catalog_is_copied_and_pinned_without_personal_files(self):
        catalog=self.root/'catalog';catalog.mkdir()
        (catalog/'foundations.json').write_text('{"version":1,"entries":[]}')
        (catalog/'private-auth.json').write_text('NEVER_COPY_UNDECLARED_DATA')
        with library_catalog.use_library(catalog):
            self.rows.extend(bind(p) for p in library_catalog.catalog_files());job=self.capture()
        self.assertEqual(Path(job['library_catalog']['path']),self.run/'runtime/library/foundations.json')
        self.assertFalse((self.run/'runtime/library/private-auth.json').exists())
        (catalog/'foundations.json').write_text('invalid after preparation')
        snapshots.validate(job)
        env=snapshots.environment(job)
        self.assertEqual(env['YUI_LIBRARY_ROOT'],str(self.run/'runtime/library'))

    def test_case_launcher_uses_the_retained_executable(self):
        job=self.capture();path=self.run/'job.json';path.write_text(json.dumps(job))
        with patch.object(queue_controller.subprocess,'Popen') as start:
            queue_controller.launch_case(path,self.run)
        argv=start.call_args.args[0]
        self.assertEqual(Path(argv[3]),self.run/'runtime/nl0/scripts/case_runner.py')
        self.assertEqual(start.call_args.kwargs['env']['YUI_LIBRARY_ROOT'],str(self.run/'runtime/library'))

    def test_capture_rejects_a_changed_or_undeclared_external_file(self):
        (self.core/'SKILL.md').write_text('not the collected source')
        with self.assertRaisesRegex(ValueError,'changed'):self.capture()
        shutil.rmtree(self.run/'runtime')
        p=self.root/'foreign.json';p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'outside'):
            snapshots.capture(self.run,[bind(p)],core=self.core)


if __name__=='__main__':unittest.main()
