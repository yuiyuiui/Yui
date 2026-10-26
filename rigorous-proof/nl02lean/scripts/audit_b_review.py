#!/usr/bin/env python3
"""Run an actual fresh, paired source/kernel Audit B review after a real build."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'nl0/scripts'))
from controller_common import CORE, bind, write, manifest
from audit_a_campaign import blocking_finding
sys.path.insert(0,str(CORE/'nl0/scripts'))
sys.path.insert(0,str(CORE/'nl02lean/scripts'))
import ir
import audit_b
import concurrency
import review_materials
from clean_stage import ArtifactStage
from review_contract import ReviewContract
from execution_health import require_review_execution, review_outcome


PROMPT='''Perform the actual fresh Audit B semantic review under endpoint-fidelity-2.
Read the compact review-packet.json using read_task_input JSON pointers. Start
with /scope and /mechanical_summary, list /endpoints, then read each endpoint's
/source, /actual and /correspondence. Large objects return keys; large strings
return next_offset. Follow has_more until each required statement is complete.
The /documents index names exact original source/context and actual Proof.lean
documents. Read relevant source definitions and actual Lean definitions there,
including structure fields which could hide a stronger assumption. No raw
compiler output or imported dependency dump needs to be read. The machine
summary reports actual recorded checks, never a semantic verdict. If native
evidence is inherited, it is NOT a new compiler run or previous semantic PASS.
Review exactly every external E and complete P. The target
includes ALL parameters, quantifiers, hypotheses, domains and the conclusion.
The author's explanation helps locate the comparison; independently verify it
against the source and actual Lean. A claimed direct translation or equivalence
is not itself evidence of correctness. Check hidden proof fields and edge cases
when they affect an endpoint's meaning. Equivalent mathematical encodings are
allowed without duplicating a literal Mathlib object or requiring a redundant
formal isomorphism. If a proof uses two representations, their actual conversions
must be checked. Reject changed/strengthened assumptions, unsupported equivalence,
wrong domains or an omitted target clause.

The pinned Mathlib environment is freely available. Do NOT review whether its
theorem names, counts or per-node uses match the NL0 M inventory. There is no
per-M, per-N, per-D, instance or calculation permission audit. Inspect relevant
local definitions to understand E/P, not as a separate source-inventory test.
Check the actual standalone root, completed assembly and recorded kernel trust
evidence. External inputs remain conditional; do not claim their publications
were proved in Lean. Compilation and accepted JSON are not a semantic PASS.

Return exactly nodes,checks,findings. nodes has exactly the /scope/endpoint_ids
keys (E and P). checks has exactly endpoint_inventory_and_scope,
external_statement_fidelity,complete_target_and_representations,kernel_closure_and_trust.
Each row is {verdict:PASS|FAIL|UNVERIFIED,notes:<specific comparison>,
locations:[<JSON pointers into review-packet.json>]}. For each endpoint include
/endpoints/<ID>/source, /endpoints/<ID>/actual and /endpoints/<ID>/correspondence.
For P also include /scope/full_target, /scope/parameters and /scope/hypotheses.
Each global check includes /scope, /endpoints and /mechanical_summary plus useful
specific locations. Escape JSON pointer keys if necessary.
findings is a list of concrete {verdict,explanation,locations}, empty if none.
If there are no external inputs, say so in that global check. Preserve defects;
do not repair the proof or treat an author's assurance as a passed review.
'''


def prepare(audit,out):
    audit,out=[Path(p).resolve() for p in (audit,out)]
    audit_b.bound_inputs(audit)
    mechanical=ir.load(audit/'mechanical.json')
    if not mechanical['passed'] or mechanical['errors']:raise ValueError('A real complete mechanical Audit B pass is required')
    out.mkdir(parents=True,exist_ok=False);inputs=out/'inputs';inputs.mkdir()
    review_materials.verify_projection(audit,foundations=audit_b.AXIOMS)
    for name in review_materials.DOCUMENTS:
        shutil.copyfile(audit/name,inputs/name)
    # Full machine records remain controller evidence, outside model-visible inputs.
    write(out/'mechanical.json',mechanical)
    manifest(inputs);(out/'prompt.txt').write_text(PROMPT)
    write(out/'bindings.json',{'audit':str(audit),'mechanical':bind(audit/'mechanical.json'),
        'mapping':bind(audit/'mapping.json'),'packet':bind(audit/'review-packet.json')})
    shutil.copyfile(__file__,out/'controller.py.snapshot.txt')


def validate(value,out):
    out=Path(out);packet=ir.load(out/'inputs/review-packet.json');mechanical=machine_record(out)
    if set(value)!={'nodes','checks','findings'}:raise ValueError('Return exactly nodes, checks and findings')
    if set(value['nodes'])!=set(mechanical['required_review_locations']) or set(value['checks'])!=set(audit_b.REVIEW_CHECKS):
        raise ValueError('Review every external/target endpoint and all four global checks')
    for key,row in {**value['nodes'],**value['checks']}.items():
        if set(row)!={'verdict','notes','locations'} or row['verdict'] not in {'PASS','FAIL','UNVERIFIED'} or not row['notes'].strip():
            raise ValueError('Each row needs a real verdict, specific notes and locations')
        expected=mechanical['required_review_locations'].get(key,review_materials.locations(packet))
        if not set(expected)<=set(row['locations']):raise ValueError('Missing paired actual source/kernel locations: '+key)
        for pointer in row['locations']:audit_b.resolve(packet,pointer)
    if not isinstance(value['findings'],list):raise ValueError('findings must be a list')
    if any(blocking_finding(x) for x in value['findings']) and all(x['verdict']=='PASS' for x in [*value['nodes'].values(),*value['checks'].values()]):
        raise ValueError('Blocking findings conflict with all-PASS summaries; preserve the finding')
    return {'scope':'Completeness, location and judgment consistency only; actual semantic decisions are the reviewer\'s.'}


def machine_record(out):
    out=Path(out)
    path=out/'mechanical.json'
    return ir.load(path if path.exists() else out/'inputs/mechanical.json')


def run(out,timeout=None,budget=None):
    out=Path(out).resolve()
    mechanical=machine_record(out)
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
        'reviewer':{'identity':result.get('model',__import__('run_pilot').MODEL)+' / '+__import__('runtime_config').model_profile('audit-b')['reasoning_effort']+' / Standard','mode':'fresh_model_review','independent':True,
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run','collect']);p.add_argument('--out',required=True);p.add_argument('--audit');p.add_argument('--timeout-seconds',type=int,default=None)
    args=p.parse_args()
    result=prepare(args.audit,args.out) if args.command=='prepare' else run(args.out,args.timeout_seconds) if args.command=='run' else collect(args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))
