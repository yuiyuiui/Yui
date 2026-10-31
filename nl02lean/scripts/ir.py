#!/usr/bin/env python3
"""Typed local obligations and final proof assembly. No model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import re
import sys
import tempfile
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'nl0/scripts'))
from pilot_common import run_lean, load_lock  # noqa: E402

VERSION = 1
SUPPORTED_VERSIONS = {1, 2}
IDENTIFIER = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
FORBIDDEN = re.compile(r'\b(sorry|admit|axiom|opaque|unsafe|run_meta|run_elab|run_tac|native_decide|set_option|initialize|elab|macro|syntax|import|namespace|section|end|theorem|lemma|instance|attribute)\b|(^|\n)\s*#')
AUXILIARY_PARSER = '''
open Lean Elab Term
elab "yui_aux_type% " text:str : term => do
  let parsed ← ofExcept <| Parser.runParserCategory (← getEnv) `term text.getString
  Term.elabTerm parsed none
'''


class Invalid(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Invalid(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, f'duplicate JSON key: {key}')
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def compact(text):
    return re.sub(r'\s+', '', text)


def type_text(value):
    need(isinstance(value, str) and bool(value.strip()), 'empty proposition/type')
    # Named arguments are ordinary Lean terms, not declaration assignments.
    assignments = re.sub(r"\(\s*[\w']+\s*:=", '(', value)
    need(not FORBIDDEN.search(value) and ':=' not in assignments,
         'command/placeholder in proposition/type')


def checked_expression(name, expression, binders='', *, proposition=False):
    """Commit an actual definition: #check alone may retain unresolved holes.

    A Prop-valued definition checks a proposition, without pretending to prove
    it or introducing an axiom. Ordinary expression probes infer their type.
    """
    term = f'∀ {binders}, ({expression})' if proposition and binders else (
        f'fun {binders} => ({expression})' if binders else expression)
    annotation = ' : Prop' if proposition else ''
    return f'def {name}{annotation} :=\n  ({term})\n'


def contract(path):
    path = Path(path).resolve()
    c = load(path)
    import background_inputs
    background_inputs.mode(c)
    need(c['version'] in SUPPORTED_VERSIONS, 'unsupported contract version')
    need(IDENTIFIER.fullmatch(c['id']) is not None, 'invalid contract id')
    source = (path.parent / c['source']['path']).resolve()
    need(source.is_file() and digest(source) == c['source']['sha256'], 'stale source bytes')
    supplement=c['source'].get('background_supplement')
    if supplement is not None or c['source'].get('background_supplement_sha256'):
        import background
        need(isinstance(supplement,dict) and supplement.get('policy')==background.POLICY,'missing/unsupported background supplement')
        need(background.digest({k:v for k,v in supplement.items() if k!='sha256'})==supplement.get('sha256')
             ==c['source'].get('background_supplement_sha256'),'changed background supplement')
    lock = load_lock()
    need(c['pins']['lean_version'] == '4.32.2' and
         c['pins']['mathlib_commit'] == lock['mathlib']['rev'], 'toolchain mismatch')
    names = [p['name'] for p in c['parameters']]
    need(len(names) == len(set(names)), 'duplicate parameter')
    for p in c['parameters']:
        need(IDENTIFIER.fullmatch(p['name']) is not None, 'invalid parameter name')
        need(p.get('binder_kind','explicit') in {'explicit','implicit','instance'}, 'invalid parameter binder kind')
        type_text(p['type'])
    ids = [p['id'] for p in c['premises']]
    need(len(ids) == len(set(ids)), 'duplicate premise')
    for p in c['premises']:
        need(re.fullmatch(r'[HEMN]\d{3}', p['id']) is not None, 'invalid premise id')
        need(p['kind'] in {'hypothesis', 'external', 'mathlib', 'internal'}, 'invalid premise kind')
        type_text(p['type'])
        need(bool(p['statement'].strip()), 'premise missing mathematical text')
    need(not set(names) & {'h_' + x for x in ids}, 'parameter/premise name collision')
    type_text(c['conclusion']['type'])
    need(bool(c['conclusion']['statement'].strip()), 'missing NL conclusion')
    steps = c['source_steps']
    need(steps and len({s['id'] for s in steps}) == len(steps), 'missing/duplicate source steps')
    need(all(s['text'].strip() for s in steps), 'missing NL argument')
    # The header is trusted reviewed input. It is never accepted from a worker.
    need(isinstance(c['header'], str) and c['header'].startswith('import '), 'missing frozen header')
    need(c['review']['mode'] in {'development_owner_review', 'upstream_audited_packet', 'deferred_semantic_review'}, 'missing review scope')
    if c['review']['mode']=='deferred_semantic_review':
        need(c['review'].get('status')=='PENDING_AUDIT_B', 'deferred semantics cannot claim a review pass')
    if c['version'] == 2:
        objects = c.get('objects', [])
        need(len({o['id'] for o in objects}) == len(objects), 'duplicate mathematical object')
        for obj in objects:
            need(re.fullmatch(r'O\d{3}', obj['id']) is not None, 'invalid object id')
            need(bool(obj['definition'].strip()), 'missing mathematical object definition')
            need(obj['views'] and len({v['id'] for v in obj['views']}) == len(obj['views']), 'duplicate/missing representation')
            for view in obj['views']:
                need(re.fullmatch(r'V\d{3}', view['id']) is not None, 'invalid representation id')
                type_text(view['lean_type'])
                need(bool(view['meaning'].strip()), 'missing representation meaning')
        shared = c.get('shared_obligations', [])
        need(len({s['id'] for s in shared}) == len(shared), 'duplicate shared lemma id')
        for s in shared:
            need(re.fullmatch(r'L\d{3}', s['id']) is not None, 'invalid shared lemma id')
            type_text(s['statement'])
            need(bool(s['route'].strip()), 'missing shared proof route')
            need(s['source_steps'] and set(s['source_steps']) <= {x['id'] for x in steps}, 'unmapped shared lemma')
            review = s['review']
            need(review['classification'] in {'existing_nl0_lemma', 'implementation_extraction'}, 'new mathematical fact requires NL0/Audit A')
            need(review['status'] in {'DEVELOPMENT_OWNER_REVIEW', 'UPSTREAM_AUDITED'}, 'unreviewed shared extraction')
            need(review['reviewer'].strip() and review['basis'].strip(), 'missing shared extraction review')
            if review['status'] == 'UPSTREAM_AUDITED':
                need(c['review']['mode'] == 'upstream_audited_packet', 'development input cannot inherit Audit A')
    return c


def validate(cpath, plan):
    c = contract(cpath)
    need(plan['version'] == c['version'], 'unsupported IR version')
    need(plan['contract_sha256'] == digest(cpath), 'stale interface contract')
    need(isinstance(plan['representation_notes'], str) and plan['representation_notes'].strip(), 'missing representation notes')
    need(plan['representation_notes'].strip().lower() not in {'choices','explain choices','explain actual choices'},
         'replace the schema placeholder with actual representation choices')
    steps = plan['steps']
    need(isinstance(steps, list) and steps, 'no transitions')
    by_id = {s['id']: s for s in steps}
    need(len(by_id) == len(steps), 'duplicate transition')
    roots = {p['id'] for p in c['premises']}
    source_ids = {s['id'] for s in c['source_steps']}
    covered = set()
    shared = {s['id']: s for s in c.get('shared_obligations', [])}
    objects = {o['id']: o for o in c.get('objects', [])}
    for s in steps:
        need(re.fullmatch(r'T\d{3}', s['id']) is not None, 'invalid transition id')
        type_text(s['statement'])
        need(isinstance(s['inputs'], list) and len(set(s['inputs'])) == len(s['inputs']), 'duplicate inputs')
        need(set(s['inputs']) <= roots | by_id.keys(), 'unregistered input')
        need(s['id'] not in s['inputs'], 'self-dependency')
        need(s['source_steps'] and set(s['source_steps']) <= source_ids, 'invalid NL correspondence')
        need(s['explanation'].strip(), 'missing transition mechanism')
        if 'background_notes' in s:
            notes={rid+'.'+n['id'] for rid,rows in c['source'].get('background_supplement',{}).get('notes',{}).items() for n in rows}
            need(isinstance(s['background_notes'],list) and len(s['background_notes'])==len(set(s['background_notes']))
                 and set(s['background_notes'])<=notes,'unknown or duplicate background note in plan')
        if 'shared_lemma' in s:
            need(c['version'] == 2 and s['shared_lemma'] in shared, 'unregistered shared lemma')
            exported = shared[s['shared_lemma']]
            need(compact(s['statement']) == compact(exported['statement']) and
                 s['inputs'] == exported['inputs'] and
                 set(s['source_steps']) == set(exported['source_steps']), 'shared interface mismatch')
        for binding in s.get('representations', []):
            need(c['version'] == 2 and binding['object'] in objects, 'unregistered mathematical object')
            obj = objects[binding['object']]
            need(binding['view'] in {v['id'] for v in obj['views']}, 'unregistered representation')
            type_text(binding['expression'])
        for bridge in s.get('bridges', []):
            need(bridge['input'] in s['inputs'], 'representation bridge is not a direct input')
            need(bridge['object'] in objects, 'unregistered bridge object')
            views = {v['id'] for v in objects[bridge['object']]['views']}
            need({bridge['from'], bridge['to']} <= views, 'unregistered bridge representation')
            need(bridge['explanation'].strip(), 'missing bridge explanation')
        covered.update(s['source_steps'])
    need(covered == source_ids, 'unmapped NL paragraph')
    terminal = plan['terminal']
    need(terminal in by_id, 'missing terminal transition')
    need(compact(by_id[terminal]['statement']) == compact(c['conclusion']['type']), 'target mismatch')
    order, visiting, done = [], set(), set()

    def visit(sid):
        if sid in roots or sid in done:
            return
        need(sid not in visiting, 'cyclic transition graph')
        visiting.add(sid)
        for dep in by_id[sid]['inputs']:
            visit(dep)
        visiting.remove(sid)
        done.add(sid)
        order.append(sid)

    visit(terminal)
    need(done == set(by_id), 'retained transition does not reach target')
    return c, by_id, order


def decomposition(cpath,plan,limit=None):
    """Source coverage concentration, never a model-time prediction."""
    c,nodes,order=validate(cpath,plan)
    total=len(c['source_steps'])
    rows=[{'id':sid,'direct_inputs':nodes[sid]['inputs'],
           'source_paragraphs':len(nodes[sid]['source_steps']),
           'source_paragraph_fraction':len(nodes[sid]['source_steps'])/total,
           'shared_lemma':nodes[sid].get('shared_lemma')} for sid in order]
    return {'jobs':rows,'typed_job_count':len(rows),'configured_proof_limit':limit,
            'largest_source_paragraph_count':max(row['source_paragraphs'] for row in rows),
            'scope':'Source coverage counts are not equal work or predicted time. Compatible shared jobs may be deduplicated. Conditional local proofs require actual final assembly.'}


def parameter_text(p):
    kind=p.get('binder_kind','explicit')
    need(kind in {'explicit','implicit','instance'}, 'invalid parameter binder kind')
    left,right={'explicit':('(',')'),'implicit':('{','}'),'instance':('[',']')}[kind]
    return left+p['name']+' : '+p['type']+right


def binder_text(c):
    return ' '.join(parameter_text(p) for p in c['parameters'])


def premises(c):
    return {p['id']: p['type'] for p in c['premises']}


def local_packet(cpath, plan, sid):
    c, nodes, _ = validate(cpath, plan)
    need(sid in nodes, 'unknown transition')
    types = {**premises(c), **{k: s['statement'] for k, s in nodes.items()}}
    step = nodes[sid]
    packet = {'version': c['version'], 'contract_sha256': digest(cpath),
            'header': c['header'], 'parameters': c['parameters'],
            'representation': c['representation'],
            'inputs': [{'id': k, 'binder': 'h_' + k, 'type': types[k]} for k in step['inputs']],
            'target': step['statement'], 'explanation': step['explanation'],
            'source_steps': [s for s in c['source_steps'] if s['id'] in step['source_steps']],
            'boundary': 'Only listed inputs are project premises. The pinned Mathlib environment is freely available; no sibling proof is supplied.'}
    supplement=c['source'].get('background_supplement')
    selected=step.get('background_notes',[])
    notes={rid+'.'+note['id']:note for rid,rows in (supplement or {}).get('notes',{}).items() for note in rows}
    need(isinstance(selected,list) and len(selected)==len(set(selected)) and set(selected)<=notes.keys(),
         'unknown or duplicate local background note')
    if selected:
        packet['accepted_background_notes']={key:notes[key] for key in selected}
        packet['background_supplement_sha256']=supplement['sha256']
    if c['version'] == 2:
        selected = {b['object'] for b in step.get('representations', [])} | {b['object'] for b in step.get('bridges', [])}
        packet['objects'] = [o for o in c.get('objects', []) if o['id'] in selected]
        packet['representations'] = step.get('representations', [])
        packet['bridges'] = step.get('bridges', [])
        exports = {s['id']: s for s in c.get('shared_obligations', [])}
        packet['shared_inputs'] = [{'input': k, 'lemma_id': nodes[k]['shared_lemma'],
            'type': types[k], 'review': exports[nodes[k]['shared_lemma']]['review']}
            for k in step['inputs'] if k in nodes and 'shared_lemma' in nodes[k]]
        if 'shared_lemma' in step:
            packet['shared_export'] = exports[step['shared_lemma']]
    return packet


def proof_text(body):
    need(isinstance(body, str) and body.strip(), 'missing proof')
    need(not FORBIDDEN.search(body), 'forbidden proof command or placeholder')
    need(not re.match(r'^\s*by(?:\s|$)', body), 'supply tactic body after by')
    # Remove the common outer margin before embedding. Stripping only the
    # first line changes Lean's layout semantics for indented multiline code.
    return textwrap.indent(textwrap.dedent(body).strip('\n'), '  ')


def render(cpath, plan, proofs=None, only=None, types_only=False):
    c, nodes, order = validate(cpath, plan)
    types = {**premises(c), **{k: s['statement'] for k, s in nodes.items()}}
    if only:
        need(only in nodes, 'unknown transition')
        order = [only]
    parser = AUXILIARY_PARSER if proofs and any(isinstance(p,dict) for p in proofs.values()) else ''
    text = c['header'].rstrip() + '\n'+parser+'\nnamespace Translation\nset_option autoImplicit false\n\n'
    context = binder_text(c)
    for sid in order:
        s = nodes[sid]
        ins = ' '.join(f'(h_{k} : {types[k]})' for k in s['inputs'])
        if types_only:
            text += checked_expression('__signature_'+sid, s['statement'],
                                       (context+' '+ins).strip(), proposition=True)
            for index, binding in enumerate(s.get('representations', [])):
                obj = next(o for o in c['objects'] if o['id'] == binding['object'])
                view = next(v for v in obj['views'] if v['id'] == binding['view'])
                text += checked_expression(f'__representation_{sid}_{index}',
                    f"({binding['expression']} : {view['lean_type']})", (context+' '+ins).strip())
        else:
            need(proofs is not None and sid in proofs, f'missing proof for {sid}')
            import local_helpers
            helpers, body = local_helpers.unpack(cpath, plan, sid, proofs[sid])
            if helpers:
                text += f'namespace Local_{sid}\n'
                text += local_helpers.declarations(helpers, (context+' '+ins).strip())
                text += f'end Local_{sid}\nopen Local_{sid} in\n'
            text += f"theorem {sid} {context} {ins} :\n    {s['statement']} := by\n{proof_text(body)}\n\n"
    if types_only and not only:
        ins = ' '.join(f"(h_{p['id']} : {p['type']})" for p in c['premises'])
        text += checked_expression('__signature_P', c['conclusion']['type'],
                                   (context+' '+ins).strip(), proposition=True)
    elif not only:
        ins = ' '.join(f"(h_{p['id']} : {p['type']})" for p in c['premises'])
        # The body may generalize universe parameters absent from its result.
        # Elaborate this assembly synchronously so declaration commit sees them.
        text += f"set_option Elab.async false in\ntheorem P {context} {ins} :\n    {c['conclusion']['type']} := by\n"
        args = ' '.join(p['name'] for p in c['parameters'])
        for sid in order:
            dep = ' '.join('h_' + k for k in nodes[sid]['inputs'])
            text += f"  have h_{sid} : {nodes[sid]['statement']} := @{sid} {args} {dep}\n"
        text += f"  exact h_{plan['terminal']}\n\n#check @P\n#print axioms P\n"
    elif only and not types_only:
        text += f'#check @{only}\n#print axioms {only}\n'
    return text + '\nend Translation\n'


def check(cpath, plan, proofs=None, only=None, types_only=False, out=None, timeout=None):
    lean = render(cpath, plan, proofs, only, types_only)
    work = Path(tempfile.mkdtemp(prefix='nl0-ir-check-')).resolve()
    try:
        (work / 'input').mkdir()
        file = work / 'output' / 'Check.lean'
        file.parent.mkdir()
        file.write_text(lean)
        result = run_lean(file, work, timeout=timeout)
        result.update({'status': 'IR-TYPES-CHECKED' if types_only else
                       'LOCAL-PROOF-CHECKED' if only else 'FRAGMENT-ASSEMBLED',
                       'contract_sha256': digest(cpath),
                       'lean_sha256': digest(file), 'scope': only or 'fragment'})
        if types_only:
            result['type_check_policy'] = 'strict-declaration-1'
        if result['exit_code'] != 0:
            result['status'] = 'LEAN-CHECK-FAILED'
        if result['exit_code'] == 0 and not types_only:
            name = only or 'P'
            m = re.search(r"'Translation\." + name + r"' depends on axioms: \[([^]]*)\]", result['stdout'])
            if m:
                actual = {v.strip() for v in m[1].split(',') if v.strip()}
            elif f"'Translation.{name}' does not depend on any axioms" in result['stdout']:
                actual = set()
            else:
                actual = {'MISSING_AXIOM_REPORT'}
            result['axioms'] = sorted(actual)
            if actual - {'propext', 'Classical.choice', 'Quot.sound'}:
                result.update({'status': 'AXIOM-CHECK-FAILED', 'exit_code': 1})
        if out:
            out = Path(out)
            out.mkdir(parents=True, exist_ok=False)
            (out / 'Check.lean').write_text(lean)
            write(out / 'result.json', result)
        return result
    finally:
        shutil.rmtree(work)


def render_auxiliary(cpath,plan,step,statement,proof,*,helpers=(),validated=False):
    """Render the exact local helper wrapper without running Lean."""
    c,nodes,_=validate(cpath,plan)
    need(step in nodes,'unknown auxiliary context port')
    need(isinstance(statement,str) and statement.strip() and not FORBIDDEN.search(statement),
         'forbidden command or placeholder in auxiliary statement')
    body=proof_text(proof)
    import local_helpers
    if not validated:local_helpers.validate(cpath,plan,step,list(helpers))
    local_helpers.references(statement+'\n'+proof,[r['name'] for r in helpers])
    types={**premises(c),**{key:value['statement'] for key,value in nodes.items()}}
    inputs=' '.join(f'(h_{key} : {types[key]})' for key in nodes[step]['inputs'])
    # Parse a complete term from a string literal. This permits ordinary letI
    # expressions without exposing a command-injection splice into Lean source.
    source=c['header'].rstrip()+'\n'+AUXILIARY_PARSER+'\nnamespace YuiAuxiliary\nset_option autoImplicit false\n'
    source+=local_helpers.declarations(helpers,(binder_text(c)+' '+inputs).strip())
    source+=f'theorem checked {binder_text(c)} {inputs} : yui_aux_type% '+json.dumps(statement,ensure_ascii=False)+' := by\n'+body+'\n'
    source+='#check @checked\n#print axioms checked\nend YuiAuxiliary\n'
    return source


def check_auxiliary(cpath,plan,step,statement,proof,*,out,timeout=None,helpers=()):
    """Check one closed helper in exactly this port's context; add no premise."""
    source=render_auxiliary(cpath,plan,step,statement,proof,helpers=helpers)
    work=Path(tempfile.mkdtemp(prefix='yui-auxiliary-')).resolve();(work/'input').mkdir();(work/'output').mkdir()
    try:
        path=work/'output/Auxiliary.lean';path.write_text(source)
        result=run_lean(path,work,timeout=timeout)
        match=re.search(r"'YuiAuxiliary.checked' depends on axioms: \[([^]]*)\]",result['stdout'])
        axioms={v.strip() for v in match[1].split(',') if v.strip()} if match else set() if "'YuiAuxiliary.checked' does not depend on any axioms" in result['stdout'] else {'MISSING_AXIOM_REPORT'}
        valid=result['exit_code']==0 and not axioms-{'propext','Classical.choice','Quot.sound'}
        result.update(auxiliary_valid=valid,axioms=sorted(axioms),
            lean_sha256=hashlib.sha256(source.encode()).hexdigest(),
            scope='AUXILIARY_ONLY_NOT_ADDED_TO_PREMISES_OR_ACCEPTED_TARGET',context_port=step)
        if result['exit_code']==0 and not valid:
            result.update(compiler_exit_code=0,exit_code=1,status='AXIOM-CHECK-FAILED')
        out=Path(out);out.mkdir(parents=True,exist_ok=False);(out/'Auxiliary.lean').write_text(source);write(out/'result.json',result)
        return result
    finally:
        shutil.rmtree(work)


