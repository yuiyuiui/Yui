#!/usr/bin/env python3
"""Fresh, located source/type review for explicit proposed interfaces.

This controller records actual model judgments, never manufactures a pass from
type elaboration, and keeps rejected reviews available for bounded revisions.
"""
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
from staging_storage import copy_input
import workflow
import concurrency
from clean_stage import ArtifactStage
from review_contract import ReviewContract
import artifact_protocol as protocol
from execution_health import require_review_execution, qualification, review_outcome


PROMPT='''Perform a fresh semantic review of the complete proposed NL0-to-Lean
interface and typed plan. Read all frozen inputs and the relevant Yui rules.
The canonical source spec/graph are the mathematical authority; the formalizer's
representations, types and plan are proposals, not a reference answer. Compare
the actual complete Lean types (including binders, typeclasses, structure fields
and guards) with every external E and complete P, including all hypotheses and relevant
definitions. Use endpoint_correspondence explanations as claims to verify.
Mathlib results are freely available; do not audit M registration or names. Check both
directions of claimed representations/equivalences and their explicit planned
conversion obligations; reject stronger assumptions, hidden conclusions, standard-basis
surrogates for arbitrary lattices, omitted dimensions/characteristics/endpoints,
and types that merely give a name to an unproved result. Type elaboration is not
faithful translation. Check the actual meaning of library parameters,
order/index types, coercions and overloaded
notation in this pinned version. Do not infer a property from a symbol's
appearance or from a remembered API. Check that no domain was made vacuous and
no source property was silently strengthened or weakened by a definition.
Check each source paragraph, source output and exact
direct input boundary through implementation-only helpers. The plan must follow
the accepted source argument, not silently research a new proof or introduce a stronger
project hypothesis. Each typed obligation may be conditional, but assembly must
discharge all internal hypotheses. A difficult yet faithful obligation is not
an interface error simply because it may take time to prove.
Read workload.json when judging statements_and_local_plans. Examine long chains and bundled independent arguments. Identify an actionable smaller cut if it preserves all direct inputs and the original output; keep a coherent argument together when a split adds no useful parallel work.
Complete all named checks in the generated submission schema with your actual
judgments, specific reasoning and resolving document/pointer locations.
Locate each judgment in both source material (spec.json or nl0.json) and formal
material (contract.json or plan.json); include other actual locations as useful.
findings is a list of {verdict,explanation,locations} for concrete defects or
uncertainties, empty if none. Do not repair the proposal or invent a PASS.
Source proofs and completed local Lean proof bodies are not requested here.
For a specialized internal or prepared dependency compare the recorded input_instances with the
source use: the right ambient/index types, all needed instances and the actual
arguments or projections. Lean checks those declared calls; flag an omitted or
irrelevant use even if its declaration compiles.
Inspect __signature_P for the public endpoint. Private __preflight_ declarations
only type-check connections before proofs exist and never enter the compiled proof.
An unproved bridge assigned to a worker is a planned obligation, not a new H.
Its actual body is required at assembly/Audit B. Necessary definitional
construction fields must elaborate and cannot assume the target. Compare a
property to its actual source object and scalar field: a source hypothesis on
one object/field is not automatically the target on another object/field.
Every blocking mismatch finding includes comparison:{source:{document,pointer,
quote},formal:{document,pointer,quote},difference:<specific binder/object/field/
domain/hypothesis/conclusion/route difference>}. Quote the relevant actual
content, not a paraphrase of a remembered source. Do not repeatedly resample
reviews until one passes; an evidence-backed disagreement is a disclosed dispute.
'''


def comparison_schema():
    def side(names):
        return protocol.obj({'document':{'enum':names},'pointer':protocol.STRING,'quote':protocol.TEXT})
    return protocol.obj({'source':side(['spec.json','nl0.json','background-supplement.json']),
                         'formal':side(['contract.json','plan.json']),'difference':protocol.TEXT})


