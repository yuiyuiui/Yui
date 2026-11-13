"""Independent native import/reuse and original-environment porting decisions."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/'blocks/imported_lean.py'
SPEC=importlib.util.spec_from_file_location('import_rules_under_test',PATH)
rules=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(rules)
PASS={'native':{'exit_code':0},'source_policy_passed':True}
FAIL={'native':{'exit_code':1},'source_policy_passed':True}


class ImportedCode(unittest.TestCase):
    def test_current_pass_reuses_original_without_upstream(self):
        value=rules.decide(PASS)
        self.assertEqual(value['status'],'LOCAL_REUSED');self.assertTrue(value['accepted_for_native_reuse'])
        self.assertFalse(value['semantic_acceptance'])

    def test_failed_current_requires_declared_available_original_environment(self):
        self.assertEqual(rules.decide(FAIL)['status'],'UPSTREAM_ENVIRONMENT_REQUIRED')

    def test_missing_original_imports_do_not_blame_source_code(self):
        value=rules.decide(FAIL,upstream_available=True,context=FAIL,original=FAIL)
        self.assertEqual(value['status'],'UPSTREAM_CONTEXT_REQUIRED');self.assertFalse(value['accepted_for_native_reuse'])

    def test_working_original_routes_compatibility_port(self):
        self.assertEqual(rules.decide(FAIL,upstream_available=True,context=PASS,original=PASS)['status'],
                         'COMPATIBILITY_PORT_REQUIRED')

    def test_original_failure_in_working_context_routes_correction_and_port(self):
        self.assertEqual(rules.decide(FAIL,upstream_available=True,context=PASS,original=FAIL)['status'],
                         'CORRECTION_AND_PORT_REQUIRED')

    def test_only_completed_current_recheck_accepts_the_port(self):
        args={'upstream_available':True,'context':PASS,'original':PASS}
        good=rules.decide(FAIL,candidate=PASS,**args)
        self.assertEqual(good['status'],'PORTED_CHECKED');self.assertTrue(good['accepted_for_native_reuse'])
        bad=rules.decide(FAIL,candidate=FAIL,**args)
        self.assertEqual(bad['status'],'PORT_CHECK_FAILED');self.assertFalse(bad['accepted_for_native_reuse'])

    def test_timeout_cancel_and_missing_exit_never_pass_or_blame_source(self):
        for native in ({'exit_code':0,'timed_out':True},{'exit_code':0,'cancelled':True},
                       {'exit_code':True},{'exit_code':-9},{'exit_code':124},{'exit_code':None}):
            value={'native':native,'source_policy_passed':True}
            with self.subTest(native=native):
                self.assertEqual(rules.decide(value)['status'],'LOCAL_CHECK_INCOMPLETE')
                self.assertEqual(rules.decide(FAIL,upstream_available=True,context=PASS,original=value)['status'],
                                 'UPSTREAM_CHECK_INCOMPLETE')
                self.assertEqual(rules.decide(FAIL,upstream_available=True,context=PASS,original=PASS,candidate=value)['status'],
                                 'PORT_CHECK_INCOMPLETE')

    def test_explicit_unproved_source_cannot_be_reused_despite_exit_zero(self):
        value=deepcopy(PASS);value['source_policy_passed']=False
        answer=rules.decide(value,upstream_available=True,context=PASS,original=value)
        self.assertEqual(answer['status'],'CORRECTION_AND_PORT_REQUIRED');self.assertFalse(answer['accepted_for_native_reuse'])


if __name__=='__main__':unittest.main()
