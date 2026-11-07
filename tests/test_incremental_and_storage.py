"""Native helper modules, lossless error extraction and storage admission."""
import harness_support
from concurrent.futures import ThreadPoolExecutor
import errno
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import compiler_feedback
import helper_modules
import ir
import local_helpers
import proof_repair
import source_access
import staging_storage as storage
from audit_b_fixtures import fixture


class NativeHelperModules(unittest.TestCase):
    def test_warm_dag_replay_is_independent_of_compiled_files_at_final_assembly(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);cp,pp,_,_=fixture(root/'case')
            c=ir.load(cp)
            c['header']='import Mathlib\nnoncomputable section\nnamespace LocalTypes\nabbrev Flag := Prop\nend LocalTypes\nopen LocalTypes\n'
            ir.write(cp,c)
            plan=ir.load(pp);plan['contract_sha256']=ir.digest(cp)
            def check(label,prop,proof,rows):
                return ir.check_auxiliary(cp,plan,'T001',prop,proof,out=root/'checks'/label,helpers=rows)
            rows=[]
            for i,body in enumerate(('exact h_H001','exact @yui_aux_0001 p h_H001','exact h_H001')):
                result=check(str(i),'p',body,rows)
                self.assertTrue(result.get('auxiliary_valid'),result)
                self.assertEqual(result['native_calls'],2 if not i else 1)
                rows.append(local_helpers.append(cp,plan,'T001',rows,'p',body,result))
            # An identical successful retry does not run the compiler.
            hit=check('retry','p','exact h_H001',rows[:2])
            self.assertEqual(hit['native_calls'],0)
            compact=(root/'checks/2/Auxiliary.lean').read_text()
            self.assertIn('import YuiHelpers',compact)
            self.assertNotIn('theorem yui_aux_0001',compact)
            bad=check('mistake','False','exact h_H001',rows)
            self.assertNotEqual(bad['exit_code'],0)
            with self.assertRaisesRegex(ValueError,'forward'):
                check('forward','p','exact yui_aux_0099',rows)
            cache=root/'checks/compiled-helpers'
            for file in cache.rglob('*.olean'):
                file.write_bytes(b'corrupt')
            with self.assertRaisesRegex(RuntimeError,'Changed'):
                check('corrupt','p','exact h_H001',rows)
            shutil.rmtree(cache)
            rebuilt=check('restore','p','exact @yui_aux_0001 p h_H001',rows)
            self.assertEqual(rebuilt['native_calls'],2)
            shutil.rmtree(cache)
            package=local_helpers.package(cp,plan,'T001','exact @yui_aux_0003 p h_H001',rows)
            self.assertEqual(ir.check(cp,plan,{'T001':package})['exit_code'],0)
            package['helpers'][1]['check']['module_check']['name']='wrong'
            with self.assertRaisesRegex(ValueError,'receipt'):local_helpers.unpack(cp,plan,'T001',package)

    def test_scope_with_local_variables_uses_the_original_checker(self):
        self.assertIsNone(helper_modules.replay('import Mathlib\nvariable {p : Prop}\n'))
        self.assertIsNone(helper_modules.replay('import Mathlib\n','def internal := Nat'))
        self.assertIsNone(helper_modules.replay('import Mathlib\nnamespace OpenEnded\n'))
        scoped=helper_modules.replay('import Mathlib\nnoncomputable section\nnamespace A\nopen scoped BigOperators\nend A\nopen Nat\n')
        self.assertIn('noncomputable section',scoped);self.assertIn('open Nat',scoped)
        self.assertNotIn('open scoped BigOperators',scoped)
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);cp,pp,_,_=fixture(root/'case')
            c=ir.load(cp);c['header']+='private def localNumber := 1\n'
            ir.write(cp,c);plan=ir.load(pp);plan['contract_sha256']=ir.digest(cp)
            result=ir.check_auxiliary(cp,plan,'T001','p','exact h_H001',out=root/'check')
            self.assertTrue(result['auxiliary_valid'],result)
            self.assertNotIn('module_check',result)

    def test_warning_prefix_does_not_hide_error_or_signal_false_target_progress(self):
        text='Check.lean:1:1: warning: noise\n'*900+'Check.lean:200:7: error: unsolved goals\n⊢ False\n'
        result={'exit_code':1,'stdout':text,'stderr':'x'*2200+'real process failure'}
        compact=compiler_feedback.compact_result(result)
        self.assertIn('unsolved goals',compact['stdout'])
        self.assertIn('real process failure',compact['stderr'])
        self.assertLessEqual(len(compact['stdout']),14000);self.assertEqual(result['stdout'],text)
        progress=proof_repair.Progress()
        for i in range(4):
            out={'exit_code':0,'auxiliary_valid':True}
            progress.observe('check_auxiliary',{'statement':str(i)},out,i)
        self.assertIn('target_progress_advice',out)
        self.assertEqual(progress.metadata()['distinct_target_checks'],0)
        progress.observe('check_transition',{'proof':'exact invalid'},{'exit_code':1},5)
        self.assertEqual(progress.metadata()['helpers_since_target'],0)
        self.assertEqual(progress.metadata()['distinct_target_checks'],1)


class Staging(unittest.TestCase):
    def test_parallel_reservations_do_not_overbook_and_are_released_on_error(self):
        with tempfile.TemporaryDirectory() as raw,patch.object(storage,'available',return_value=storage.FREE_FLOOR+100), \
                patch.dict(os.environ,{'YUI_TEST_CLEANUP_ROOT':raw}):
            root=Path(raw)
            def request():
                with storage.reserve(root,70):return True
            with storage.reserve(root,70),ThreadPoolExecutor(max_workers=1) as executor:
                with self.assertRaises(storage.StoragePressure):executor.submit(request).result(timeout=5)
            with self.assertRaisesRegex(RuntimeError,'interrupted'):
                with storage.reserve(root,90):raise RuntimeError('interrupted')
            self.assertFalse(list(root.rglob('lease-*')))
            self.assertTrue(request())

    def test_copy_never_changes_immutable_source_or_keeps_partial_on_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);source=root/'source';dest=root/'view'
            source.write_bytes(b'source');storage.copy_input(source,dest)
            self.assertNotEqual(source.stat().st_ino,dest.stat().st_ino)
            dest.write_bytes(b'private');self.assertEqual(source.read_bytes(),b'source')
            def fail(src,tmp):
                Path(tmp).write_bytes(b'partial')
                raise OSError(errno.ENOSPC,'full')
            with patch.object(storage,'clone',return_value=False),patch.object(shutil,'copyfile',side_effect=fail):
                with self.assertRaises(OSError):storage.copy_input(source,dest)
            self.assertEqual(dest.read_bytes(),b'private')
            self.assertFalse(list(root.glob('.yui-input-*')))

    def test_low_disk_is_an_execution_fault_before_download_or_native_launch(self):
        import pilot_common
        with tempfile.TemporaryDirectory() as raw,patch.object(storage,'available',return_value=0), \
                patch('urllib.request.build_opener') as network,patch('subprocess.Popen') as process:
            root=Path(raw)
            with self.assertRaises(storage.StoragePressure):source_access.fetch(root/'network','https://example.org/a')
            with self.assertRaises(storage.StoragePressure):pilot_common.run_lean(root/'file.lean',root)
            network.assert_not_called();process.assert_not_called()
            self.assertFalse((root/'network').exists())
