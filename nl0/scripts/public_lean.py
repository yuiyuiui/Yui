"""Build a retained public Lean module from its pinned package source root."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
import urllib.request

from controller_common import bind, write
from execution_state import current, capture_process, terminate_owned
import lean_libraries
import lean_patches
import lean_ports
import native_workspace
from pilot_common import lean_paths, native_succeeded, run_lean
from staging_storage import copy_input

VERSION = 'yui-public-lean-build-1'
COMPANIONS = ('.olean.private','.olean.server','.ir','.ir.sig')
SOURCE = re.compile(r'https://raw\.githubusercontent\.com/([\w.-]+)/([\w.-]+)/([0-9a-f]{40})/([A-Za-z0-9_./-]+)')


def raw_pin(url, suffix='.lean'):
    match=SOURCE.fullmatch(url)
    if not match:return None
    owner,project,commit,path=match.groups()
    if not path.endswith(suffix) or any(part in {'','.','..'} for part in (owner,project,*path.split('/'))):
        return None
    return {'repository':f'https://github.com/{owner}/{project}.git','revision':commit,'source_path':path}


def source_origin(row, external):
    origin=raw_pin(row.get('final_url') or row.get('url',''))
    if row.get('status')!='READABLE' or origin is None:return None
    document=row['document'];path=Path(document['path'])
    if path.resolve()!=path or not path.is_relative_to(external.resolve()):
        raise ValueError('Retained public source escapes this stage')
    lean_libraries._verify_file(path,document['sha256'],False)
    origin['source_sha256']=document['sha256']
    if 'patched_origin' in row:
        patched=row['patched_origin']
        authority=Path(patched['patch_authority']['path'])
        if (any(patched.get(k)!=v for k,v in origin.items()) or not authority.resolve().is_relative_to(external.resolve())):
            raise ValueError('Patched public source does not bind this pinned source and recipe')
        lean_patches.verify_origin(patched)
        origin=patched
    return origin


def known_source(logs, selection):
    """Anchor a checkout to the verified public-source tool result, not prose."""
    evidence = selection.get('evidence')
    if evidence is None:return None
    external=logs/'external-sources'
    for path in sorted(external.glob('access-*.json')):
        row=json.loads(path.read_bytes())
        document = row.get('document')
        if (not isinstance(document,dict) or document.get('sha256') != evidence['sha256']
                or Path(document.get('path','')).name != Path(evidence['path']).name):
            continue
        origin=source_origin(row,external)
        if origin is not None:return origin
    return None


def known_dependency(logs, module):
    """Use an unambiguous fixed source retained by this author's own source tool."""
    external=logs/'external-sources'
    suffix=Path(*module.split('.')).with_suffix('.lean').parts
    origins={}
    for path in sorted(external.glob('access-*.json')):
        row=json.loads(path.read_bytes())
        pin=raw_pin(row.get('final_url') or row.get('url',''))
        if pin is None or Path(pin['source_path']).parts[-len(suffix):]!=suffix:continue
        origin=source_origin(row,external)
        if origin is None:continue
        key=(origin['repository'],origin['revision'],origin['source_path'],origin['source_sha256'],
             tuple(origin.get('patch_order',[])))
        origins[key]=origin
    return next(iter(origins.values())) if len(origins)==1 else None


class BuildFailure(ValueError):
    def __init__(self, status, diagnostic, *, bound=None, missing_module=None):
        super().__init__(diagnostic)
        self.status=status
        self.bound=bound
        self.missing_module=missing_module