def validate_comparison(comparison,docs):
    protocol.validate(comparison,comparison_schema(),'/comparison')
    import audit_b
    for side,allowed in [('source',{'spec.json','nl0.json','background-supplement.json'}),('formal',{'contract.json','plan.json'})]:
        row=comparison[side]
        try:value=audit_b.resolve(docs[row['document']],row['pointer'])
        except (IndexError,KeyError,TypeError) as error:raise ValueError('Comparison pointer does not resolve') from error
        text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,sort_keys=True)
        if not isinstance(row['quote'],str) or not row['quote'].strip() or row['quote'] not in text:
            raise ValueError('Quoted comparison evidence is absent at the supplied location')
    return {'scope':'Quoted bytes and paired locations only; semantic equivalence remains a real judgment.'}


def copy_review_inputs(author,inputs):
    """Disclose canonical task data, not the author's repair history/verdicts."""
    permitted={'spec.json','nl0.json','source-map.json','background-supplement.json','problem.md','source-context.md','frozen-target.md'}
    for src in (Path(author)/'inputs').iterdir():
        if src.is_file() and src.name in permitted:copy_input(src,Path(inputs)/src.name)


def verify_candidate_artifact(actual,c,p,outputs):
    actual_steps,plan_steps=actual['steps'],p['steps']
    if c['source'].get('background_mode')=='node_local_reference':
        # Note locations are copied from accepted Audit A by the controller.
        actual_steps=[{k:v for k,v in step.items() if k!='background_notes'} for step in actual_steps]
        plan_steps=[{k:v for k,v in step.items() if k!='background_notes'} for step in plan_steps]
    pairs=[(actual['header'],c['header']),(actual['parameters'],c['parameters']),
           (actual['premise_types'],{x['id']:x['type'] for x in c['premises']}),
           (actual['conclusion_type'],c['conclusion']['type']),
           (actual['representation'],c['representation']),(actual['objects'],c['objects']),
           (actual_steps,plan_steps),(actual['terminal'],p['terminal']),
           (actual.get('shared_obligations',[]),c.get('shared_obligations',[])),
           (actual['source_outputs'],outputs),
           (actual.get('endpoint_correspondence',{}),c.get('endpoint_correspondence',{}))]
    if any(left!=right for left,right in pairs):raise ValueError('The selected typed candidate differs from the actual model artifact')


