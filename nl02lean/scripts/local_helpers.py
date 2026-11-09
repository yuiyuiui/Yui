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


def required(rows, text):
    """Minimal transitive helper context in original declaration order."""
    needed = set(references(text, [r['name'] for r in rows]))
    for row in reversed(rows):
        if row['name'] in needed:
            needed.update(row['dependencies'])
    return [row for row in rows if row['name'] in needed]


def validate(cpath, plan, step, rows):
    import ir
    ir.need(isinstance(rows, list), 'Local helpers must be an ordered list')
    available = []
    expected_context = context(cpath,plan,step) if rows else None
    import helper_modules
    options = helper_modules.context(cpath,plan,step) if any(isinstance(r,dict) and isinstance(r.get('check'),dict) and 'module_check' in r['check'] for r in rows) else None
    for row in rows:
        ir.need(isinstance(row, dict) and set(row) == {
            'name', 'statement', 'proof', 'dependencies', 'context_sha256', 'sha256', 'check'},
            'Invalid local helper record')
        name = row['name']
        ir.need(isinstance(name, str) and NAME.fullmatch(name) and name not in available,
                'Invalid or duplicate local helper name')
        ir.need(row['context_sha256'] == expected_context, 'Stale or foreign helper context')
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
        if 'module_check' in check:
            helper_modules.validate(options,rows[:len(available)],row)
            available.append(name)
            continue
        prefix = rows[:len(available)]
        if 'checked_helpers' in check:
            prefix = required(prefix, row['statement'] + '\n' + row['proof'])
            ir.need(check['checked_helpers'] == [r['name'] for r in prefix],
                    'Local helper receipt differs from its required dependencies')
        expected = ir.render_auxiliary(cpath, plan, step, row['statement'], row['proof'],
                                       helpers=prefix, validated=True)
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


def check_edit(stage, args, number):
    """Publish a helper edit only after all receipts still bind the resulting registry."""
    import ir
    rows = stage.local_helpers
    replace = args.get('replace')
    index = len(rows)
    if replace is not None:
        names = [row['name'] for row in rows]
        ir.need(replace in names, 'Select an existing same-node helper')
        index = names.index(replace)
        ir.need(args['statement'] == rows[index]['statement'], 'A body repair preserves the helper statement')
    prefix = list(rows[:index])
    out = stage.logs/'auxiliary-checks'/f'{number:04d}'

    def check(statement, proof, destination):
        import lean_timeout_policy
        with lean_timeout_policy.stage_scope(stage, f'yui_aux_{len(prefix)+1:04d}'):
            result = ir.check_auxiliary(stage.cpath, stage.plan, stage.step, statement, proof,
                                        out=destination, timeout=stage.lean_timeout(), helpers=prefix,
                                        cache=stage.work/'output/compiled-helpers')
        stage.lean_calls += result.get('native_calls', 1)
        if result.get('auxiliary_valid') and result.get('lean_sha256'):
            prefix.append(append(stage.cpath, stage.plan, stage.step, prefix, statement, proof, result))
        return result

    result = check(args['statement'], args['proof'], out)
    if len(prefix) == index:
        return result, None
    helper = prefix[-1]
    for row in rows[index+1:]:
        try:
            validate(stage.cpath, stage.plan, stage.step, [*prefix, row])
        except ir.Invalid:
            # A compiled module or in-file receipt may bind a changed predecessor.
            # Keep the original body and renew only receipts which no longer validate.
            renewed = check(row['statement'], row['proof'], out/'rechecked'/row['name'])
            if prefix[-1]['name'] != row['name']:
                return {**renewed, 'failed_helper': row['name']}, None
        else:
            prefix.append(row)
    from controller_common import write
    write(stage.logs/'local-helpers.json', prefix)
    stage.local_helpers = prefix
    return result, helper


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