def git(work, cwd, arguments, deadline):
    """Fixed Git commands in an owned directory, with no ambient credentials."""
    recorder, task = current()
    env={'PATH':'/usr/bin:/bin','HOME':str(work/'home'),'GIT_CONFIG_NOSYSTEM':'1',
         'GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0'}
    proxy=urllib.request.getproxies().get('https')
    if proxy and not urllib.request.proxy_bypass('github.com'):
        env['https_proxy']=proxy
    cmd=['/usr/bin/git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',
         '-c','protocol.file.allow=never',*arguments]
    if arguments==['rev-parse','HEAD']:
        if recorder:recorder.check(task)
        remaining=deadline-time.monotonic()
        try:
            if remaining<=0:raise subprocess.TimeoutExpired(cmd,0)
            result=subprocess.run(cmd,cwd=cwd,env=env,stdin=subprocess.DEVNULL,capture_output=True,
                                  text=True,timeout=min(remaining,5))
        except subprocess.TimeoutExpired as error:
            raise BuildFailure('PUBLIC_SOURCE_FETCH_FAILED','Pinned local Git HEAD read reached its time limit.') from error
        if recorder:recorder.check(task)
        if result.returncode:raise BuildFailure('PUBLIC_SOURCE_FETCH_FAILED',result.stderr[-4000:])
        return result.stdout.strip()
    process=subprocess.Popen(cmd,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,text=True,start_new_session=True)
    owner={'pid':process.pid,'pgid':process.pid,'started':None}
    native_workspace.record(work,confirmed=False,phase='public-source-fetch',process=owner)
    try:
        owner=(recorder.register_process(process,'public-lean-fetch',task,private_group=True)
               if recorder else capture_process(process,private_group=True))
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
    root=work/'checkout';root.mkdir();(work/'home').mkdir(exist_ok=True)
    git(work,root,['init','--template='],deadline)
    git(work,root,['remote','add','origin',repository],deadline)
    git(work,root,['sparse-checkout','set','--no-cone','lakefile.lean','lakefile.toml'],deadline)
    fetch=['fetch','--depth=1','--no-tags','--filter=blob:none','origin',revision]
    try:
        git(work,root,fetch,min(deadline,time.monotonic()+60))
    except BuildFailure:
        if time.monotonic()>=deadline:raise
        git(work,root,fetch,min(deadline,time.monotonic()+120))
    git(work,root,['checkout','--detach','FETCH_HEAD'],min(deadline,time.monotonic()+120))
    if git(work,root,['rev-parse','HEAD'],deadline)!=revision:
        raise BuildFailure('PUBLIC_SOURCE_FETCH_FAILED','Checkout differs from the declared public revision.')
    return root