def prepare(author,out,candidate=None,*,adjudicate=None,dispute=None):
    author,out=[Path(p).resolve() for p in (author,out)]
    result=ir.load(author/'stage/result.json')
    if not qualification(result)['identity_and_input_boundary_verified']:
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
    write(inputs/'workload.json',ir.decomposition(contract,ir.load(plan)))
    for src,name in [(contract,'contract.json'),(plan,'plan.json')]:shutil.copyfile(src,inputs/name)
    copy_review_inputs(author,inputs)
    adjudication=None
    if (adjudicate is None)!=(dispute is None):raise ValueError('A targeted adjudication needs both the prior review and located dispute')
    if adjudicate is not None:
        prior=Path(adjudicate).resolve();old=ir.load(prior/'bindings.json')
        if old.get('adjudication'):raise ValueError('One targeted adjudication only; an unresolved disagreement remains disputed')
        require_review_execution(ir.load(prior/'stage/result.json'),prior/'stage/result.json',phase='prior-interface-review')
        for key,path in [('contract',contract),('plan',plan),('source_graph',author/'inputs/nl0.json'),('spec',author/'inputs/spec.json')]:
            if ir.digest(old[key]['path'])!=old[key]['sha256'] or old[key]['sha256']!=ir.digest(path):
                raise ValueError('Dispute must concern the exact same source/interface proposal')
        claim=ir.load(dispute)
        docs={p.name:ir.load(p) for p in inputs.glob('*.json')}
        validate_comparison(claim['comparison'],docs)
        shutil.copyfile(prior/'stage/accepted.json',inputs/'prior-disputed-review.json')
        shutil.copyfile(dispute,inputs/'dispute.json')
        adjudication={'prior_review':bind(prior/'stage/accepted.json'),'dispute':bind(dispute),
                      'disclosure':'One targeted adjudication with the prior verdict and located dispute disclosed; not an untouched independent review.'}
    candidate=contract.parent
    for name in ['Check.lean','result.json']:
        if (candidate/'types'/name).exists():shutil.copyfile(candidate/'types'/name,inputs/('type-'+name))
    repair_context=None
    if (author/'inputs/internal-repair-context.json').is_file():
        import internal_interface_repair as repair
        repair_context=ir.load(author/'inputs/internal-repair-context.json')
        impact=repair.verify_revision(repair_context,contract,plan)
        repair_context={**repair_context,**impact}
        write(inputs/'internal-repair-context.json',repair_context)
        for key in ('contract','plan','review'):
            shutil.copyfile(repair_context[key]['path'],inputs/('repair-parent-'+key+'.json'))
    prompt=PROMPT+ ('\nThis is a targeted adjudication. The prior review and located dispute are explicitly disclosed. Assess the actual source/types; preserve unresolved disagreement rather than inventing a PASS.\n' if adjudication else '')
    if repair_context:
        prompt+='\nThis is an INTERNAL_INTERFACE_DELTA review. The parent independent semantic receipt is disclosed and machine-validated. Protected source, H/E/P and all public definitions are unchanged. Inherit only those exact unchanged scopes; inspect changed T obligations and affected consumers against NL0, including allowed input boundaries and whether the reported defect was repaired. In the four check notes distinguish inherited judgments from this new delta review; do not claim a fresh whole-proof review or repeat unchanged work. A new actual passing receipt is required.'
    manifest(inputs);(out/'prompt.txt').write_text(prompt)
    write(out/'selected-author-artifact.json',actual)
    write(out/'bindings.json',{'author':str(author),'contract':bind(contract),'plan':bind(plan),
        'source_graph':bind(author/'inputs/nl0.json'),'spec':bind(author/'inputs/spec.json'),
        'paragraph_mapping':paths['paragraph_mapping'],'source_outputs':paths['source_outputs'],
        'candidate_selection':selection,'adjudication':adjudication,
        **({'internal_repair':repair_context} if repair_context else {})})
    shutil.copyfile(__file__,out/'controller.py.snapshot.txt')


def review_shape():
    location=protocol.obj({'document':protocol.TEXT,'pointer':{'type':'string','pattern':'^/'}})
    return protocol.ReviewShape(groups={'checks':{key:protocol.judgment(location) for key in workflow.INTERFACE_CHECKS}},
        summary={'findings':protocol.array(protocol.finding_schema({'comparison':comparison_schema()}))})


def validate(value,out):
    review_shape().validate(value)
    docs={p.name:ir.load(p) for p in (Path(out)/'inputs').glob('*.json') if p.name!='inputs.json'}
    for row in value['checks'].values():
        located=set()
        for item in row['locations']:
            if set(item)!={'document','pointer'} or item['document'] not in docs:raise ValueError('Use a declared JSON document and pointer')
            ir.need(isinstance(item['pointer'],str),'A pointer must be a string')
            # The root pointer is unnecessary: locate the actual source/type field.
            if not item['pointer'].startswith('/'):raise ValueError('Use specific absolute JSON pointers')
            import audit_b
            try:audit_b.resolve(docs[item['document']],item['pointer'])
            except IndexError as error:
                raise ValueError('Review pointer array index is out of range: '+item['pointer']) from error
            located.add(item['document'])
        if not located&{'spec.json','nl0.json'} or not located&{'contract.json','plan.json'}:
            raise ValueError('Locate the comparison in both original source and formal types/plan')
    if not isinstance(value['findings'],list):raise ValueError('findings must be a list')
    if any(blocking_finding(x) for x in value['findings']) and all(x['verdict']=='PASS' for x in value['checks'].values()):
        raise ValueError('Blocking findings conflict with all-PASS checks; preserve the finding and correct the affected check')
    if any(x['verdict']=='FAIL' for x in value['checks'].values()) and not any(blocking_finding(f) for f in value['findings']):
        raise ValueError('A failed semantic check needs its concrete located mismatch finding')
    for finding in value['findings']:
        if blocking_finding(finding):validate_comparison(finding.get('comparison'),docs)
    return {'scope':'Review completeness and resolving paired locations only; semantic verdicts remain the actual reviewer judgments.'}


