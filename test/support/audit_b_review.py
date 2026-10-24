#!/usr/bin/env python3
"""Run an actual fresh, paired source/kernel Audit B review after a real build."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from audit_a_campaign import CORE, bind, write, manifest, blocking_finding
sys.path.insert(0,str(CORE/'scripts'))
sys.path.insert(0,str(CORE/'translation/scripts'))
import ir
import audit_b
import concurrency
from clean_stage import ArtifactStage
from review_contract import ReviewContract
from execution_health import require_review_execution, review_outcome


PROMPT='''Perform the actual fresh Audit B semantic review. Read the original
independent NL0 inventory and all paired actual kernel evidence in
review-packet.json, mechanical.json, and the relevant Yui Audit B rules.
The completed proof and formalizer's types are candidates, not a reference
answer. For every required source node, implementation declaration and allowed
calculation, compare the FULL source statement with the FULL elaborated Lean
type and inspect actual proof/definition/dependency evidence. Check all
parameters, hypothesis strength, quantifiers, domains, representation bridges,
hidden proof fields, source N closure, permitted library uses, original target,
edge cases, assembly and trust assumptions. Read every paired location in
mechanical.required_review_locations. Compiler success and equal labels alone
are insufficient. External source inputs remain explicitly conditional; do not
claim the publications themselves proved in Lean. Return JSON with exactly
nodes,checks,findings. nodes has exactly every required_review_locations key;
checks has exactly inventory_and_scope,
parameters_definitions_and_representations,complete_signature_and_hidden_fields,
direct_dependencies_and_route,shared_proofs_and_final_closure,
library_and_calculation_correspondence,warnings_and_trusted_environment.
Every row has {verdict:PASS|FAIL|UNVERIFIED,notes:<actual specific comparison>,
locations:[<resolving JSON pointers into review-packet.json>]}. Each node row
must include all its required paired source/kernel pointers. Each global check
includes /inventory and /actual_elaborated_evidence plus useful precise fields.
findings is a list of concrete {verdict,explanation,locations}, empty if none.
Preserve real defects; do not fix the proof, strengthen H, or invent a PASS.
'''


def prepare(audit,out):
    audit,out=[Path(p).resolve() for p in (audit,out)]
    audit_b.bound_inputs(audit)
    mechanical=ir.load(audit/'mechanical.json')
    if not mechanical['passed'] or mechanical['errors']:raise ValueError('A real complete mechanical Audit B pass is required')
    out.mkdir(parents=True,exist_ok=False);inputs=out/'inputs';inputs.mkdir()
    for name in ['review-packet.json','mechanical.json','Audit.lean','compiler.json']:
        shutil.copyfile(audit/name,inputs/name)
    manifest(inputs);(out/'prompt.txt').write_text(PROMPT)
    write(out/'bindings.json',{'audit':str(audit),'mechanical':bind(audit/'mechanical.json'),
        'mapping':bind(audit/'mapping.json'),'packet':bind(audit/'review-packet.json')})
    shutil.copyfile(__file__,out/'controller.py.snapshot.txt')


def validate(value,out):
    out=Path(out);packet=ir.load(out/'inputs/review-packet.json');mechanical=ir.load(out/'inputs/mechanical.json')
    if set(value)!={'nodes','checks','findings'}:raise ValueError('Return exactly nodes, checks and findings')
    if set(value['nodes'])!=set(mechanical['required_review_locations']) or set(value['checks'])!=set(audit_b.REVIEW_CHECKS):
        raise ValueError('Review every required source/implementation/calculation and all seven global checks')
    for key,row in {**value['nodes'],**value['checks']}.items():
        if set(row)!={'verdict','notes','locations'} or row['verdict'] not in {'PASS','FAIL','UNVERIFIED'} or not row['notes'].strip():
            raise ValueError('Each row needs a real verdict, specific notes and locations')
        expected=mechanical['required_review_locations'].get(key,['/inventory','/actual_elaborated_evidence'])
        if not set(expected)<=set(row['locations']):raise ValueError('Missing paired actual source/kernel locations: '+key)
        for pointer in row['locations']:audit_b.resolve(packet,pointer)
    if not isinstance(value['findings'],list):raise ValueError('findings must be a list')
    if any(blocking_finding(x) for x in value['findings']) and all(x['verdict']=='PASS' for x in [*value['nodes'].values(),*value['checks'].values()]):
        raise ValueError('Blocking findings conflict with all-PASS summaries; preserve the finding')
    return {'scope':'Completeness, location and judgment consistency only; actual semantic decisions are the reviewer\'s.'}


def run(out,timeout=1800,budget=None):
    out=Path(out).resolve()
    mechanical=ir.load(out/'inputs/mechanical.json')
    required=['/nodes/'+key for key in mechanical['required_review_locations']]+['/checks/'+key for key in audit_b.REVIEW_CHECKS]
    packet=ir.load(out/'inputs/review-packet.json')
    contract=ReviewContract(out/'review-work',{'nodes':{},'checks':{}},required,lambda value:validate(value,out),
        finding_validator=lambda finding:[audit_b.resolve(packet,p) for p in finding['locations']])
    stage=ArtifactStage(out/'stage',(out/'prompt.txt').read_text(),phase='audit-b-semantic-review',
        inputs=out/'inputs/inputs.json',library=True,timeout=timeout,
        validator=contract,budget=concurrency.serial_budget(budget))
    return stage.execute()[0]


def collect(out):
    out=Path(out).resolve();binding=ir.load(out/'bindings.json');result=ir.load(out/'stage/result.json')
    qualification=require_review_execution(result,out/'stage/result.json',phase='audit-b')
    for key in ['mechanical','mapping','packet']:
        if ir.digest(binding[key]['path'])!=binding[key]['sha256']:raise ValueError('Reviewed audit evidence changed')
    raw=ir.load(out/'stage/accepted.json');validate(raw,out)
    evidence=[]
    for name in ['accepted.json','result.json','exposure-audit.json','execution-manifest.json']:
        path=out/'stage'/name;evidence.append({**bind(path),'path':str(path.relative_to(out))})
    review={'version':audit_b.VERSION,'mechanical_sha256':binding['mechanical']['sha256'],
        'mapping_sha256':binding['mapping']['sha256'],
        'reviewer':{'identity':__import__('run_pilot').MODEL+' high Standard','mode':'fresh_model_review','independent':True,
            'disclosure':'Fresh clean context; read only original source/paired kernel review packet, actual mechanical results, Yui rules and pinned Mathlib. No author history, prior verdict, or hidden reference proof.'},
        'nodes':{key:{**row,'evidence':evidence} for key,row in raw['nodes'].items()},
        'checks':{key:{**row,'evidence':evidence} for key,row in raw['checks'].items()}}
    path=out/'review.json'
    if path.exists():raise ValueError('Preserve previous actual review')
    write(path,review)
    passed=all(row['verdict']=='PASS' for row in [*raw['nodes'].values(),*raw['checks'].values()]) and not any(blocking_finding(f) for f in raw['findings'])
    report={'all_checks_passed':passed,'review':bind(path),'findings':raw['findings'],'qualification':qualification}
    report['review_status']=review_outcome(x['verdict'] for x in [*raw['nodes'].values(),*raw['checks'].values()])
    write(out/'report.json',report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run','collect']);p.add_argument('--out',required=True);p.add_argument('--audit');p.add_argument('--timeout-seconds',type=int,default=1800)
    args=p.parse_args()
    result=prepare(args.audit,args.out) if args.command=='prepare' else run(args.out,args.timeout_seconds) if args.command=='run' else collect(args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))
