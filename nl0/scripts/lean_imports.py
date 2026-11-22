"""Check source-bound imported Lean locally before original-version diagnosis/porting."""
import fcntl
import hashlib
from importlib.util import module_from_spec,spec_from_file_location
import json
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from controller_common import bind,write,verify_bindings
import lean_environment
import lean_libraries
import native_workspace
from pilot_common import run_lean
import runtime_config

_SPEC=spec_from_file_location('yui_imported_lean_rules',Path(__file__).resolve().parents[2]/'workflow/blocks/imported_lean.py')
rules=module_from_spec(_SPEC);_SPEC.loader.exec_module(rules)
VERSION=rules.VERSION

FOLLOW_UP = {
    'LOCAL_CHECK_INCOMPLETE': 'Inspect the native diagnostic and retry the same local check after addressing the failure.',
    'UPSTREAM_ENVIRONMENT_REQUIRED': (
        'Use the source project\'s exact declared Lean and Mathlib pins to retry check_imported_lean. '
        'If the verified pair is unavailable, investigate an alternative for this foundation and continue independent work.'),
    'UPSTREAM_CONTEXT_REQUIRED': (
        'The source is retained. Investigate the missing dependency context for this foundation with the current author '
        'or investigate_basis_frontier. Locate the exact upstream imports or choose a checked alternative in the pinned '
        'environment. Continue independent foundations and keep the affected use pending until checked.'),
    'UPSTREAM_CHECK_INCOMPLETE': 'Address the native failure and retry in the same declared upstream environment.',
    'COMPATIBILITY_PORT_REQUIRED': (
        'Use the retained original and these diagnostics to prepare the compatibility edit. After selecting the '
        'natural-language basis route, retry check_imported_lean with candidate in the current pinned environment.'),
    'CORRECTION_AND_PORT_REQUIRED': (
        'Use the retained original and both diagnostics to correct and adapt this unit. After selecting the '
        'natural-language basis route, retry check_imported_lean with candidate in the current pinned environment.'),
    'PORT_CHECK_FAILED': (
        'Use the current candidate diagnostic to repair the port and retry check_imported_lean with candidate.'),
    'PORT_CHECK_INCOMPLETE': 'Address the native failure and recheck the same candidate in the current environment.',
}