def run(out,timeout=None,budget=None):
    out=Path(out).resolve()
    docs={p.name:ir.load(p) for p in (out/'inputs').glob('*.json') if p.name!='inputs.json'}
    contract=ReviewContract.structured(out/'review-work',review_shape(),lambda value:validate(value,out),
        finding_validator=lambda finding:validate_comparison(finding['comparison'],docs))
    phase='interface-dispute-review' if ir.load(out/'bindings.json').get('adjudication') else 'interface-semantic-review'
    stage=ArtifactStage(out/'stage',(out/'prompt.txt').read_text(),phase=phase,
        inputs=out/'inputs/inputs.json',library=True,timeout=timeout,
        validator=contract,budget=concurrency.serial_budget(budget))
    return stage.execute()[0]


def collect(out):
    out=Path(out).resolve();bindings=ir.load(out/'bindings.json');result=ir.load(out/'stage/result.json')
    qualification=require_review_execution(result,out/'stage/result.json',phase='interface')
    raw=ir.load(out/'stage/accepted.json');validate(raw,out)
    for key in ['contract','plan','source_graph','spec']:
        row=bindings[key]
        if ir.digest(row['path'])!=row['sha256']:raise ValueError('Reviewed bytes changed')
    if bindings.get('adjudication'):
        for key in ['prior_review','dispute']:
            row=bindings['adjudication'][key]
            if ir.digest(row['path'])!=row['sha256']:raise ValueError('Adjudication evidence changed')
    files=[]
    for name in ['accepted.json','result.json','exposure-audit.json','execution-manifest.json']:
        p=out/'stage'/name;files.append({**bind(p),'path':str(p.relative_to(out))})
    review={'version':workflow.VERSION,'source_graph_sha256':bindings['source_graph']['sha256'],
        'contract_sha256':bindings['contract']['sha256'],'plan_sha256':bindings['plan']['sha256'],
        'reviewer':{'identity':result.get('model',__import__('run_pilot').MODEL)+' / '+__import__('runtime_config').model_profile('interface')['reasoning_effort']+' / Standard','mode':'fresh_model_review','independent':True,
            'disclosure':'Separate clean semantic reviewer; read only the explicit source, typed candidate and Yui rules, with pinned Mathlib tools. No author history, previous verdict or proof reference.'},
        'checks':raw['checks'],'paragraph_mapping':bindings['paragraph_mapping'],
        'source_outputs':bindings['source_outputs'],'evidence':files,
        'preparation_cost':{'status':'DEVELOPMENT_ITERATIONS_NOT_COLD_BENCHMARK','owner_work':'UNMEASURED',
            'author_stage':str(Path(bindings['author'])/'stage'),'semantic_review_stage':str(out/'stage'),
            'candidate_selection':bindings.get('candidate_selection')}}
    if bindings.get('internal_repair'):
        import internal_interface_repair as repair
        repair.verify_revision(bindings['internal_repair'],bindings['contract']['path'],bindings['plan']['path'])
        review['internal_repair']=bindings['internal_repair']
        review['review_scope']='INTERNAL_INTERFACE_DELTA'
        review['reviewer']['disclosure']='Independent author-separated delta review; exact protected semantic scopes inherit the bound parent review, changed T obligations and affected consumers were reviewed in this stage.'
    if bindings.get('adjudication'):
        review['reviewer'].update(mode='targeted_adjudication',independent=False,
            disclosure=bindings['adjudication']['disclosure'])
        review['preparation_cost']['adjudication']=bindings['adjudication']
    elif (result.get('role_session') or {}).get('prior_submissions'):
        review['reviewer'].update(mode='retained_role_review',disclosure='Separate reviewer role retaining its own earlier incremental/interface reviews and findings; no author conversation or fresh-history claim.')
    path=out/'review.json'
    if path.exists():raise ValueError('Preserve the previous review')
    write(path,review)
    report={'all_checks_passed':all(x['verdict']=='PASS' for x in raw['checks'].values()) and not any(blocking_finding(x) for x in raw['findings']),
        'review':bind(path),'findings':raw['findings'],'qualification':qualification}
    report['review_status']=review_outcome(x['verdict'] for x in raw['checks'].values())
    if bindings.get('adjudication') and not report['all_checks_passed']:report['review_status']='DISPUTED_REVIEW'
    write(out/'report.json',report);return report