@contextmanager
def cached_checkout(work, origin, cache, deadline):
    repository, revision = origin['repository'], origin['revision']
    if cache is None:
        yield checkout(work,repository,revision,deadline)
        return
    cache.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(f'{repository}\n{revision}'.encode()).hexdigest()
    destination=cache/key
    with (cache/(key+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if destination.exists() or destination.is_symlink():
            (work/'home').mkdir(exist_ok=True)
            if (destination.resolve()!=destination or (destination/'.git').is_symlink()
                    or not (destination/'.git').is_dir()
                    or git(work,destination,['rev-parse','HEAD'],deadline)!=revision
                    or git(work,destination,['status','--porcelain','--untracked-files=all','--ignored'],deadline)):
                raise BuildFailure('PUBLIC_SOURCE_FETCH_FAILED','The retained pinned checkout changed.')
        else:
            source=checkout(work,repository,revision,deadline)
            with tempfile.TemporaryDirectory(prefix='incoming-',dir=cache) as temp:
                incoming=Path(temp)/'checkout'
                shutil.move(str(source),incoming)
                incoming.rename(destination)
        yield destination


def materialize(work, root, paths, deadline):
    """Hydrate only these exact paths from the shallow checkout's pinned tree."""
    missing=['/'+str(path.relative_to(root)) for path in paths if not path.is_file()]
    if missing:
        git(work,root,['sparse-checkout','add','--',*missing],min(deadline,time.monotonic()+120))


def module_at(path, root):
    if not path.is_relative_to(root):return None
    parts=path.relative_to(root).with_suffix('').parts
    name='.'.join(parts)
    if all('.' not in part for part in parts) and lean_libraries.MODULE.fullmatch(name):return name
    return None


def package_roots(package):
    """Read static source-root declarations without loading an upstream Lake program."""
    from lean_imports import code_tokens
    toml, lean = package/'lakefile.toml', package/'lakefile.lean'
    if toml.is_file() and not toml.is_symlink():
        try:
            config=tomllib.loads(toml.read_text())
            root=package/config.get('srcDir','.')
            return [(root/lib.get('srcDir','.'),lib['name']) for lib in config.get('lean_lib',[])]
        except (KeyError,TypeError,ValueError,OSError) as error:
            raise BuildFailure('PUBLIC_LEAN_LAYOUT_REQUIRED','Cannot read declared source roots in '+str(toml.name)) from error
    if lean.is_file() and not lean.is_symlink():
        text=code_tokens(lean.read_text())
        if re.search(r'\bsrcDir\b',text):return []
        return [(package,name) for name in re.findall(r'\blean_lib\s+([A-Za-z][\w.]*)',text)]
    return None


def source_layout(checkout_root, origin):
    """Resolve the Git path and the Lean module as separate identities."""
    path=checkout_root/origin['source_path']
    if not path.is_relative_to(checkout_root) or path.resolve()!=path or not path.is_file():
        raise BuildFailure('PUBLIC_LEAN_LAYOUT_REQUIRED','Missing or redirected pinned source '+origin['source_path'])
    expected=origin.get('expected_module')
    declared=None
    for package in path.parents:
        if not package.is_relative_to(checkout_root):break
        declared=package_roots(package)
        if declared is None:continue
        candidates=set()
        for root, name in declared:
            relative=root.resolve()
            if not relative.is_relative_to(package) or not path.is_relative_to(relative):continue
            module=module_at(path,relative)
            if module and module.split('.')[0]==name.split('.')[0]:candidates.add((relative,module))
        if len(candidates)==1:
            root,module=candidates.pop()
            if expected is not None and expected!=module:
                raise BuildFailure('PUBLIC_LEAN_LAYOUT_REQUIRED','The declared module is '+module+', not '+expected)
            return root,module
        break
    if expected is not None:
        relative=Path(*expected.split('.')).with_suffix('.lean')
        root=path.parents[len(relative.parts)-1] if len(relative.parts)<=len(path.relative_to(checkout_root).parts) else None
        if root is not None and root/relative==path:return root,expected
    elif declared is None:
        module=module_at(path,checkout_root)
        if module:return checkout_root,module
    raise BuildFailure('PUBLIC_LEAN_LAYOUT_REQUIRED',
                       'Supply the exact Lean import name as module for '+origin['source_path'])


def scope(source_root, entry, prepare, *, compiled=None, edited=None, deadline=None):
    """Resolve the package closure with a single native header parser."""
    from lean_headers import parser
    from lean_imports import code_tokens
    from runtime_config import load_lock
    namespace=entry.partition('.')[0]
    compiled=compiled or {}
    headers={};paths={};seen=set()
    available=[*lean_paths(()),Path(load_lock()['lean']['local_path'])/'lib/lean']
    pending=[entry]
    with parser(deadline=deadline) as parse:
        while pending:
            batch=[]
            files=[]
            for module in dict.fromkeys(pending):
                if module in seen:
                    continue
                seen.add(module)
                if not lean_libraries.MODULE.fullmatch(module):
                    raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Unsupported module name '+module)
                relative=Path(*module.split('.')).with_suffix('.lean')
                if module.partition('.')[0]!=namespace:
                    if any((Path(root)/relative.with_suffix('.olean')).is_file() for root in available):
                        continue
                    raise BuildFailure('PUBLIC_LEAN_DEPENDENCY_REQUIRED','Bind the pinned public source for import '+module,
                                       missing_module=module)
                path=edited if module==entry and edited is not None else source_root/relative
                if module in compiled:
                    if path.is_file() and (path.resolve()!=path or hashlib.sha256(path.read_bytes()).hexdigest()!=compiled[module]):
                        raise BuildFailure('PUBLIC_LEAN_CONFLICT','Pinned import has different source bytes: '+module)
                    continue
                if path.resolve()!=path or not path.is_file():
                    raise BuildFailure('PUBLIC_LEAN_DEPENDENCY_REQUIRED','Missing source at the pinned revision for '+module,
                                       missing_module=module)
                text=path.read_bytes().decode()
                if re.search(r'\b(sorry|admit|axiom)\b',code_tokens(text)):
                    raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Source policy failed for '+module)
                paths[module]=path
                batch.append(module)
                files.append(text)
            pending=[]
            for module,header in zip(batch,parse(files) if files else []):
                if 'error' in header:
                    raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Malformed import header for '+module+': '+header['error'])
                headers[module]=header['imports']
                pending.extend(header['imports'])
            prepare([source_root/Path(*name.split('.')).with_suffix('.lean') for name in dict.fromkeys(pending)
                     if name not in seen and name.partition('.')[0]==namespace and lean_libraries.MODULE.fullmatch(name)])
    done={};active=set()
    def visit(module):
        if module in done or module not in paths:
            return
        if module in active:
            raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Cycle at import '+module)
        active.add(module)
        for dependency in headers[module]:
            visit(dependency)
        active.remove(module)
        done[module]=paths[module]
    visit(entry)
    return namespace,done


def same_pin(first, second):
    return (all(first[key]==second[key] for key in ('repository','revision'))
            and first.get('patch_order',[])==second.get('patch_order',[]))


def prior_library(namespace, entry, origin, entries, environment, *, porting=False):
    """Find the active checked public predecessor in this build's inputs."""
    for descriptor, metadata in lean_libraries.validate(lean_libraries.current()):
        if descriptor['name']!=namespace:continue
        owner=next((item for item in reversed(entries) if item['library']==descriptor),None)
        previous={}
        if owner:
            ref=owner['check'];lean_libraries._verify_file(Path(ref['path']),ref['sha256'],False)
            previous=json.loads(Path(ref['path']).read_bytes())
        if (previous.get('version')!=VERSION or not same_pin(previous['origin'],origin)
                or previous['environment']!=environment):
            raise BuildFailure('PUBLIC_LEAN_CONFLICT','Namespace already belongs to a different pinned library: '+namespace)
        matched=next((row for row in metadata['modules'] if row['module']==entry),None)
        bound={'library':descriptor,'registration':owner['check']} if owner else None
        if matched and porting:
            raise BuildFailure('PUBLIC_LEAN_CONFLICT','The original module is already registered: '+entry)
        if matched and entry in metadata.get('ports',{}):
            receipt=lean_ports.inventory(Path(descriptor['root']),metadata)[1][entry]
            if receipt['origin']['source_sha256']==origin['source_sha256'] and entry in metadata['imports']:
                raise BuildFailure('PUBLIC_LEAN_ALREADY_BOUND','The original module has a checked compatibility port: '+entry,bound=bound)
        if matched and matched['source_sha256']!=origin['source_sha256']:
            raise BuildFailure('PUBLIC_LEAN_CONFLICT','Source bytes conflict with the bound module: '+entry)
        if entry in metadata['imports']:
            raise BuildFailure('PUBLIC_LEAN_ALREADY_BOUND','The pinned module is already bound: '+entry,bound=bound)
        return descriptor,metadata
    return None,None


def build(origin, directory, environment, *, timeout, source_cache=None, previous_entries=(), port=None):
    """Use the installed sandboxed compiler. Keep enough evidence for replay and porting."""
    from runtime_config import use_environment
    import lean_environment
    directory.mkdir(parents=True)
    deadline=time.monotonic()+timeout
    entry=None;checks={};bindings=[];previous=None;original_source=None;bound=None;missing_module=None
    selected=lean_environment.identity(environment)
    try:
        with use_environment(environment),native_workspace.temporary('yui-public-lean-',logs=directory) as work:
            input_libraries=lean_libraries.identity()
            native_workspace.record(work,confirmed=True,phase='public-source-prepare')
            with lean_patches.worktree(work,origin,source_cache,deadline) as root:
                def prepare(paths):
                    materialize(work,root,paths,deadline)

                entry_path=root/origin['source_path']
                prepare([entry_path])
                source_dir,entry=source_layout(root,origin)
                if hashlib.sha256(entry_path.read_bytes()).hexdigest()!=origin['source_sha256']:
                    raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED','Pinned module bytes differ from the retained source.')
                namespace=entry.split('.')[0]
                previous,metadata=prior_library(namespace,entry,origin,previous_entries,selected,porting=port is not None)
                edited=None
                if port is not None:
                    inputs,upstream=lean_ports.authorization(port['authority'],origin,entry,selected)
                    edited=directory/'ported.lean';edited.write_text(port['candidate'])
                old_modules=metadata['modules'] if metadata else []
                original_hashes={row['module']:row['source_sha256'] for row in old_modules}
                if metadata and metadata.get('ports'):
                    _,receipts=lean_ports.inventory(Path(previous['root']),metadata)
                    original_hashes.update({module:receipt['original_sha256'] for module,receipt in receipts.items()})
                namespace, sources=scope(source_dir,entry,prepare,edited=edited,
                                         compiled=original_hashes,deadline=deadline)
            output=work/'output'; output.mkdir(); (work/'input').mkdir()
            source_root=directory/'source';build_root=directory/'build'
            rows=list(old_modules)
            ports=dict(metadata.get('ports',{})) if metadata else {}
            if previous:
                old_root=Path(previous['root'])
                lean_ports.copy_evidence(old_root,directory,metadata)
                for row in old_modules:
                    relative=Path(*row['module'].split('.'))
                    for folder, suffix in [('source','.lean'),*[('lib',s) for s,_ in lean_libraries._artifacts(row)]]:
                        member=Path(folder)/(str(relative)+suffix)
                        destination=(source_root if folder=='source' else build_root)/member.relative_to(folder)
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        copy_input(old_root/member,destination)
                        if folder=='lib':
                            # Lean resolves a namespace in the first root containing it.
                            staged=output/member.relative_to(folder)
                            staged.parent.mkdir(parents=True,exist_ok=True)
                            copy_input(destination,staged)
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
                    if port is None and module==entry and lean_ports.failed_native(result):
                        copy_input(source,directory/'original.lean')
                        original_source=bind(directory/'original.lean')
                    from compiler_feedback import excerpt
                    raise BuildFailure('PUBLIC_LEAN_BUILD_FAILED',module+': '+excerpt(native_log,5000)[0])
                dest=source_root/relative.with_suffix('.lean');dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,dest);source_ref=bind(dest);bindings.append(source_ref);artifacts={}
                if port is not None and module==entry:
                    receipt=lean_ports.create(directory/'ports'/entry,entry,origin,selected,
                                              inputs,upstream,checks[entry],source_ref['sha256'])
                    ports[entry]=receipt['sha256']
                for suffix in ('.olean',*COMPANIONS):
                    path=Path(str(compiled.with_suffix(''))+suffix)
                    if not path.is_file():continue
                    dest=build_root/(str(relative)+suffix);dest.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(path,dest);ref=bind(dest);bindings.append(ref);artifacts[suffix]=ref['sha256']
                rows.append({'module':module,'source_sha256':source_ref['sha256'],
                    'olean_sha256':artifacts.pop('.olean'),**({'companions':artifacts} if artifacts else {})})
            spec={'version':lean_libraries.VERSION,'name':namespace,'lean_version':selected['lean_version'],
                'mathlib_commit':selected['mathlib_commit'],'source_root':str(source_root),'build_root':str(build_root),
                'imports':[*metadata['imports'],entry] if metadata else [entry],'modules':rows}
            if ports:spec['ports']=ports
            if 'patch_authority' in origin:
                if previous:
                    # A generation retains the reviewed authorization of its first build.
                    patch_root=Path(previous['root'])
                    spec['patches']=metadata['patches']
                else:
                    patch_root,_=lean_patches.verify_origin(origin)
                    spec['patches']=origin['patch_authority']['sha256']
                lean_patches.copy_evidence(patch_root,directory,spec)
                bindings.extend(bind(directory/path) for path in lean_patches.inventory(directory,spec)[0])
            write(directory/'library.json',spec)
            status='PUBLIC_LEAN_READY'; detail='Pinned public module compiled with the selected compiler.'
    except BuildFailure as error:
        status,detail=error.status,str(error)
        bound=error.bound
        missing_module=error.missing_module
    result={'version':VERSION,'status':status,'diagnostic':detail,'origin':origin,
            'environment':selected,'checks':checks,'bindings':bindings,'input_libraries':input_libraries}
    if previous:result['previous_manifest_sha256']=previous['manifest']['sha256']
    if original_source:result['original_source']=original_source
    if bound is not None:result['bound']=bound
    if missing_module:result['missing_module']=missing_module
    if port is not None:result['port_authority']=port['authority']
    if entry is not None:result['module']=entry
    if status=='PUBLIC_LEAN_READY':result['specification']=bind(directory/'library.json')
    path=directory/'result.json';write(path,result)
    return {**result,'receipt':bind(path)}


def qualify(check, metadata, *, previous=None, full=False):
    """Check the selected source/olean inventory against actual native builds."""
    import lean_environment
    from runtime_config import require_environment
    if check['status']!='PUBLIC_LEAN_READY' or check['environment']!=lean_environment.identity(require_environment()):
        raise ValueError('Public Lean library has no successful check in the selected environment')
    for ref in [check['specification'],*check['bindings'],*check['checks'].values()]:
        lean_libraries._verify_file(Path(ref['path']),ref['sha256'],full)
    spec=json.loads(Path(check['specification']['path']).read_text())
    if any(spec.get(key)!=metadata.get(key) for key in ('name','imports','modules','lean_version','mathlib_commit','ports','patches')):
        raise ValueError('Public Lean library manifest differs from the checked source/olean inventory')
    if 'patch_authority' in check['origin']:
        lean_patches.verify_origin(check['origin'],full=full)
        root=Path(spec['source_root']).parent
        _,patches=lean_patches.inventory(root,metadata,full=full)
        expected=previous[1].get('patches') if previous else check['origin']['patch_authority']['sha256']
        if patches is None or patches['order']!=check['origin']['patch_order'] or metadata['patches']!=expected:
            raise ValueError('Public Lean library does not retain its authorized patch order')
    elif 'patches' in metadata:
        raise ValueError('Public Lean library has unauthorized patches')
    module=check['module']
    modules={row['module']:row for row in metadata['modules']}
    old_ports=previous[1].get('ports',{}) if previous else {}
    ports=metadata.get('ports',{})
    expected_ports=dict(old_ports)
    expected_source=check['origin']['source_sha256']
    if 'port_authority' in check:
        root=Path(spec['source_root']).parent
        files,upstream=lean_ports.authorization(check['port_authority'],check['origin'],module,check['environment'])
        receipts=lean_ports.inventory(root,metadata,full=full)[1]
        receipt=receipts[module]
        if (module in old_ports or receipt['origin']!=check['origin']
                or receipt['target_environment']!=check['environment'] or receipt['upstream_environment']!=upstream
                or any(receipt['files'][key]['sha256']!=ref['sha256'] for key,ref in files.items())
                or receipt['files']['target_ported']['sha256']!=check['checks'][module]['sha256']):
            raise ValueError('Public Lean port differs from the checked compatibility evidence')
        expected_ports[module]=ports[module]
        expected_source=receipt['ported_sha256']
    if ports!=expected_ports or module not in modules or modules[module]['source_sha256']!=expected_source:
        raise ValueError('Public Lean entry source differs from the pinned check')
    old_modules=set()
    if previous:
        prior,old_metadata,old_check=previous
        if (old_check['version']!=VERSION or not same_pin(check['origin'],old_check['origin'])
                or check['environment']!=old_check['environment']
                or check.get('previous_manifest_sha256')!=prior['manifest']['sha256']
                or module in old_metadata['imports']
                or metadata['imports']!=[*old_metadata['imports'],module]
                or any(modules.get(row['module'])!=row for row in old_metadata['modules'])):
            raise ValueError('Public Lean generation changes a previously checked library')
        old_modules={row['module'] for row in old_metadata['modules']}
    elif 'previous_manifest_sha256' in check or metadata['imports']!=[module]:
        raise ValueError('Public Lean generation has no matching predecessor')
    if set(check['checks'])!=set(modules)-old_modules or any(
            not native_succeeded(json.loads(Path(ref['path']).read_text())) for ref in check['checks'].values()):
        raise ValueError('Public Lean library has incomplete native coverage')
