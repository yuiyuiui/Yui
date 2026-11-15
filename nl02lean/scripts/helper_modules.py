"""Case-local compiled helper prefixes. Receipts remain verifiable from the final source."""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import time

import ir
import local_helpers
import runtime_config

VERSION = 'yui-helper-module-1'
ALLOWED = {'propext', 'Classical.choice', 'Quot.sound'}
PROOF_MODULE_VERSION = 'yui-compiled-proof-1'


def proof_module_spec(source, checks):
    """Keep expected expressions in their original private/notation context."""
    import lean_libraries
    import lean_environment
    import pilot_common
    namespace = 'YuiExpected' + local_helpers.digest([source, checks])
    body = source + '\nnamespace '+namespace+'\n'
    converted = []
    for index, (key, selector, expected, parts) in enumerate(checks):
        name = namespace+'.item_'+str(index)
        body += 'def item_'+str(index)+' : Prop := ('+expected+')\n'
        converted.append((key, selector, 'value:'+name, parts))
    body += 'end '+namespace+'\n'
    identity = {'schema':PROOF_MODULE_VERSION, 'source_sha256':digest(source),
        'compiled_source_sha256':digest(body), 'logical_checks':checks,
        'environment':lean_environment.identity(runtime_config.require_environment()),
        'dependencies':runtime_config.load_lock()['dependencies'], 'libraries':lean_libraries.identity(),
        'tools':{Path(p).name:ir.digest(p) for p in
            (__file__, ir.__file__, pilot_common.__file__)},
        'options':{'jobs':1, 'max_heartbeats':runtime_config.native_heartbeats()}}
    name = 'YuiProof'+local_helpers.digest(identity)
    return name, body, converted, identity


def verify_proof_module(path, source, checks):
    path = Path(path)
    row = ir.load(path)
    name, body, converted, identity = proof_module_spec(source, checks)
    ir.need(row.get('identity') == json.loads(json.dumps(identity)) and row.get('name') == name
            and row.get('compiled_only') is True and ir.native_succeeded(row.get('native', {})),
            'Changed or incomplete compiled proof module')
    ir.need(row.get('checks') == json.loads(json.dumps(converted)), 'Changed compiled signature bindings')
    required = {name+'.lean', name+'.olean'}
    ir.need(required <= row.get('artifacts', {}).keys(), 'Incomplete compiled proof output')
    for filename, sha in row['artifacts'].items():
        ir.need(filename in {name+suffix for suffix in
            ('.lean', '.olean', '.olean.private', '.olean.server', '.ilean')}, 'Unexpected compiled module file')
        file = path.parent/filename
        ir.need(file.is_file() and not file.is_symlink() and ir.digest(file) == sha,
                'Changed compiled proof artifact: '+filename)
    ir.need((path.parent/(name+'.lean')).read_text() == body, 'Compiled module no longer matches its exact source')
    return row


