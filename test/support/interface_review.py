#!/usr/bin/env python3
"""Fresh, located source/type review for the selected exercise interfaces.

This controller records actual model judgments, never manufactures a pass from
type elaboration, and keeps rejected reviews available for bounded revisions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from audit_a_campaign import ROOT, CORE, bind, write, manifest, blocking_finding
sys.path.insert(0,str(CORE/'scripts'))
sys.path.insert(0,str(CORE/'translation/scripts'))
import ir
import workflow
import concurrency
from clean_stage import ArtifactStage


PROMPT='''Perform a fresh semantic review of the complete proposed NL0-to-Lean
interface and typed plan. Read all frozen inputs and the relevant Yui rules.
The canonical source spec/graph are the mathematical authority; the formalizer's
representations, types and plan are proposals, not a reference answer. Compare
the actual complete Lean types (including binders, typeclasses, structure fields
and guards) with every original H/E/M/N/P and global definition. Check both
directions of claimed representations/equivalences and their proved conversion
obligations; reject stronger assumptions, hidden conclusions, standard-basis
surrogates for arbitrary lattices, omitted dimensions/characteristics/endpoints,
and types that merely give a name to an unproved result. Type elaboration is not
faithful translation. Check each source paragraph, source output and exact
direct input boundary through implementation-only helpers. The plan must follow
the accepted source argument, not silently research a new proof or use a stronger
library shortcut. Each typed obligation may be conditional, but assembly must
discharge all internal hypotheses. A difficult yet faithful obligation is not
an interface error simply because it may take time to prove.
Return JSON with exactly checks and findings. checks has exactly
source_route_and_coverage,parameters_and_allowed_inputs,
representations_and_conversion_obligations,statements_and_local_plans.
Each check has {verdict:PASS|FAIL|UNVERIFIED,notes:<actual specific reasoning>,
locations:[{document:<JSON document ID>,pointer:<resolving JSON pointer>},...]}.
Locate each judgment in both source material (spec.json or nl0.json) and formal
material (contract.json or plan.json); include other actual locations as useful.
findings is a list of {verdict,explanation,locations} for concrete defects or
uncertainties, empty if none. Do not repair the proposal or invent a PASS.
Source proofs and completed local Lean proof bodies are not requested here.
'''


def verify_candidate_artifact(actual,c,p,outputs):
    pairs=[(actual['header'],c['header']),(actual['parameters'],c['parameters']),
           (actual['premise_types'],{x['id']:x['type'] for x in c['premises']}),
           (actual['conclusion_type'],c['conclusion']['type']),
           (actual['representation'],c['representation']),(actual['objects'],c['objects']),
           (actual['steps'],p['steps']),(actual['terminal'],p['terminal']),
           (actual['source_outputs'],outputs)]
    if any(left!=right for left,right in pairs):raise ValueError('The selected typed candidate differs from the actual model artifact')


def prepare(author,out,candidate=None):
    author,out=[Path(p).resolve() for p in (author,out)]
    result=ir.load(author/'stage/result.json')
    if result.get('exposure',{}).get('status')!='TRANSMITTED-EXPOSURE-CHECK-PASSED':
        raise ValueError('The interface author exposure is not qualified')
    selection={'mode':'ACTUAL_SUBMITTED_ARTIFACT','author_result':bind(author/'stage/result.json')}
    if candidate is None:
        if result.get('status')!='ACCEPTED' or not (author/'stage/accepted.json').is_file():
            raise ValueError('An actually submitted interface artifact is required, or explicitly select an actual checked candidate')
        paths=ir.load(author/'accepted-interface-paths.json')
        contract,plan=[Path(paths[k]) for k in ('contract','plan')]
        actual=ir.load(author/'stage/accepted.json')
    else:
        if type(candidate) is not int or candidate<1:raise ValueError('Select a positive actual candidate number')
        contract=author/'candidates'/f'{candidate:04d}'/'contract.json';plan=contract.parent/'plan.json'
        events=[json.loads(line) for line in (author/'stage/tools.jsonl').read_text().splitlines()]
        matches=[]
        for index,event in enumerate(events):
            feedback=event.get('result',{}).get('validation',{})
            if feedback.get('status')=='IR-TYPES-CHECKED' and feedback.get('candidate')==candidate and event['result'].get('accepted'):
                args=event['arguments'];value=args.get('artifact') if event['tool'] in {'check_draft','submit_draft'} else json.loads(args['artifact_json'])
                matches.append((index+1,value))
        if len(matches)!=1:raise ValueError('Select exactly one actual successful model type-check event')
        row_number,actual=matches[0]
        if ir.load(contract.parent/'types/result.json')['exit_code']!=0:raise ValueError('The selected actual native type check did not pass')
        source=ir.load(author/'inputs/source-map.json')
        paths={'paragraph_mapping':source['paragraph_mapping'],'source_outputs':actual['source_outputs']}
        selection.update(mode='EXPLICIT_RECOVERY_OF_CHECKED_MODEL_CANDIDATE_NOT_AUTHOR_SUBMISSION',
            candidate=candidate,tool_row_number=row_number,tool_log=bind(author/'stage/tools.jsonl'),
            note='The author result is preserved. Selecting an actual immutable model draft grants no semantic, proof or performance acceptance; this new independent review must establish correspondence.')
    c=ir.load(contract);p=ir.load(plan)
    verify_candidate_artifact(actual,c,p,paths['source_outputs'])
    out.mkdir(parents=True,exist_ok=False);inputs=out/'inputs';inputs.mkdir()
    for src,name in [(contract,'contract.json'),(plan,'plan.json')]:shutil.copyfile(src,inputs/name)
    for src in (author/'inputs').iterdir():
        if src.is_file() and src.name!='inputs.json':shutil.copyfile(src,inputs/src.name)
    candidate=contract.parent
    for name in ['Check.lean','result.json']:
        if (candidate/'types'/name).exists():shutil.copyfile(candidate/'types'/name,inputs/('type-'+name))
    manifest(inputs);(out/'prompt.txt').write_text(PROMPT)
    write(out/'selected-author-artifact.json',actual)
    write(out/'bindings.json',{'author':str(author),'contract':bind(contract),'plan':bind(plan),
        'source_graph':bind(author/'inputs/nl0.json'),'spec':bind(author/'inputs/spec.json'),
        'paragraph_mapping':paths['paragraph_mapping'],'source_outputs':paths['source_outputs'],
        'candidate_selection':selection})
    shutil.copyfile(__file__,out/'controller.py.snapshot.txt')


def validate(value,out):
    if not isinstance(value,dict) or set(value)!={'checks','findings'}:raise ValueError('Return checks and findings')
    if set(value['checks'])!=workflow.INTERFACE_CHECKS:raise ValueError('Review exactly all four interface checks')
    docs={p.name:ir.load(p) for p in (Path(out)/'inputs').glob('*.json') if p.name!='inputs.json'}
    for row in value['checks'].values():
        if set(row)!={'verdict','notes','locations'} or row['verdict'] not in {'PASS','FAIL','UNVERIFIED'} or not row['notes'].strip():
            raise ValueError('Each check needs an actual verdict, specific notes and locations')
        located=set()
        for item in row['locations']:
            if set(item)!={'document','pointer'} or item['document'] not in docs:raise ValueError('Use a declared JSON document and pointer')
            ir.need(isinstance(item['pointer'],str),'A pointer must be a string')
            # The root pointer is unnecessary: locate the actual source/type field.
            if not item['pointer'].startswith('/'):raise ValueError('Use specific absolute JSON pointers')
            import audit_b
            audit_b.resolve(docs[item['document']],item['pointer']);located.add(item['document'])
        if not located&{'spec.json','nl0.json'} or not located&{'contract.json','plan.json'}:
            raise ValueError('Locate the comparison in both original source and formal types/plan')
    if not isinstance(value['findings'],list):raise ValueError('findings must be a list')
    if any(blocking_finding(x) for x in value['findings']) and all(x['verdict']=='PASS' for x in value['checks'].values()):
        raise ValueError('Blocking findings conflict with all-PASS checks; preserve the finding and correct the affected check')
    return {'scope':'Review completeness and resolving paired locations only; semantic verdicts remain the actual reviewer judgments.'}


def run(out,timeout=1800,budget=None):
    out=Path(out).resolve()
    stage=ArtifactStage(out/'stage',(out/'prompt.txt').read_text(),phase='interface-semantic-review',
        inputs=out/'inputs/inputs.json',library=True,timeout=timeout,
        validator=lambda value:validate(value,out),budget=budget or concurrency.Budget(concurrency.resolve()))
    return stage.execute()[0]


def collect(out):
    out=Path(out).resolve();bindings=ir.load(out/'bindings.json');result=ir.load(out/'stage/result.json')
    if not result.get('measurement_valid'):raise ValueError('Reviewer execution is not qualified; preserve the candidate judgment separately')
    raw=ir.load(out/'stage/accepted.json');validate(raw,out)
    for key in ['contract','plan','source_graph','spec']:
        row=bindings[key]
        if ir.digest(row['path'])!=row['sha256']:raise ValueError('Reviewed bytes changed')
    files=[]
    for name in ['accepted.json','result.json','exposure-audit.json','execution-manifest.json']:
        p=out/'stage'/name;files.append({**bind(p),'path':str(p.relative_to(out))})
    review={'version':workflow.VERSION,'source_graph_sha256':bindings['source_graph']['sha256'],
        'contract_sha256':bindings['contract']['sha256'],'plan_sha256':bindings['plan']['sha256'],
        'reviewer':{'identity':'gpt-6-luna high Standard','mode':'fresh_model_review','independent':True,
            'disclosure':'Separate clean semantic reviewer; read only the explicit source, typed candidate and Yui rules, with pinned Mathlib tools. No author history, previous verdict or proof reference.'},
        'checks':raw['checks'],'paragraph_mapping':bindings['paragraph_mapping'],
        'source_outputs':bindings['source_outputs'],'evidence':files,
        'preparation_cost':{'status':'DEVELOPMENT_ITERATIONS_NOT_COLD_BENCHMARK','owner_work':'UNMEASURED',
            'author_stage':str(Path(bindings['author'])/'stage'),'semantic_review_stage':str(out/'stage'),
            'candidate_selection':bindings.get('candidate_selection')}}
    path=out/'review.json'
    if path.exists():raise ValueError('Preserve the previous review')
    write(path,review)
    report={'all_checks_passed':all(x['verdict']=='PASS' for x in raw['checks'].values()) and not any(blocking_finding(x) for x in raw['findings']),
        'review':bind(path),'findings':raw['findings']}
    write(out/'report.json',report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run','collect']);p.add_argument('--out',required=True);p.add_argument('--author');p.add_argument('--candidate',type=int);p.add_argument('--timeout-seconds',type=int,default=1800)
    args=p.parse_args()
    result=prepare(args.author,args.out,args.candidate) if args.command=='prepare' else run(args.out,args.timeout_seconds) if args.command=='run' else collect(args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))
