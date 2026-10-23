#!/usr/bin/env python3
"""Project-local, content-addressed conditional Lean proofs. No model calls.

The first implementation rechecks source at each use; it does not cache .olean
files or infer mathematical equivalence. The store is an explicit task input.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time

import ir


def hashed(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def obligation(cpath, plan, sid):
    c, nodes, _ = ir.validate(cpath, plan)
    step = nodes[sid]
    ir.need('shared_lemma' in step, 'step has no reviewed shared export')
    packet = ir.local_packet(cpath, plan, sid)
    record = next(x for x in c['shared_obligations'] if x['id'] == step['shared_lemma'])
    return {'pins': c['pins'], 'header': c['header'], 'parameters': c['parameters'],
            'inputs': packet['inputs'], 'target': step['statement'],
            'objects': packet.get('objects', []),
            'representations': packet.get('representations', []),
            'bridges': packet.get('bridges', []), 'route': record['route']}


def signature_key(value):
    """Conservative typed/route key; only binder alpha-renaming is normalized."""
    replacements = {p['name']: f'param_{i}' for i, p in enumerate(value['parameters'])}
    replacements.update({p['binder']: f'premise_{i}' for i, p in enumerate(value['inputs'])})

    def normalize(text):
        return re.sub(r'\b[A-Za-z][A-Za-z0-9_]*\b',
                      lambda m: replacements.get(m[0], m[0]), text)

    # Binder names/IDs themselves are not mathematical assumptions. All types,
    # equality modes, header bytes, route and representation records remain.
    canonical = {'pins': value['pins'], 'header_sha256': hashlib.sha256(value['header'].encode()).hexdigest(),
                 'parameters': [normalize(p['type']) for p in value['parameters']],
                 'inputs': [normalize(p['type']) for p in value['inputs']],
                 'target': normalize(value['target']),
                 'objects': value['objects'], 'representations': value['representations'],
                 'bridges': value['bridges'], 'route': value['route']}
    return hashed(canonical)


def quantified(value):
    binders = [f"({p['name']} : {p['type']})" for p in value['parameters']]
    binders += [f"({p['binder']} : {p['type']})" for p in value['inputs']]
    return ('∀ ' + ' '.join(binders) + ', ' if binders else '') + value['target']


def reuse_body(entry, requested):
    ir.need(signature_key(entry['obligation']) == signature_key(requested), 'incompatible cached interface')
    old = entry['obligation']
    names = [p['name'] for p in old['parameters']] + [p['binder'] for p in old['inputs']]
    # The old binders are introduced inside a closed local theorem. No textual
    # rewrite of a tactic body's bound variables or shadowing is attempted.
    taken = {p['name'] for p in requested['parameters']} | {p['binder'] for p in requested['inputs']}
    local_name = 'shared_cached'
    while local_name in taken:
        local_name += '_proof'
    body = f"have {local_name} : {quantified(old)} := by\n"
    if names:
        body += '  intro ' + ' '.join(names) + '\n'
    body += ir.proof_text(entry['proof']) + '\n'
    args = [p['name'] for p in requested['parameters']] + [p['binder'] for p in requested['inputs']]
    return body + f'exact {local_name}' + ((' ' + ' '.join(args)) if args else '')


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = self.root / 'index.json'
        with self.locked():
            if not self.index.exists():
                ir.write(self.index, {'version': 1, 'entries': {}})

    @contextlib.contextmanager
    def locked(self):
        with (self.root / '.index.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def snapshot(self):
        with self.locked():
            return {'index_sha256': ir.digest(self.index), 'index': ir.load(self.index)}

    def lookup(self, requested):
        start = time.monotonic()
        key = signature_key(requested)
        with self.locked():
            index = ir.load(self.index)
            ir.need(index['version'] == 1, 'unsupported shared index')
            row = index['entries'].get(key)
            entry = None
            reason = 'NOT_FOUND'
            if row is not None:
                # Paths are derived from the typed key, never from mutable JSON.
                directory = self.root / 'objects' / key
                source = self.root / 'Shared' / f'L{key}.lean'
                metadata = directory / 'entry.json'
                try:
                    ir.need(ir.digest(metadata) == row['entry_sha256'], 'changed entry')
                    entry = ir.load(metadata)
                    ir.need(entry['status'] == 'VERIFIED_LEAN_CONDITIONAL', 'unverified entry')
                    ir.need(entry['key'] == key == signature_key(entry['obligation']), 'changed interface')
                    ir.need(ir.digest(source) == entry['module_sha256'], 'changed module')
                    ir.need(hashed(entry['proof']) == entry['proof_sha256'], 'changed proof')
                    ir.need(ir.digest(directory/'verification.json') == entry['verification_sha256'], 'changed verification')
                    ir.need(ir.digest(directory/'module-verification.json') == entry['module_verification_sha256'], 'changed module verification')
                    ir.need(ir.load(directory/'module-verification.json')['exit_code'] == 0, 'failed module verification')
                    receipt = ir.load(directory/'verification.json')
                    ir.need(receipt['exit_code'] == 0 and receipt['status'] == 'LOCAL-PROOF-CHECKED', 'failed verification')
                    ir.need(not set(receipt['axioms']) - {'propext', 'Classical.choice', 'Quot.sound'}, 'unpermitted axioms')
                    reason = 'EXACT_TYPED_ROUTE_MATCH'
                except (OSError, ir.Invalid, KeyError, TypeError, ValueError):
                    entry, reason = None, 'INVALIDATED_ARTIFACT'
            receipt = {'key': key, 'status': 'HIT' if entry else 'MISS', 'reason': reason,
                       'index_sha256': ir.digest(self.index), 'lookup_seconds': time.monotonic()-start}
        return entry, receipt

    def admit(self, cpath, plan, sid, proof, checked=None):
        start = time.monotonic()
        value = obligation(cpath, plan, sid)
        ir.proof_text(proof)
        key = signature_key(value)
        prior, _ = self.lookup(value)
        if checked is None and prior is not None and prior['proof_sha256'] == hashed(proof):
            return {'status': 'ALREADY_PRESENT', 'key': key, 'registration_seconds': time.monotonic()-start}
        # Only controller-produced check receipts may be reused internally.
        # The public CLI always performs its own Lean check.
        checked = checked if checked is not None else ir.check(cpath, plan, {sid: proof}, only=sid)
        ir.need(checked['exit_code'] == 0 and checked['status'] == 'LOCAL-PROOF-CHECKED', 'unproved shared lemma')
        expected_lean = ir.render(cpath, plan, {sid: proof}, only=sid)
        ir.need(checked['lean_sha256'] == hashlib.sha256(expected_lean.encode()).hexdigest(), 'verification/proof mismatch')
        ir.need(checked['contract_sha256'] == ir.digest(cpath), 'verification/contract mismatch')
        ir.need(not set(checked['axioms']) - {'propext', 'Classical.choice', 'Quot.sound'}, 'unpermitted shared axioms')
        c = ir.contract(cpath)
        packet = ir.local_packet(cpath, plan, sid)
        module = value['header'] + '\nnamespace Shared\nset_option autoImplicit false\n\n'
        binders = ir.binder_text(c) + ' ' + ' '.join(f"({p['binder']} : {p['type']})" for p in value['inputs'])
        module += f"theorem L{key} {binders} : {value['target']} := by\n{ir.proof_text(proof)}\n\nend Shared\n"
        with tempfile.TemporaryDirectory(prefix='shared-module-') as temp_work:
            work = Path(temp_work)
            (work/'input').mkdir()
            (work/'output').mkdir()
            file = work/'output'/'Shared.lean'
            file.write_text(module + f'\n#check @Shared.L{key}\n#print axioms Shared.L{key}\n')
            module_check = ir.run_lean(file, work)
            ir.need(module_check['exit_code'] == 0, 'generated shared module failed Lean')
            match = re.search(r"'Shared\.L" + key + r"' depends on axioms: \[([^]]*)\]", module_check['stdout'])
            if match:
                axioms = {x.strip() for x in match[1].split(',') if x.strip()}
            elif f"'Shared.L{key}' does not depend on any axioms" in module_check['stdout']:
                axioms = set()
            else:
                axioms = {'MISSING_AXIOM_REPORT'}
            module_check['axioms'] = sorted(axioms)
            ir.need(not axioms - {'propext', 'Classical.choice', 'Quot.sound'}, 'unpermitted shared module axioms')
        entry = {'version': 1, 'status': 'VERIFIED_LEAN_CONDITIONAL', 'key': key,
                 'declaration': f'Shared.L{key}', 'obligation': value, 'full_type': quantified(value),
                 'proof': proof, 'proof_sha256': hashed(proof),
                 'module_sha256': hashlib.sha256(module.encode()).hexdigest(),
                 'provenance': {'contract_sha256': ir.digest(cpath), 'source': c['source'],
                                'source_steps': packet['source_steps'], 'shared_export': packet['shared_export'],
                                'review': c['review']},
                 'audit_b': 'NOT_PERFORMED',
                 'cost': {'verification_seconds': checked['wall_seconds'],
                          'module_verification_seconds': module_check['wall_seconds']}}
        with self.locked():
            index = ir.load(self.index)
            if key in index['entries']:
                return {'status': 'ALREADY_PRESENT', 'key': key, 'registration_seconds': time.monotonic()-start}
            temp = Path(tempfile.mkdtemp(prefix='.admit-', dir=self.root))
            try:
                ir.write(temp/'verification.json', checked)
                ir.write(temp/'module-verification.json', module_check)
                entry['verification_sha256'] = ir.digest(temp/'verification.json')
                entry['module_verification_sha256'] = ir.digest(temp/'module-verification.json')
                ir.write(temp/'entry.json', entry)
                final = self.root/'objects'/key
                final.parent.mkdir(exist_ok=True)
                ir.need(not final.exists(), 'unindexed shared artifact; inspect before recovery')
                temp.rename(final)
                (self.root/'Shared').mkdir(exist_ok=True)
                (self.root/'Shared'/f'L{key}.lean').write_text(module)
                index['entries'][key] = {'entry_sha256': ir.digest(final/'entry.json'),
                                         'declaration': entry['declaration']}
                pending = self.root/'index.pending.json'
                ir.write(pending, index)
                pending.replace(self.index)
            finally:
                if temp.exists():
                    shutil.rmtree(temp)
        return {'status': 'REGISTERED', 'key': key, 'registration_seconds': time.monotonic()-start}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['lookup', 'admit'])
    ap.add_argument('store', type=Path)
    ap.add_argument('contract', type=Path)
    ap.add_argument('plan', type=Path)
    ap.add_argument('--step', required=True)
    ap.add_argument('--proof', type=Path)
    args = ap.parse_args()
    store = Store(args.store)
    plan = ir.load(args.plan)
    if args.command == 'admit':
        ir.need(args.proof is not None, 'provide a tactic-body file')
        result = store.admit(args.contract, plan, args.step, args.proof.read_text())
    else:
        entry, result = store.lookup(obligation(args.contract, plan, args.step))
        if entry:
            result['full_type'] = entry['full_type']
            result['declaration'] = entry['declaration']
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
