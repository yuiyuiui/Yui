"""Structural artifact contracts for clean authoring. No mathematical PASS is generated."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import nl0
from pilot_common import run_lean
from runtime_config import load_lock
from execution_state import atomic


def write(path, value):
    atomic(path,value)


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
    return list(dict.fromkeys(errors))


def expand_submission(value, documents, drafts=None):
    """Expand explicit JSON data edits; never execute text or infer missing mathematics."""
    if set(value) == {'spec', 'graph'}:
        return deepcopy(value), None
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
    for change in value['patches']:
        if not isinstance(change, dict) or change.get('op') not in {'add', 'remove', 'replace', 'test'}:
            raise ValueError('Supported edit operations: add, remove, replace, test')
        op, pointer = change['op'], change.get('path')
        expected = {'op', 'path'} | ({'value'} if op != 'remove' else set())
        if set(change) != expected or not isinstance(pointer, str) or not pointer.startswith('/'):
            raise ValueError('Each edit needs op, an absolute JSON pointer, and value except for remove')
        if re.search(r'~(?![01])', pointer):
            raise ValueError('Invalid JSON pointer escape')
        parts = [p.replace('~1', '/').replace('~0', '~') for p in pointer[1:].split('/')]
        if parts[0] not in {'spec', 'graph'} or len(parts) < 2:
            raise ValueError('Edit a field inside spec or graph, not the submission root')
        parent = result
        try:
            for key in parts[:-1]:
                if isinstance(parent, list):
                    if not re.fullmatch(r'0|[1-9][0-9]*', key):
                        raise ValueError('Invalid array index')
                    parent = parent[int(key)]
                else:
                    parent = parent[key]
            key = parts[-1]
            if isinstance(parent, list):
                if key == '-' and op == 'add':
                    index = len(parent)
                elif re.fullmatch(r'0|[1-9][0-9]*', key):
                    index = int(key)
                else:
                    raise ValueError('Invalid array index')
                if not 0 <= index < len(parent) + (op == 'add'):
                    raise ValueError('Array index is outside the existing document')
                if op == 'add': parent.insert(index, deepcopy(change['value']))
                elif op == 'remove': parent.pop(index)
                elif op == 'replace': parent[index] = deepcopy(change['value'])
                elif parent[index] != change['value']: raise ValueError('Edit precondition does not match')
            elif isinstance(parent, dict):
                if op != 'add' and key not in parent:
                    raise ValueError('Edit path does not exist')
                if op == 'remove': del parent[key]
                elif op in {'add', 'replace'}: parent[key] = deepcopy(change['value'])
                elif parent[key] != change['value']: raise ValueError('Edit precondition does not match')
            else:
                raise ValueError('Edit parent is not a JSON container')
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError('Edit path does not resolve: ' + pointer) from error
    provenance={'base_sha256':hashlib.sha256(documents[identifier].encode()).hexdigest(),
                'patches':deepcopy(value['patches'])}
    provenance['base_candidate' if own_candidate is not None else 'base_input']=own_candidate if own_candidate is not None else identifier
    if reset:provenance['reset_base']=True
    return result,provenance


def signature_probe(case, identifier, declaration, module, sequence, *, timeout=120, use_catalog=True, on_native=None):
    """Only validated identifiers enter this trusted, sandboxed query program."""
    case=Path(case).resolve()
    if not re.fullmatch(r'M\d{3,}', identifier):
        raise ValueError('Expected an M source ID')
    atom = r"[^\W\d]\w*(?:'*)"
    if not re.fullmatch(atom + r'(?:\.' + atom + r')*', declaration, re.UNICODE):
        raise ValueError('Expected a declaration name, without Lean code')
    if not re.fullmatch(r'Mathlib(?:\.[A-Za-z][A-Za-z0-9_]*)+', module):
        raise ValueError('Expected a Mathlib module name')
    lock = load_lock()
    relative = module.replace('.', '/') + '.lean'
    source = Path(lock['mathlib']['local_path']) / relative
    if not source.is_file():
        raise ValueError('The requested module does not exist in the pinned library')
    out = Path(case) / 'library' / f'{identifier}-{sequence:04d}'
    out.mkdir(parents=True, exist_ok=False)
    if use_catalog:
        from library_catalog import cached_probe
        cached=cached_probe(identifier,declaration,module,lock)
        if cached:
            row,report=cached
            receipt=out/'library-sources.json';write(receipt,report)
            return {'id':identifier,**row,'metadata_reused':True,'evidence':[
                {'path':str(receipt.relative_to(case)),'sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()}]}
    work = out / 'work'
    (work / 'input').mkdir(parents=True)
    program = '\n'.join(['import Mathlib', 'set_option pp.universes true',
        'set_option pp.explicit false', 'open Lean Elab Command in', 'run_elab do',
        '  let env ← getEnv', f'  match env.find? `{declaration} with',
        '  | some (.thmInfo _) => pure ()',
        '  | _ => throwError "This source is not a proved theorem declaration"',
        f'  let actual ← findModuleOf? `{declaration}',
        f'  unless actual == some `{module} do',
        f'    throwError "Declaration source module differs: actual={{actual}}, requested={module}"',
        f'#eval IO.println "BEGIN_SIGNATURE:{identifier}"', f'#check @{declaration}',
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
        if 'not a proved theorem declaration' in detail:
            raise ValueError('SOURCE_KIND_MISMATCH: the declaration is available but is not a proved theorem. '
                             'Register a definition in D; source any mathematical properties separately. '+detail)
        raise ValueError('Library probe failed: ' + detail)
    signature = result['stdout'].split(f'BEGIN_SIGNATURE:{identifier}\n', 1)[1].split(f'BEGIN_AXIOMS:{identifier}\n', 1)[0].strip()
    axioms = result['stdout'].split(f'BEGIN_AXIOMS:{identifier}\n', 1)[1].split(f'END_SOURCE:{identifier}\n', 1)[0].strip()
    row = {'declaration': declaration, 'module': module, 'declaration_kind': 'theorem',
        'signature': signature, 'axioms': axioms, 'source_path': relative,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'mathlib_commit': lock['mathlib']['rev']}
    report = {'probe_version': 1, 'started_at': started,
        'finished_at': datetime.now(timezone.utc).isoformat(), 'exit_code': 0,
        'lean_version': lock['lean']['version'], 'mathlib_commit': lock['mathlib']['rev'],
        'execution_boundary': 'offline native Lean sandbox', 'sources': {identifier: row},
        'signature_display_policy':'#check @declaration preserves the complete outer implicit/typeclass/explicit telescope. Nested applications use ordinary Lean notation rather than recursively expanding every inherited structure argument; exact source bytes, environment pins and actual kernel theorem kind/axioms remain checked.',
        'result': result}
    receipt = out / 'library-sources.json'
    write(receipt, report)
    return {'id': identifier, **row, 'evidence': [
        {'path': str(receipt.relative_to(case)), 'sha256': hashlib.sha256(receipt.read_bytes()).hexdigest()}]}


class NL0Contract:
    """Bind metadata/omitted aliases; leave primary mathematical content to authors/reviewers."""
    def __init__(self, directory, documents, case_id=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.expected_inputs = []
        self.case_id = case_id
        self.attempt = 0
        self.documents = dict(documents)
        self.drafts = {}
        self.last_valid_candidate = None
        self.last_check = None
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
        if self.case_id is not None:
            for name,document in [('spec',spec),('graph',graph)]:
                if 'case_id' in document and document['case_id']!=self.case_id:
                    raise ValueError('Expected '+name+'.case_id='+repr(self.case_id)+'; received '+repr(document['case_id']))
                document['case_id']=self.case_id
        errors=preflight(spec,graph)
        if errors:raise ValueError('STRUCTURAL_PREFLIGHT:\n'+'\n'.join(errors))
        lock = load_lock()
        # Bind reproducibility metadata and explicitly omitted duplicate aliases.
        # The author's primary statements and all proof text remain unchanged.
        spec['inputs'] = self.expected_inputs
        spec['pins'] = {'lean_version': '4.32.2', 'mathlib_commit': lock['mathlib']['rev'],
                        'mathlib_root': lock['mathlib']['local_path']}
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
                continue
            identifier, source = proposition.get('id'), proposition.get('source', {})
            if not isinstance(source, dict):
                raise ValueError('FIELDS: a mathlib source must be an object')
            if not all(isinstance(value, str) and value for value in
                       (identifier, source.get('declaration'), source.get('module'))):
                raise ValueError('SOURCE-PROBE: supply an M ID, declaration and dotted module before binding metadata')
            matches = []
            for path in sorted((self.directory/'library').glob('*/library-sources.json')):
                report = json.loads(path.read_text())
                row = report.get('sources', {}).get(identifier, {})
                if (report.get('probe_version') == 1 and report.get('exit_code') == 0
                        and report.get('mathlib_commit') == lock['mathlib']['rev']
                        and row.get('declaration') == source.get('declaration')
                        and row.get('module') == source.get('module')):
                    matches.append((path, row))
            if not matches:
                raise ValueError('SOURCE-PROBE: no actual successful stage probe for '+str(identifier)+
                    '; call probe_library with this exact ID, declaration and dotted module.')
            path, row = matches[-1]
            fields = ('signature', 'declaration_kind', 'mathlib_commit', 'source_path', 'source_sha256')
            before = {key: source.get(key) for key in (*fields, 'evidence')}
            source.update({key: row[key] for key in fields})
            source['evidence'] = [{'path': str(path.relative_to(self.directory)),
                                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]
            bindings.append({'id': identifier, 'declaration': source['declaration'],
                'before': before, 'after': {key: source[key] for key in (*fields, 'evidence')}})
        write(self.directory/f'probe-bindings-{self.attempt:04d}.json', {
            'scope': 'Actual library metadata and explicitly omitted aliases only. Authored primary statements, hypotheses, definitions and arguments are unchanged; conflicting duplicates are rejected.',
            'bindings': bindings, 'omitted_aliases': aliases})
        write(self.directory / 'spec.json', spec)
        graph['spec_sha256'] = nl0.sha(self.directory / 'spec.json')
        write(self.directory / 'nl0.json', graph)
        try:
            summary = nl0.validate(self.directory / 'nl0.json', self.directory / 'spec.json')[0]
        except ValueError as error:
            self.last_check={'candidate':self.attempt,'status':'STRUCTURE_REJECTED','error':str(error)}
            write(self.directory/f'check-result-{self.attempt:04d}.json',self.last_check)
            if str(error).startswith('HYPOTHESIS:'):
                raise ValueError(str(error) + ' The comparison is against spec.hypotheses in your own '
                    'submitted artifact, not an undisclosed controller H list. Preserve its mathematical '
                    'meaning and copy each H statement exactly into the corresponding graph node; '
                    'the controller binds only inputs, pins and spec_sha256.') from error
            raise
        self.last_valid_candidate=self.attempt
        self.last_check={'candidate':self.attempt,'status':'STRUCTURE_PASSED','mathematical_acceptance':False}
        write(self.directory/f'check-result-{self.attempt:04d}.json',self.last_check)
        return {'status': 'NL0-STRUCTURALLY-VALID', 'summary': summary,
                'mathematical_acceptance': False,
                'note': 'Actual source fidelity, proof replay and Audit A remain required.'}
