"""Single local-adaptation coordinator; publish defaults only after real checks."""
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid

import local_config
from controller_common import CORE,bind,write
from runtime_config import use_environment,use_profiles


def parsers(commands):
    p=commands.add_parser('setup',help='Execute setup/README.md: adapt, verify or switch the local default')
    p.add_argument('--mode',choices=['nl0','lean'])
    p.add_argument('--lean-root',type=Path);p.add_argument('--mathlib-root',type=Path)
    p.add_argument('--lean-version');p.add_argument('--mathlib-version')
    p.add_argument('--install',action='store_true',help='Install the explicitly requested missing scientific environment')
    p.add_argument('--directory',type=Path)
    p.add_argument('--codex-binary',type=Path);p.add_argument('--auth-home',type=Path)
    p.add_argument('--rg-binary',type=Path);p.add_argument('--profiles-file',type=Path)
    p.add_argument('--skill-root',type=Path)
    p.add_argument('--lean-library',action='append',type=Path,default=[])
    p.add_argument('--no-libraries',action='store_true',help='Explicitly remove optional libraries from the new default')
    p.add_argument('--library-source',type=Path);p.add_argument('--library-build',type=Path)
    p.add_argument('--library-name');p.add_argument('--library-import',action='append',default=[])
    p.add_argument('--bootstrap',action='store_true',help='Create the local venv and install declared Python dependencies')


@contextmanager
def environment(values):
    """Scope explicit setup choices without changing the operator's shell."""
    old={key:os.environ.get(key) for key in values}
    try:
        for key,value in values.items():
            if value is not None:os.environ[key]=str(value)
        yield
    finally:
        for key,value in old.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value


def bootstrap():
    if sys.version_info<(3,11):
        raise local_config.rules.SetupRequired('Install Python 3.11 or newer before setup')
    target=CORE/'.venv'
    if target.is_symlink():
        raise ValueError('Refuse a symlinked Python environment')
    if target.exists() and any(target.iterdir()) and not (target/'pyvenv.cfg').is_file():
        raise local_config.rules.SetupRequired('Preserve the existing .venv directory; choose a real Python environment')
    if not (target/'bin/python').is_file():
        subprocess.run([sys.executable,'-m','venv',str(target)],check=True)
    subprocess.run([str(target/'bin/python'),'-m','pip','install','-r',str(CORE/'workflow/requirements.txt'),
                    'pypdf'],check=True)
    return {'status':'BOOTSTRAPPED','python':str(target/'bin/python'),
            'next':'Continue setup/README.md with this interpreter; bootstrap alone is not READY'}


def register_skill(requested=None):
    import yaml
    text=(CORE/'SKILL.md').read_text()
    if not text.startswith('---\n'):
        raise ValueError('The skill entry is missing its metadata')
    metadata=yaml.safe_load(text.split('---',2)[1])
    if not isinstance(metadata,dict) or metadata.get('name')!='rigorous-proof' or not metadata.get('description'):
        raise ValueError('The skill entry must identify rigorous-proof')
    choices=[Path(requested).expanduser()] if requested else [
        Path.home()/'.codex/skills/rigorous-proof',Path.home()/'.agents/skills/rigorous-proof']
    for path in choices:
        if (path.exists() or path.is_symlink()) and path.resolve()==CORE.resolve():
            if not (path/'SKILL.md').is_file():raise ValueError('Registered skill has no entry')
            return path
    destination=choices[0]
    if destination.exists() or destination.is_symlink():
        raise local_config.rules.SetupRequired('A different rigorous-proof skill already exists; preserve it',
                                               [{'kind':'choose_skill_location','path':str(destination)}])
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.symlink_to(CORE.resolve(),target_is_directory=True)
    return destination


