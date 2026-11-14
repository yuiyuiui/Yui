"""Check source-bound imported Lean locally before original-version diagnosis/porting."""
import fcntl
import hashlib
from importlib.util import module_from_spec,spec_from_file_location
import json
from pathlib import Path
import re
import shutil
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


def hashed(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def diagnostic(check):
    """Return a bounded view; the complete compiler output has one bound owner."""
    return check['diagnostic'] if check is not None else None


environment_identity=lean_environment.identity

def code_tokens(text):
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
        if char=='"':string=True;result.append(' ');index+=1;continue
        result.append(char);index+=1
    if depth or string:raise ValueError('A complete imported unit must close its comments and strings')
    return ''.join(result)


def preamble(text):
    clean=code_tokens(text).splitlines();original=text.splitlines(keepends=True);count=0
    for line in clean:
        value=line.strip()
        if not value or value in {'module','prelude'}:count+=1;continue
        if re.match(r'^(?:(?:public|private|meta)\s+)*import\b',value):
            if not re.fullmatch(r'(?:(?:public|private|meta)\s+)*import\s+[A-Za-z][A-Za-z0-9_.]*(?:\s+[A-Za-z][A-Za-z0-9_.]*)*',value):
                return None
            count+=1;continue
        break
    return ''.join(original[:count])


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
        def view(text,limit):
            return text if len(text)<=limit else text[:limit//2]+'\n[... retained output omitted ...]\n'+text[-limit//2:]
        stdout=native.get('stdout','');stderr=native.get('stderr','')
        display={'stdout':view(stdout,12000),'stderr':view(stderr,4000),
                 'truncated':len(stdout)>12000 or len(stderr)>4000,'complete':bind(attempt/'native.json')}
        result={'version':VERSION,'key':key,'module':module,'source':bind(original),
                'environment':identity,'lean_environment':environment,'libraries':libraries,
                'native':{k:v for k,v in native.items() if k not in {'stdout','stderr'}},
                'native_evidence':bind(attempt/'native.json'),'diagnostic':display,
                'source_policy_passed':bool(policy),'artifacts':artifacts,
                'bindings':[bind(original),bind(attempt/'native.json'),*artifacts]}
        write(attempt/'result.json',result);receipt=bind(attempt/'result.json')
        if rules.passed(result):write(index,{'result':receipt})
        return {**result,'receipt':receipt,'cache_reused':False}


def original_environment(declared):
    if not isinstance(declared,dict) or set(declared)!={'lean_version','mathlib_ref'} or not all(isinstance(v,str) and v for v in declared.values()):
        raise ValueError('Declare exact source-project lean_version and mathlib_ref before upstream checking')
    candidates,errors=lean_environment.discover()
    try:return lean_environment.rules.select(candidates,lean_version=declared['lean_version'],mathlib_ref=declared['mathlib_ref'])
    except lean_environment.SelectionRequired as error:
        error.request['discovery_errors']=errors
        raise


def publish_checked(check,root):
    """Publish availability before freeze, preserving checked bytes as public library input."""
    root=Path(root).resolve()
    if root.name!='imported-lean' or not (root.parent/'job.json').is_file():raise ValueError('Publish checked imports only inside an explicitly owned prepared case')
    if (root.parent/'basis-selection.json').exists() or any((root.parent/'nl0-to-lean').glob('*/workflow/freeze-seal.json')):
        raise ValueError('The basis/interface is frozen; use its authorized revision route before adding imports')
    if not rules.passed(check):raise ValueError('Only a completed current native check can publish imported code')
    if check['environment']!=environment_identity(runtime_config.require_environment()):raise ValueError('Cannot publish a check from another selected environment')
    verify_bindings([check['receipt'],*check['bindings']])
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        prior=lean_libraries.read_generated(root)
        existing=next((row for row in prior if row['name']==check['module']),None)
        if existing:return existing
        module=check['module'];source=Path(check['source']['path']);build=source.parent.parent/'build'
        companions={p.name[len(module):]:bind(p)['sha256'] for p in build.iterdir() if p.name!=module+'.olean'}
        spec={'version':lean_libraries.VERSION,'name':module,'lean_version':check['environment']['lean_version'],
              'mathlib_commit':check['environment']['mathlib_commit'],'source_root':str(source.parent),
              'build_root':str(build),'imports':[module],'modules':[{'module':module,
              'source_sha256':check['source']['sha256'],'olean_sha256':bind(build/(module+'.olean'))['sha256'],
              **({'companions':companions} if companions else {})}]}
        path=root/('spec-'+module+'.json');write(path,spec)
        try:descriptor=lean_libraries.capture(path,root)
        finally:path.unlink(missing_ok=True)
        index=root/'index.json'
        value=json.loads(index.read_text()) if index.is_file() else {
            'version':'yui-imported-lean-registry-1','job':bind(root.parent/'job.json'),'entries':[]}
        value['entries'].append({'library':descriptor,'check':check['receipt']})
        write(index,value)
        lean_libraries.read_generated(root)
        return descriptor


def check(stage,source,*,upstream=None,candidate=None,publish=False,allow_publish=False):
    if type(publish) is not bool:raise ValueError('publish must be an explicit boolean')
    raw,text,origin=source_bytes(stage,source)
    request=stage.logs/'imported-lean'/('request-'+uuid.uuid4().hex);request.mkdir(parents=True)
    (request/'original.lean').write_bytes(raw);(request/'selected.lean').write_text(text);write(request/'source.json',origin)
    selected=runtime_config.require_environment();attached=lean_libraries.current()
    timeout=stage.lean_timeout() if hasattr(stage,'lean_timeout') else None
    current=compile_unit(text,selected,stage.logs/'imported-lean/checks',attachments=attached,timeout=timeout)
    result={'source':bind(request/'source.json'),'original_source':bind(request/'original.lean'),
            'selected_source':bind(request/'selected.lean'),'current_check':current['receipt'],
            'current_cache_reused':current['cache_reused']}
    checked=current
    decision=rules.decide(current)
    if decision['status']=='UPSTREAM_ENVIRONMENT_REQUIRED' and upstream is not None:
        try:old=original_environment(upstream)
        except lean_environment.SelectionRequired as error:
            result['selection_request']=error.request
        else:
            header=preamble(text)
            compatible=(environment_identity(old)==environment_identity(selected))
            old_libraries=attached if compatible else []
            context=(compile_unit(header,old,stage.logs/'imported-lean/checks',attachments=old_libraries,timeout=timeout)
                     if header is not None else None)
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
            'properties':{'lean_version':{'type':'string'},'mathlib_ref':{'type':'string'}},'required':['lean_version','mathlib_ref']},
         'candidate':{'type':'string'},'publish':{'type':'boolean'}},['source'])]
