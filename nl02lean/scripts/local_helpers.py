"""Bound, same-node helper declarations. Every exported body is compiled again."""
from __future__ import annotations

import hashlib
import json
import re

SCHEMA = 'yui-local-proof-1'
NAME = re.compile(r'\byui_aux_[0-9]{4,}\b')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def context(cpath, plan, step):
    import ir
    return digest(ir.local_packet(cpath, plan, step))


def references(text, available):
    import ir
    found = set(NAME.findall(text))
    ir.need(found <= set(available), 'Missing, forward, cyclic or foreign-node helper reference')
    return sorted(found)


def validate(cpath, plan, step, rows):
    import ir
    ir.need(isinstance(rows, list), 'Local helpers must be an ordered list')
    available = []
    for row in rows:
        ir.need(isinstance(row, dict) and set(row) == {
            'name', 'statement', 'proof', 'dependencies', 'context_sha256', 'sha256', 'check'},
            'Invalid local helper record')
        name = row['name']
        ir.need(isinstance(name, str) and NAME.fullmatch(name) and name not in available,
                'Invalid or duplicate local helper name')
        ir.need(row['context_sha256'] == context(cpath, plan, step), 'Stale or foreign helper context')
        ir.need(isinstance(row['statement'], str) and row['statement'].strip()
                and not ir.FORBIDDEN.search(row['statement']), 'Invalid helper statement')
        ir.proof_text(row['proof'])
        deps = references(row['statement']+'\n'+row['proof'], available)
        ir.need(row['dependencies'] == deps, 'Changed local helper dependencies')
        payload = {k: row[k] for k in ('name', 'statement', 'proof', 'dependencies', 'context_sha256')}
        ir.need(row['sha256'] == digest(payload), 'Changed local helper source')
        check = row['check']
        ir.need(isinstance(check, dict) and check.get('exit_code') == 0
                and check.get('auxiliary_valid') is True
                and not set(check.get('axioms', [])) - {'propext', 'Classical.choice', 'Quot.sound'},
                'Local helper has no successful native check')
        expected = ir.render_auxiliary(cpath, plan, step, row['statement'], row['proof'],
                                       helpers=rows[:len(available)], validated=True)
        ir.need(check.get('lean_sha256') == hashlib.sha256(expected.encode()).hexdigest(),
                'Local helper native receipt differs from its exact source')
        available.append(name)
    return rows


def append(cpath, plan, step, rows, statement, proof, check):
    import ir
    validate(cpath, plan, step, rows)
    ir.need(check.get('exit_code') == 0 and check.get('auxiliary_valid') is True,
            'Only a successfully checked helper can be registered')
    name = f'yui_aux_{len(rows)+1:04d}'
    payload = {'name': name, 'statement': statement, 'proof': proof,
               'dependencies': references(statement+'\n'+proof, [r['name'] for r in rows]),
               'context_sha256': context(cpath, plan, step)}
    row = {**payload, 'sha256': digest(payload), 'check': dict(check)}
    validate(cpath, plan, step, [*rows, row])
    return row


def package(cpath, plan, step, body, rows):
    import ir
    ir.proof_text(body)
    validate(cpath, plan, step, rows)
    references(body, [r['name'] for r in rows])
    if not rows:
        return body
    return {'schema': SCHEMA, 'step': step, 'context_sha256': context(cpath, plan, step),
            'helpers': json.loads(json.dumps(rows)), 'body': body}


def unpack(cpath, plan, step, value):
    import ir
    if isinstance(value, str):
        ir.proof_text(value)
        return [], value
    ir.need(isinstance(value, dict) and set(value) == {'schema','step','context_sha256','helpers','body'}
            and value['schema'] == SCHEMA and value['step'] == step,
            'Invalid same-node proof package')
    ir.need(value['context_sha256'] == context(cpath, plan, step), 'Proof package context changed')
    rows = validate(cpath, plan, step, value['helpers'])
    ir.proof_text(value['body'])
    references(value['body'], [r['name'] for r in rows])
    return rows, value['body']


def declarations(rows, binders):
    import ir
    return ''.join(f"theorem {r['name']} {binders} : yui_aux_type% {json.dumps(r['statement'],ensure_ascii=False)} := by\n{ir.proof_text(r['proof'])}\n\n"
                   for r in rows)


def as_tactic(value, obligation):
    """Close an exact shared-proof alias without importing another node's module."""
    import ir
    if isinstance(value, str):return value
    binders = ' '.join([ir.parameter_text(p) for p in obligation['parameters']]+
                      [f"({p['binder']} : {p['type']})" for p in obligation['inputs']])
    return ''.join(f"have {r['name']} {binders} : ({r['statement']}) := by\n{ir.proof_text(r['proof'])}\n"
                   for r in value['helpers'])+value['body']
