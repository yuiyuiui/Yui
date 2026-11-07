"""Structural artifact contracts for clean authoring. No mathematical PASS is generated."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from difflib import get_close_matches
import hashlib
import json
from pathlib import Path
import re
import uuid

import nl0
import foundations
import task_proof_text
from pilot_common import run_lean
from runtime_config import load_lock
from execution_state import atomic


def write(path, value):
    atomic(path,value)


def publish_valid_pair(directory, spec, graph):
    """Publish an already validated pair; restore exact previous bytes on I/O failure."""
    values = [(Path(directory)/'spec.json', spec), (Path(directory)/'nl0.json', graph)]
    previous = {path: path.read_bytes() if path.exists() else None for path, _ in values}
    try:
        for path, value in values: write(path, value)
    except OSError as error:
        failures = []
        for path, before in previous.items():
            temporary = path.with_name('.'+path.name+'.rollback-'+uuid.uuid4().hex)
            try:
                if before is None: path.unlink(missing_ok=True)
                else:
                    temporary.write_bytes(before)
                    temporary.replace(path)
            except OSError as rollback_error:
                failures.append(str(path)+': '+str(rollback_error))
            finally:
                temporary.unlink(missing_ok=True)
        if failures:
            raise OSError('Valid-pair publication failed and rollback is unconfirmed: '+repr(failures)) from error
        raise


def preflight(spec, graph):
    """Aggregate independent, decidable reference errors before native/source work."""
    errors=[]
    props=graph.get('propositions',[]);steps=graph.get('inferences',[]);defs=spec.get('definitions',[])
    if not all(isinstance(rows,list) for rows in [props,steps,defs]):
        return ['propositions, inferences and definitions must each be lists']
    pids=[p.get('id') for p in props if isinstance(p,dict)]
    dids={d.get('id') for d in defs if isinstance(d,dict) and isinstance(d.get('id'),str)}
    valid={p for p in pids if isinstance(p,str)}
    for i,p in enumerate(props):
        if not isinstance(p,dict): errors.append(f'/graph/propositions/{i}: expected an object');continue
        if isinstance(p.get('id'),str) and pids.count(p['id'])>1:errors.append(f'/graph/propositions/{i}/id: duplicate {p["id"]}')
        for d in p.get('definitions',[]) if isinstance(p.get('definitions',[]),list) else []:
            if isinstance(d,str) and d not in dids:errors.append(f'/graph/propositions/{i}/definitions: unknown {d}; available={sorted(dids)}')
    for i,r in enumerate(steps):
        if not isinstance(r,dict):errors.append(f'/graph/inferences/{i}: expected an object');continue
        refs=(r.get('inputs',[]) if isinstance(r.get('inputs'),list) else [])+[r.get('output')]
        for p in refs:
            if isinstance(p,str) and p not in valid:errors.append(f'/graph/inferences/{i}: unknown proposition {p}; available={sorted(valid)}')
        arguments=r.get('argument',[]) if isinstance(r.get('argument'),list) else []
        positions={s.get('id'):j for j,s in enumerate(arguments)
                   if isinstance(s,dict) and isinstance(s.get('id'),str)}
        for j,local in enumerate(r.get('locals',[]) if isinstance(r.get('locals'),list) else []):
            if not isinstance(local,dict):continue
            label=local.get('scope')
            if isinstance(label,str):
                owners=set(re.findall(r'\bR\d{3,}\b',label))
                if owners-{r.get('id')}:
                    errors.append(f'/graph/inferences/{i}/locals/{j}/scope: LOCAL-SCOPE-OWNER: '
                        f'label={label!r}; actual owner={r.get("id")}; other named owners={sorted(owners-{r.get("id")})}. '
                        'A local binding belongs to this inference and its actual start/end S range; no owner or span was changed.')
            start,end=local.get('start'),local.get('end')
            if not isinstance(start,str) or not isinstance(end,str):continue
            if start not in positions or end not in positions or positions[start]>positions[end]:
                errors.append(f'/graph/inferences/{i}/locals/{j}: LOCAL-SCOPE: '+
                    f'start={start}, end={end}; actual argument IDs={list(positions)}; no scope was changed')
        for j,app in enumerate(r.get('applications',[]) if isinstance(r.get('applications'),list) else []):
            if not isinstance(app,dict):continue
            at,pid=app.get('at'),app.get('input');location=f'/graph/inferences/{i}/applications/{j}'
            if isinstance(at,str) and at not in positions:
                errors.append(location+f': APPLICATION-STEP: at={at}; actual argument IDs={list(positions)}')
            if isinstance(pid,str) and isinstance(r.get('inputs'),list) and pid not in r['inputs']:
                errors.append(location+f': APPLICATION-INPUT: input={pid}; actual direct inputs={r["inputs"]}')
            if isinstance(at,str) and at in positions and isinstance(pid,str):
                uses=arguments[positions[at]].get('uses')
                if isinstance(uses,list) and pid not in uses:
                    errors.append(location+f': APPLICATION-STEP: input={pid} is absent from {at}.uses={uses}')
        # Natural-language types and theorem names are not machine-checked
        # semantics. Audit A checks hidden hypotheses and actual applications
        # for every subject; word lists cannot establish or reject them.

    # Collect independent inventory mistakes in one reply. This intentionally
    # uses a superset of visible names; the full validator below still checks
    # definition dependencies, guards, declaration order and exact scope.
    def declared(rows):
        return {row['symbol'] for row in rows if isinstance(row,dict)
                and isinstance(row.get('symbol'),str)} if isinstance(rows,list) else set()

    logic=spec.get('logic',{})
    global_names=declared(spec.get('parameters',[])) | declared(defs)
    if isinstance(logic,dict):global_names |= declared(logic.get('primitives',[]))

    def inventory(row, available, location):
        if not isinstance(row,dict) or not isinstance(row.get('objects'),list):return
        available=available | declared(row.get('binders',[]))
        for name in row['objects']:
            if isinstance(name,str) and name not in available:
                nearby=get_close_matches(name,sorted(available),n=3,cutoff=0.65)
                errors.append(location+'/objects: undeclared '+repr(name)+
                              ('; similar declared names='+repr(nearby) if nearby else '')+
                              '; declare or consistently rename it; no mathematical identity is inferred')

    for i,row in enumerate(defs):inventory(row,global_names,f'/spec/definitions/{i}')
    for i,row in enumerate(props):inventory(row,global_names,f'/graph/propositions/{i}')
    for i,r in enumerate(steps):
        if not isinstance(r,dict):continue
        available=global_names | declared(r.get('locals',[]))
        for j,row in enumerate(r.get('locals',[]) if isinstance(r.get('locals'),list) else []):
            inventory(row,available,f'/graph/inferences/{i}/locals/{j}')
        for j,row in enumerate(r.get('argument',[]) if isinstance(r.get('argument'),list) else []):
            location=f'/graph/inferences/{i}/argument/{j}'
            inventory(row,available,location)
            if not isinstance(row,dict):continue
            for k,fact in enumerate(row.get('produces',[]) if isinstance(row.get('produces'),list) else []):
                inventory(fact,available,location+f'/produces/{k}')
    return list(dict.fromkeys(errors))


def edit_mismatch(pointer, expected, actual, parent, document):
    try:
        collection = nl0.closure.resolve(document, pointer.rsplit('/', 2)[0])
        if isinstance(collection, list): parent = collection
    except (KeyError, ValueError, TypeError, IndexError):
        pass
    records = []
    if isinstance(parent, list):
        records = [{'index': i, **{k: row[k] for k in ['id', 'symbol', 'scope'] if k in row}}
                   for i, row in enumerate(parent) if isinstance(row, dict)]
    elif isinstance(parent, dict):
        records = [{k: parent[k] for k in ['id', 'symbol', 'scope'] if k in parent}]
    render = lambda value: json.dumps(value, ensure_ascii=False)[:1500]
    raise ValueError('Edit precondition does not match at '+pointer+
                     '; expected='+render(expected)+'; actual='+render(actual)+
                     '; current records='+render(records))


def replace_text(current, change, pointer):
    old, new = change['old'], change['new']
    if not all(isinstance(value, str) for value in [current, old, new]) or not old:
        raise ValueError('replace_text needs an existing string and nonempty old plus string new: '+pointer)
    count = len(re.findall('(?='+re.escape(old)+')', current))
    if count != 1:
        raise ValueError('replace_text requires exactly one literal match at '+pointer+'; found '+str(count)+
                         '. No edits were applied. Actual current text='+repr(current[:4000])+
                         (' [read the same-stage pointer for the remainder]' if len(current)>4000 else '')+
                         '. For multiline/escaped text, use read_draft with start_line/end_line then replace_lines with its text_sha256; do not guess another escaped old string.')
    return current.replace(old, new, 1)


def own_text_lines(value, start, end):
    """Bounded view of an existing own string, including its exact line endings."""
    if not isinstance(value, str):
        raise ValueError('Line view requires an existing string at the selected own pointer')
    lines = value.splitlines(keepends=True)
    if (type(start) is not int or type(end) is not int or
            not 1 <= start <= end or start > len(lines) or end-start >= 250):
        raise ValueError('Choose up to 250 existing positive inclusive lines; total_lines='+str(len(lines)))
    requested_end=end
    end=min(end,len(lines))
    selected = lines[start-1:end]
    if sum(map(len, selected)) > 20000:
        raise ValueError('Selected lines exceed 20000 characters; choose a smaller line range')
    return {'text_sha256': hashlib.sha256(value.encode()).hexdigest(), 'total_lines': len(lines),
            'requested_range':{'start_line':start,'end_line':requested_end},
            'actual_range':{'start_line':start,'end_line':end},
            'lines': [{'line': i, 'text': lines[i-1]} for i in range(start, end+1)]}


def replace_lines(current, change, pointer):
    """Explicit byte-preserving line splice, never a mathematical text repair."""
    text = change['text']
    if not isinstance(current, str) or not isinstance(text, str):
        raise ValueError('replace_lines requires existing and replacement strings: '+pointer)
    actual = hashlib.sha256(current.encode()).hexdigest()
    if change['text_sha256'] != actual:
        raise ValueError('replace_lines complete-string hash is stale at '+pointer+
                         '; read this exact candidate/pointer again; actual text_sha256='+actual)
    lines = current.splitlines(keepends=True)
    start, end = change['start_line'], change['end_line']
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise ValueError('replace_lines needs existing positive inclusive lines at '+pointer+
                         '; total_lines='+str(len(lines)))
    if end < len(lines) and text and not text.endswith(('\r', '\n')):
        raise ValueError('replace_lines before retained lines needs its intended line terminator; no newline was added: '+pointer)
    return ''.join(lines[:start-1])+text+''.join(lines[end:])


def own_path_context(value, prefix):
    """Only bounded keys/identities from the actually reached own value."""
    details = {'deepest_existing_prefix': prefix or '/', 'value_type': type(value).__name__}
    if isinstance(value, list):
        details['total_items'] = len(value)
        details['records'] = [{'index': i, **{k: row[k] for k in ['id', 'symbol'] if k in row}}
                              for i, row in enumerate(value[:16]) if isinstance(row, dict)]
        details['hint'] = 'Use an actual existing @ID/@symbol selector; no edit was redirected.'
    elif isinstance(value, dict):
        details['keys'] = list(value)[:24]
    return json.dumps(details, ensure_ascii=False)


def array_index(rows, key, *, insertion=False):
    """Resolve explicit same-stage record identity; never fuzzy-match a name."""
    if key.startswith('@'):
        if insertion:raise ValueError('Use a numeric index or /- for array insertion; @ selectors identify existing records')
        found=[i for i,row in enumerate(rows) if isinstance(row,dict) and key[1:] in {row.get('id'),row.get('symbol')}]
        if len(found)!=1:
            raise ValueError('Record selector '+repr(key)+' needs exactly one existing id/symbol; matches='+repr(found))
        return found[0]
    if not re.fullmatch(r'0|[1-9][0-9]*',key):raise ValueError('Use an array index or unique @ID/@symbol selector')
    return int(key)


def resolve_own(value, pointer):
    """Own-author view selector, separate from standard Audit A JSON pointers."""
    if not isinstance(pointer,str) or not pointer.startswith('/') or re.search(r'~(?![01])',pointer):
        raise ValueError('Expected an own-draft JSON pointer with valid escapes')
    traversed = []
    for raw in pointer[1:].split('/'):
        key=raw.replace('~1','/').replace('~0','~')
        try:
            child=value[array_index(value,key)] if isinstance(value,list) else value[key]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError('Own path does not resolve: '+pointer+'; '+str(error)+'; '+
                             own_path_context(value, '/'+ '/'.join(traversed) if traversed else '')) from error
        value=child
        traversed.append(raw)
    return value


def bind_source_uses(value, uses):
    """Serialize one author-declared call into its three canonical reference views."""
    if not isinstance(uses,list) or not uses:
        raise ValueError('source_uses must be a nonempty list of explicit author-declared applications')
    graph=value.get('graph',{})
    def find(rows,identifier,label):
        matches=[row for row in rows if isinstance(row,dict) and row.get('id')==identifier] if isinstance(rows,list) else []
        if len(matches)!=1:raise ValueError('SOURCE_USE: expected exactly one '+label+' '+repr(identifier))
        return matches[0]
    for call in uses:
        from artifact_protocol import validate
        from payload_protocols import source_use_schema
        validate(call,source_use_schema(),'/source_uses')
        r=find(graph.get('inferences',[]),call['inference'],'inference')
        s=find(r.get('argument',[]),call['at'],'paragraph')
        p=find(graph.get('propositions',[]),call['input'],'source')
        if p.get('kind') not in {'mathlib','external'}:
            raise ValueError('SOURCE_USE: select an existing M/E source, not a new assumption or conclusion')
        if not isinstance(call['bindings'],str) or not call['bindings'].strip() or not isinstance(call['hypothesis_checks'],list) or any(not isinstance(x,str) or not x.strip() for x in call['hypothesis_checks']):
            raise ValueError('SOURCE_USE: bindings and every condition check must be explicit nonempty text')
        if not all(isinstance(x,list) for x in [r.get('inputs'),s.get('uses'),r.get('applications')]):
            raise ValueError('SOURCE_USE: existing inputs, uses and applications must be lists')
        app={key:deepcopy(call[key]) for key in ['input','at','bindings','hypothesis_checks']}
        if 'id' in call:app['id']=call['id']
        identical=app in r['applications']
        identity=app.get('id',app['input'])
        if not identical and any(a.get('id',a.get('input'))==identity for a in r['applications'] if isinstance(a,dict)):
            raise ValueError('SOURCE_USE: application identity already exists; use a distinct actual-use id for another instantiation, or patch the existing record explicitly')
        if call['input'] not in r['inputs']:r['inputs'].append(call['input'])
        if call['input'] not in s['uses']:s['uses'].append(call['input'])
        if not identical:r['applications'].append(app)


def submission_schema():
    from payload_protocols import editable, OBJECT
    from artifact_protocol import obj
    # The author language is normalized and checked by NL0Contract._validate.
    # These objects are deliberately drafts, not already-normalized NL0 files.
    return editable(obj({'spec':OBJECT,'graph':OBJECT}),source_uses=True)


def expand_submission(value, documents, drafts=None):
    """Expand explicit JSON data edits; never execute text or infer missing mathematics."""
    from artifact_protocol import validate
    validate(value,submission_schema())
    if set(value) == {'spec', 'graph'}:
        return deepcopy(value), None
    if set(value)=={'base_candidate','source_uses'}:
        number=value['base_candidate']
        if type(number) is not int or not drafts or number not in drafts:
            raise ValueError('base_candidate must name an existing candidate from this same stage')
        result=json.loads(drafts[number],object_pairs_hook=nl0.unique_object)
        bind_source_uses(result,value['source_uses'])
        return result,{'base_candidate':number,'base_sha256':hashlib.sha256(drafts[number].encode()).hexdigest(),
                       'operation':'explicit_source_use_binding','source_uses':deepcopy(value['source_uses'])}
    if set(value)=={'accept_candidate'}:
        number=value['accept_candidate']
        if type(number) is not int or not drafts or number not in drafts:
            raise ValueError('accept_candidate must name an existing candidate from this same stage')
        return json.loads(drafts[number],object_pairs_hook=nl0.unique_object), {
            'base_candidate':number,'base_sha256':hashlib.sha256(drafts[number].encode()).hexdigest(),
            'patches':[],'operation':'resubmit_exact_own_candidate'}
    own_candidate = None
    if set(value) == {'base_candidate', 'patches'}:
        number=value['base_candidate']
        if type(number) is not int or not drafts or number not in drafts:
            raise ValueError('base_candidate must name an existing candidate from this same stage')
        own_candidate=number
        documents={'same-stage-candidate':drafts[number]}
        value={'base_input':'same-stage-candidate','patches':value['patches']}
    if set(value)=={'base_input','patches','reset_base'}:
        if value['reset_base'] is not True:raise ValueError('reset_base must be explicitly true')
        value={k:v for k,v in value.items() if k!='reset_base'}
        reset=True
    else:reset=False
    if drafts and own_candidate is None and set(value)=={'base_input','patches'} and not reset:
        raise ValueError('This stage already has candidate_number '+str(max(drafts))+
            '. Use base_candidate to preserve your accumulated proof edits. To deliberately discard them and restart from a frozen input, include reset_base:true.')
    if (set(value) != {'base_input', 'patches'} or not isinstance(value['base_input'], str)
            or value['base_input'] not in documents):
        raise ValueError('Expected {spec,graph} or {base_input:<frozen task ID>,patches:[JSON edits]}')
    identifier = value['base_input']
    base = json.loads(documents[identifier], object_pairs_hook=nl0.unique_object)
    if not isinstance(base, dict) or set(base) != {'spec', 'graph'}:
        raise ValueError('Patch base must be an explicit frozen {spec,graph} task document')
    if not isinstance(value['patches'], list) or not value['patches']:
        raise ValueError('Supply a nonempty list of explicit edits')
    result = deepcopy(base)
    for edit_index, change in enumerate(value['patches']):
        if not isinstance(change, dict) or change.get('op') not in {'add', 'remove', 'replace', 'test', 'replace_text', 'replace_lines'}:
            raise ValueError('Supported edit operations: add, remove, replace, test, replace_text, replace_lines')
        op, pointer = change['op'], change.get('path')
        from payload_protocols import edit_schema
        expected=set(next(branch['properties'] for branch in edit_schema()['anyOf'] if branch['properties']['op']['const']==op))
        if set(change) != expected or not isinstance(pointer, str) or not pointer.startswith('/'):
            raise ValueError(f'EDIT_FIELDS: /patches/{edit_index}, op={op!r}, path={pointer!r}; '
                f'missing={sorted(expected-set(change))}; unexpected={sorted(set(change)-expected)}; '
                f'exact fields={sorted(expected)}. path must be an absolute JSON pointer. '
                'For replace_lines, use the complete text_sha256 from read_draft on this exact base candidate; no hash or edit is inferred.')
        if re.search(r'~(?![01])', pointer):
            raise ValueError('Invalid JSON pointer escape')
        parts = [p.replace('~1', '/').replace('~0', '~') for p in pointer[1:].split('/')]
        if parts[0] not in {'spec', 'graph'} or len(parts) < 2:
            raise ValueError('Edit a field inside spec or graph, not the submission root')
        parent = resolve_own(result, pointer.rsplit('/', 1)[0])
        try:
            key = parts[-1]
            if isinstance(parent, list):
                if key == '-' and op == 'add':
                    index = len(parent)
                else:
                    index=array_index(parent,key,insertion=op=='add')
                if not 0 <= index < len(parent) + (op == 'add'):
                    raise ValueError('Array index is outside the existing document at '+pointer+'; '+
                                     own_path_context(parent, pointer.rsplit('/', 1)[0]))
                if op == 'add': parent.insert(index, deepcopy(change['value']))
                elif op == 'remove': parent.pop(index)
                elif op == 'replace': parent[index] = deepcopy(change['value'])
                elif op == 'replace_text': parent[index] = replace_text(parent[index], change, pointer)
                elif op == 'replace_lines': parent[index] = replace_lines(parent[index], change, pointer)
                elif parent[index] != change['value']: edit_mismatch(pointer, change['value'], parent[index], parent, result)
            elif isinstance(parent, dict):
                if op != 'add' and key not in parent:
                    raise ValueError('Edit path does not exist: '+pointer+'; '+
                                     own_path_context(parent, pointer.rsplit('/', 1)[0]))
                if op == 'remove': del parent[key]
                elif op in {'add', 'replace'}: parent[key] = deepcopy(change['value'])
                elif op == 'replace_text': parent[key] = replace_text(parent[key], change, pointer)
                elif op == 'replace_lines': parent[key] = replace_lines(parent[key], change, pointer)
                elif parent[key] != change['value']: edit_mismatch(pointer, change['value'], parent[key], parent, result)
            else:
                raise ValueError('Edit parent is not a JSON container')
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError('Edit path does not resolve: '+pointer+'; '+
                             own_path_context(parent, pointer.rsplit('/', 1)[0])) from error
    provenance={'base_sha256':hashlib.sha256(documents[identifier].encode()).hexdigest(),
                'patches':deepcopy(value['patches'])}
    provenance['base_candidate' if own_candidate is not None else 'base_input']=own_candidate if own_candidate is not None else identifier
    if reset:provenance['reset_base']=True
    return result,provenance


def reserve_probe_directory(case, identifier, sequence):
    """Reserve fresh evidence atomically, including after inherited probes."""
    if not re.fullmatch(r'M\d{3,}', identifier) or type(sequence) is not int or sequence < 1:
        raise ValueError('Expected an M source ID and a positive probe sequence')
    root = Path(case).resolve() / 'library'
    if root.is_symlink():
        raise OSError('Probe evidence root must not be a symbolic link')
    root.mkdir(parents=True, exist_ok=True)
    while True:
        out = root / f'{identifier}-{sequence:04d}'
        try:
            out.mkdir()
            return out
        except FileExistsError:
            if out.is_symlink() or not out.is_dir():
                raise OSError('Probe evidence reservation encountered an unsafe occupied path: '+str(out))
            # A prior receipt, failed query or concurrent caller owns this
            # directory. Never overwrite it or infer that its query matches.
            sequence += 1


def signature_probe(case, identifier, declaration, module, sequence, *, timeout=None, use_catalog=True, on_native=None):
    """Only validated identifiers enter this trusted, sandboxed query program."""
    case=Path(case).resolve()
    if not re.fullmatch(r'M\d{3,}', identifier):
        raise ValueError('Expected an M source ID')
    atom = r"[^\W\d]\w*(?:'*)"
    if not re.fullmatch(atom + r'(?:\.' + atom + r')*', declaration, re.UNICODE):
        raise ValueError('Expected a declaration name, without Lean code')
    if module is not None and not re.fullmatch(r'Mathlib(?:\.[A-Za-z][A-Za-z0-9_]*)+', module):
        raise ValueError('Expected a dotted Mathlib module name, for example Mathlib.Topology.Basic; '
                         'received '+repr(module)+'. Omit this optional locator hint to resolve the actual native module. Paths and Lean code are not accepted.')
    lock = load_lock()
    out = reserve_probe_directory(case, identifier, sequence)
    if use_catalog:
        from library_catalog import cached_probe
        cached=cached_probe(identifier,declaration,module,lock)
        if cached:
            row,report=cached
            report['requested_selector']={'declaration':declaration,'module_hint':module}
            receipt=out/'library-sources.json';write(receipt,report)
            return {'id':identifier,**row,'metadata_reused':True,'evidence':[
                {'path':str(receipt.relative_to(case)),'sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()}]}
    work = out / 'work'
    (work / 'input').mkdir(parents=True)
    program = '\n'.join(['import Mathlib', 'set_option pp.universes true',
        'set_option pp.explicit false', 'open Lean Elab Command in', 'run_elab do',
        f'  let name ← resolveGlobalConstNoOverloadCore `{declaration}',
        '  let info ← getConstInfo name',
        '  match info with',
        '  | .thmInfo _ => pure ()',
        '  | _ => throwError "This source is not a proved theorem declaration"',
        '  let actual ← findModuleOf? name',
        f'  IO.println s!"RESOLVED_NAME:{identifier}:{{name}}"',
        '  match actual with',
        f'  | some source => IO.println s!"RESOLVED_MODULE:{identifier}:{{source}}"',
        '  | none => throwError "This source has no imported module"',
        f'  IO.println "BEGIN_SIGNATURE:{identifier}"',
        '  let printed ← Meta.ppExpr info.type',
        '  IO.println s!"@{name} : {printed}"',
        f'#eval IO.println "BEGIN_AXIOMS:{identifier}"', f'#print axioms {declaration}',
        f'#eval IO.println "END_SOURCE:{identifier}"']) + '\n'
    lean = work / 'input/LibraryProbe.lean'
    lean.write_text(program)
    started = datetime.now(timezone.utc).isoformat()
    if on_native:on_native()
    result = run_lean(lean, work, timeout=timeout)
    (out / 'library-probe.log').write_text(result['stdout'] + result['stderr'])
    if result['exit_code'] and ('sandbox-exec:' in result['stderr'] or result['exit_code'] in {126,127}):
        raise OSError('Native Lean probe execution failed: '+result['stderr'][:6000])
    if result['exit_code']:
        detail=(result['stdout'] + result['stderr'])[:6000]
        if 'Unknown source declaration' in detail or 'Unknown constant' in detail or 'Unknown identifier' in detail:
            raise ValueError('SOURCE_NOT_FOUND: this exact declaration name does not exist in the pinned environment. '
                             'Search and inspect the real namespace/name; do not register a guessed name as a D definition. '+detail)
        if 'not a proved theorem declaration' in detail:
            raise ValueError('SOURCE_KIND_MISMATCH: the declaration is available but is not a proved theorem. '
                             'Register a definition in D; source any mathematical properties separately. '+detail)
        raise ValueError('Library probe failed: ' + detail)
    canonical=re.search(r'^RESOLVED_NAME:'+identifier+r':(.+)$',result['stdout'],re.M)
    locator=re.search(r'^RESOLVED_MODULE:'+identifier+r':(.+)$',result['stdout'],re.M)
    if not canonical or not locator:raise OSError('Native source probe returned no resolved declaration/module metadata')
    canonical,module_actual=canonical[1].strip(),locator[1].strip()
    if not re.fullmatch(r'Mathlib(?:\.[A-Za-z][A-Za-z0-9_]*)+',module_actual):
        raise ValueError('SOURCE_MODULE: only a proved declaration from an actual pinned Mathlib source is accepted')
    relative=module_actual.replace('.','/')+'.lean'
    source=Path(lock['mathlib']['local_path'])/relative
    if not source.is_file():raise OSError('Actual native Mathlib source file is missing')
    signature = result['stdout'].split(f'BEGIN_SIGNATURE:{identifier}\n', 1)[1].split(f'BEGIN_AXIOMS:{identifier}\n', 1)[0].strip()
    axioms = result['stdout'].split(f'BEGIN_AXIOMS:{identifier}\n', 1)[1].split(f'END_SOURCE:{identifier}\n', 1)[0].strip()
    row = {'declaration': canonical, 'module': module_actual, 'declaration_kind': 'theorem',
        'signature': signature, 'axioms': axioms, 'source_path': relative,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'mathlib_commit': lock['mathlib']['rev']}
    report = {'probe_version': 1, 'started_at': started,
        'finished_at': datetime.now(timezone.utc).isoformat(), 'exit_code': 0,
        'lean_version': lock['lean']['version'], 'mathlib_commit': lock['mathlib']['rev'],
        'execution_boundary': 'offline native Lean sandbox', 'sources': {identifier: row},
        'requested_selector':{'declaration':declaration,'module_hint':module},
        'signature_display_policy':'Native Meta.ppExpr prints the canonical declaration type and its complete outer implicit/typeclass/explicit telescope. Nested applications use ordinary Lean notation rather than recursively expanding every inherited structure argument; exact source bytes, environment pins and actual kernel theorem kind/axioms remain checked.',
        'result': result}
    receipt = out / 'library-sources.json'
    write(receipt, report)
    return {'id': identifier, **row, 'evidence': [
        {'path': str(receipt.relative_to(case)), 'sha256': hashlib.sha256(receipt.read_bytes()).hexdigest()}]}


class NL0Contract:
    """Bind metadata/omitted aliases; leave primary mathematical content to authors/reviewers."""
    def __init__(self, directory, documents, case_id=None, *, global_only=False):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.expected_inputs = []
        self.case_id = case_id
        self.global_only = global_only
        self.attempt = 0
        self.documents = dict(documents)
        self.drafts = {}
        self.valid_drafts = {}
        from author_check import AuthorCheck
        self.author_check=AuthorCheck(self)
        self.last_valid_candidate = None
        self.last_check = None
        self.schema=submission_schema()
        for identifier, text in documents.items():
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', identifier) or identifier in {'.','..'}:
                raise ValueError('Task document ID is not a safe local filename')
            path = self.directory / 'inputs' / identifier
            path.parent.mkdir(exist_ok=True)
            path.write_text(text)
            self.expected_inputs.append({'path': str(path.relative_to(self.directory)),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

    def __call__(self, artifact):
        expanded, patch = expand_submission(artifact, self.documents, self.drafts)
        self.attempt+=1
        write(self.directory/f'candidate-{self.attempt:04d}.json',expanded)
        self.drafts[self.attempt]=json.dumps(expanded,ensure_ascii=False)
        if patch is not None:
            write(self.directory/f'submission-edits-{self.attempt:04d}.json', patch)
        try:
            result=self._validate(expanded)
        except ValueError as error:
            self.last_check={'candidate':self.attempt,'status':'STRUCTURE_REJECTED','error':str(error)}
            write(self.directory/f'check-result-{self.attempt:04d}.json',self.last_check)
            raise
        finally:
            # Preserve authored edits even when a later metadata/source check fails.
            write(self.directory/f'candidate-{self.attempt:04d}.json',expanded)
            self.drafts[self.attempt]=json.dumps(expanded,ensure_ascii=False)
        artifact.clear();artifact.update(expanded)
        return result

    def _validate(self, expanded):
        spec, graph = expanded['spec'], expanded['graph']
        if not isinstance(spec, dict) or not isinstance(graph, dict):
            raise ValueError('Spec and graph must be objects')
        copied=task_proof_text.materialize(graph,self.documents,spec=spec)
        write(self.directory/f'task-text-bindings-{self.attempt:04d}.json',{
            'scope':'Exact declared same-stage input text only. Copying does not establish object/dependency closure or mathematical correctness.',
            'bindings':copied})
        foundations.bind_author(spec.get('logic'))
        if 'target-selection.json' in self.documents:
            selected=json.loads(self.documents['target-selection.json'])
            if spec.get('full_target')!=selected['full_target']:
                raise ValueError('TARGET_SELECTION: full_target must preserve the complete selected target verbatim')
        if self.case_id is not None:
            for name,document in [('spec',spec),('graph',graph)]:
                if 'case_id' in document and document['case_id']!=self.case_id:
                    raise ValueError('Expected '+name+'.case_id='+repr(self.case_id)+'; received '+repr(document['case_id']))
                document['case_id']=self.case_id
        errors=[] if self.global_only else preflight(spec,graph)
        if errors:raise ValueError('STRUCTURAL_PREFLIGHT:\n'+'\n'.join(errors))
        lock = load_lock()
        # Bind reproducibility metadata and explicitly omitted duplicate aliases.
        # The author's primary statements and all proof text remain unchanged.
        spec['inputs'] = self.expected_inputs
        spec['pins'] = {'lean_version': '4.32.2', 'mathlib_commit': lock['mathlib']['rev'],
                        'mathlib_root': lock['mathlib']['local_path']}
        if 'proof-context.json' in self.documents:
            import basis
            context=json.loads(self.documents['proof-context.json'])
            registry=basis.verify_context(context)
            if spec['full_target']!=context['full_target']:
                raise ValueError('Basis NL0 changed the original target')
            basis.basis_graph.verify_handoff(registry,graph)
            expected={r['port']:r['statement'] for r in registry['dependencies'] if r['port'] and r['port'].startswith('E')}
            actual={p['id']:p['statement'] for p in graph['propositions'] if p['kind']=='external'}
            if actual!=expected:raise ValueError('Basis NL0 changed the frozen E statements')
        # The author selects a declaration and writes its mathematical meaning.
        # Exact Lean printer output and evidence hashes come from actual probes,
        # rather than an error-prone model transcription of thousands of bytes.
        bindings, aliases = [], []
        propositions = graph.get('propositions', [])
        if not isinstance(propositions, list):
            raise ValueError('FIELDS: graph.propositions must be a list')
        hypotheses = {row['id']: row['statement'] for row in spec.get('hypotheses', [])
                      if isinstance(row, dict) and 'id' in row and 'statement' in row}
        for proposition in propositions:
            if not isinstance(proposition, dict):
                raise ValueError('FIELDS: each proposition must be an object')
            identifier, kind = proposition.get('id'), proposition.get('kind')
            if 'statement' not in proposition:
                if kind == 'hypothesis' and identifier in hypotheses:
                    proposition['statement'] = hypotheses[identifier]
                    aliases.append({'id': identifier, 'field': 'statement', 'from': 'spec.hypotheses'})
                elif kind == 'target' and 'conclusion' in spec:
                    proposition['statement'] = spec['conclusion']
                    aliases.append({'id': identifier, 'field': 'statement', 'from': 'spec.conclusion'})
            if kind in {'mathlib', 'external'} and isinstance(proposition.get('source'), dict):
                source = proposition['source']
                if 'statement' not in source and 'statement' in proposition:
                    source['statement'] = proposition['statement']
                    aliases.append({'id': identifier, 'field': 'source.statement', 'from': 'proposition.statement'})
                elif source.get('statement') != proposition.get('statement'):
                    raise ValueError('SOURCE: source restatement mismatch '+str(identifier)+
                        '. Both texts are authored in this artifact, not an unavailable library source. '
                        'Primary proposition.statement='+repr(proposition.get('statement'))+
                        '; duplicate source.statement='+repr(source.get('statement'))+
                        '. They must match exactly. You may omit source.statement to serialize a copy '
                        'of the primary statement; actual source fidelity is reviewed against the probe/primary document.')
            if proposition.get('kind') != 'mathlib':
                if proposition.get('kind')=='external' and source.get('verification'):
                    from source_qualification import load_bound
                    reference=source['verification']['record']
                    deferred=json.loads(load_bound(self.directory,reference).read_text())
                    source['evidence']=list({(row['path'],row['sha256']):row for row in
                        [*source.get('evidence',[]),reference,deferred['basis'],*deferred['attempts']]}.values())
                continue
            identifier, source = proposition.get('id'), proposition.get('source', {})
            if not isinstance(source, dict):
                raise ValueError('FIELDS: a mathlib source must be an object')
            if not all(isinstance(value, str) and value for value in (identifier, source.get('declaration'))):
                raise ValueError('SOURCE-PROBE: supply an M ID and actual declaration selector before binding metadata')
            if not re.fullmatch(r'M\d{3,}',identifier):
                raise ValueError('SOURCE-PROBE: a source ID must have the safe Mddd form before any metadata binding')
            matches = []
            for path in sorted((self.directory/'library').glob('*/library-sources.json')):
                report = json.loads(path.read_text())
                sources=report.get('sources',{})
                if (report.get('probe_version') != 1 or report.get('exit_code') != 0
                        or report.get('mathlib_commit') != lock['mathlib']['rev']):continue
                for original_id,row in sources.items():
                    # A report-level alias describes its sole actual source,
                    # never an absent ID or another row in a multi-source file.
                    selectors={row.get('declaration')}
                    if len(sources)==1:selectors.add(report.get('requested_selector',{}).get('declaration'))
                    if row and source.get('declaration') in selectors:
                        matches.append((path,row,original_id,report))
            if not matches:
                raise ValueError('SOURCE-PROBE: no actual successful stage probe for '+str(identifier)+
                    '; call probe_library with this exact ID and declaration. A module is an optional locator hint; the native resolver binds its actual module.')
            exact_id=[match for match in matches if match[2]==identifier]
            path,row,original_id,report=(exact_id or matches)[-1]
            if original_id!=identifier:
                original_path=path;original_hash=hashlib.sha256(path.read_bytes()).hexdigest()
                rebound=deepcopy(report);rebound['sources']={identifier:deepcopy(row)}
                rebound['metadata_reuse']={
                    'original_source_id':report.get('metadata_reuse',{}).get('original_source_id',original_id),
                    'previous_bound_source_id':original_id,
                    'stage_evidence_path':str(original_path.relative_to(self.directory)),
                    'stage_evidence_sha256':original_hash,
                    'original_native_cost_seconds':report['result']['wall_seconds'],
                    'parent_reuse':report.get('metadata_reuse'),
                    'scope':'Exact same-stage native theorem metadata ID remapping only; no new source acquisition, NL statement or applicability approval.'}
                path=self.directory/'library'/f'bound-{identifier}-{original_hash[:16]}'/'library-sources.json'
                path.parent.mkdir(parents=True,exist_ok=True);write(path,rebound)
            fields = ('declaration','module','signature', 'declaration_kind', 'mathlib_commit', 'source_path', 'source_sha256')
            before = {key: source.get(key) for key in (*fields, 'evidence')}
            source.update({key: row[key] for key in fields})
            source['evidence'] = [{'path': str(path.relative_to(self.directory)),
                                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]
            bindings.append({'id': identifier, 'declaration': source['declaration'],
                'before': before, 'after': {key: source[key] for key in (*fields, 'evidence')}})
        write(self.directory/f'probe-bindings-{self.attempt:04d}.json', {
            'scope': 'Actual library metadata and explicitly omitted aliases only. Authored primary statements, hypotheses, definitions and arguments are unchanged; conflicting duplicates are rejected.',
            'bindings': bindings, 'omitted_aliases': aliases})
        # Validate beside the case evidence, without replacing the last valid
        # handover files with an unaccepted draft.
        token = uuid.uuid4().hex
        staged_spec = self.directory / ('.validation-spec-'+token+'.json')
        staged_graph = self.directory / ('.validation-nl0-'+token+'.json')
        try:
            write(staged_spec, spec)
            graph['spec_sha256'] = nl0.sha(staged_spec)
            write(staged_graph, graph)
            summary = nl0.validate(staged_graph, staged_spec, global_only=self.global_only)[0]
        except ValueError as error:
            self.last_check={'candidate':self.attempt,'status':'STRUCTURE_REJECTED','error':str(error)}
            write(self.directory/f'check-result-{self.attempt:04d}.json',self.last_check)
            if str(error).startswith('HYPOTHESIS:'):
                raise ValueError(str(error) + ' The comparison is against spec.hypotheses in your own '
                    'submitted artifact, not an undisclosed controller H list. Preserve its mathematical '
                    'meaning and copy each H statement exactly into the corresponding graph node; '
                    'the controller binds only inputs, pins and spec_sha256.') from error
            raise
        finally:
            staged_spec.unlink(missing_ok=True)
            staged_graph.unlink(missing_ok=True)
        publish_valid_pair(self.directory, spec, graph)
        import source_qualification
        if not self.global_only:
            source_qualification.publish(self.directory,nl0.validate(self.directory/'nl0.json',self.directory/'spec.json'))
        self.last_valid_candidate=self.attempt
        self.valid_drafts[self.attempt]=deepcopy(expanded)
        self.last_check={'candidate':self.attempt,'status':'STRUCTURE_PASSED','mathematical_acceptance':False}
        write(self.directory/f'check-result-{self.attempt:04d}.json',self.last_check)
        return {'status': 'GLOBAL-GRAPH-STRUCTURALLY-VALID' if self.global_only else 'NL0-STRUCTURALLY-VALID', 'summary': summary,
                'mathematical_acceptance': False,
                'note': 'Actual source fidelity, proof replay and Audit A remain required.'}
