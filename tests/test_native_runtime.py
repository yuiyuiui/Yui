"""Dependency discovery/binding without model inference or a real installation."""
import harness_support
import json
from pathlib import Path
import tempfile
import unittest
import native_runtime


class NativeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'Codex installation with spaces';self.root.mkdir()
        self.binary=self.root/'App/Contents/MacOS/codex';self.binary.parent.mkdir(parents=True)
        self.binary.write_text('native executable');self.binary.chmod(0o700)
        self.helper=self.root/'bin/codex-code-mode-host';self.helper.parent.mkdir()
        self.helper.write_text('native helper');self.helper.chmod(0o700)
        self.manifest=self.root/'codex-package.json'
        self.manifest.write_text(json.dumps({'layoutVersion':1,'version':'0.test'}))

    def resolve(self):return native_runtime.resolve(self.binary,'codex-cli 0.test')

    def test_package_layout_and_spaces_bind_the_actual_helper(self):
        bound=self.resolve();self.assertEqual(bound['code_mode_host']['path'],str(self.helper.resolve()))
        self.assertEqual(native_runtime.verify(bound),bound)

    def test_missing_or_nonexecutable_helper_is_rejected_before_dispatch(self):
        self.helper.chmod(0o600)
        with self.assertRaises(FileNotFoundError):self.resolve()
        self.helper.unlink()
        with self.assertRaises(FileNotFoundError):self.resolve()

    def test_wrong_or_incomplete_package_version_is_rejected(self):
        for version in ('different',None):
            self.manifest.write_text(json.dumps({'layoutVersion':1,'version':version}))
            with self.assertRaises(ValueError):self.resolve()

    def test_helper_cannot_escape_the_selected_installation(self):
        outside=Path(self.temp.name)/'other-helper';outside.write_text('other');outside.chmod(0o700)
        self.helper.unlink();self.helper.symlink_to(outside)
        with self.assertRaises(ValueError):self.resolve()

    def test_changed_main_helper_or_manifest_invalidates_binding(self):
        for path in (self.binary,self.helper,self.manifest):
            bound=self.resolve();before=path.read_bytes();path.write_bytes(before+b'changed')
            with self.assertRaises(ValueError):native_runtime.verify(bound)
            path.write_bytes(before)

    def test_standalone_installation_uses_only_adjacent_helper(self):
        self.manifest.unlink();self.binary.unlink();self.binary=self.helper.parent/'codex'
        self.binary.write_text('native executable');self.binary.chmod(0o700)
        self.assertIsNone(self.resolve()['package_manifest'])

    def test_stage_must_keep_prepared_native_binding(self):
        case=Path(self.temp.name)/'run';logs=case/'author/logs';logs.mkdir(parents=True)
        (case/'.yui-run.json').write_text('{}');bound=self.resolve()
        (case/'job.json').write_text(json.dumps({'native_components':bound}))
        self.assertEqual(native_runtime.for_stage(logs,bound),bound)
        changed={**bound,'version':'unapproved-version'}
        with self.assertRaisesRegex(ValueError,'differ from prepared'):native_runtime.for_stage(logs,changed)
        self.helper.write_text('replaced helper')
        with self.assertRaisesRegex(ValueError,'component changed'):native_runtime.for_stage(logs,bound)

    def test_legacy_job_without_component_record_remains_readable(self):
        case=Path(self.temp.name)/'run';case.mkdir()
        (case/'.yui-run.json').write_text('{}');(case/'job.json').write_text('{}')
        bound=self.resolve();self.assertEqual(native_runtime.for_stage(case,bound),bound)
