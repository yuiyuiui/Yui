"""Version-bound Audit A background supplements. No mathematical verdict is inferred."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import artifact_protocol as protocol
from variant import BACKGROUND_POLICY, BACKGROUND_MODE

POLICY = BACKGROUND_POLICY
MODE = BACKGROUND_MODE
GROUND_ROOTS = ('/inputs', '/parameters', '/definitions', '/logic', '/inference/locals', '/inference/argument')


def source_schema():
    return protocol.obj({**{key:protocol.TEXT for key in
        ['declaration','module','signature','source_path','source_sha256','mathlib_commit']},
        'declaration_kind':{'enum':['theorem','proved_instance']},
        'evidence':protocol.array(protocol.obj({'path':protocol.TEXT,'sha256':protocol.TEXT}),minItems=1)})


def note_schema(*, native=True):
    common={'id':{'type':'string','pattern':r'^BG\d{3,}$'},
        'at':{'type':'string','pattern':r'^/inference/argument/\d+(?:/text)?$'},
        'fact':protocol.TEXT,'justification':protocol.TEXT,
        'grounds':protocol.array(protocol.obj({'location':protocol.TEXT,'reason':protocol.TEXT}),minItems=1),
        'hint':protocol.STRING}
    variants=[(['elementary','mathematical'],{})]
    if native:variants.append((['mathlib'],{'source':source_schema()}))
    shapes=[protocol.obj({**common,'kind':{'enum':kinds},**extra},
        required=(set(common)-{'hint'})|{'kind'}|set(extra))
        for kinds,extra in variants]
    return protocol.choice(*shapes) if native else shapes[0]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def need(ok, message):
    if not ok:
        raise ValueError('BACKGROUND: '+message)


def evidence(base, rows):
    need(isinstance(rows, list) and rows, 'missing source evidence')
    result = []
    for row in rows:
        need(isinstance(row, dict) and set(row) == {'path', 'sha256'}, 'invalid evidence binding')
        path = (Path(base)/row['path']).resolve()
        need(not Path(row['path']).is_absolute() and path.is_relative_to(Path(base).resolve()), 'escaping evidence')
        need(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'], 'changed source evidence')
        result.append(path)
    return result


def source_check(source, base, pins):
    """Check actual successful pinned probe bytes; applicability is reviewed separately."""
    schema=source_schema();protocol.validate(source,schema,'/source')
    keys=set(schema['properties'])
    need(source['mathlib_commit'] == pins['mathlib_commit'], 'wrong library pin')
    need(source['source_path'] == source['module'].replace('.', '/')+'.lean', 'source module mismatch')
    need(re.match(r'^@?'+re.escape(source['declaration'])+r'(?:\.\{|\s|:)', source['signature']), 'signature names another fact')
    root = Path(pins['mathlib_root']).resolve()
    path = (root/source['source_path']).resolve()
    need(path.is_relative_to(root/'Mathlib') and path.is_file(), 'source is outside pinned Mathlib')
    need(hashlib.sha256(path.read_bytes()).hexdigest() == source['source_sha256'], 'changed Mathlib source')
    rev = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    clean = subprocess.run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--', source['source_path']], capture_output=True)
    tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '--error-unmatch', source['source_path']], capture_output=True)
    need(rev == pins['mathlib_commit'] and clean.returncode == tracked.returncode == 0, 'unqualified library checkout')
    found = False
    for p in evidence(base, source['evidence']):
        if p.suffix != '.json': continue
        row = json.loads(p.read_text())
        if row.get('probe_version') != 1 or row.get('exit_code') != 0 or row.get('mathlib_commit') != pins['mathlib_commit']: continue
        if pins['lean_version'] not in row.get('lean_version', ''): continue
        found |= any(all(value.get(k) == source[k] for k in keys-{'evidence'}) for value in row.get('sources', {}).values())
    need(found, 'no matching successful native/catalog probe')


def validate(notes, packet, base):
    """Validate identities, scope pointers and source provenance, never mathematical truth."""
    import closure
    protocol.validate(notes,protocol.array(note_schema()),'/background_notes')
    ids = set()
    for index, note in enumerate(notes):
        field = f'/background_notes/{index}'
        note_id = note['id']
        need(isinstance(note['id'], str) and re.fullmatch(r'BG\d{3,}', note['id']) and note['id'] not in ids, 'invalid/duplicate local note ID')
        ids.add(note['id'])
        need(note['kind'] in {'elementary', 'mathematical', 'mathlib'}, 'use elementary, mathematically reviewed routine facts, or explicit pinned-library facts')
        for key in ['at', 'fact', 'justification']:
            need(isinstance(note[key], str) and note[key].strip(), 'empty '+key)
        match = re.fullmatch(r'/inference/argument/(\d+)(?:/text)?', note['at'])
        need(match is not None, 'locate the actual argument step')
        try:
            closure.resolve(packet, note['at'])
        except ValueError as error:
            raise ValueError(f'{field}/at ({note_id}): {error}') from error
        need(isinstance(note['grounds'], list) and note['grounds'], 'record actual available grounds')
        for number, ground in enumerate(note['grounds']):
            need(isinstance(ground, dict) and set(ground) == {'location', 'reason'}, 'invalid local condition check')
            loc = ground['location']
            where = f'{field}/grounds/{number}/location ({note_id})'
            if not any(loc == p or loc.startswith(p+'/') for p in GROUND_ROOTS):
                raise ValueError(f'{where}: ground is not available local context ({loc!r}). '
                                 f'Use an existing packet location under {", ".join(GROUND_ROOTS)}.')
            earlier = re.match(r'/inference/argument/(\d+)', loc)
            need(not earlier or int(earlier[1]) <= int(match[1]),
                 f'{where}: {loc!r} is a future argument for {note["at"]}')
            try:
                closure.resolve(packet, loc)
            except ValueError as error:
                raise ValueError(f'{where}: {error}. Use an existing location in this packet.') from error
            need(isinstance(ground['reason'], str) and ground['reason'].strip(), 'missing actual condition explanation')
        if 'hint' in note: need(isinstance(note['hint'], str), 'invalid Lean hint')
        if note['kind'] == 'mathlib': source_check(note.get('source'), base, packet['pins'])
        else: need('source' not in note, 'non-native notes cannot carry unreviewed source bindings')
    return deepcopy(notes)


def supplement(data, by_inference):
    result = data[0]
    payload = {'policy': POLICY, 'graph_sha256': result['graph_sha256'],
               'spec_sha256': result['spec_sha256'], 'notes': deepcopy(by_inference)}
    return {**payload, 'sha256': digest(payload)}


def effective(data):
    """Derived dependency view; preserve canonical author bytes and proof paragraphs."""
    props, steps = deepcopy(data[3]), deepcopy(data[4])
    serial = 1
    sources={(p.get('source',{}).get('declaration'),p['statement']):pid for pid,p in props.items() if p['kind']=='mathlib'}
    for rid, notes in sorted(data[0].get('background_notes', {}).items()):
        need(rid in steps, 'unknown supplemented inference')
        steps[rid]['background_notes'] = deepcopy(notes)
        for note in notes:
            if note['kind'] != 'mathlib': continue
            key=(note['source']['declaration'],note['fact'])
            pid=sources.get(key)
            if pid is None:
                while f'M{serial:03d}' in props: serial += 1
                pid = f'M{serial:03d}'; serial += 1
                props[pid] = {'id': pid, 'kind': 'mathlib', 'statement': note['fact'],
                             'definitions': steps[rid]['definitions'], 'binders': [], 'objects': [],
                             'source': deepcopy(note['source']), 'background_origin': {'inference': rid, 'note': note['id']}}
                sources[key]=pid
            if pid not in steps[rid]['inputs']:steps[rid]['inputs'].append(pid)
    return props, steps


def source_from_probe(root, identifier):
    for path in sorted((Path(root)/'library').glob(identifier+'-*/library-sources.json'), reverse=True):
        row = json.loads(path.read_text())
        value = row.get('sources', {}).get(identifier)
        if row.get('exit_code') == 0 and value:
            keys = ['declaration', 'module', 'signature', 'declaration_kind', 'source_path', 'source_sha256', 'mathlib_commit']
            return {**{k: value[k] for k in keys}, 'evidence': [
                {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]}
    raise ValueError('BACKGROUND: no matching successful pinned native evidence for this source ID')
