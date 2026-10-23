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


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def signature_probe(case, identifier, declaration, module, sequence, *, timeout=120):
    """Only validated identifiers enter this trusted, sandboxed query program."""
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
    work = out / 'work'
    (work / 'input').mkdir(parents=True)
    program = '\n'.join(['import Mathlib', 'set_option pp.universes true',
        'set_option pp.explicit true', 'open Lean Elab Command in', 'run_elab do',
        '  let env ← getEnv', f'  match env.find? `{declaration} with',
        '  | some (.thmInfo _) => pure ()',
        '  | _ => throwError "This source is not a proved theorem declaration"',
        f'#eval IO.println "BEGIN_SIGNATURE:{identifier}"', f'#check @{declaration}',
        f'#eval IO.println "BEGIN_AXIOMS:{identifier}"', f'#print axioms {declaration}',
        f'#eval IO.println "END_SOURCE:{identifier}"']) + '\n'
    lean = work / 'input/LibraryProbe.lean'
    lean.write_text(program)
    started = datetime.now(timezone.utc).isoformat()
    result = run_lean(lean, work, timeout=timeout)
    (out / 'library-probe.log').write_text(result['stdout'] + result['stderr'])
    if result['exit_code']:
        raise ValueError('Library probe failed: ' + (result['stdout'] + result['stderr'])[:6000])
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
        'result': result}
    receipt = out / 'library-sources.json'
    write(receipt, report)
    return {'id': identifier, **row, 'evidence': [
        {'path': str(receipt.relative_to(case)), 'sha256': hashlib.sha256(receipt.read_bytes()).hexdigest()}]}


class NL0Contract:
    """Freeze explicit task documents and bind metadata; leave all mathematics to authors/reviewers."""
    def __init__(self, directory, documents, case_id=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.expected_inputs = []
        self.case_id = case_id
        self.attempt = 0
        for identifier, text in documents.items():
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', identifier) or identifier in {'.','..'}:
                raise ValueError('Task document ID is not a safe local filename')
            path = self.directory / 'inputs' / identifier
            path.parent.mkdir(exist_ok=True)
            path.write_text(text)
            self.expected_inputs.append({'path': str(path.relative_to(self.directory)),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

    def __call__(self, artifact):
        if set(artifact) != {'spec', 'graph'}:
            raise ValueError('NL0 artifact must have exactly spec and graph objects')
        spec, graph = deepcopy(artifact['spec']), deepcopy(artifact['graph'])
        if not isinstance(spec, dict) or not isinstance(graph, dict):
            raise ValueError('Spec and graph must be objects')
        if self.case_id is not None and spec.get('case_id') != self.case_id:
            raise ValueError('Expected spec.case_id='+repr(self.case_id)+'; received '+repr(spec.get('case_id')))
        lock = load_lock()
        # These bindings are controller metadata, never edits to mathematical content.
        spec['inputs'] = self.expected_inputs
        spec['pins'] = {'lean_version': '4.32.2', 'mathlib_commit': lock['mathlib']['rev'],
                        'mathlib_root': lock['mathlib']['local_path']}
        write(self.directory / 'spec.json', spec)
        graph['spec_sha256'] = nl0.sha(self.directory / 'spec.json')
        write(self.directory / 'nl0.json', graph)
        self.attempt += 1
        write(self.directory / f'candidate-{self.attempt:04d}.json', {'spec': spec, 'graph': graph})
        summary = nl0.validate(self.directory / 'nl0.json', self.directory / 'spec.json')[0]
        artifact.update(spec=spec, graph=graph)
        return {'status': 'NL0-STRUCTURALLY-VALID', 'summary': summary,
                'mathematical_acceptance': False,
                'note': 'Actual source fidelity, proof replay and Audit A remain required.'}
