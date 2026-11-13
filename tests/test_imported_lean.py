"""Real Lean local/upstream/port checks with source and environment bindings."""
import harness_support
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from controller_common import bind,write
import lean_environment
import lean_imports
import lean_libraries
import pilot_common
import runtime_config

GOOD='import Mathlib\nnamespace ImportedExample\ntheorem witness : True := by trivial\nend ImportedExample\n'
BAD=GOOD.replace('by trivial','by exact nonexistentOriginalProof')
OLD=Path.home()/'formalization-tools/lean-mathlib-v4.32.2'


class ImportedLeanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=lean_environment.resolve(lean_root=OLD/'lean',mathlib_root=OLD/'mathlib')
        path=os.environ.get('YUI_TEST_ALTERNATE_ENVIRONMENT')
        cls.current=json.loads(Path(path).read_text()) if path else cls.old

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.logs=self.root/'stage';self.logs.mkdir()
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
        version=self.old['lean']['version_number']
        self.stage.task_inputs['original.lean']='import Mathlib\nimport Lean\n#guard Lean.versionString == '+json.dumps(version)+'\n'+GOOD.removeprefix('import Mathlib\n')
        with patch.object(lean_imports,'original_environment',return_value=self.old):
            result=self.check(upstream=self.upstream(),candidate=GOOD) if self.current!=self.old else self.check(upstream=self.upstream())
        if self.current==self.old:self.assertEqual(result['status'],'LOCAL_REUSED')
        else:
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


if __name__=='__main__':unittest.main()
