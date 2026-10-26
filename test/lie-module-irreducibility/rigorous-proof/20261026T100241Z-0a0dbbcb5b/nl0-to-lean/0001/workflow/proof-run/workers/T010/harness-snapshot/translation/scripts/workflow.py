#!/usr/bin/env python3
"""Stage gates for an accepted structured NL0 -> frozen IR -> Lean -> Audit B.

Humans/models author and review the mathematics. This controller binds those
artifacts and composes existing implementations; it is not a general NL parser.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import time

import audit_b
import concurrency
import ir
import run_graph
import source_preparation as source
import execution_state
import background
import background_inputs

VERSION = 'nl0-lean-workflow-1'
INTERFACE_CHECKS = {'source_route_and_coverage', 'parameters_and_allowed_inputs',
                    'representations_and_conversion_obligations', 'statements_and_local_plans'}


def check_source_boundary(data, c, plan, mapping, exported):
    """Mechanical source/port/paragraph checks; never a semantic review verdict."""
    nodes = {step['id']:step for step in plan['steps']}
    props, effective_steps = background_inputs.effective(data, background_inputs.mode(c))
    supplement=data[0].get('background_supplement')
    if data[0].get('background_note_count',0):
        ir.need(c['source'].get('background_supplement_sha256') == supplement['sha256']
                and c['source'].get('background_supplement') == supplement,
                'interface omitted or changed accepted background supplement')
    roots = {p['id'] for p in c['premises']}
    ir.need({p['id'] for p in c['premises'] if p['kind']!='mathlib'} <=
            {p for p,v in props.items() if v['kind'] in {'hypothesis','external'}},
            'unregistered/internal root premise')
    ir.need({p for p,v in props.items() if v['kind'] in {'hypothesis','external'}} <= roots, 'missing original hypothesis/external premise')
    for p in c['premises']:
        if p['kind']!='mathlib':
            ir.need(p['kind'] == props[p['id']]['kind'] and p['statement'] == props[p['id']]['statement'], 'changed source premise text/kind')
    ir.need(c['conclusion']['statement'] == props['P']['statement'], 'changed source target text')
    # Every NL paragraph is paired to exact bytes, rather than a planner's recollection.
    paragraphs = {(rid,s['id']): s['text'] for rid,r in data[4].items() for s in r['argument']}
    ir.need(set(mapping) == {s['id'] for s in c['source_steps']}, 'missing/extra source paragraph mapping')
    actual = set()
    for row in c['source_steps']:
        pair = (mapping[row['id']]['inference'], mapping[row['id']]['paragraph'])
        ir.need(pair in paragraphs and row['text'] == paragraphs[pair], 'source argument text differs from canonical NL0')
        actual.add(pair)
    ir.need(actual == set(paragraphs), 'whole workflow omits source argument paragraphs')
    for step in nodes.values():
        pairs={(mapping[s]['inference'],mapping[s]['paragraph']) for s in step['source_steps']}
        needed=set()
        for rid,notes in data[0].get('background_notes',{}).items():
            for note in notes:
                index=int(note['at'].split('/')[3]);sid=data[4][rid]['argument'][index]['id']
                if (rid,sid) in pairs:needed.add(rid+'.'+note['id'])
        ir.need(set(step.get('background_notes',[]))==needed,'local plan omitted or imported background notes at '+step['id'])
    expected = {r['output'] for r in data[4].values()}
    ir.need(set(exported) == expected and exported['P'] == plan['terminal'], 'missing/extra source output mapping')
    ir.need(len(set(exported.values())) == len(exported), 'distinct source outputs need distinct primary realizations')
    ir.need(set(exported.values()) <= nodes.keys(), 'source output maps to an unknown Lean task')
    # Compare direct source boundaries through implementation-only helper ports.
    boundary = {tid: pid for pid,tid in exported.items()}
    def dependencies(tid, start, seen):
        if tid not in nodes: return {tid}
        if tid != start and tid in boundary: return {boundary[tid]}
        ir.need(tid not in seen, 'cyclic implementation dependency')
        return set().union(*(dependencies(x,start,seen|{tid}) for x in nodes[tid]['inputs'])) if nodes[tid]['inputs'] else set()
    mathlib_ids = {p for p,v in props.items() if v['kind']=='mathlib'} | {
        p['id'] for p in c['premises'] if p['kind']=='mathlib'}
    for rid,r in effective_steps.items():
        tid = exported[r['output']]
        ir.need(dependencies(tid,tid,set()) - mathlib_ids == set(r['inputs']) - mathlib_ids,
                'source input boundary changed at ' + rid)
    return {'status':'SOURCE_BOUNDARIES_CHECKED','semantic_review':'PENDING_AUDIT_B'}


def freeze(graph, spec, contract, plan, interface_review, out, *, audit_a=None,
           incremental=None, max_concurrency='auto', interface_binding=None):
    started = time.monotonic()
    graph, spec, contract, plan, out = [Path(x).resolve() for x in (graph, spec, contract, plan, out)]
    data, authority_paths = source.read_source(graph, spec, audit_a, incremental)
    ir.need(data[0]['current_standard_receipt_valid'], 'source is not accepted under current Audit A; complete missing baseline/local reviews first')
    c, nodes, _ = ir.validate(contract, ir.load(plan))
    ir.need(c['source']['sha256'] == ir.digest(graph), 'whole workflow contract must bind the selected canonical NL0, not a separate summary')
    if data[0].get('background_note_count',0):
        supplement=data[0]['background_supplement']
        ir.need(c['source'].get('background_supplement_sha256')==supplement['sha256']
                and c['source'].get('background_supplement')==supplement,
                'interface omitted or changed accepted background supplement')
    if interface_review is not None:
        interface_review = Path(interface_review).resolve()
        review = ir.load(interface_review)
        ir.need(review['version'] == VERSION and review['source_graph_sha256'] == ir.digest(graph)
                and review['contract_sha256'] == ir.digest(contract) and review['plan_sha256'] == ir.digest(plan), 'stale interface review')
        source.reviewer(review['reviewer'])
        ir.need(set(review['checks']) == INTERFACE_CHECKS and all(x['verdict'] == 'PASS' and x['notes'].strip() for x in review['checks'].values()), 'unperformed interface review')
        ir.need(review['evidence'], 'missing actual interface review evidence')
        record_paths = [interface_review]+source.evidence_paths(review['evidence'], interface_review.parent)
        semantic_status = 'INTERFACE_REVIEW_PASSED_FINAL_AUDIT_B_REQUIRED'
    else:
        ir.need(interface_binding is not None, 'Deferred review requires an actual bound interface artifact')
        interface_binding = Path(interface_binding).resolve()
        review = ir.load(interface_binding)
        ir.need(review.get('contract_sha256') == ir.digest(contract)
                and review.get('plan_sha256') == ir.digest(plan)
                and review.get('source_graph_sha256') == ir.digest(graph), 'stale interface binding')
        ir.need(review.get('status') == 'IR_TYPES_CHECKED_SEMANTIC_REVIEW_PENDING_AUDIT_B', 'not a mechanically checked interface')
        record_paths = [interface_binding]
        semantic_status = 'PENDING_AUDIT_B'
    check_source_boundary(data,c,ir.load(plan),review['paragraph_mapping'],review['source_outputs'])
    typed = ir.check(contract, ir.load(plan), types_only=True)
    ir.need(typed['exit_code'] == 0, 'interface types/representations fail Lean')
    configuration = concurrency.resolve(max_concurrency)
    out.mkdir(parents=True, exist_ok=False)
    copied, _ = run_graph.package(contract, plan, out)
    bindings = [source.binding(p) for p in dict.fromkeys(authority_paths+[contract,plan]+record_paths)]
    runtime_paths=[*(ir.HERE/'scripts').glob('*.py'),*(ir.ROOT/'scripts').glob('*.py'),
        ir.ROOT/'SKILL.md',ir.ROOT/'config.json',ir.ROOT/'toolchain/lock.json',
        *(ir.ROOT/'references').glob('*.md'),*(ir.HERE/'references').glob('*.md'),
        *(ir.ROOT/'templates').glob('*.md'),*(ir.HERE/'templates').glob('*.md')]
    tools = [source.binding(p) for p in sorted(set(runtime_paths))]
    manifest = {'version': VERSION, 'authority': {'graph':str(graph),'spec':str(spec),
                'audit_a':str(Path(audit_a).resolve()) if audit_a else None,
                'incremental':str(Path(incremental).resolve()) if incremental else None},
                'bindings': bindings, 'tools': tools, 'contract':str(copied), 'plan':str(out/'inputs/plan.json'),
                'interface_review':str(interface_review) if interface_review else None,
                'interface_binding':str(interface_binding) if interface_binding else None,
                'interface_semantic_status':semantic_status,'concurrency':configuration,
                'source_outputs':review['source_outputs'], 'created_at_unix':time.time(),
                'background_supplement':data[0].get('background_supplement'),
                'background_mode':background_inputs.mode(c),
                'freeze_seconds':time.monotonic()-started, 'types_check':typed,
                'preparation_cost':review.get('preparation_cost', {'status':'UNMEASURED'}),
                'status':'SOURCE_AND_IR_FROZEN'}
    manifest['frozen_input_bindings'] = [source.binding(p) for p in (out/'inputs').rglob('*') if p.is_file()]
    ir.write(out/'manifest.json',manifest)
    ir.write(out/'freeze-seal.json', {'version': VERSION, 'manifest': source.binding(out/'manifest.json')})
    return manifest


def bound(directory):
    out = Path(directory).resolve(); manifest = ir.load(out/'manifest.json')
    seal = ir.load(out/'freeze-seal.json')
    ir.need(seal['version'] == VERSION and Path(seal['manifest']['path']) == out/'manifest.json', 'invalid workflow freeze seal')
    source.unchanged(seal['manifest'])
    ir.need(manifest['version'] == VERSION, 'unsupported workflow version')
    for row in manifest['bindings'] + manifest['tools'] + manifest['frozen_input_bindings']: source.unchanged(row)
    data,_ = source.read_source(**manifest['authority'])
    ir.need(data[0]['current_standard_receipt_valid'], 'source acceptance is no longer valid')
    ir.validate(Path(manifest['contract']), ir.load(manifest['plan']))
    return manifest


def run(directory, *, shared_store=None, timeout_seconds=None, bank=False):
    out = Path(directory).resolve(); manifest = bound(out)
    recorder=execution_state.Recorder(out,ir.contract(manifest['contract'])['id'],manifest['concurrency'])
    budget = concurrency.Budget(manifest['concurrency'],execution=recorder,role='proof')
    try:
        with execution_state.activate(recorder),recorder.signals():
            result = run_graph.run(Path(manifest['contract']),Path(manifest['plan']),out/'proof-run',
                               shared_store=shared_store,timeout_seconds=timeout_seconds,bank=bank,budget=budget)
            bound(out)
            return result
    finally:
        recorder.close('CANCELLED' if recorder.cancelled() else locals().get('result',{}).get('status','EXECUTION_FAULT'))


def prepare_audit(directory):
    out = Path(directory).resolve(); manifest = bound(out)
    result = ir.load(out/'proof-run/report.json')
    ir.need(result['status'] == 'FRAGMENT_ASSEMBLED', 'proof graph is unfinished')
    cpath = out/'proof-run/inputs/contract.json'; ppath = out/'proof-run/inputs/plan.json'
    ir.need(ir.digest(cpath) == ir.digest(manifest['contract']) and ir.digest(ppath) == ir.digest(manifest['plan']),
            'proof run uses a different frozen interface or plan')
    prepared = audit_b.prepare(cpath,ppath,out/'proof-run/proofs.json',out/'audit-b',**manifest['authority'])
    mapping = ir.load(out/'audit-b/mapping.json')
    ir.write(out/'audit-b/mapping.json',mapping)
    return prepared


def finish(directory, review):
    out = Path(directory).resolve(); manifest = bound(out)
    ir.need(ir.digest(out/'proof-run/inputs/contract.json') == ir.digest(manifest['contract'])
            and ir.digest(out/'proof-run/inputs/plan.json') == ir.digest(manifest['plan']), 'proof/audit interface changed after freeze')
    verdict = audit_b.check(out/'audit-b',Path(review).resolve())
    ir.need(verdict['status'] == 'AUDIT-B-PASSED', 'whole workflow requires whole-proof Audit B acceptance')
    proof = ir.load(out/'proof-run/report.json')
    review_path=Path(review).resolve()
    report = {'version':VERSION,'status':'WORKFLOW-PASSED','audit_b':verdict,
              'source_status':source.read_source(**manifest['authority'])[0][0]['audit_status'],
              'concurrency':proof['concurrency'],'freeze_seconds':manifest['freeze_seconds'],
              'proof_phase_wall_seconds':proof['runner_wall_seconds'],
              'elapsed_since_freeze_seconds':time.time()-manifest['created_at_unix'],
              'preparation_cost':manifest['preparation_cost'],
              'audit_build_seconds':ir.load(out/'audit-b/mechanical.json').get('wall_seconds'),
              'owner_review_seconds':None,'owner_review_cost_status':'UNMEASURED_UNLESS_RECORDED_IN_REVIEW_EVIDENCE',
              'speedup_measured':False,'pure_internal_model_reasoning_seconds':None,
              'note':'Nested compiler/tool time is already included in model-stage wall time; do not add twice.',
              'bindings':[source.binding(out/'manifest.json'),source.binding(out/'proof-run/report.json'),
                          source.binding(out/'proof-run/proofs.json'),source.binding(review_path)]}
    ir.need(not (out/'report.json').exists(), 'preserve completed workflow report; no overwrite')
    ir.write(out/'report.json',report)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['freeze','run','audit-prepare','audit-build','audit-check','status','cancel'])
    ap.add_argument('directory',type=Path)
    for name in ('graph','spec','audit-a','incremental','contract','plan','interface-review','review','shared-store','interface-binding'):
        ap.add_argument('--'+name,type=Path)
    ap.add_argument('--max-concurrency',default='auto');ap.add_argument('--timeout-seconds',type=int,default=None)
    ap.add_argument('--task',help='Cancel only this recorded task; omission cancels the case run')
    ap.add_argument('--bank',action='store_true');args=ap.parse_args()
    try:
        if args.command=='cancel':result=execution_state.request_cancel(args.directory,args.task)
        elif args.command=='status' and (args.directory/'execution-status.json').is_file():
            result=execution_state.inspect(args.directory)
            if (args.directory/'manifest.json').is_file():result['frozen_source_status']=bound(args.directory)['status']
        elif args.command=='freeze':
            result=freeze(args.graph,args.spec,args.contract,args.plan,args.interface_review,args.directory,
                          audit_a=args.audit_a,incremental=args.incremental,max_concurrency=args.max_concurrency,interface_binding=args.interface_binding)
        elif args.command=='run':result=run(args.directory,shared_store=args.shared_store,timeout_seconds=args.timeout_seconds,bank=args.bank)
        elif args.command=='audit-prepare':result=prepare_audit(args.directory)
        elif args.command=='audit-build':bound(args.directory);result=audit_b.build(args.directory/'audit-b')
        elif args.command=='audit-check':result=finish(args.directory,args.review)
        else:result={'status':bound(args.directory)['status'],'completed_report_present':(args.directory/'report.json').exists()}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ValueError,KeyError,TypeError,OSError) as error:
        print(json.dumps({'status':'WORKFLOW-NOT-PASSED','error':str(error)},ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
