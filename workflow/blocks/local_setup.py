"""Small shared readiness rules; setup must qualify actual consuming paths."""
from pathlib import PurePath
import re

VERSION = 'yui-local-config-1'
RUN_VERSION = 'yui-run-environment-1'
BASE_CHECKS = {'host', 'provider', 'skill'}
LEAN_CHECKS = {'environment', 'mathlib_query', 'core_inspector', 'basis_export', 'negative_proof'}
SHA = re.compile(r'[0-9a-f]{64}')
REPORT_SCHEMA = {
    'type':'object',
    'properties':{'status':{'enum':['READY','NEEDS_USER_ACTION','FAILED']},
        'entry':{'const':'setup/README.md'},'configuration_published':{'type':'boolean'},
        'mode':{'enum':['nl0','lean']},'attempt':{'type':'string','minLength':1},
        'configuration':{'type':'object','properties':{'path':{'type':'string','minLength':1},
                         'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'}},
                         'required':['path','sha256'],'additionalProperties':False},
        'capabilities':{'type':'object','properties':{'mode':{'enum':['nl0','lean']},
                        'libraries':{'type':'array','items':{'type':'string'}}},
                        'required':['mode','libraries'],'additionalProperties':False},
        'checks':{'type':'object'}},
    'required':['status','entry','configuration_published','mode','attempt'],
    'oneOf':[{'properties':{'status':{'const':'READY'},'configuration_published':{'const':True}},
              'required':['configuration','capabilities','checks']},
             {'properties':{'status':{'enum':['NEEDS_USER_ACTION','FAILED']},
                            'configuration_published':{'const':False}}}],
    'additionalProperties':True}


class SetupRequired(ValueError):
    def __init__(self, reason, actions=()):
        self.request = {'status': 'NEEDS_USER_ACTION', 'reason': str(reason),
                        'actions': list(actions), 'entry': 'setup/README.md'}
        super().__init__(str(reason))


def binding(value):
    if (not isinstance(value, dict) or set(value) != {'path', 'sha256'}
            or not isinstance(value['path'], str) or not PurePath(value['path']).is_absolute()
            or not isinstance(value['sha256'], str) or not SHA.fullmatch(value['sha256'])):
        raise ValueError('Invalid setup evidence binding')


def validate_host(value):
    if not isinstance(value, dict) or set(value) != {'codex', 'ripgrep', 'python', 'auth_home'}:
        raise ValueError('Invalid local host configuration')
    for key in ('auth_home', 'python'):
        if not isinstance(value[key], str) or not PurePath(value[key]).is_absolute():
            raise ValueError('Local host paths must be absolute')
    binding(value['ripgrep'])
    native = value['codex']
    if (not isinstance(native, dict) or not isinstance(native.get('binary_path'), str)
            or not PurePath(native['binary_path']).is_absolute()
            or not SHA.fullmatch(native.get('sha256', '')) or not native.get('version')):
        raise ValueError('Invalid selected native carrier')
    binding(native['code_mode_host'])
    if native.get('package_manifest') is not None:
        binding(native['package_manifest'])
    return value


def required_checks(mode, libraries):
    if mode not in {'nl0', 'lean'}:
        raise ValueError('Unknown local setup capability')
    return BASE_CHECKS | (LEAN_CHECKS if mode == 'lean' else set()) | {
        'library:' + name for name in libraries}


def validate_runtime(value):
    if (not isinstance(value,dict) or set(value)!={'version','host','profiles','lean_environment'}
            or value['version']!=RUN_VERSION):
        raise ValueError('Invalid frozen run environment')
    validate_host(value['host'])
    if set(value['profiles'])!={'nl0','lean'}:
        raise ValueError('Frozen run profiles are incomplete')
    return value


