#!/usr/bin/env python3
"""Allowlisted NL0 factoring and evidence-bound incremental Audit A.

The parent mathematical standard remains unchanged. Hashes and graph checks do not
perform mathematical review. New producers use the ordinary fresh-packet gate;
changed consumers use located substitution reviews, with explicit inheritance.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
import shutil
import sys
import tempfile
import time

import ir
from shared_lemmas import hashed

PARENT = Path(__file__).resolve().parents[2] / 'nl0/scripts'
sys.path.insert(0, str(PARENT))
import nl0
import background

VERSION = 'nl0-local-revision-1'
CUT_CHECKS = {'existing_derivation', 'condition_discharge', 'conclusion_match',
              'continuation_preservation', 'dependency_accounting'}


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': ir.digest(path)}


def unchanged(item):
    path = Path(item['path'])
    ir.need(path.is_file() and ir.digest(path) == item['sha256'], 'stale bound artifact: ' + str(path))
    return path


def evidence_paths(value, base):
    """Parent-compatible case-relative evidence, not arbitrary path strings."""
    result = []
    if isinstance(value, dict):
        if set(value) == {'path', 'sha256'}:
            path = nl0.local_path(Path(base), value['path'])
            ir.need(path.is_file() and ir.digest(path) == value['sha256'], 'stale evidence: ' + str(path))
            result.append(path)
        else:
            for child in value.values(): result.extend(evidence_paths(child, base))
    elif isinstance(value, list):
        for child in value: result.extend(evidence_paths(child, base))
    return list(dict.fromkeys(result))


def read_source(graph, spec, audit_a=None, incremental=None, *, active=None):
    graph, spec = Path(graph).resolve(), Path(spec).resolve()
    import basis
    basis.source_context(graph,spec)
    ir.need(not (audit_a and incremental), 'choose ordinary or incremental Audit A, not both')
    if incremental:
        receipt_path = Path(incremental).resolve()
        active = set() if active is None else set(active)
        ir.need(receipt_path not in active, 'cyclic incremental review chain')
        active.add(receipt_path)
        receipt = ir.load(receipt_path)
        ir.need(receipt['version'] == VERSION and receipt['kind'] == 'incremental_acceptance', 'unsupported incremental acceptance')
        for row in receipt['bindings']: unchanged(row)
        manifest_path = unchanged(receipt['manifest'])
        verdict = check(manifest_path.parent, active=active, write=False)
        ir.need(receipt['result'] == verdict['result'], 'incremental acceptance result changed')
        ir.need(all(receipt[key] == verdict[key] for key in ('manifest','graph','spec','coverage','bindings')),
                'incremental acceptance coverage/bindings changed')
        ir.need(verdict['graph'] == binding(graph) and verdict['spec'] == binding(spec), 'incremental record belongs to another source')
        data = nl0.validate(graph, spec)
        data[0].update(verdict['result'])
        paths = [receipt_path, manifest_path] + [Path(x['path']) for x in receipt['bindings']]
        return data, list(dict.fromkeys(paths))
    data = nl0.validate(graph, spec, audit_a, allow_unresolved=True)
    paths = [graph, spec] + evidence_paths(ir.load(spec), graph.parent) + evidence_paths(ir.load(graph), graph.parent)
    if audit_a:
        paths += [Path(audit_a).resolve()] + evidence_paths(ir.load(audit_a), graph.parent)
    return data, list(dict.fromkeys(paths))


def inventory(graph, spec, audit_a=None, incremental=None):
    data, _ = read_source(graph, spec, audit_a, incremental)
    result, _, _, props, steps, *_ = data
    consumers = {pid: sorted(rid for rid, r in steps.items() if pid in r['inputs']) for pid in props}
    return {'case_id': result['case_id'], 'graph_sha256': ir.digest(graph),
            'background_supplement':result.get('background_supplement'),
            'upstream_audit_passed': result['current_standard_receipt_valid'],
            'existing_shared_nodes': {pid: rows for pid, rows in consumers.items()
                                      if props[pid]['kind'] == 'internal' and len(rows) >= 2},
            'direct_consumers': consumers,
            'inference_sha256': {rid:hashed(r) for rid,r in steps.items()},
            'locations': {rid: [{'paragraph': s['id'], 'sha256': hashed(s), 'text': s['text']}
                                for s in r['argument']] for rid, r in steps.items()},
            'warning': 'Fanout is graph metadata, not measured repeated Lean construction or a speedup.'}


def apply_patch(graph, patch):
    ir.need(patch['version'] == VERSION and isinstance(patch['candidates'], list), 'unsupported extraction patch')
    ir.need(set(patch) <= {'version', 'baseline_graph_sha256', 'spec_sha256', 'candidates', 'discovery_and_author_cost_seconds'}, 'unknown patch fields')
    old = copy.deepcopy(graph)
    revised = copy.deepcopy(graph)
    props = {p['id']: p for p in old['propositions']}
    steps = {r['id']: r for r in old['inferences']}
    new_ids, changed, cut_packets = set(), set(), {}
    for candidate in patch['candidates']:
        ir.need(set(candidate) == {'id','proposition','producer','derivation','expected_avoided_work','consumers'}, 'unknown/missing candidate fields')
        cid = candidate['id']
        ir.need(isinstance(cid, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',cid) is not None
                and cid not in new_ids, 'duplicate/missing or unsafe candidate id')
        new_ids.add(cid)
        p, producer = candidate['proposition'], candidate['producer']
        ir.need(not any(x['kind'] == 'internal' and x['statement'].strip() == p['statement'].strip() for x in props.values()),
                'reuse an existing exported N instead of extracting its identical statement')
        ir.need(p['kind'] == 'internal' and p['id'] not in props and p['id'] not in new_ids, 'candidate must add one fresh N')
        ir.need(producer['id'] not in steps and producer['id'] not in new_ids and producer['output'] == p['id'], 'candidate must add one fresh R producer')
        new_ids.update((p['id'], producer['id']))
        ir.need(set(producer['inputs']) <= props.keys(), 'new producer borrows an unexported/new fact')
        origin = candidate['derivation']
        ir.need(origin['inference'] in steps and origin['paragraphs'], 'missing existing derivation')
        old_origin = steps[origin['inference']]
        positions = {s['id']: s for s in old_origin['argument']}
        ir.need(set(origin['paragraphs']) <= positions.keys(), 'unknown derivation paragraph')
        ir.need(candidate['expected_avoided_work'].strip(), 'missing extraction cost/benefit basis')
        consumers = candidate['consumers']
        ir.need(isinstance(consumers, list) and len(consumers) >= 2, 'a shared extraction needs at least two distinct consumers')
        consumer_ids = [x['inference'] for x in consumers]
        ir.need(len(set(consumer_ids)) == len(consumer_ids), 'duplicate extraction consumer')
        revised['propositions'].append(copy.deepcopy(p))
        revised['inferences'].append(copy.deepcopy(producer))
        for consumer in consumers:
            ir.need(set(consumer) <= {'inference','before_sha256','inputs','replacements','applications','cut'}, 'unknown consumer patch fields')
            rid = consumer['inference']
            ir.need(rid in steps and rid not in changed, 'unknown or overlapping consumer patches; merge before staging')
            changed.add(rid)
            before = steps[rid]
            ir.need(consumer['before_sha256'] == hashed(before), 'stale consumer patch')
            after = copy.deepcopy(before)
            after['inputs'] = consumer['inputs']
            ir.need(p['id'] in after['inputs'] and set(after['inputs']) <= set(before['inputs']) | {p['id']}, 'extra/unrelated consumer input')
            rows = consumer['replacements']
            ir.need(rows and len({x['paragraph'] for x in rows}) == len(rows), 'missing/duplicate replacement spans')
            by_id = {s['id']: s for s in before['argument']}
            replacement = {}
            for row in rows:
                sid = row['paragraph']
                ir.need(sid in by_id and row['before_sha256'] == hashed(by_id[sid]), 'stale/unknown replacement paragraph')
                if 'splices' in row:
                    ir.need('after' not in row and row['splices'], 'choose exact splices or a full paragraph replacement')
                    value = copy.deepcopy(by_id[sid])
                    text = value['text']; intervals = []
                    for splice in row['splices']:
                        before_text, after_text = splice['old'], splice['new']
                        ir.need(isinstance(before_text,str) and before_text and text.count(before_text) == 1,
                                'splice must match exactly once in the original paragraph')
                        ir.need(isinstance(after_text,str) and after_text and after_text != before_text, 'empty/unchanged splice')
                        position=text.index(before_text); end=position+len(before_text)
                        ir.need(all(end <= a or position >= b for a,b,_ in intervals), 'overlapping text splices')
                        intervals.append((position,end,after_text))
                    for a,b,replacement_text in sorted(intervals,reverse=True): text=text[:a]+replacement_text+text[b:]
                    value['text']=text
                    value['uses']=row['uses_after']
                    for name in ('uses_local','objects'):
                        if name+'_after' in row: value[name]=row[name+'_after']
                else:
                    value = row['after']
                ir.need(value['id'] == sid and set(value) == set(by_id[sid]), 'replacement changes paragraph identity/schema')
                protected = set(value) - {'text', 'uses', 'uses_local', 'objects'}
                ir.need(all(value[k] == by_id[sid][k] for k in protected), 'replacement changes local facts or assumption lifetime')
                ir.need(value['text'] != by_id[sid]['text'], 'replacement must change proof text, not only metadata')
                replacement[sid] = value
            after['argument'] = [copy.deepcopy(replacement.get(s['id'], s)) for s in before['argument']]
            after['applications'] = consumer.get('applications', before['applications'])
            ir.need(all(x in before['applications'] for x in after['applications']), 'new source applications are outside this consumer factoring operation')
            cut = consumer['cut']
            for key in ('old_conclusion', 'shared_instantiation', 'supplied_conclusion', 'continuation'):
                ir.need(isinstance(cut[key], str) and cut[key].strip(), 'missing substitution contract: ' + key)
            ir.need(isinstance(cut['conditions'], list) and all(x['condition'].strip() and x['justification'].strip() for x in cut['conditions']), 'missing application conditions')
            revised['inferences'][next(i for i,r in enumerate(revised['inferences']) if r['id'] == rid)] = after
            cut_packets[cid + ':' + rid] = {'candidate': cid, 'consumer': rid,
                'shared_statement': p, 'producer': producer,
                'input_statements_before': [props[x] for x in before['inputs']],
                'input_statements_after': [p if x == p['id'] else props[x] for x in after['inputs']],
                'output_statement': props[before['output']],
                'producer_source_derivation': {'inference': origin['inference'], 'paragraphs': [positions[x] for x in origin['paragraphs']]},
                'old_derivation': {'inference': rid, 'paragraphs': [by_id[x['paragraph']] for x in rows]},
                'before': before, 'after': after, 'replaced_paragraphs': [x['paragraph'] for x in rows], 'contract': cut,
                'scope': 'old_derivation is THIS consumer\'s replaced baseline proof. producer_source_derivation is where the shared proof was copied ONCE; it may be a different consumer with a different final goal. Review shared intermediate conclusion and this substitution, not equality of supplier/consumer final goals. Whole-A acceptance is a separate program gate. Internal N uses are inputs/prose, not E/M source-application records.'}
    ir.need(all(next(p for p in revised['propositions'] if p['id'] == pid) == value for pid,value in props.items()), 'existing proposition changed')
    ir.need(all(next(r for r in revised['inferences'] if r['id'] == rid) == value for rid,value in steps.items() if rid not in changed), 'unlisted proof changed')
    return revised, cut_packets


def cut_context(cuts, spec):
    for packet in cuts.values():
        packet['global_context'] = {key:copy.deepcopy(spec[key]) for key in ('parameters','definitions','logic','pins')}
    return cuts


def stage(graph, spec, patch_path, out, *, audit_a=None, incremental=None):
    started = time.monotonic()
    graph, spec, patch_path, out = [Path(x).resolve() for x in (graph, spec, patch_path, out)]
    data, baseline_paths = read_source(graph, spec, audit_a, incremental)
    ir.need(data[1]['format_version'] == 2, 'incremental acceptance requires current v2 source; legacy experiments stay development-only')
    patch = ir.load(patch_path)
    ir.need(patch['baseline_graph_sha256'] == ir.digest(graph) and patch['spec_sha256'] == ir.digest(spec), 'patch binds a different baseline')
    revised, cuts = apply_patch(data[1], patch)
    changed={p['consumer'] for p in cuts.values()}
    ir.need(not any(data[0].get('background_notes',{}).get(rid) for rid in changed),
            'changed consumer has accepted background notes: complete its scoped re-review before extraction; unchanged notes may be inherited')
    cut_context(cuts, data[2])
    out.mkdir(parents=True, exist_ok=False)
    case = out/'case'; case.mkdir()
    # Copy only canonical dependencies; do not clone a project or alter source records.
    for path in evidence_paths(data[1], graph.parent) + evidence_paths(data[2], graph.parent) + evidence_paths(data[0].get('background_notes',{}),graph.parent):
        relative = path.relative_to(graph.parent)
        ir.need(relative not in {Path('nl0.json'), Path('spec.json')}, 'input evidence collides with revised canonical files')
        destination = case/relative; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    shutil.copyfile(spec, case/'spec.json')
    if patch['candidates']: ir.write(case/'nl0.json', revised)
    else: shutil.copyfile(graph, case/'nl0.json')
    new_data = nl0.validate(case/'nl0.json', case/'spec.json')
    shutil.copyfile(patch_path, out/'patch.json')
    old_rids = set(data[4]); new_rids = set(new_data[4]) - old_rids
    for rid in sorted(new_rids): ir.write(case/'producer-packets'/f'{rid}.json', nl0.packet(new_data, rid))
    for key, packet in cuts.items(): ir.write(case/'cut-packets'/f'{key.replace(":", "-")}.json', packet)
    template = nl0.closure.audit_template(new_data, nl0.CHECKS, nl0.EXTERNAL_CHECKS, 'nl0.json', 'spec.json')
    producer_review = {'reviewer': template['reviewer'], 'reviews': {rid: template['inference_reviews'][rid] for rid in sorted(new_rids)}}
    ir.write(case/'producer-review.json', producer_review)
    cut_review = {'version': VERSION, 'reviewer': {'identity': 'UNASSIGNED', 'mode': 'unperformed', 'independent': False,
                  'disclosure': 'Delta review with baseline access; not a fresh whole-consumer replay.'}, 'cuts': {}}
    for key in cuts:
        cut_review['cuts'][key] = {'verdict': 'UNVERIFIED', 'notes': 'Not reviewed.', 'locations': [], 'evidence': [],
                                  'packet_sha256': hashed(cuts[key]),
                                  'checks': {name: 'UNVERIFIED' for name in sorted(CUT_CHECKS)}}
    ir.write(case/'cut-review.json', cut_review)
    new_paths = [case/'nl0.json', case/'spec.json', out/'patch.json']
    new_paths += list((case/'producer-packets').glob('*.json')) + list((case/'cut-packets').glob('*.json'))
    new_paths += evidence_paths(revised, case) + evidence_paths(data[2], case)
    manifest = {'version': VERSION, 'kind': 'local_source_preparation',
                'baseline': {'graph': str(graph), 'spec': str(spec), 'audit_a': str(Path(audit_a).resolve()) if audit_a else None,
                             'incremental': str(Path(incremental).resolve()) if incremental else None},
                'bindings': [binding(x) for x in dict.fromkeys(baseline_paths + new_paths)],
                'tools': [binding(Path(__file__)), binding(Path(ir.__file__)), binding(Path(__file__).with_name('shared_lemmas.py')),
                          binding(PARENT/'nl0.py'), binding(PARENT/'closure.py'), binding(PARENT/'background.py')],
                'new_producers': sorted(new_rids), 'changed_consumers': sorted({p['consumer'] for p in cuts.values()}),
                'inherited_inferences': sorted(old_rids - {p['consumer'] for p in cuts.values()}),
                'cut_ids': sorted(cuts), 'stage_wall_seconds': time.monotonic() - started,
                'discovery_and_author_cost_seconds': patch.get('discovery_and_author_cost_seconds'),
                'source_freeze': 'STAGED_PENDING_ACTUAL_LOCAL_REVIEWS', 'mathematics_automatically_verified': False}
    ir.write(out/'manifest.json', manifest)
    return {'status': 'SOURCE-REVISION-STAGED', 'directory': str(out), 'new_producers': sorted(new_rids),
            'changed_consumers': manifest['changed_consumers'], 'inherited_inferences': manifest['inherited_inferences']}


def reviewer(value):
    ir.need(value['identity'].strip() not in {'', 'UNASSIGNED'} and value['disclosure'].strip(), 'unperformed/undisclosed reviewer')
    ir.need(type(value['independent']) is bool, 'invalid review independence')
    ir.need(value['mode'] in {'human', 'fresh_model_review', 'retained_role_review', 'same_context_self_audit', 'external_review', 'delta_review_with_baseline', 'targeted_adjudication'}, 'invalid review mode')
    ir.need(not (value['mode'] in {'same_context_self_audit','targeted_adjudication'} and value['independent']), 'self-review/adjudication cannot claim untouched independence')
    ir.need(value['independent'] is True,'Formal acceptance requires a separate independent reviewer; self-review is development evidence only')


def check(directory, *, active=None, write=True):
    started = time.monotonic()
    out = Path(directory).resolve(); case = out/'case'
    manifest_path = out/'manifest.json'; manifest = ir.load(manifest_path)
    ir.need(manifest['version'] == VERSION and manifest['kind'] == 'local_source_preparation', 'unsupported preparation manifest')
    paths = [unchanged(x) for x in manifest['bindings'] + manifest['tools']]
    authority = manifest['baseline']
    baseline, baseline_paths = read_source(**authority, active=active)
    patch = ir.load(out/'patch.json')
    ir.need(patch['baseline_graph_sha256'] == ir.digest(authority['graph']) and patch['spec_sha256'] == ir.digest(authority['spec']), 'patch baseline binding changed')
    expected, cuts = apply_patch(baseline[1], patch)
    cut_context(cuts, baseline[2])
    ir.need(ir.load(case/'nl0.json') == expected and ir.digest(case/'spec.json') == ir.digest(authority['spec']), 'revision escaped the allowlisted patch')
    data = nl0.validate(case/'nl0.json', case/'spec.json')
    new_ids = sorted(set(data[4]) - set(baseline[4]))
    changed = sorted({x['consumer'] for x in cuts.values()})
    ir.need(not any(baseline[0].get('background_notes',{}).get(rid) for rid in changed),
            'changed consumer background needs a fresh scoped review before incremental acceptance')
    inherited = sorted(set(baseline[4]) - set(changed))
    ir.need(manifest['new_producers'] == new_ids and manifest['cut_ids'] == sorted(cuts)
            and manifest['changed_consumers'] == changed and manifest['inherited_inferences'] == inherited, 'incorrect audit coverage partition')
    producer_path, cut_path = case/'producer-review.json', case/'cut-review.json'
    producers, reviewed_cuts = ir.load(producer_path), ir.load(cut_path)
    ir.need(set(producers['reviews']) == set(new_ids), 'missing/extra producer review')
    ir.need(reviewed_cuts['version'] == VERSION and set(reviewed_cuts['cuts']) == set(cuts), 'missing/extra substitution review')
    if new_ids:
        reviewer(producers['reviewer']); reviewer(reviewed_cuts['reviewer'])
        # Validate new producers with every ordinary Audit A rule. Other entries
        # stay UNVERIFIED; they are never fabricated into fresh passing replays.
        temporary = nl0.closure.audit_template(data, nl0.CHECKS, nl0.EXTERNAL_CHECKS, 'nl0.json', 'spec.json')
        temporary['reviewer'] = producers['reviewer']
        for rid in new_ids:
            for row in [producers['reviews'][rid], *producers['reviews'][rid]['checks'].values()]:
                ir.need(row['verdict'] == 'PASS', 'unperformed/failed new producer review: ' + rid)
            temporary['inference_reviews'][rid] = producers['reviews'][rid]
        with tempfile.TemporaryDirectory(prefix='incremental-producer-check-') as temp:
            audit_path = Path(temp)/'audit.json'; ir.write(audit_path, temporary)
            validated = nl0.validate(case/'nl0.json', case/'spec.json', audit_path, allow_unresolved=True)
            ir.need(not any(x['review'].split('.')[0] in new_ids for x in validated[0]['unresolved_reviews']),
                    'new producer has unresolved application or closure reviews')
    for key, expected_packet in cuts.items():
        packet_path = case/'cut-packets'/f'{key.replace(":", "-")}.json'
        ir.need(ir.load(packet_path) == expected_packet, 'changed substitution packet')
        row = reviewed_cuts['cuts'][key]
        ir.need(row.get('packet_sha256') == hashed(expected_packet), 'stale substitution review packet: ' + key)
        ir.need(row['verdict'] == 'PASS' and set(row['checks']) == CUT_CHECKS
                and all(v == 'PASS' for v in row['checks'].values()), 'unperformed/failed substitution review: ' + key)
        ir.need(row['notes'].strip() not in {'', 'Not reviewed.'}, 'missing substitution judgment')
        required = {'/before', '/after', '/contract', '/old_derivation', '/shared_statement',
                    '/producer_source_derivation', '/input_statements_before', '/input_statements_after', '/global_context'}
        ir.need(required <= set(row['locations']), 'missing paired substitution locations')
        for pointer in row['locations']: nl0.closure.resolve(expected_packet, pointer)
        ir.need(row['evidence'], 'missing substitution evidence')
        nl0.evidence(case, row['evidence'])
    accepted = baseline[0]['current_standard_receipt_valid']
    result = {'current_standard_receipt_valid': accepted, 'audit_receipt_valid': accepted,
              'audit_status': 'INCREMENTAL-AUDIT-A-PASSED' if accepted else 'DEVELOPMENT-LOCAL-REVIEW-ONLY',
              'mathematics_automatically_verified': False,
              'reviewer': {'baseline': baseline[0].get('reviewer'), 'producer': producers['reviewer'], 'cuts': reviewed_cuts['reviewer']},
              'unresolved_reviews': baseline[0].get('unresolved_reviews', [])}
    notes=copy.deepcopy(baseline[0].get('background_notes',{}))
    for rid in new_ids:notes[rid]=producers['reviews'][rid].get('background_notes',[])
    if any(notes.values()):
        for rid, rows in notes.items():background.validate(rows,nl0.packet(data,rid),case)
        result.update(background_policy=background.POLICY,background_notes=notes,
                      background_note_count=sum(len(x) for x in notes.values()),
                      background_supplement=background.supplement(data,notes))
    paths += baseline_paths + [producer_path, cut_path]
    paths += evidence_paths(producers, case) + evidence_paths(reviewed_cuts, case)
    output = {'version': VERSION, 'kind': 'incremental_acceptance', 'manifest': binding(manifest_path),
              'graph': binding(case/'nl0.json'), 'spec': binding(case/'spec.json'), 'result': result,
              'coverage': {'new_full_reviews': new_ids, 'substitution_reviews': changed, 'inherited_inferences': inherited,
                           'new_full_consumer_replays': [], 'inherited_target_sources_definitions': True},
              'bindings': [binding(x) for x in dict.fromkeys(paths)],
              'machine_check_seconds': time.monotonic() - started}
    if write:
        destination = out/'source-acceptance.json'
        ir.need(not destination.exists(), 'acceptance already recorded; check without overwrite or start a new revision')
        ir.write(destination, output)
    return output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['inventory', 'stage', 'check'])
    ap.add_argument('--graph', type=Path); ap.add_argument('--spec', type=Path)
    ap.add_argument('--audit-a', type=Path); ap.add_argument('--incremental', type=Path)
    ap.add_argument('--patch', type=Path); ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    try:
        if args.command == 'inventory': result = inventory(args.graph, args.spec, args.audit_a, args.incremental)
        elif args.command == 'stage': result = stage(args.graph, args.spec, args.patch, args.out, audit_a=args.audit_a, incremental=args.incremental)
        else: result = check(args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({'status': 'SOURCE-NOT-ACCEPTED', 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__': raise SystemExit(main())
