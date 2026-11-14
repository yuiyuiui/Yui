"""Select none/current/exact requirements before test class setup runs."""
import argparse
import ast
from contextlib import ExitStack
import fnmatch
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

TESTS=Path(__file__).resolve().parent
CORE=TESTS.parent
sys.path[:0]=[str(CORE/'nl0/scripts'),str(CORE/'nl02lean/scripts')]
import local_config
rules=local_config.rules


def catalogue():
    value=json.loads((TESTS/'requirements.json').read_text())
    modules={p.stem for p in TESTS.glob('test_*.py')}
    if set(value['modules'])!=modules:
        raise ValueError('Test requirement catalogue is missing or contains stale modules: '+
                         str(sorted(modules^set(value['modules']))))
    for row in [*value['modules'].values(),*value['classes'].values(),*value['tests'].values()]:
        rules.test_requirement(row,None)
    for identifier in [*value['classes'],*value['tests']]:
        parts=identifier.split('.')
        tree=ast.parse((TESTS/(parts[0]+'.py')).read_text())
        cls=next((node for node in tree.body if isinstance(node,ast.ClassDef) and node.name==parts[1]),None)
        if cls is None or (len(parts)>2 and not any(isinstance(n,ast.FunctionDef) and n.name==parts[2] for n in cls.body)):
            raise ValueError('Stale test requirement override: '+identifier)
    return value


def requirement(identifier, data):
    if identifier in data['tests']:return data['tests'][identifier]
    owner='.'.join(identifier.split('.')[:2])
    if owner in data['classes']:return data['classes'][owner]
    module=identifier.split('.')[0]
    if module not in data['modules']:
        raise ValueError('Unclassified or failed-to-import test: '+identifier)
    return data['modules'][module]


def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--group',choices=['none','current','exact','all'],default='all')
    p.add_argument('--all',action='store_true',help='Run all applicable classes; report exact-history mismatches')
    p.add_argument('--environment',type=Path,help='Selected verified environment descriptor')
    p.add_argument('--historical-environment',type=Path,help='Explicit separate environment for exact-history tests')
    p.add_argument('--comparison-environment',type=Path,help='Optional second environment for porting checks')
    p.add_argument('--report',type=Path,default=CORE/'.runtime/test-report.json')
    p.add_argument('-v','--verbose',action='store_true')
    p.add_argument('-q','--quiet',action='store_true')
    p.add_argument('-f','--failfast',action='store_true')
    p.add_argument('-s',default=str(TESTS));p.add_argument('-p',default='test_*.py')
    p.add_argument('selectors',nargs='*')
    return p


def load_suite(args,modules):
    loader=unittest.TestLoader()
    names=[s for s in args.selectors if s!='discover']
    if names:
        return loader.loadTestsFromNames(names)
    return loader.loadTestsFromNames(sorted(name for name in modules if fnmatch.fnmatch(name+'.py',args.p)))


class VersionSkip(unittest.TestCase):
    def __init__(self,identifier,reason):
        super().__init__('runTest');self.identifier=identifier;self.reason=reason
    def id(self):return self.identifier
    def runTest(self):self.skipTest(self.reason)