def compile_proof_module(source, checks, out, work):
    """Case-owned reuse only. Compilation alone never grants Audit B acceptance."""
    import shutil
    from execution_state import current
    from controller_common import bind, write
    recorder, task = current()
    if recorder:recorder.check(task)
    name, body, converted, identity = proof_module_spec(source, checks)
    root = recorder.root if recorder else Path(out)
    cache = root/'compiled-proofs'/name
    cache.mkdir(parents=True, exist_ok=True)
    ir.need(not cache.is_symlink(), 'Compiled proof cache cannot be a symbolic link')
    receipt = cache/'module.json'
    target = Path(work)/'output'
    target.mkdir(parents=True, exist_ok=True)
    with (cache/'compile.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        reused = receipt.is_file()
        cache_source=cache/(name+'.lean')
        if cache_source.exists():
            ir.need(not cache_source.is_symlink() and cache_source.read_text()==body, 'Changed compiled proof input')
        else:cache_source.write_text(body)
        link = {'schema':PROOF_MODULE_VERSION, 'name':name, 'checks':converted,
                'logical_checks':checks, 'source':bind(cache_source), 'reused':reused, 'receipt':None}
        write(Path(out)/'compiled-module.json', link)
        if reused:
            row = verify_proof_module(receipt, source, checks)
            for filename in row['artifacts']:shutil.copyfile(cache/filename, target/filename)
            native = dict(row['native'])
        else:
            file = target/(name+'.lean');file.write_text(body)
            native = ir.run_lean(file, Path(work), output=file.with_suffix('.olean'))
            if ir.native_succeeded(native):
                artifacts = {}
                for suffix in ('.lean', '.olean', '.olean.private', '.olean.server', '.ilean'):
                    file = target/(name+suffix)
                    if file.is_file():
                        shutil.copyfile(file, cache/file.name)
                        artifacts[file.name] = ir.digest(file)
                row = {'name':name, 'identity':identity, 'checks':converted, 'artifacts':artifacts,
                       'native':native, 'compiled_only':True,
                       'scope':'Stable source compilation only; signatures, full dependencies and trust still require native inspection.'}
                if recorder:recorder.check(task)
                write(receipt, row)
                verify_proof_module(receipt, source, checks)
        link['receipt']=bind(receipt) if receipt.exists() else None
        write(Path(out)/'compiled-module.json', link)
    if recorder:recorder.check(task)
    return native, link


def compiled_input(out):
    """The exact failed or successful compiler input, including expected types."""
    from controller_common import verify_bindings
    out = Path(out)
    link = ir.load(out/'compiled-module.json')
    ir.need(link.get('schema')==PROOF_MODULE_VERSION, 'Unknown compiled proof input')
    verify_bindings([link['source']])
    name,body,converted,_=proof_module_spec((out/'Proof.lean').read_text(),link['logical_checks'])
    file=Path(link['source']['path'])
    ir.need(name==link['name'] and file.name==name+'.lean' and file.read_text()==body
            and link['checks']==json.loads(json.dumps(converted)), 'Changed actual assembly input')
    return file


def bound_proof_module(out):
    from controller_common import verify_bindings
    out = Path(out)
    compiled_input(out)
    link = ir.load(out/'compiled-module.json')
    ir.need(link.get('schema') == PROOF_MODULE_VERSION and link.get('receipt'), 'Missing compiled proof receipt')
    verify_bindings([link['receipt']])
    row = verify_proof_module(link['receipt']['path'], (out/'Proof.lean').read_text(), link['logical_checks'])
    ir.need(link['name'] == row['name'] and link['checks'] == row['checks'], 'Changed compiled module link')
    return link


def _code(text):
    """Erase comments/strings for conservative command-scope inspection."""
    out=[];i=0;depth=0;quoted=False
    while i<len(text):
        pair=text[i:i+2];ch=text[i]
        if depth:
            if pair=='/-':depth+=1;out.extend('  ');i+=2;continue
            if pair=='-/':depth-=1;out.extend('  ');i+=2;continue
            out.append('\n' if ch=='\n' else ' ');i+=1;continue
        if quoted:
            if ch=='\\':out.extend('  ');i+=2;continue
            if ch=='"':quoted=False
            out.append('\n' if ch=='\n' else ' ');i+=1;continue
        if pair=='/-':depth=1;out.extend('  ');i+=2;continue
        if pair=='--':
            end=text.find('\n',i);end=len(text) if end<0 else end
            out.extend(' '*(end-i));i=end;continue
        if ch=='"':quoted=True;out.append(' ');i+=1;continue
        out.append(ch);i+=1
    return ''.join(out)


def replay(header, internal=''):
    """Replay visible scope after importing the compiled public declarations."""
    if internal:
        return None
    code=_code(header)
    if re.search(r'\b(private|variable|variables|local|include|omit|set_option|notation|macro|syntax|attribute)\b',code):
        return None
    frames=[]
    commands=[]
    for line in code.splitlines():
        value=line.strip()
        if not value or value=='import Mathlib':
            continue
        if re.fullmatch(r'namespace\s+[\w.]+|(?:noncomputable\s+)?section(?:\s+\w+)?',value):
            frames.append((value,len(commands)))
            if value.startswith('noncomputable section'):
                commands.append('noncomputable section')
        elif re.fullmatch(r'end(?:\s+[\w.]+)?',value):
            if not frames:return None
            _,previous=frames.pop()
            del commands[previous:]
        elif re.fullmatch(r'(?:open(?: scoped)?|universe)\s+[\w.]+(?:\s+[\w.]+)*',value) and ' in ' not in value:
            commands.append(value)
        elif re.match(r'(?:noncomputable )?(?:def|abbrev|structure|class|inductive)\s',value):
            continue
        elif value.startswith(('open ','namespace ','section ','end ','import ','set_option ')) or not line[0].isspace():
            return None
    if any(name!='noncomputable section' for name,_ in frames):return None
    return '\n'.join(commands+['open Lean Elab Term'])


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def context(cpath, plan, step):
    packet = ir.local_packet(cpath, plan, step)
    preamble = replay(packet['header'], packet.get('internal_type_context'))
    if preamble is None:
        return None
    pins = runtime_config.load_lock()
    import lean_libraries
    identity = local_helpers.digest([VERSION, ir.digest(__file__), ir.AUXILIARY_PARSER, packet,
                                     {k:pins[k] for k in ('lean','mathlib','dependencies')},lean_libraries.identity()])
    binders = ' '.join([ir.binder_text(ir.contract(cpath))] +
                       [f"({p['binder']} : {p['type']})" for p in packet['inputs']]).strip()
    return identity, packet['header'], preamble, binders


def prefix(identity, rows):
    return 'YuiHelpers' + local_helpers.digest([identity, [r['sha256'] for r in rows]])


def candidate(options, rows, name, statement, proof):
    identity, _, preamble, binders = options
    parent = prefix(identity, rows)
    decl = {'name':name, 'statement':statement, 'proof':proof}
    source = ('import '+parent+'\n'+preamble+'\nnamespace YuiAuxiliary\nset_option autoImplicit false\n'
              +local_helpers.declarations([decl], binders)+'#print axioms '+name+'\nend YuiAuxiliary\n')
    return source, {'version':VERSION, 'context':identity, 'parent':parent, 'name':name,
                    'source_sha256':digest(source)}


def validate(options, rows, row):
    ir.need(options is not None, 'Compiled helper context changed')
    source, receipt = candidate(options, rows, row['name'], row['statement'], row['proof'])
    ir.need(row['check']['module_check'] == receipt and row['check']['lean_sha256'] == digest(source),
            'Compiled helper receipt differs from its exact source')


def axiom_set(stdout, name):
    target = "'YuiAuxiliary."+name+"'"
    match = re.search(re.escape(target)+r' depends on axioms: \[([^]]*)\]', stdout)
    if match:
        return {s.strip() for s in match[1].split(',') if s.strip()}
    return set() if target+' does not depend on any axioms' in stdout else {'MISSING_AXIOM_REPORT'}


def checked_module(directory, name, visited):
    if not (directory/(name+'.json')).is_file():return False
    chain=set()
    while name and name not in visited:
        if name in chain or not re.fullmatch(r'YuiHelpers[0-9a-f]{64}',name):
            raise RuntimeError('Invalid or cyclic helper module manifest')
        chain.add(name)
        file=directory/(name+'.json')
        if file.is_symlink() or not file.is_file():raise RuntimeError('Missing imported helper module')
        row=ir.load(file)
        if (row.get('name')!=name or row.get('result',{}).get('exit_code')!=0
                or row['result'].get('auxiliary_valid') is not True or set(row['result'].get('axioms',[]))-ALLOWED):
            raise RuntimeError('Invalid successful helper module manifest')
        for ext in ('.lean','.olean'):
            artifact=directory/(name+ext)
            if artifact.is_symlink() or not artifact.is_file() or ir.digest(artifact)!=row[ext]:
                raise RuntimeError('Changed owned compiled helper '+name+ext)
        parent=row['parent']
        if parent and not (directory/(name+'.lean')).read_text().startswith('import '+parent+'\n'):
            raise RuntimeError('Changed helper import chain')
        name=parent
    visited.update(chain)
    return True


def check(options, cpath, plan, step, statement, proof, rows, out, timeout, *, cache=None):
    begin = time.monotonic()
    identity, header, _, binders = options
    work = (Path(cache) if cache else Path(out).resolve().parent/'compiled-helpers')/identity
    directory = work/'output'
    directory.mkdir(parents=True, exist_ok=True)
    parent = prefix(identity, rows)
    name = f'yui_aux_{len(rows)+1:04d}'
    source, receipt = candidate(options,rows,name,statement,proof)
    payload = {'name':name,'statement':statement,'proof':proof,'context_sha256':local_helpers.context(cpath,plan,step),
               'dependencies':local_helpers.references(statement+'\n'+proof,[r['name'] for r in rows])}
    target = prefix(identity,[*rows,{'sha256':local_helpers.digest(payload)}])
    calls = 0

    def compile_one(module, body, previous, names):
        nonlocal calls
        path = directory/(module+'.lean')
        path.write_text(body)
        calls += 1
        result = ir.run_lean(path,work,extra=[directory],output=path.with_suffix('.olean'),timeout=timeout)
        axioms = set().union(*(axiom_set(result['stdout'],n) for n in names))
        valid = result['exit_code']==0 and not axioms-ALLOWED
        result.update(auxiliary_valid=valid,axioms=sorted(axioms))
        if result['exit_code']==0 and not valid:
            result.update(status='AXIOM-CHECK-FAILED',exit_code=1,compiler_exit_code=0)
        if valid:
            manifest = {'name':module,'parent':previous,'.lean':ir.digest(path),'.olean':ir.digest(path.with_suffix('.olean')),
                        'result':result}
            temporary = path.with_suffix('.tmp')
            ir.write(temporary,manifest)
            temporary.replace(path.with_suffix('.json'))
        return result

    with (work/'compile.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        visited = set()
        if checked_module(directory,target,visited):
            result = ir.load(directory/(target+'.json'))['result']
        else:
            if not checked_module(directory,parent,visited):
                base = (header.rstrip()+'\n'+ir.AUXILIARY_PARSER+'\nnamespace YuiAuxiliary\nset_option autoImplicit false\n'
                        +local_helpers.declarations(rows,binders)
                        +''.join('#print axioms '+r['name']+'\n' for r in rows)+'end YuiAuxiliary\n')
                bootstrap = compile_one(parent,base,None,[r['name'] for r in rows])
                if bootstrap['exit_code']:
                    # Keep the native fault or candidate diagnostic for the owner.
                    source, result = base, bootstrap
                    result['cache_bootstrap_failed'] = True
                else:
                    result = compile_one(target,source,parent,[name])
            else:
                result = compile_one(target,source,parent,[name])
    result = {**result,'native_calls':calls,'incremental_seconds':time.monotonic()-begin,
              'module_check':receipt,'lean_sha256':digest(source),'context_port':step,
              'scope':'AUXILIARY_ONLY_NOT_ADDED_TO_PREMISES_OR_ACCEPTED_TARGET'}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'Auxiliary.lean').write_text(source)
    ir.write(out/'result.json',result)
    return result
