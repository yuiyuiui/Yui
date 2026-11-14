"""Independent readiness, scope and test-selection obligations; no host access."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from blocks import local_setup as rules
from wfcore.model import Model


def host():
    def bound(path):return {'path':path,'sha256':'a'*64}
    return {'codex':{'binary_path':'/tools/codex','sha256':'b'*64,'version':'codex-cli fixture',
                    'code_mode_host':bound('/tools/code-mode'),'package_manifest':None},
            'ripgrep':bound('/tools/rg'),'python':'/tools/python','auth_home':'/auth'}


def check():
    return {'passed':True,'execution':'actual','evidence':[{'path':'/evidence/check.json','sha256':'c'*64}]}


def config(mode='nl0'):
    profile={'id':'chosen','reasoning_effort':'high','speed':'standard','automatic_fallback':False}
    return {'version':rules.VERSION,'root':'/installation','mode':mode,'host':host(),
            'profiles':{'nl0':dict(profile),'lean':dict(profile)},
            'lean_environment':None if mode=='nl0' else {'fixture':'selected scientific descriptor'},
            'implementation':{'program.py':'f'*64},
            'libraries':[],'checks':{key:check() for key in rules.required_checks(mode,[])},
            'created_at':'fixture time'}


class LocalAdaptation(unittest.TestCase):
    def test_pure_nl0_requires_no_scientific_environment(self):
        value=config();self.assertEqual(rules.validate_config(value),value)

    def test_lean_readiness_requires_every_actual_consumer_check(self):
        value=config('lean');rules.validate_config(value)
        for name in rules.LEAN_CHECKS:
            bad=deepcopy(value);del bad['checks'][name]
            with self.subTest(name=name),self.assertRaises(ValueError):rules.validate_config(bad)

    def test_directory_existence_or_simulated_success_cannot_publish_ready(self):
        for replacement in ({'passed':True,'execution':'actual','evidence':[]},
                            {'passed':True,'execution':'fixture','evidence':check()['evidence']},
                            {'passed':False,'execution':'actual','evidence':check()['evidence']}):
            value=config();value['checks']['host']=replacement
            with self.subTest(row=replacement),self.assertRaises(ValueError):rules.validate_config(value)

    def test_requested_external_library_adds_a_mandatory_consumer_check(self):
        value=config('lean')
        value['libraries']=[{'name':'PublicLib','specification':{'path':'/spec.json','sha256':'d'*64}}]
        with self.assertRaises(ValueError):rules.validate_config(value)
        value['checks']['library:PublicLib']=check();rules.validate_config(value)

    def test_scope_mismatch_and_credentials_in_configuration_are_rejected(self):
        for mutate in (lambda v:v.update(mode='lean'),lambda v:v.update(auth_token='never store'),
                       lambda v:v['host'].update(secret='never store')):
            value=config();mutate(value)
            with self.assertRaises(ValueError):rules.validate_config(value)

    def test_published_report_contract_matches_its_owner(self):
        model=Model(ROOT)
        self.assertEqual(model.contracts['LocalSetupReport@1'],rules.REPORT_SCHEMA)
        for status in ('NEEDS_USER_ACTION','FAILED'):
            report={'status':status,'entry':'setup/README.md','mode':'lean',
                    'configuration_published':False,'attempt':'/attempt'}
            model.check('LocalSetupReport@1',report,'incomplete adaptation')
            rules.validate_report(report)
            report['configuration_published']=True
            with self.assertRaises(ValueError):model.check('LocalSetupReport@1',report,'false publication')
            with self.assertRaises(ValueError):rules.validate_report(report)

    def test_ready_report_cannot_omit_checks_or_claim_a_different_scope(self):
        report={'status':'READY','entry':'setup/README.md','mode':'lean','attempt':'/attempt',
            'configuration_published':True,'configuration':{'path':'/config.json','sha256':'e'*64},
            'capabilities':{'mode':'lean','libraries':[]},'checks':config('lean')['checks']}
        Model(ROOT).check('LocalSetupReport@1',report,'ready adaptation');rules.validate_report(report)
        for mutate in (lambda v:v['checks'].pop('basis_export'),
                       lambda v:v['capabilities'].update(mode='nl0'),
                       lambda v:v['checks']['provider'].update(execution='fixture')):
            value=deepcopy(report);mutate(value)
            with self.assertRaises(ValueError):rules.validate_report(value)

    def test_none_and_current_requirements_do_not_imply_a_fixed_version(self):
        self.assertEqual(rules.test_requirement({'lean':'none'},None),'RUN')
        self.assertEqual(rules.test_requirement({'lean':'current'},None),'ENVIRONMENT_REQUIRED')
        for version in ('0.0.1','0.0.2','0.0.3'):
            selected={'lean':{'version_number':version},'mathlib':{'rev':'f'*40}}
            self.assertEqual(rules.test_requirement({'lean':'current'},selected),'RUN')

    def test_exact_history_checks_the_pair_and_reports_mismatch(self):
        requirement={'lean':'exact','lean_version':'historical','mathlib_commit':'f'*40,
                     'reason':'Original immutable source receipt'}
        selected={'lean':{'version_number':'historical'},'mathlib':{'rev':'f'*40}}
        self.assertEqual(rules.test_requirement(requirement,selected),'RUN')
        for changed in (None,{'lean':{'version_number':'other'},'mathlib':{'rev':'f'*40}},
                        {'lean':{'version_number':'historical'},'mathlib':{'rev':'e'*40}}):
            self.assertEqual(rules.test_requirement(requirement,changed),'SKIPPED_VERSION_MISMATCH')

    def test_generic_tests_cannot_sneak_in_a_version_whitelist(self):
        with self.assertRaises(ValueError):
            rules.test_requirement({'lean':'current','lean_version':'fixed'},None)


if __name__=='__main__':unittest.main()
