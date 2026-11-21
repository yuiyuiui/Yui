"""Build a retained public Lean module and its same-repository dependencies."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from controller_common import bind, write
from execution_state import current, capture_process, terminate_owned, ProcessIdentityUnconfirmed
import lean_libraries
import native_workspace
from pilot_common import lean_paths, native_succeeded, run_lean

VERSION = 'yui-public-lean-build-1'
COMPANIONS = ('.olean.private','.olean.server','.ir','.ir.sig')
SOURCE = re.compile(r'https://raw\.githubusercontent\.com/([\w.-]+)/([\w.-]+)/([0-9a-f]{40})/([A-Za-z0-9_/]+)\.lean')


def known_source(logs, selection):
    """Anchor a checkout to the verified public-source tool result, not prose."""
    evidence = selection.get('evidence')
    if evidence is None:return None
    for path in sorted((logs/'external-sources').glob('access-*.json')):
        row=json.loads(path.read_bytes())
        if not isinstance(row.get('document'),dict) or row['document'].get('sha256') != evidence['sha256']:
            continue
        match=SOURCE.fullmatch(row.get('final_url') or row.get('url',''))
        if row.get('status')=='READABLE' and match:
            owner, project, commit, module_path=match.groups()
            if owner in {'.','..'} or project in {'.','..'} or any(not x for x in module_path.split('/')):
                continue
            return {'repository':f'https://github.com/{owner}/{project}.git', 'revision':commit,
                    'module': module_path.replace('/','.'), 'source_sha256':evidence['sha256']}
    return None


class BuildFailure(ValueError):
    def __init__(self, status, diagnostic):
        super().__init__(diagnostic)
        self.status=status


def git(work, cwd, arguments, deadline):
    """Fixed Git commands in an owned directory, with no ambient credentials."""
    recorder, task = current()
    env={'PATH':'/usr/bin:/bin','HOME':str(work/'home'),'GIT_CONFIG_NOSYSTEM':'1',
         'GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0'}
    cmd=['/usr/bin/git','-c','core.hooksPath=/dev/null','-c','protocol.file.allow=never',*arguments]
    process=subprocess.Popen(cmd,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,text=True,start_new_session=True)
    owner={'pid':process.pid,'pgid':process.pid,'started':None}
    native_workspace.record(work,confirmed=False,phase='public-source-fetch',process=owner)
    try:
        try:
            owner=(recorder.register_process(process,'public-lean-fetch',task,private_group=True)
                   if recorder else capture_process(process,private_group=True))
        except ProcessIdentityUnconfirmed:
            if process.poll() is None:
                raise native_workspace.unconfirmed('Public Lean Git process identity could not be confirmed',work)
        while True:
            if recorder:recorder.check(task)
            if time.monotonic()>=deadline:
                raise BuildFailure('PUBLIC_SOURCE_FETCH_FAILED','Pinned public Git operation reached its time limit.')
            try: stdout,stderr=process.communicate(timeout=.2)
            except subprocess.TimeoutExpired:continue
            if process.returncode:
                raise BuildFailure('PUBLIC_SOURCE_FETCH_FAILED',stderr[-4000:])
            return stdout.strip()
    finally:
        confirmed=terminate_owned(process,owner)
        native_workspace.record(work,confirmed=confirmed,phase='public-source-fetch-exit',process=owner,exit_code=process.returncode)
        if not confirmed:raise native_workspace.unconfirmed('Public Lean Git cleanup could not be confirmed',work)


def checkout(work, repository, revision, deadline):
    root=work/'checkout';root.mkdir();(work/'home').mkdir()
    git(work,root,['init','--template='],deadline)
    git(work,root,['fetch','--depth=1','--no-tags',repository,revision],deadline)
    git(work,root,['checkout','--detach','FETCH_HEAD'],deadline)
    if git(work,root,['rev-parse','HEAD'],deadline)!=revision:
        raise BuildFailure('PUBLIC_SOURCE_FETCH_FAILED','Checkout differs from the declared public revision.')
    return root


def scope(checkout_root, entry):
    """Read the original closure in producer order. Other packages must be bound."""
    from lean_imports import code_tokens, preamble
    from runtime_config import load_lock
    namespace=entry.partition('.')[0]
    done={};active=set();available=[*lean_paths(()),Path(load_lock()['lean']['local_path'])/'lib/lean']
    def visit(module):
        if module in done:return
        if module in active:raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Cycle at import '+module)
        if not lean_libraries.MODULE.fullmatch(module):
            raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Unsupported module name '+module)
        relative=Path(*module.split('.'))
        if module.partition('.')[0]!=namespace:
            if any((Path(root)/relative.with_suffix('.olean')).is_file() for root in available):return
            raise BuildFailure('PUBLIC_LEAN_DEPENDENCY_REQUIRED','Bind the pinned public source for import '+module)
        path=checkout_root/relative.with_suffix('.lean')
        if path.resolve()!=path or not path.is_file():
            raise BuildFailure('PUBLIC_LEAN_DEPENDENCY_REQUIRED','Missing source at the pinned revision for '+module)
        text=path.read_text(); header=preamble(text)
        if header is None or re.search(r'\b(sorry|admit|axiom)\b',code_tokens(text)):
            raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Source policy or import header failed for '+module)
        active.add(module)
        for line in code_tokens(header).splitlines():
            match=re.fullmatch(r'\s*(?:(?:public|private|meta)\s+)*import\s+(.+)',line)
            if match:
                for dependency in match[1].split():visit(dependency)
        active.remove(module);done[module]=path
    visit(entry)
    return namespace,done


def build(origin, directory, environment, *, timeout):
    """Use the installed sandboxed compiler. Keep enough evidence for replay and porting."""
    from runtime_config import use_environment
    import lean_environment
    directory.mkdir(parents=True)
    deadline=time.monotonic()+timeout
    entry=origin['module'];checks={};bindings=[]
    try:
        with use_environment(environment),native_workspace.temporary('yui-public-lean-',logs=directory) as work:
            root=checkout(work,origin['repository'],origin['revision'],min(deadline,time.monotonic()+60))
            namespace, sources=scope(root,entry)
            if hashlib.sha256(sources[entry].read_bytes()).hexdigest()!=origin['source_sha256']:
                raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Pinned module bytes differ from the retained source.')
            output=work/'output'; output.mkdir(); (work/'input').mkdir()
            source_root=directory/'source';build_root=directory/'build'
            rows=[]
            for module, path in sources.items():
                remaining=deadline-time.monotonic()
                if remaining<=0:raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Build time elapsed before '+module)
                relative=Path(*module.split('.'));source=output/relative.with_suffix('.lean')
                source.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,source)
                compiled=source.with_suffix('.olean')
                result=run_lean(source,work,extra=[output],output=compiled,timeout=remaining,module_root=output)
                log=directory/(module+'.json');write(log,result);checks[module]=bind(log)
                native_log=result.get('stdout','')+'\n'+result.get('stderr','')
                if not native_succeeded(result) or not compiled.is_file() or re.search(r"declaration uses ['‘]sorry['’]",native_log):
                    raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED',module+': '+(result.get('stdout','')+'\n'+result.get('stderr',''))[-5000:])
                dest=source_root/relative.with_suffix('.lean');dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,dest);source_ref=bind(dest);bindings.append(source_ref);artifacts={}
                for suffix in ('.olean',*COMPANIONS):
                    path=Path(str(compiled.with_suffix(''))+suffix)
                    if not path.is_file():continue
                    dest=build_root/(str(relative)+suffix);dest.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(path,dest);ref=bind(dest);bindings.append(ref);artifacts[suffix]=ref['sha256']
                rows.append({'module':module,'source_sha256':source_ref['sha256'],
                    'olean_sha256':artifacts.pop('.olean'),**({'companions':artifacts} if artifacts else {})})
            selected=lean_environment.identity(environment)
            spec={'version':lean_libraries.VERSION,'name':namespace,'lean_version':selected['lean_version'],
                'mathlib_commit':selected['mathlib_commit'],'source_root':str(source_root),'build_root':str(build_root),
                'imports':[entry],'modules':rows}
            write(directory/'library.json',spec)
            status='PUBLIC_LEAN_READY'; detail='Pinned public module compiled with the selected compiler.'
    except BuildFailure as error:
        status,detail=error.status,str(error)
    result={'version':VERSION,'status':status,'diagnostic':detail,'origin':origin,
            'environment':lean_environment.identity(environment),'checks':checks,'bindings':bindings}
    if status=='PUBLIC_LEAN_READY':result['specification']=bind(directory/'library.json')
    path=directory/'result.json';write(path,result)
    return {**result,'receipt':bind(path)}


def qualify(check, metadata, *, full=False):
    """Check the selected source/olean inventory against actual native builds."""
    import lean_environment
    from runtime_config import require_environment
    if check['status']!='PUBLIC_LEAN_READY' or check['environment']!=lean_environment.identity(require_environment()):
        raise ValueError('Public Lean library has no successful check in the selected environment')
    for ref in [check['specification'],*check['bindings'],*check['checks'].values()]:
        lean_libraries._verify_file(Path(ref['path']),ref['sha256'],full)
    spec=json.loads(Path(check['specification']['path']).read_text())
    if any(spec[key]!=metadata[key] for key in ('name','imports','modules','lean_version','mathlib_commit')):
        raise ValueError('Public Lean library manifest differs from the checked source/olean inventory')
    if set(check['checks'])!={row['module'] for row in spec['modules']} or any(
            not native_succeeded(json.loads(Path(ref['path']).read_text())) for ref in check['checks'].values()):
        raise ValueError('Public Lean library has incomplete native coverage')
