"""Independent test-runner outcomes: skip before setup, fail honestly, retain fixtures."""
import harness_support
from contextlib import redirect_stderr,redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import selection
from fixture_environment import prepare


class RequirementSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def test_catalogue_covers_actual_modules_and_unknown_tests_cannot_fall_back(self):
        value=selection.catalogue()
        self.assertEqual(set(value['modules']),{p.stem for p in harness_support.TESTS.glob('test_*.py')})
        with self.assertRaisesRegex(ValueError,'Unclassified'):
            selection.requirement('future_unreviewed.Test.test_case',value)

    def test_history_mismatch_skips_before_class_initializer(self):
        touched=[]
        class History(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                touched.append('incorrectly initialized')
                raise AssertionError('Historical dependency must not be accessed')
            def test_case(self):raise AssertionError('Must not execute')
        case=History('test_case');identifier=case.id()
        req={'lean':'exact','lean_version':'fixture','mathlib_commit':'a'*40,'reason':'Immutable original evidence'}
        data={'modules':{},'classes':{},'tests':{identifier:req}}
        output=self.root/'report.json'
        with patch.object(selection,'catalogue',return_value=data), \
             patch.object(selection,'load_suite',return_value=unittest.TestSuite([case])), \
             patch.dict(os.environ,{'YUI_TEST_GROUP':'exact','YUI_LEAN_ENVIRONMENT':'null',
                                   'YUI_TEST_WORKER_REPORT':str(output)}), \
             redirect_stderr(io.StringIO()):
            code=selection.worker([])
        self.assertEqual(code,0);self.assertEqual(touched,[])
        report=json.loads(output.read_text())
        self.assertEqual(report['decisions'][identifier],'SKIPPED_VERSION_MISMATCH')
        self.assertIn('requires fixture',report['outcomes'][identifier]['reason'])

    def test_nonzero_native_worker_cannot_be_reported_as_success(self):
        data={'modules':{'test_fixture':{'lean':'current'}},'classes':{},'tests':{}}
        selected={'lean':{'version_number':'fixture','local_path':'/lean'},
                  'mathlib':{'rev':'a'*40,'local_path':'/mathlib'}}
        host={'codex':{'binary_path':'/codex'},'tools':{'ripgrep':{'binary_path':'/rg'}}}
        def failed(arguments,*,test_env):
            Path(test_env['YUI_TEST_WORKER_REPORT']).write_text(json.dumps({
                'group':'current','passed':True,'tests':1,'outcomes':{}}))
            return 1
        with patch.object(selection,'catalogue',return_value=data), \
             patch('runtime_config.require_environment',return_value=selected), \
             patch('runtime_config.host_tools',return_value=host),redirect_stdout(io.StringIO()):
            code=selection.dispatch(['test_fixture','--report',str(self.root/'all.json')],failed)
        self.assertEqual(code,1)
        self.assertFalse(json.loads((self.root/'all.json').read_text())['passed'])

    def test_explicit_current_test_without_environment_is_a_failure(self):
        data={'modules':{'test_fixture':{'lean':'current'}},'classes':{},'tests':{}}
        with patch.object(selection,'catalogue',return_value=data), \
             patch('runtime_config.require_environment',side_effect=ValueError('Missing selected environment')), \
             redirect_stdout(io.StringIO()):
            code=selection.dispatch(['test_fixture','--report',str(self.root/'missing.json')],
                                    lambda *args,**kwargs:0)
        self.assertEqual(code,1)
        self.assertIn('Missing selected environment',json.loads((self.root/'missing.json').read_text())['error'])

    def test_selected_fixture_projection_does_not_rewrite_original_or_history(self):
        source=self.root/'source';(source/'lean/examples/simple').mkdir(parents=True)
        (source/'legacy').mkdir()
        contract=source/'lean/examples/simple/contract.json'
        contract.write_text(json.dumps({'pins':{'lean_version':'historical','mathlib_commit':'b'*40}}))
        history=source/'legacy/evidence.json';history.write_bytes(b'Immutable historical proof evidence')
        before={p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()}
        selected={'lean':{'version_number':'chosen'},'mathlib':{'rev':'c'*40}}
        out=prepare(source,self.root/'selected',selected)
        self.assertEqual(json.loads((out/'lean/examples/simple/contract.json').read_text())['pins'],
                         {'lean_version':'chosen','mathlib_commit':'c'*40})
        self.assertEqual((out/'legacy/evidence.json').read_bytes(),history.read_bytes())
        self.assertEqual(before,{p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()})


if __name__=='__main__':unittest.main()
