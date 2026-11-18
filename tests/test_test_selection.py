"""Independent test-runner outcomes: skip before setup, fail honestly, retain fixtures."""
import harness_support
from contextlib import redirect_stderr,redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sys
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

    def test_cross_version_case_skips_without_a_distinct_lean_environment(self):
        from test_imported_lean import ImportedLeanTests
        from types import SimpleNamespace
        current={'lean':{'version_number':'selected'},'mathlib':{'rev':'a'*40}}
        for comparison in (None,current,{'lean':{'version_number':'selected'},'mathlib':{'rev':'b'*40}}):
            case=ImportedLeanTests('test_actual_version_specific_original_passes_old_and_requires_current_port')
            case.current=current;case.comparison=comparison;case.old=comparison or current
            case.stage=SimpleNamespace(task_inputs={})
            case.check=lambda **kwargs:self.fail('A same-version check cannot stand in for a cross-version test')
            with self.subTest(comparison=comparison),self.assertRaisesRegex(unittest.SkipTest,'SKIPPED_COMPARISON'):
                case.test_actual_version_specific_original_passes_old_and_requires_current_port()

    def test_quick_manifest_selectors_and_area_names_are_checked(self):
        catalogue=selection.catalogue()['modules']
        profile=json.loads((selection.TESTS/'quick.json').read_text())
        self.assertTrue(selection.quick_selectors(profile['areas'],catalogue))
        with self.assertRaisesRegex(ValueError,'Unknown quick area'):
            selection.quick_selectors(['unregistered-area'],catalogue)
        (self.root/'test_fixture.py').write_text('class Example:\n    def test_actual(self):pass\n')
        (self.root/'quick.json').write_text(json.dumps({'core':['test_fixture.Example.test_obsolete'],'areas':{}}))
        with patch.object(selection,'TESTS',self.root),self.assertRaisesRegex(ValueError,'test_obsolete'):
            selection.quick_selectors([],{'test_fixture'})

    def test_quick_areas_share_cases_and_full_discovery_runs_unlisted_classes(self):
        name='test_quick_fixture'
        (self.root/(name+'.py')).write_text(
            'import unittest\nfrom pathlib import Path\nclass Fast(unittest.TestCase):\n'
            '    def test_core(self): pass\n    def test_edge(self): pass\n'
            'class Full(unittest.TestCase):\n    @classmethod\n    def setUpClass(cls):\n'
            '        Path(__file__).with_suffix(".started").touch()\n    def test_slow(self): pass\n')
        self.addCleanup(sys.modules.pop,name,None)
        core=name+'.Fast.test_core';edge=name+'.Fast.test_edge';slow=name+'.Full.test_slow'
        (self.root/'quick.json').write_text(json.dumps({'core':[core],'areas':{'alpha':[edge],'beta':[name+'.Fast']}}))
        data={'modules':{name:{'lean':'none'}},'classes':{},'tests':{}}
        host={'codex':{'binary_path':'/codex'},'tools':{'ripgrep':{'binary_path':'/rg'}}}
        def launch(arguments,*,test_env):
            with patch.dict(os.environ,test_env):
                return selection.worker(arguments)
        def run(args):
            report=self.root/'report.json'
            self.assertEqual(selection.dispatch([*args,'--report',str(report)],launch),0)
            return json.loads(report.read_text())
        marker=self.root/(name+'.started')
        with patch.object(selection,'TESTS',self.root),patch.object(selection,'CORE',self.root), \
                patch.object(selection,'catalogue',return_value=data), \
                patch.object(sys,'path',[str(self.root),*sys.path]),patch('runtime_config.host_tools',return_value=host), \
                patch('runtime_config.require_environment',side_effect=AssertionError('unexpected Lean setup')), \
                redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            self.assertEqual(run(['--quick'])['selected_tests'],[core])
            quick=run(['--quick','--area','alpha','--area','beta','--area','alpha'])
            self.assertEqual(quick['profile'],'quick')
            self.assertEqual(quick['areas'],['alpha','beta'])
            self.assertEqual(set(quick['selected_tests']),{core,edge})
            self.assertEqual(quick['outcome_counts'],{'PASS':2})
            self.assertFalse(marker.exists())
            for args in ([],['--all']):
                full=run(args)
                self.assertEqual(full['profile'],'full')
                self.assertEqual(set(full['selected_tests']),{core,edge,slow})
                self.assertTrue(marker.is_file())
            default_report=self.root/'.runtime/test-report.json'
            default_report.parent.mkdir(exist_ok=True)
            default_report.write_text('prior full result')
            self.assertEqual(selection.dispatch(['--quick'],launch),0)
            self.assertEqual(default_report.read_text(),'prior full result')
            self.assertEqual(json.loads(default_report.with_name('test-report-quick.json').read_text())['profile'],'quick')
            for args in (['--area','alpha'],['--quick','--all'],['--quick',name],['--quick','--area','absent']):
                with self.subTest(args=args),self.assertRaises(SystemExit):
                    run(args)

    def test_quiet_skip_reports_the_reason_and_never_records_pass(self):
        class MissingComparison(unittest.TestCase):
            def runTest(self):self.skipTest('SKIPPED_COMPARISON_ENVIRONMENT_REQUIRED: supply a second Lean version')
        case=MissingComparison();stream=io.StringIO()
        result=unittest.TextTestRunner(stream=stream,verbosity=0,resultclass=selection.Results).run(case)
        self.assertEqual(result.outcomes[case.id()]['status'],'SKIP')
        self.assertIn('SKIPPED_COMPARISON_ENVIRONMENT_REQUIRED',stream.getvalue())

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

    def test_skipped_comparison_is_visible_in_the_overall_result(self):
        data={'modules':{'test_fixture':{'lean':'none'}},'classes':{},'tests':{}}
        host={'codex':{'binary_path':'/codex'},'tools':{'ripgrep':{'binary_path':'/rg'}}}
        def skipped(arguments,*,test_env):
            self.assertEqual(test_env['YUI_TEST_UPSTREAM_ENVIRONMENT'],'')
            Path(test_env['YUI_TEST_WORKER_REPORT']).write_text(json.dumps({'group':'none','passed':True,
                'tests':1,'outcomes':{'case':{'status':'SKIP','reason':'SKIPPED_COMPARISON_ENVIRONMENT_REQUIRED'}}}))
            return 0
        output=io.StringIO();path=self.root/'skipped.json'
        with patch.object(selection,'catalogue',return_value=data),patch('runtime_config.host_tools',return_value=host), \
                redirect_stdout(output):
            code=selection.dispatch(['test_fixture','--report',str(path)],skipped)
        value=json.loads(path.read_text());self.assertEqual(code,0)
        self.assertEqual(value['status'],'PASSED_WITH_SKIPS');self.assertEqual(value['outcome_counts'],{'SKIP':1})
        self.assertIn('PASSED_WITH_SKIPS',output.getvalue())

    def test_explicit_current_test_without_environment_is_a_failure(self):
        data={'modules':{'test_fixture':{'lean':'current'}},'classes':{},'tests':{}}
        with patch.object(selection,'catalogue',return_value=data), \
             patch('runtime_config.require_environment',side_effect=ValueError('Missing selected environment')), \
             redirect_stdout(io.StringIO()):
            code=selection.dispatch(['test_fixture','--report',str(self.root/'missing.json')],
                                    lambda *args,**kwargs:0)
        self.assertEqual(code,1)
        self.assertIn('Missing selected environment',json.loads((self.root/'missing.json').read_text())['error'])

    def test_selected_fixture_projection_does_not_rewrite_unrelated_inputs(self):
        source=self.root/'source';(source/'lean/examples/simple').mkdir(parents=True)
        (source/'unrelated').mkdir()
        contract=source/'lean/examples/simple/contract.json'
        contract.write_text(json.dumps({'pins':{'lean_version':'UNSELECTED','mathlib_commit':'b'*40}}))
        history=source/'unrelated/evidence.json';history.write_bytes(b'Unrelated fixture input')
        before={p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()}
        selected={'lean':{'version_number':'chosen'},'mathlib':{'rev':'c'*40}}
        out=prepare(source,self.root/'selected',selected)
        self.assertEqual(json.loads((out/'lean/examples/simple/contract.json').read_text())['pins'],
                         {'lean_version':'chosen','mathlib_commit':'c'*40})
        self.assertEqual((out/'unrelated/evidence.json').read_bytes(),history.read_bytes())
        self.assertEqual(before,{p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()})


if __name__=='__main__':unittest.main()