def validate_config(value):
    fields = {'version', 'root', 'mode', 'host', 'profiles', 'lean_environment',
              'libraries', 'checks', 'created_at', 'implementation'}
    if not isinstance(value, dict) or set(value) != fields or value['version'] != VERSION:
        raise ValueError('Unsupported local setup configuration')
    if not isinstance(value['root'], str) or not PurePath(value['root']).is_absolute():
        raise ValueError('Invalid local installation root')
    validate_host(value['host'])
    implementation=value['implementation']
    if (not isinstance(implementation,dict) or not implementation
            or any(not isinstance(name,str) or PurePath(name).is_absolute() or '..' in PurePath(name).parts
                   or not isinstance(sha,str) or not SHA.fullmatch(sha) for name,sha in implementation.items())):
        raise ValueError('Setup must bind the qualified implementation')
    if not isinstance(value['profiles'], dict) or set(value['profiles']) != {'nl0', 'lean'}:
        raise ValueError('Setup must select both phase profile slots')
    for profile in value['profiles'].values():
        if (set(profile) != {'id', 'reasoning_effort', 'speed', 'automatic_fallback'}
                or not isinstance(profile['id'], str) or not profile['id'].strip()
                or profile['speed'] != 'standard' or profile['automatic_fallback'] is not False
                or profile['reasoning_effort'] not in {
                    'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'}):
            raise ValueError('Invalid setup model selection')
    if (value['mode'] == 'lean') != (value['lean_environment'] is not None):
        raise ValueError('Setup scientific capability and environment disagree')
    libraries = value['libraries']
    if not isinstance(libraries, list) or (libraries and value['mode'] != 'lean'):
        raise ValueError('External Lean libraries require Lean setup')
    names = []
    for row in libraries:
        if set(row) != {'name', 'specification'} or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', row['name']):
            raise ValueError('Invalid configured external library')
        names.append(row['name'])
        binding(row['specification'])
    if len(names) != len(set(names)):
        raise ValueError('Repeated configured library')
    checks = value['checks']
    if not isinstance(checks, dict) or set(checks) != required_checks(value['mode'], names):
        raise ValueError('Required consuming-path qualification is missing')
    for row in checks.values():
        if (not isinstance(row, dict) or set(row) != {'passed', 'execution', 'evidence'}
                or row['passed'] is not True or row['execution'] != 'actual'
                or not isinstance(row['evidence'], list) or not row['evidence']):
            raise ValueError('Only actual successful checks can publish READY')
        for item in row['evidence']:
            binding(item)
    if not isinstance(value['created_at'], str) or not value['created_at']:
        raise ValueError('Missing setup completion time')
    return value


def validate_report(report):
    if report.get('status') not in {'READY','NEEDS_USER_ACTION','FAILED'}:
        raise ValueError('Unknown setup result')
    if report['status']=='READY':
        if report.get('configuration_published') is not True:
            raise ValueError('READY requires a published verified configuration')
        binding(report['configuration'])
        scope=report['capabilities']
        if report['mode']!=scope['mode']:
            raise ValueError('Setup readiness scope differs from the request')
        if set(report['checks'])!=required_checks(scope['mode'],scope['libraries']):
            raise ValueError('READY omitted required consumer checks')
        for row in report['checks'].values():
            if row.get('passed') is not True or row.get('execution')!='actual' or not row.get('evidence'):
                raise ValueError('READY cannot be based on an absent or simulated check')
    elif report.get('configuration_published') is not False:
        raise ValueError('Failed/incomplete setup cannot publish a new default')
    return report


def test_requirement(requirement, selected):
    """Decide selection before unittest class initialization, not after failure."""
    kind = requirement.get('lean')
    if kind not in {'none', 'current', 'exact'}:
        raise ValueError('A test must declare none/current/exact Lean requirements')
    if kind == 'exact':
        if set(requirement) != {'lean', 'lean_version', 'mathlib_commit', 'reason'}:
            raise ValueError('An exact test must state its historical pair and purpose')
        if not requirement['reason']:
            raise ValueError('Historical tests need an independent purpose')
        matches = selected is not None and (
            selected['lean']['version_number'] == requirement['lean_version']
            and selected['mathlib']['rev'] == requirement['mathlib_commit'])
        return 'RUN' if matches else 'SKIPPED_VERSION_MISMATCH'
    if set(requirement) != {'lean'}:
        raise ValueError('Generic tests must not declare a version restriction')
    return 'RUN' if kind == 'none' or selected is not None else 'ENVIRONMENT_REQUIRED'