def verify_receipt(path,contract,plan,graph_sha256):
    """Read back an actual independent reviewer, not a hand-written PASS wrapper."""
    path=Path(path).resolve();out=path.parent;review=ir.load(path)
    bindings=ir.load(out/'bindings.json');raw=ir.load(out/'stage/accepted.json')
    require_review_execution(ir.load(out/'stage/result.json'),out/'stage/result.json',phase='interface')
    validate(raw,out)
    import source_preparation
    source_preparation.reviewer(review['reviewer'])
    ir.need(not bindings.get('adjudication') and review['reviewer'].get('independent') is True
            and review['reviewer'].get('mode') in {'fresh_model_review','retained_role_review'},
            'A full workflow requires an independent author-separated interface review')
    if review['reviewer']['mode']=='retained_role_review':
        result=ir.load(out/'stage/result.json')
        ir.need(result.get('role_session',{}).get('role')=='lean-global-reviewer' and
            result['role_session'].get('prior_submissions'),'Undisclosed retained reviewer history')
    ir.need(review['source_graph_sha256']==bindings['source_graph']['sha256']==graph_sha256
        and review['contract_sha256']==bindings['contract']['sha256']==ir.digest(contract)
        and review['plan_sha256']==bindings['plan']['sha256']==ir.digest(plan),
        'stale interface review')
    for key in ['contract','plan','source_graph','spec']:
        source_preparation.unchanged(bindings[key])
    ir.need(review['checks']==raw['checks'] and set(raw['checks'])==workflow.INTERFACE_CHECKS
        and all(row['verdict']=='PASS' for row in raw['checks'].values())
        and not any(blocking_finding(row) for row in raw['findings']),
        'No complete actual passing interface review')
    expected={name:ir.digest(out/'stage'/name) for name in
              ['accepted.json','result.json','exposure-audit.json','execution-manifest.json']}
    actual={}
    for item in review['evidence']:
        file=(out/item['path']).resolve()
        ir.need(file.parent==out/'stage' and file.name in expected
            and ir.digest(file)==item['sha256'],'Invalid interface-review evidence binding')
        actual[file.name]=item['sha256']
    ir.need(actual==expected,'Missing actual interface-review evidence')
    if bindings.get('internal_repair'):
        import internal_interface_repair as repair
        context=bindings['internal_repair']
        ir.need(review.get('internal_repair')==context and
            review.get('review_scope')=='INTERNAL_INTERFACE_DELTA' and
            ir.load(out/'inputs/internal-repair-context.json')==context,
            'Changed internal repair lineage or review scope')
        repair.verify_revision(context,contract,plan)
    return review


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run','collect']);p.add_argument('--out',required=True);p.add_argument('--author');p.add_argument('--candidate',type=int);p.add_argument('--timeout-seconds',type=int,default=None);p.add_argument('--adjudicate',type=Path);p.add_argument('--dispute',type=Path)
    args=p.parse_args()
    result=prepare(args.author,args.out,args.candidate,adjudicate=args.adjudicate,dispute=args.dispute) if args.command=='prepare' else run(args.out,args.timeout_seconds) if args.command=='run' else collect(args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))