def hashed(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def diagnostic(check):
    """Return a bounded view; the complete compiler output has one bound owner."""
    return check['diagnostic'] if check is not None else None


def dependency_followup(log):
    """Recover outstanding native diagnostics from this stage's own tool receipts."""
    if not log.is_file():return {}
    latest = {}
    with log.open() as stream:
        for line in stream:
            call=json.loads(line)
            if call['tool']!='check_imported_lean':continue
            reply=call['result']
            if 'receipt' not in reply:continue
            source=call['arguments']['source']
            label=source.get('document') or source['evidence']['path']
            latest[label]=reply['receipt']
    pending={}
    for label, receipt in latest.items():
        path=Path(receipt['path']).resolve()
        if path.parent.parent!=log.parent.resolve()/'imported-lean' or path.name!='result.json':
            raise ValueError('Import diagnostic belongs to another stage')
        verify_bindings([receipt]);result=json.loads(path.read_bytes())
        if result['version']!=VERSION:raise ValueError('Unrecognized import diagnostic')
        public=result.get('public_library')
        unresolved_public=public and public['status'] not in {'PUBLIC_LEAN_READY','PUBLIC_LEAN_ALREADY_BOUND'}
        if not result['accepted_for_native_reuse'] or unresolved_public:
            pending[label]={**{key:result[key] for key in ('status','diagnostics','next_action','public_library',
                                                         'upstream_public_library') if key in result},'receipt':receipt}
    return pending


def wait_for_dependency(stage, receipt):
    """Wait for operator recheck of an exact, still-unresolved native dependency."""
    from execution_state import current
    from fault_control import Gate
    diagnostic=next((row for row in dependency_followup(stage.logs/'tools.jsonl').values()
                     if row['receipt']==receipt),None)
    if diagnostic is None:raise ValueError('Select an outstanding check_imported_lean receipt from this stage')
    recorder,task=current()
    gate=Gate(stage.logs/'dependency-request',recorder=recorder,task=task,stage='lean-dependency')
    gate.pause({'code':'workflow_blocked','message':'An external Lean dependency needs an operator recheck.'},
               resumable=True,checkpoint={'import_diagnostic':receipt,'status':diagnostic['status']})
    return {'status':'RETRY_LEAN_DEPENDENCY','dependency_followup':diagnostic,'stage_complete':False,
            'instruction':'Retry the bound check using the current dependency diagnostic.'}


environment_identity=lean_environment.identity

def code_tokens(text, *, preserve_interpolation=False):
    """Remove nested comments and string contents without moving line numbers."""
    result=[];index=0;depth=0;string=False
    while index<len(text):
        char=text[index];pair=text[index:index+2]
        if depth:
            if pair=='/-':depth+=1;result.extend('  ');index+=2;continue
            if pair=='-/':depth-=1;result.extend('  ');index+=2;continue
            result.append('\n' if char=='\n' else ' ');index+=1;continue
        if string:
            if char=='\\' and index+1<len(text):result.extend('  ');index+=2;continue
            if char=='"':string=False
            result.append('\n' if char=='\n' else ' ');index+=1;continue
        raw=re.match(r'r(#+)?"',text[index:]) if char=='r' else None
        if raw:
            end=text.find('"'+(raw[1] or ''),index+len(raw[0]))
            if end<0:raise ValueError('A complete imported unit must close its raw strings')
            end+=1+len(raw[1] or '')
            result.extend('\n' if c=='\n' else ' ' for c in text[index:end]);index=end;continue
        literal=re.match(r"'(?:\\(?:u\{[0-9A-Fa-f]+\}|.)|[^'\\\n])'",text[index:]) if char=="'" else None
        if literal:result.extend(' '*len(literal[0]));index+=len(literal[0]);continue
        if char=='«':
            end=text.find('»',index+1)
            if end>=0:result.extend(' '*(end-index+1));index=end+1;continue
        if pair=='/-':depth=1;result.extend('  ');index+=2;continue
        if pair=='--':
            end=text.find('\n',index)
            if end<0:end=len(text)
            result.extend(' '*(end-index));index=end;continue
        if char=='"':
            # Interpolated strings can contain executable term syntax. Keep
            # the rest of the unit visible to declaration/proof guards.
            if preserve_interpolation and index and text[index-1]=='!':
                return ''.join(result)+text[index:]
            string=True;result.append(' ');index+=1;continue
        result.append(char);index+=1
    if depth or string:raise ValueError('A complete imported unit must close its comments and strings')
    return ''.join(result)


def preamble(text):
    from lean_headers import parser
    with parser() as parse:
        [header]=parse([text])
    return None if 'error' in header else text.encode()[:header['endBytes']].decode()


def source_bytes(stage,selection):
    if not isinstance(selection,dict) or set(selection)-{'document','evidence','start','end'} or ('document' in selection)==('evidence' in selection):
        raise ValueError('Select one explicit stage document or hash-bound retained public source')
    if 'document' in selection:
        name=selection['document']
        if not isinstance(name,str) or name not in getattr(stage,'task_inputs',{}):raise ValueError('Unknown explicit source document')
        raw=stage.task_inputs[name].encode('utf-8');origin={'document':name,'sha256':hashlib.sha256(raw).hexdigest()}
    else:
        evidence=selection['evidence']
        if not isinstance(evidence,dict) or set(evidence)!={'path','sha256'}:raise ValueError('Bind the retained public source path and digest')
        relative=Path(evidence['path']);root=stage.logs/'external-sources';path=stage.logs/relative
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Imported code must be a retained public source')
        if any(p.is_symlink() for p in (path,*path.parents) if p.is_relative_to(stage.logs)):
            raise ValueError('Retained imported source cannot contain symlinks')
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError('Imported code must be an existing retained public source')
        if bind(path)['sha256']!=evidence['sha256']:raise ValueError('Retained imported source changed')
        raw=path.read_bytes();origin={'evidence':evidence}
    lines=raw.decode('utf-8').splitlines(keepends=True)
    start=selection.get('start',1);end=selection.get('end',len(lines))
    if type(start) is not int or type(end) is not int or not 1<=start<=end<=len(lines):
        raise ValueError('Use an exact one-based line range within the retained source')
    selected=''.join(lines[start-1:end])
    if not selected.strip():raise ValueError('Imported source is empty')
    return raw,selected,{**origin,'start':start,'end':end,'selected_sha256':hashlib.sha256(selected.encode()).hexdigest()}


def compile_unit(source,environment,directory,*,attachments=(),timeout=None):
    """Keep native receipts and artifacts; only completed checked results are cached."""
    lean_environment.verify(environment)
    module='YuiImported'+hashlib.sha256(source.encode()).hexdigest()[:24]
    attachments=[row for row in attachments if row['name']!=module]
    with runtime_config.use_environment(environment),lean_libraries.use(attachments),lean_libraries.generated(None):
        identity=environment_identity(environment);libraries=lean_libraries.identity()
        key=hashed([VERSION,source,identity,libraries])
        directory=Path(directory)/key;directory.mkdir(parents=True,exist_ok=True)
        index=directory/'checked.json'
        if index.is_file():
            value=json.loads(index.read_text());verify_bindings([value['result']])
            result=json.loads(Path(value['result']['path']).read_text());verify_bindings(result['bindings'])
            if result['key']!=key or not rules.passed(result):raise ValueError('Changed imported Lean cache authority')
            return {**result,'receipt':value['result'],'cache_reused':True}
        attempt=directory/uuid.uuid4().hex;attempt.mkdir()
        source_root=attempt/'source';source_root.mkdir();original=source_root/(module+'.lean');original.write_text(source)
        build=attempt/'build';build.mkdir()
        policy=not re.search(r'\b(sorry|admit|axiom)\b',code_tokens(source))
        with native_workspace.temporary('yui-imported-lean-',logs=attempt) as work:
            (work/'input').mkdir();(work/'output').mkdir()
            file=work/'output'/(module+'.lean');file.write_text(source)
            native=run_lean(file,work,output=work/'output'/(module+'.olean'),timeout=timeout)
            policy=policy and not re.search(r"declaration uses ['‘]sorry['’]",native.get('stdout','')+'\n'+native.get('stderr',''))
            write(attempt/'native.json',native)
            artifacts=[]
            if rules.passed({'native':native,'source_policy_passed':policy}):
                for suffix in ('.olean','.olean.private','.olean.server','.ir','.ir.sig'):
                    path=work/'output'/(module+suffix)
                    if path.is_file():
                        shutil.copyfile(path,build/path.name);artifacts.append(bind(build/path.name))
                if not (build/(module+'.olean')).is_file():raise ValueError('A checked imported module must retain its actual compiler output')
        from compiler_feedback import excerpt
        stdout=native.get('stdout','');stderr=native.get('stderr','')
        display={'stdout':excerpt(stdout,12000)[0],'stderr':excerpt(stderr,4000)[0],
                 'truncated':len(stdout)>12000 or len(stderr)>4000,'complete':bind(attempt/'native.json')}
        result={'version':VERSION,'key':key,'module':module,'source':bind(original),
                'environment':identity,'lean_environment':environment,'libraries':libraries,
                'native':{k:v for k,v in native.items() if k not in {'stdout','stderr'}},
                'native_evidence':bind(attempt/'native.json'),'diagnostic':display,
                'missing_import':native_missing_import(native),
                'source_policy_passed':bool(policy),'artifacts':artifacts,
                'bindings':[bind(original),bind(attempt/'native.json'),*artifacts]}
        write(attempt/'result.json',result);receipt=bind(attempt/'result.json')
        if rules.passed(result):write(index,{'result':receipt})
        return {**result,'receipt':receipt,'cache_reused':False}


def original_environment(declared):
    pins={'lean_version','mathlib_ref'}
    if (not isinstance(declared,dict) or set(declared)-{'dependencies'}!=pins
            or not all(isinstance(declared[k],str) and declared[k] for k in pins)):
        raise ValueError('Declare exact source-project lean_version and mathlib_ref before upstream checking')
    candidates,errors=lean_environment.discover()
    try:return lean_environment.rules.select(candidates,lean_version=declared['lean_version'],mathlib_ref=declared['mathlib_ref'])
    except lean_environment.SelectionRequired as error:
        error.request['discovery_errors']=errors
        raise


def publish_library(specification,root,receipt):
    """Publish one verified manifest atomically within the owned pre-freeze registry."""
    root=Path(root).resolve()
    if root.name!='imported-lean' or not (root.parent/'job.json').is_file():raise ValueError('Publish checked imports only inside an explicitly owned prepared case')
    if not Path(receipt['path']).resolve().is_relative_to(root.parent):raise ValueError('Library check belongs to another case')
    verify_bindings([receipt])
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (root.parent/'basis-selection.json').exists() or any((root.parent/'nl0-to-lean').glob('*/workflow/freeze-seal.json')):
            raise ValueError('The basis/interface is frozen; use its authorized revision route before adding imports')
        spec=json.loads(Path(specification).read_bytes());name=spec['name']
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',name):raise ValueError('Invalid generated library namespace')
        prior=lean_libraries.read_generated(root)
        existing=next((row for row in prior if row['name']==name),None)
        check=json.loads(Path(receipt['path']).read_bytes())
        value=lean_libraries.registry_index(root)
        if existing and check.get('previous_manifest_sha256')!=existing['manifest']['sha256']:
            metadata=json.loads(Path(existing['manifest']['path']).read_bytes())
            entry=next(item for item in reversed(value['entries']) if item['library']==existing)
            old=json.loads(Path(entry['check']['path']).read_bytes())
            if (old['version']!=check['version'] or old['environment']!=check['environment']
                    or old.get('origin')!=check.get('origin')
                    or any(metadata.get(key)!=spec.get(key)
                           for key in ('imports','modules','lean_version','mathlib_commit','ports','patches'))):
                raise ValueError('The active library changed during building; check the current pinned library: '+name)
            return existing
        index=root/'index.json'
        generations=root/'generations';generations.mkdir(exist_ok=True)
        if generations.is_symlink():raise ValueError('Invalid owned Lean library generations directory')
        destination=Path(tempfile.mkdtemp(dir=generations))
        proposed=None
        try:
            descriptor=lean_libraries.capture(specification,destination)
            proposed={**value,'entries':[*value['entries'],{'library':descriptor,'check':receipt}]}
            lean_libraries.generated_inventory(root,proposed=proposed)
            write(index,proposed)
        except BaseException:
            # Do not delete a generation the atomic index has already exposed.
            if not index.is_file() or lean_libraries.registry_index(root)!=proposed:
                shutil.rmtree(destination)
            raise
        return descriptor


def publish_checked(check,root):
    """Publish a single completed check before freeze."""
    if not rules.passed(check):raise ValueError('Only a completed current native check can publish imported code')
    if check['environment']!=environment_identity(runtime_config.require_environment()):raise ValueError('Cannot publish a check from another selected environment')
    verify_bindings([check['receipt'],*check['bindings']])
    module=check['module'];source=Path(check['source']['path']);build=source.parent.parent/'build'
    companions={p.name[len(module):]:bind(p)['sha256'] for p in build.iterdir() if p.name!=module+'.olean'}
    spec={'version':lean_libraries.VERSION,'name':module,'lean_version':check['environment']['lean_version'],
          'mathlib_commit':check['environment']['mathlib_commit'],'source_root':str(source.parent),
          'build_root':str(build),'imports':[module],'modules':[{'module':module,
          'source_sha256':check['source']['sha256'],'olean_sha256':bind(build/(module+'.olean'))['sha256'],
          **({'companions':companions} if companions else {})}]}
    path=Path(check['receipt']['path']).with_name('library.json');write(path,spec)
    return publish_library(path,root,check['receipt'])


def public_context(stage, request, origin, environment, attachments, *, publish, port=None, prior=()):
    """Acquire and compile a known dependency before escalating at the author boundary."""
    import public_lean
    from execution_state import current
    identity=environment_identity(environment)
    libraries=[{'name':row['name'],'manifest_sha256':row['manifest']['sha256']} for row in attachments]
    directory=stage.logs/'imported-lean'/'public-builds'/hashed([origin,identity,libraries,port])
    directory.parent.mkdir(parents=True,exist_ok=True)
    owned=lean_libraries.generated_root()
    root=Path(owned).resolve() if publish else None
    source_cache=(Path(owned).resolve() if owned is not None else directory.parent.parent)/'public-sources'
    if root is not None:
        if (root.parent/'basis-selection.json').exists() or any((root.parent/'nl0-to-lean').glob('*/workflow/freeze-seal.json')):
            return {'status':'PUBLIC_LEAN_DEPENDENCY_REQUIRED',
                    'diagnostic':'The current mathematical boundary is frozen. Revise the dependency binding before importing '+origin['source_path']}, []
    existing=lean_libraries.registry_index(root)['entries'] if root is not None else prior
    with (directory.parent/(directory.name+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with runtime_config.use_environment(environment),lean_libraries.use(attachments),lean_libraries.generated(None):
            directory.mkdir(exist_ok=True)
            saved=directory/'result.json'
            if saved.is_file():
                ref=json.loads(saved.read_bytes())['result'];verify_bindings([ref])
                result={**json.loads(Path(ref['path']).read_bytes()),'receipt':ref}
                if result['origin']!=origin or result['environment']!=identity:
                    raise ValueError('Changed public Lean build provenance')
            else:
                recorder,_=current()
                limit=recorder.remaining(1800) if recorder else 1800
                result=public_lean.build(origin,directory/uuid.uuid4().hex,environment,timeout=limit,
                                         source_cache=source_cache,previous_entries=existing,port=port)
                if result['status']=='PUBLIC_LEAN_READY':
                    write(saved,{'result':result['receipt']})
            if result['status']=='PUBLIC_LEAN_ALREADY_BOUND':
                return result,[result['bound']['library']]
            if result['status']!='PUBLIC_LEAN_READY':return result, []
            specification=result['specification'];verify_bindings([specification])
            if root is None:
                return result,[lean_libraries.capture(specification['path'],request/result['receipt']['sha256'])]
        descriptor=publish_library(specification['path'],root,result['receipt'])
        return result,[descriptor]


def native_missing_import(native):
    text=native.get('stdout','')+'\n'+native.get('stderr','')
    return bool(re.search(r'unknown module prefix|object file.*\.olean.*does not exist',text,re.I))


def missing_import(check):
    if not check:
        return False
    if 'missing_import' in check:
        return check['missing_import']
    receipt=check.get('native_evidence')
    if not receipt:
        return False
    verify_bindings([receipt])
    return native_missing_import(json.loads(Path(receipt['path']).read_bytes()))


def build_upstream(stage, request, origin, declared, environment):
    """Resolve the cross-library closure using only this upstream compiler."""
    import public_lean
    explicit=declared.get('dependencies',{})
    if not isinstance(explicit,dict) or not all(lean_libraries.MODULE.fullmatch(module) for module in explicit):
        raise ValueError('Name each upstream dependency by its exact Lean module')
    entries={};active=set()

    def build(pin):
        key=(pin['repository'],pin['revision'],pin['source_path'],tuple(pin.get('patch_order',[])))
        if key in active:raise ValueError('Cycle in pinned upstream Lean sources: '+pin['source_path'])
        active.add(key)
        try:
            while True:
                prior=list(entries.values())
                result,installed=public_context(stage,request,pin,environment,
                    [row['library'] for row in prior],publish=False,prior=prior)
                if installed:
                    library=installed[0]
                    if result['status']=='PUBLIC_LEAN_READY':
                        entries[library['name']]={'library':library,'check':result['receipt']}
                    return result
                missing=result.get('missing_module')
                if not missing or (result.get('module') and missing.split('.')[0]==result['module'].split('.')[0]):
                    return result
                if missing in explicit:
                    selection=explicit[missing]
                    raw,text,_=source_bytes(stage,selection)
                    dependency=public_lean.known_source(stage.logs,selection) if raw==text.encode() else None
                    if dependency is None:raise ValueError('Upstream dependency needs its full retained fixed source: '+missing)
                else:
                    dependency=public_lean.known_dependency(stage.logs,missing)
                    if dependency is None:return result
                completed=build({**dependency,'expected_module':missing})
                if completed['status'] not in {'PUBLIC_LEAN_READY','PUBLIC_LEAN_ALREADY_BOUND'}:
                    return completed
        finally:
            active.remove(key)

    return build(origin)


def public_port(stage, request, origin, target, declared, environment, attachments, candidate):
    """Authorize an original-name port using actual builds of the pinned module."""
    if not target or not target.get('original_source') or declared is None:
        if candidate is not None:
            if target and target.get('status') in {'PUBLIC_LEAN_ALREADY_BOUND','PUBLIC_LEAN_READY','PUBLIC_LEAN_CONFLICT'}:
                raise ValueError('The original module is already registered or conflicts with a registered module')
            raise ValueError('An original-name port requires a completed target compilation failure and a declared upstream pair')
        return None
    try:
        old=original_environment(declared)
    except lean_environment.SelectionRequired as error:
        if candidate is None:return None
        raise ValueError('The pinned upstream Lean/Mathlib pair must be available before original-name porting') from error
    if environment_identity(old)==environment_identity(environment):
        if candidate is None:return None
        raise ValueError('The declared upstream pair must differ from the target for a compatibility port')
    upstream=build_upstream(stage,request,origin,declared,old)
    if upstream['status']!='PUBLIC_LEAN_READY':
        return {'status':upstream['status'],'upstream_public_library':upstream,
                'upstream_check':upstream.get('receipt'),
                'diagnostics':{'current':target['diagnostic'],'upstream':upstream['diagnostic']}}
    import lean_ports
    authority={'upstream':upstream['receipt'],'target_original':target['receipt']}
    lean_ports.authorization(authority,origin,target['module'],environment_identity(environment))
    result={'version':VERSION,'status':'COMPATIBILITY_PORT_REQUIRED','accepted_for_native_reuse':False,
            'semantic_acceptance':False,'upstream_public_library':upstream,'upstream_check':upstream['receipt'],
            'target_original_check':target['receipt'],'module':target['module'],
            'diagnostics':{'current':target['diagnostic'],'upstream':upstream['diagnostic']}}
    if candidate is not None:
        if not isinstance(candidate,str) or not candidate.strip():raise ValueError('Supply the complete edited compilation unit')
        built, descriptors=public_context(stage,request,origin,environment,attachments,publish=True,
                                          port={'authority':authority,'candidate':candidate})
        result.update(status='PORTED_CHECKED' if descriptors else 'PORT_CHECK_FAILED',
                      original_route='COMPATIBILITY_PORT_REQUIRED',public_library=built,
                      accepted_for_native_reuse=bool(descriptors))
        if 'receipt' in built:result['candidate_check']=built['receipt']
        if descriptors:
            result.update(library=descriptors[0],**{'import':'import '+target['module']})
    return result


def check_public(stage, request, source, pin, selected, attached, upstream, candidate):
    result={'version':VERSION,'source':bind(request/'source.json'),
            'original_source':bind(request/'original.lean'),'selected_source':bind(request/'selected.lean'),
            'semantic_acceptance':False,'accepted_for_native_reuse':False}
    if pin is None:
        result.update(status='PUBLIC_SOURCE_EVIDENCE_REQUIRED',
                      diagnostics={'current':'Read the complete public Lean module at its fixed Git commit.'})
        return result
    built,descriptors=public_context(stage,request,pin,selected,attached,publish=True)
    result.update(status=built['status'],public_library=built,diagnostics={'current':built['diagnostic']},
                  current_check=built.get('receipt'),
                  current_cache_reused=built['status']=='PUBLIC_LEAN_ALREADY_BOUND')
    if candidate is not None or upstream is not None:
        comparison=public_port(stage,request,pin,built,upstream,selected,attached,candidate)
        if comparison is not None:
            result.update(comparison)
            if not result['accepted_for_native_reuse']:
                result['next_action']={'source':source,'upstream':upstream,
                    'instruction':'Use this complete pinned source and module to repair the target build in this stage.'}
            return result
    if descriptors:
        [descriptor]=descriptors
        module=built['module']
        relative=Path(*module.split('.')).with_suffix('.lean')
        result.update(status='LOCAL_REUSED',accepted_for_native_reuse=True,
                      checked_source=bind(Path(descriptor['root'])/'source'/relative),
                      module=module,library=descriptor,**{'import':'import '+module})
    else:
        result['next_action']={'source':source,'upstream':upstream,
            'instruction':'Continue using the retained public-library diagnostic.'}
    return result


def check(stage,source,*,upstream=None,candidate=None,publish=False,bind_public=False,module=None,allow_publish=False):
    if type(publish) is not bool:raise ValueError('publish must be an explicit boolean')
    if module is not None and (not isinstance(module,str) or not lean_libraries.MODULE.fullmatch(module)):
        raise ValueError('Use the exact Lean module name for module')
    raw,text,origin=source_bytes(stage,source)
    full_pin=None
    if bind_public and text.encode()==raw:
        from public_lean import known_source
        full_pin=known_source(stage.logs,source)
    if bind_public and candidate is not None and not full_pin:
        raise ValueError('Original-name porting requires complete pinned source, not a document excerpt')
    request=stage.logs/'imported-lean'/('request-'+uuid.uuid4().hex);request.mkdir(parents=True)
    (request/'original.lean').write_bytes(raw);(request/'selected.lean').write_text(text);write(request/'source.json',origin)
    selected=runtime_config.require_environment();attached=lean_libraries.current()
    can_bind=allow_publish and lean_libraries.generated_root() is not None
    if bind_public:
        if not can_bind:
            raise ValueError('This role cannot add a public library to its bound context')
        if full_pin and module is not None:
            full_pin['expected_module']=module
        result=check_public(stage,request,source,full_pin,selected,attached,upstream,candidate)
        write(request/'result.json',result)
        return {**result,'receipt':bind(request/'result.json'),'stage_complete':False}
    timeout=stage.lean_timeout() if hasattr(stage,'lean_timeout') else None
    current=compile_unit(text,selected,stage.logs/'imported-lean/checks',attachments=attached,timeout=timeout)
    origin=None; built=None
    if can_bind and missing_import(current):
        from public_lean import known_source
        origin=known_source(stage.logs,source)
        if origin:
            if module is not None:origin['expected_module']=module
            built,descriptors=public_context(stage,request,origin,selected,attached,publish=True)
            if descriptors:
                attached=lean_libraries.current()
                current=compile_unit(text,selected,stage.logs/'imported-lean/checks',attachments=attached,timeout=timeout)
    result={'source':bind(request/'source.json'),'original_source':bind(request/'original.lean'),
            'selected_source':bind(request/'selected.lean'),'current_check':current['receipt'],
            'current_cache_reused':current['cache_reused']}
    if built:result['public_library']=built
    checked=current
    decision=rules.decide(current)
    if decision['status']=='UPSTREAM_ENVIRONMENT_REQUIRED' and upstream is not None:
        try:old=original_environment(upstream)
        except lean_environment.SelectionRequired as error:
            result['selection_request']=error.request
        else:
            compatible=(environment_identity(old)==environment_identity(selected))
            with runtime_config.use_environment(old):
                header=preamble(text)
            old_libraries=attached if compatible else []
            context=(compile_unit(header,old,stage.logs/'imported-lean/checks',attachments=old_libraries,timeout=timeout)
                     if header is not None else None)
            if origin and not compatible and missing_import(context):
                old_build, extra=public_context(stage,request,origin,old,old_libraries,publish=False)
                result['upstream_public_library']=old_build
                if extra:
                    old_libraries=[*old_libraries,*extra]
                    context=compile_unit(header,old,stage.logs/'imported-lean/checks',attachments=old_libraries,timeout=timeout)
            original=None
            if rules.passed(context):
                original=current if compatible else compile_unit(text,old,stage.logs/'imported-lean/checks',attachments=old_libraries,timeout=timeout)
            result.update(declared_upstream=upstream,upstream_environment=old,
                upstream_context_check=context['receipt'] if context else None,
                upstream_check=original['receipt'] if original else None)
            decision=rules.decide(current,upstream_available=True,context=context,original=original)
            if candidate is not None and decision['status'] in {'COMPATIBILITY_PORT_REQUIRED','CORRECTION_AND_PORT_REQUIRED'}:
                if not isinstance(candidate,str) or not candidate.strip():raise ValueError('Supply the complete edited compilation unit')
                checked=compile_unit(candidate,selected,stage.logs/'imported-lean/checks',attachments=attached,timeout=timeout)
                result['candidate_check']=checked['receipt']
                decision=rules.decide(current,upstream_available=True,context=context,original=original,candidate=checked)
    if candidate is not None and rules.passed(current) and candidate!=text:
        raise ValueError('The unchanged original already passes locally; reuse it before proposing an unnecessary port')
    result.update(decision)
    result['diagnostics']={'current':diagnostic(current)} if 'native_evidence' in current else {}
    if result.get('upstream_context_check'):
        result['diagnostics']['upstream_context']=diagnostic(context)
    if result.get('upstream_check'):result['diagnostics']['upstream']=diagnostic(original)
    if result.get('candidate_check'):result['diagnostics']['candidate']=diagnostic(checked)
    follow_up=FOLLOW_UP.get(decision['status'])
    if built and built['status'] not in {'PUBLIC_LEAN_READY','PUBLIC_LEAN_ALREADY_BOUND'}:
        follow_up=(follow_up+' ' if follow_up else '')+(
            'Continue this dependency using the public-library diagnostic. If operator action is still required, '
            'use wait_for_lean_dependency with this check receipt where available.')
    if follow_up:
        result['next_action']={'source':source,'upstream':upstream,'instruction':follow_up}
    if decision['accepted_for_native_reuse']:
        result['checked_source']=checked['source'];result['module']=checked['module']
        if publish:
            if not allow_publish:raise ValueError('This role may check imported code but cannot add imports to a frozen context')
            root=lean_libraries.generated_root()
            if root is None:raise ValueError('Prepare an owned case before publishing checked imports')
            result['library']=publish_checked(checked,root);result['import']='import '+checked['module']
    write(request/'result.json',result)
    return {**result,'receipt':bind(request/'result.json'),'stage_complete':False}


def tools():
    import native_carrier
    return [native_carrier.tool('check_imported_lean',
        'Check a complete, source-bound imported Lean unit in the current environment first. On failure, check declared source-project versions and imports before requesting compatibility porting or correction. A candidate must pass current checking. publish is allowed only before basis/interface freeze; no source or semantic approval is granted.',
        {'source':{'type':'object','additionalProperties':True},'upstream':{'type':'object','additionalProperties':False,
            'properties':{'lean_version':{'type':'string'},'mathlib_ref':{'type':'string'},
                          'dependencies':{'type':'object','additionalProperties':{'type':'object','additionalProperties':True}}},
            'required':['lean_version','mathlib_ref']},
         'candidate':{'type':'string'},'publish':{'type':'boolean'},
         'module':{'type':'string','description':'Exact Lean import name when its source root cannot be discovered from static Lake metadata.'},
         'bind_public':{'type':'boolean',
             'description':'Bind an original module at its exact public Git commit. For a compatibility port, give the complete retained source, upstream pins, exact module and complete candidate; only an unregistered original name may be filled.'}},['source'])]