class Results(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.outcomes={}
    def addSuccess(self,test):
        super().addSuccess(test);self.outcomes[test.id()]={'status':'PASS'}
    def addError(self,test,error):
        super().addError(test,error);self.outcomes[test.id()]={'status':'ERROR'}
    def addFailure(self,test,error):
        super().addFailure(test,error);self.outcomes[test.id()]={'status':'FAIL'}
    def addSkip(self,test,reason):
        super().addSkip(test,reason);self.outcomes[test.id()]={'status':'SKIP','reason':reason}
    def addSubTest(self,test,subtest,error):
        super().addSubTest(test,subtest,error)
        if error is not None:
            row=self.outcomes.setdefault(test.id(),{'status':'FAIL','subtests':[]})
            row.setdefault('subtests',[]).append(str(subtest))
    def addExpectedFailure(self,test,error):
        super().addExpectedFailure(test,error);self.outcomes[test.id()]={'status':'EXPECTED_FAILURE'}
    def addUnexpectedSuccess(self,test):
        super().addUnexpectedSuccess(test);self.outcomes[test.id()]={'status':'UNEXPECTED_SUCCESS'}


def worker(arguments):
    args=parser().parse_args(arguments);group=os.environ['YUI_TEST_GROUP']
    selected=json.loads(os.environ.get('YUI_LEAN_ENVIRONMENT','null'))
    data=catalogue()
    if selected is not None:
        from fixture_environment import prepare
        root=Path(os.environ['YUI_TEST_CLEANUP_ROOT'])/'fixtures'
        os.environ['YUI_TEST_FIXTURE_ROOT']=str(prepare(TESTS/'fixtures',root,selected))
    with ExitStack() as stack:
        if group=='none':
            import lean_environment
            import pilot_common
            import harness_support
            def forbidden(*args,**kwargs):
                raise harness_support.LiveModelAttemptBlocked('Class-A test attempted actual Lean resolution or compilation')
            for owner,name in ((lean_environment,'describe'),(lean_environment,'checked'),
                               (lean_environment,'discover'),(pilot_common,'_run_lean')):
                stack.enter_context(patch.object(owner,name,side_effect=forbidden))
        suite=load_suite(args,data['modules']);chosen=[];seen=set();decisions={}
        for test in flatten(suite):
            identifier=test.id()
            if identifier in seen:continue
            seen.add(identifier)
            req=requirement(identifier,data)
            if req['lean']!=group:continue
            decision=rules.test_requirement(req,selected);decisions[identifier]=decision
            if decision=='ENVIRONMENT_REQUIRED':
                raise ValueError('Current-environment tests require a selected Lean/Mathlib pair')
            if decision=='SKIPPED_VERSION_MISMATCH':
                reason='SKIPPED_VERSION_MISMATCH: requires '+req['lean_version']+'/'+req['mathlib_commit']
                reason+='; selected '+('none' if selected is None else
                    selected['lean']['version_number']+'/'+selected['mathlib']['rev'])
                chosen.append(VersionSkip(identifier,reason))
            else:chosen.append(test)
        runner=unittest.TextTestRunner(verbosity=2 if args.verbose else 0 if args.quiet else 1,
                                     failfast=args.failfast,resultclass=Results)
        result=runner.run(unittest.TestSuite(chosen))
        report={'group':group,'passed':result.wasSuccessful(),'tests':result.testsRun,
                'outcomes':result.outcomes,'decisions':decisions,
                'selected_environment':None if selected is None else {
                    'lean_version':selected['lean']['version_number'],'mathlib_commit':selected['mathlib']['rev']}}
        Path(os.environ['YUI_TEST_WORKER_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
        return 0 if report['passed'] else 1


def dispatch(arguments,launch):
    args=parser().parse_args(arguments);data=catalogue()
    selectors=[s for s in args.selectors if s!='discover']
    requested_modules={s.split('.')[0] for s in selectors} if selectors else {
        name for name in data['modules'] if fnmatch.fnmatch(name+'.py',args.p)}
    if args.all:args.group='all'
    if selectors:
        possible=set()
        for identifier in selectors:
            if identifier in data['tests']:
                possible.add(data['tests'][identifier]['lean']);continue
            owner='.'.join(identifier.split('.')[:2])
            base=data['classes'].get(owner,data['modules'].get(identifier.split('.')[0]))
            if base is None:raise ValueError('Unknown requested test: '+identifier)
            possible.add(base['lean'])
            for mapping in (data['classes'],data['tests']):
                possible|={row['lean'] for name,row in mapping.items() if name.startswith(identifier+'.')}
    else:
        possible={row['lean'] for name,row in data['modules'].items() if name in requested_modules}
        possible|={row['lean'] for name,row in data['classes'].items() if name.split('.')[0] in requested_modules}
        possible|={row['lean'] for name,row in data['tests'].items() if name.split('.')[0] in requested_modules}
    groups=[g for g in ('none','current','exact') if g in possible and (args.group=='all' or args.group==g)]
    report={'passed':False,'requested_groups':groups,'not_requested_groups':sorted({'none','current','exact'}-set(groups)),
            'batches':[],'scope':'Software tests; deterministic provider fixtures are not live model acceptance.'}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    def save():
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    try:
        selected=None
        if any(g!='none' for g in groups):
            import lean_environment
            selected=(lean_environment.verify(json.loads(args.environment.read_text())) if args.environment else
                      __import__('runtime_config').require_environment())
        import runtime_config
        host=runtime_config.host_tools()
        for group in groups:
            current=(__import__('lean_environment').verify(json.loads(args.historical_environment.read_text()))
                     if group=='exact' and args.historical_environment else selected)
            if group=='none':current=None
            worker_file=args.report.with_name(args.report.stem+'-'+group+'.json')
            values={'YUI_TEST_GROUP':group,'YUI_TEST_WORKER_REPORT':str(worker_file.resolve()),
                'YUI_FROZEN_LOCAL_CONFIG':'null','YUI_LEAN_ENVIRONMENT':json.dumps(current),
                'YUI_CODEX_BINARY':host['codex']['binary_path'],
                'YUI_RG_BINARY':host['tools']['ripgrep']['binary_path']}
            if current is not None:
                values.update(YUI_LEAN_ROOT=current['lean']['local_path'],YUI_MATHLIB_ROOT=current['mathlib']['local_path'])
            if args.comparison_environment:
                values['YUI_TEST_UPSTREAM_ENVIRONMENT']=str(args.comparison_environment.resolve())
                values['YUI_TEST_ALTERNATE_ENVIRONMENT']=str(args.comparison_environment.resolve())
            # Each group gets its own process and cleanup boundary; class setup cannot leak between groups.
            worker_file.unlink(missing_ok=True)
            code=launch(arguments,test_env=values)
            batch=json.loads(worker_file.read_text()) if worker_file.is_file() else {
                'group':group,'passed':False,'error':'Test worker failed before writing its report'}
            batch['exit_code']=code;batch['passed']=bool(batch.get('passed') and code==0)
            report['batches'].append(batch);save()
        report['passed']=bool(groups) and all(row['exit_code']==0 and row['passed'] for row in report['batches'])
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error)
        report['status']='ENVIRONMENT_REQUIRED_OR_TEST_SETUP_FAILED'
    save()
    print('test report: '+str(args.report.resolve()),flush=True)
    print('test groups: '+', '.join(row['group']+'='+('PASS' if row['passed'] else 'FAIL')
                                  for row in report['batches']),flush=True)
    return 0 if report['passed'] else 1