def host_check(directory):
    import runtime_config
    from setup_checks import record,source_readers
    if sys.platform!='darwin' or not Path('/usr/bin/sandbox-exec').is_file():
        raise local_config.rules.SetupRequired('Current native isolation supports macOS only')
    if sys.version_info<(3,11):
        raise local_config.rules.SetupRequired('Python 3.11 or newer is required')
    missing=[name for name in ('git',) if not shutil.which(name)]
    if not shutil.which('pdftotext') and importlib.util.find_spec('pypdf') is None:
        missing.append('pdftotext or pypdf')
    if any(importlib.util.find_spec(name) is None for name in ('jsonschema','yaml')):
        missing.append('workflow/requirements.txt')
    if missing:
        raise local_config.rules.SetupRequired('Missing local dependencies: '+', '.join(missing),
                                               [{'kind':'bootstrap','entry':'setup/README.md'}])
    host=runtime_config.host_tools()
    import native_runtime
    native_runtime.verify(host['codex'])
    subprocess.run([host['codex']['code_mode_host']['path'],'--help'],
                   capture_output=True,text=True,timeout=20,check=True)
    subprocess.run([host['tools']['ripgrep']['binary_path'],'--version'],
                   capture_output=True,text=True,timeout=20,check=True)
    auth=runtime_config.auth_home()
    if not (auth/'auth.json').is_file():
        raise local_config.rules.SetupRequired('Log into the selected Codex installation, then repeat setup',
                                               [{'kind':'login','binary':host['codex']['binary_path']}])
    binding={'codex':host['codex'],'ripgrep':{'path':host['tools']['ripgrep']['binary_path'],
        'sha256':host['tools']['ripgrep']['sha256']},'python':str(Path(sys.executable).absolute()),
        'auth_home':str(auth)}
    readers=source_readers(directory)
    return binding,record(directory,'host',{'host':binding,'platform':sys.platform,'source_readers':readers,
                'python_version':list(sys.version_info[:3]),'credentials_copied':False})


def select_environment(args,previous):
    if args.mode=='nl0':
        if args.lean_library or args.library_source:
            raise ValueError('External Lean libraries require Lean setup')
        return None
    import lean_environment as environments
    explicit=any(getattr(args,key,None) for key in ('lean_root','mathlib_root','lean_version','mathlib_version'))
    if not explicit and previous and previous['lean_environment'] is not None:
        return environments.verify(previous['lean_environment'])
    try:
        return environments.resolve(lean_root=args.lean_root,mathlib_root=args.mathlib_root,
            lean_version=args.lean_version,mathlib_ref=args.mathlib_version)
    except environments.SelectionRequired:
        if not args.install or not args.mathlib_version or args.lean_root or args.mathlib_root:raise
        return environments.install(lean_version=args.lean_version,mathlib_ref=args.mathlib_version,
                                    directory=args.directory)


