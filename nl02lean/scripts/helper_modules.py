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
    identity = local_helpers.digest([VERSION, ir.digest(__file__), ir.AUXILIARY_PARSER, packet,
                                     {k:pins[k] for k in ('lean','mathlib','dependencies')}])
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