def check_interface(cpath, draft, timeout=None):
    """Development oracle: compare proposed ports with owner-reviewed ports.

    This is not a semantic natural-language equivalence checker. Its frozen
    expected contract is withheld from the measured frontend worker.
    """
    c = contract(cpath)
    need([p['name'] for p in draft['parameters']] == [p['name'] for p in c['parameters']],
         'keep the specified parameter names and order')
    need([p.get('binder_kind','explicit') for p in draft['parameters']] ==
         [p.get('binder_kind','explicit') for p in c['parameters']], 'keep the specified parameter binder kinds')
    need([p['id'] for p in draft['premises']] == [p['id'] for p in c['premises']],
         'keep exactly the original premise IDs and order')
    for p in draft['parameters'] + draft['premises']:
        type_text(p['type'])
    type_text(draft['conclusion_type'])
    need(isinstance(draft['representation_notes'], str) and draft['representation_notes'].strip(),
         'missing interface representation notes')
    proposed = ' '.join(parameter_text(p) for p in draft['parameters'])
    original_inputs = ' '.join(f"(h_{p['id']} : {p['type']})" for p in c['premises'])
    proposed_inputs = ' '.join(f"(h_{p['id']} : {p['type']})" for p in draft['premises'])
    left = f"∀ {binder_text(c)} {original_inputs}, {c['conclusion']['type']}"
    right = f"∀ {proposed} {proposed_inputs}, {draft['conclusion_type']}"
    lean = c['header'] + f'\nexample : ({left}) = ({right}) := by\n  rfl\n'
    # Also check each premise and output separately; whole-implication equality
    # alone should not conceal a changed intermediate port.
    for p, q in zip(c['premises'], draft['premises']):
        lean += f"\nexample {binder_text(c)} : ({p['type']}) = ({q['type']}) := by\n  rfl\n"
    lean += f"\nexample {binder_text(c)} : ({c['conclusion']['type']}) = ({draft['conclusion_type']}) := by\n  rfl\n"
    work = Path(tempfile.mkdtemp(prefix='nl0-interface-check-')).resolve()
    try:
        (work/'input').mkdir()
        (work/'output').mkdir()
        file = work/'output/Interface.lean'
        file.write_text(lean)
        result = run_lean(file, work, timeout=timeout)
        result['status'] = 'DEVELOPMENT-INTERFACE-MATCHED' if result['exit_code'] == 0 else 'INTERFACE-MISMATCH'
        result['boundary'] = 'Definitional equality to owner-reviewed development oracle, not automatic NL semantic verification.'
        return result
    finally:
        shutil.rmtree(work)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['validate', 'packet', 'types', 'check'])
    ap.add_argument('contract', type=Path)
    ap.add_argument('plan', type=Path)
    ap.add_argument('--proofs', type=Path)
    ap.add_argument('--step')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    try:
        plan = load(a.plan)
        c, nodes, order = validate(a.contract, plan)
        if a.command == 'validate':
            result = {'status': 'IR-STRUCTURE-PASSED', 'assembly_order': order,
                      'proof_body_parallel_ready': sorted(nodes), 'semantics_automatically_checked': False}
        elif a.command == 'packet':
            result = local_packet(a.contract, plan, a.step)
        else:
            bundle = load(a.proofs) if a.proofs else None
            if bundle is not None:
                need(bundle['contract_sha256'] == digest(a.contract), 'stale proof contract')
                need(bundle['plan_sha256'] == digest(a.plan), 'stale proof plan')
            result = check(a.contract, plan, bundle['proofs'] if bundle else None,
                           a.step, a.command == 'types', a.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('exit_code', 0) == 0 else 1
    except (Invalid, KeyError, TypeError, json.JSONDecodeError) as e:
        print(json.dumps({'status': 'IR-INVALID', 'error': str(e)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