def run(args):
    """Run actual checks in a provisional scope; failed switches keep the old default."""
    if args.bootstrap:return bootstrap()
    storage=CORE/'.runtime'
    if storage.is_symlink():raise ValueError('Local setup storage must not be a symlink')
    storage.mkdir(exist_ok=True)
    evidence=storage/'setup-evidence'
    if evidence.is_symlink():raise ValueError('Setup evidence must stay inside the installation')
    evidence.mkdir(exist_ok=True)
    attempt=evidence/uuid.uuid4().hex;attempt.mkdir()
    report={'status':'FAILED','entry':'setup/README.md','attempt':str(attempt),
            'configuration_published':False,'mode':args.mode or 'lean'}
    try:
        try:previous=local_config.current()
        except (ValueError,OSError,KeyError):previous=None
        args.mode=args.mode or (previous['mode'] if previous else 'lean')
        report['mode']=args.mode
        defaults=json.loads((CORE/'config.json').read_text())
        profiles=(json.loads(args.profiles_file.read_text()) if args.profiles_file else
                  previous['profiles'] if previous else
                  {'nl0':defaults['model'],'lean':defaults['phase_models']['nl0_to_lean']})
        import runtime_config
        profiles={key:runtime_config.validate_profile(value) for key,value in profiles.items()}
        if set(profiles)!={'nl0','lean'}:raise ValueError('Select both model profile slots')
        host_defaults=previous['host'] if previous else {}
        choices={'YUI_CODEX_BINARY':args.codex_binary or host_defaults.get('codex',{}).get('binary_path'),
                 'YUI_RG_BINARY':args.rg_binary or host_defaults.get('ripgrep',{}).get('path'),
                 'YUI_CODEX_HOME':args.auth_home or host_defaults.get('auth_home')}
        import setup_checks
        with local_config.use(None),use_environment(None),environment(choices):
            host,host_result=host_check(attempt)
            selected=select_environment(args,previous)
        skill=register_skill(args.skill_root)
        checks={'host':host_result,'skill':setup_checks.record(attempt,'skill',
            {'path':str(skill),'root':str(CORE),'entry':bind(CORE/'SKILL.md')})}
        candidate={'version':local_config.rules.VERSION,'root':str(CORE.resolve()),'mode':args.mode,
            'host':host,'profiles':profiles,'lean_environment':selected,'libraries':[],
            'checks':checks,'created_at':datetime.now(timezone.utc).isoformat(),
            'implementation':{str(path.relative_to(CORE)):bind(path)['sha256']
                for folder in ('nl0/scripts','nl02lean/scripts','workflow/blocks')
                for path in sorted((CORE/folder).glob('*')) if path.suffix in {'.py','.lean'}}}
        with local_config.use(candidate,provisional=True),use_environment(selected),use_profiles(profiles):
            checks['provider']=setup_checks.provider(attempt,profiles if args.mode=='lean' else {'nl0':profiles['nl0']})
            if selected is not None:
                checks.update(setup_checks.native(attempt,selected))
            specifications=list(args.lean_library)
            if args.no_libraries and any((specifications,args.library_source,args.library_build,args.library_name,args.library_import)):
                raise ValueError('Do not combine --no-libraries with requested libraries')
            explicit_libraries=bool(specifications or args.library_source)
            if not args.no_libraries and not explicit_libraries and previous and args.mode=='lean':
                specifications=[Path(row['specification']['path']) for row in previous['libraries']]
            if any((args.library_source,args.library_build,args.library_name,args.library_import)):
                if not all((args.library_source,args.library_build,args.library_name,args.library_import)):
                    raise local_config.rules.SetupRequired('Specify the external source/build roots, namespace and entry imports')
                specifications.append(setup_checks.library_specification(args.library_source,args.library_build,
                    args.library_name,args.library_import,attempt/'library-specification.json',
                    allowed_external=[json.loads(Path(spec).read_text())['name'] for spec in specifications]))
            qualified=[]
            for number,specification in enumerate(specifications,1):
                data=json.loads(Path(specification).read_text());name=data['name']
                if any(row['name']==name for row in candidate['libraries']):
                    raise ValueError('Repeated external library name')
                checked=setup_checks.external_library(attempt/('library-'+str(number)),specification,selected,profiles,
                                                      attachments=qualified)
                # Configuration retains an owned immutable specification, not a mutable user pointer.
                captured=attempt/(name+'-specification.json');write(captured,data)
                candidate['libraries'].append({'name':name,'specification':bind(captured)})
                checks['library:'+name]=checked
                qualified.append(specification)
            local_config.verify(candidate)
        write(local_config.path(),candidate)
        report.update(status='READY',configuration_published=True,configuration=bind(local_config.path()),
            capabilities={'mode':args.mode,'libraries':[row['name'] for row in candidate['libraries']]},
            lean_environment=selected,skill=str(skill),checks=checks,
            next='Use $rigorous-proof on your proof; frozen jobs keep their own environment.')
    except local_config.rules.SetupRequired as error:
        report.update(error.request)
    except Exception as error:
        import lean_environment
        if isinstance(error,lean_environment.SelectionRequired):
            report.update(status='NEEDS_USER_ACTION',reason=error.request['reason'],selection=error.request)
        else:
            # Do not serialize raw authentication or subprocess arguments.
            report.update(status='FAILED',error=type(error).__name__+': '+str(error)[:4000])
    local_config.rules.validate_report(report)
    for path in (attempt/'report.json',storage/'setup-report.json'):
        try:write(path,report)
        except OSError as error:
            # Qualification/publication status stays truthful even if a later log write fails.
            report.setdefault('report_persistence_errors',[]).append({
                'path':str(path),'error':type(error).__name__})
    return report
