"""Bounded shared-source discovery followed by actual producer and cut reviews."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'nl0/scripts'))
from controller_common import write, bind, manifest
from clean_stage import ArtifactStage
from execution_health import require_review_execution, StageFailure
import audit_a_campaign as a
import source_preparation as source
import ir
from staging_storage import copy_input
import artifact_protocol as protocol
from shared_lemmas import hashed
from runtime_config import model_profile, use_profiles


PROMPT = '''Inspect the accepted NL0 for worthwhile repeated mathematical derivations.
This is a bounded factoring step, not another proof construction. Read inventory.json
first. Existing exported shared nodes should be reused, not duplicated. Propose
an extraction only when an existing local derivation can replace work in at least
two consumers without changing target, definitions, hypotheses or proof route.
Return {status:NO_CHANGE, reason:<specific cost/benefit account>} when no worthwhile
eligible extraction exists. A no-change result is a normal outcome.
Otherwise submit the allowlisted patch schema from source-refactoring.md:
version, baseline_graph_sha256, spec_sha256, candidates. The real staging tool
returns exact boundary feedback. Each candidate supplies its existing derivation,
new producer, at least two consumers, exact splices and substitution contracts.
Never rewrite the whole NL0. Consumers with accepted background notes cannot use
the current narrow delta route; leave those derivations in place. All proposed
producers and cuts still require actual independent reviews before acceptance.
'''


def run(authority, out, budget, *, sessions=None, prior_artifact=None, findings=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    data,_=source.read_source(**authority)
    from source_qualification import usable
    if not usable(data[0]):
        raise ValueError('Source factoring requires accepted Audit A authority')
    if data[0].get('current_conditional_receipt_valid'):
        write(out/'selection.json',{'unchanged':True,'authority':authority,
            'reason':'Preserve the exact conditionally audited source and its unresolved primary-source qualifications.'})
        return authority
    inputs=out/'inputs';inputs.mkdir()
    inventory=source.inventory(**authority);inventory.pop('background_supplement',None)
    inventory['consumers_with_background_notes']=sorted(rid for rid,notes in data[0].get('background_notes',{}).items() if notes)
    write(inputs/'inventory.json',inventory)
    write(inputs/'spec.json',data[2]);write(inputs/'nl0.json',data[1])
    if prior_artifact:
        shutil.copyfile(prior_artifact,inputs/'prior-extraction.json')
        shutil.copyfile(findings,inputs/'incremental-findings.json')
    manifest(inputs)
    chosen={};attempt=0
    def validate(value):
        nonlocal attempt
        attempt+=1
        if value.get('status')=='NO_CHANGE':
            if set(value)!={'status','reason'} or not isinstance(value['reason'],str) or not value['reason'].strip():
                raise ValueError('Explain the no-change decision')
            chosen.update(unchanged=True)
            return {'status':'UNCHANGED_SOURCE_SELECTED','semantic_acceptance':False}
        patch=out/'patches'/f'{attempt:04d}.json';write(patch,value)
        staged=out/'candidates'/f'{attempt:04d}'
        result=source.stage(**authority,patch_path=patch,out=staged)
        chosen.update(unchanged=False,directory=staged)
        return result
    from translation_author import InterfaceStage
    shape=protocol.choice(protocol.obj({'status':protocol.literal('NO_CHANGE'),'reason':protocol.TEXT}),source.patch_schema())
    stage=InterfaceStage(out/'stage',PROMPT,phase='translation-source-preparation',inputs=inputs/'inputs.json',
                        validator=protocol.Contract(shape,validate),budget=budget,library=True)
    if sessions:
        with sessions.use('lean-global-author'):stage.execute()
    else:stage.execute()
    require_review_execution(ir.load(out/'stage/result.json'),out/'stage/result.json',phase='source-preparation')
    if chosen.get('unchanged'):
        write(out/'selection.json',{'unchanged':True,'authority':authority,'decision':bind(out/'stage/accepted.json')})
        return authority
    revised=chosen.get('directory')
    if revised is None:raise StageFailure('PREPARATION_INCOMPLETE','No selected source revision')
    case=revised/'case';plan=ir.load(revised/'manifest.json')
    # The narrow local reviews are translation work and use the Lean profile.
    profile=model_profile('translation-preparation')
    selected={k:profile[k] for k in ('id','reasoning_effort','speed','automatic_fallback')}
    with use_profiles({'nl0':selected,'lean':selected}):
        producer_reviews(case,plan,out/'producer-reviews',budget,sessions=sessions)
        cut_reviews(case,plan,out/'cut-reviews',budget,sessions=sessions)
    failures=[]
    for path in [case/'producer-review.json',case/'cut-review.json']:
        def visit(value):
            if isinstance(value,dict):
                if value.get('verdict') in {'FAIL','UNVERIFIED'}:failures.append(value)
                for item in value.values():visit(item)
            elif isinstance(value,list):
                for item in value:visit(item)
        visit(ir.load(path))
    if failures:
        write(out/'review-findings.json',{'findings':failures,'candidate':bind(out/'stage/accepted.json')})
        raise StageFailure('SOURCE_EXTRACTION_REVIEW_FAILED','Located incremental source findings',phase='source-extraction-review',evidence=out/'review-findings.json')
    result=source.check(revised)
    if not result['result']['current_standard_receipt_valid']:
        raise StageFailure('SOURCE_REVISION_UNVERIFIED','Local source revision did not obtain actual acceptance')
    selected_authority={'graph':str(case/'nl0.json'),'spec':str(case/'spec.json'),
                        'incremental':str(revised/'source-acceptance.json')}
    write(out/'selection.json',{'unchanged':False,'authority':selected_authority})
    return selected_authority


def producer_reviews(case, plan, out, budget, *, sessions=None):
    data=ir.load(case/'producer-review.json');new=plan['new_producers']
    if not new:return
    prepared=a.prepare(case,case,out)
    prepared['jobs']=[row for row in prepared['jobs'] if row['id'] in new]
    write(out/'campaign.json',prepared)
    a.run(out,budget=budget,audit_budget=budget,sessions=sessions,review_role='lean-global-reviewer')
    for rid in new:
        stage=out/rid/'stage';result=ir.load(stage/'result.json')
        try:require_review_execution(result,stage/'result.json',phase='source-producer-review')
        except StageFailure as error:
            if error.result.get('record_context_qualified'):
                raise StageFailure('SOURCE_EXTRACTION_REVIEW_FAILED','Located incomplete producer review',phase='source-extraction-review',evidence=stage/'accepted.json') from error
            raise
        raw=ir.load(stage/'accepted.json');a.validate_review(raw,out/rid,False)
        target=case/'revision-evidence'/rid;target.mkdir(parents=True)
        for name in ('accepted.json','result.json','exposure-audit.json','execution-manifest.json'):
            shutil.copyfile(stage/name,target/name)
        ev=[{'path':str(p.relative_to(case)),'sha256':bind(p)['sha256']} for p in target.iterdir()]
        def judgment(row, located=False):
            value={'verdict':row['verdict'],'notes':row['notes'],'evidence':ev}
            if located:value['locations']=row['locations']
            return value
        row=judgment(raw);row['checks']={k:judgment(v,True) for k,v in raw['checks'].items()}
        row['external_applications']={}
        for aid,app in raw.get('external_applications',{}).items():
            row['external_applications'][aid]={**judgment(app),'input':app['input'],
                'bindings_review':judgment(app['bindings_review']),
                'hypothesis_reviews':[judgment(v) for v in app['hypothesis_reviews']],
                'conclusion_review':judgment(app['conclusion_review']),'bridges':app['bridges']}
        row['background_notes']=copy.deepcopy(raw.get('background_notes',[]))
        for note in row['background_notes']:
            if note['kind']!='mathlib':continue
            for evidence in note['source']['evidence']:
                original=stage/evidence['path'];destination=target/evidence['path']
                destination.parent.mkdir(parents=True,exist_ok=True)
                if bind(original)['sha256']!=evidence['sha256']:raise ValueError('Changed producer source evidence')
                copy_input(original,destination);evidence['path']=str(destination.relative_to(case))
        packet=ir.load(out/rid/'packet.json')
        library_evidence=[ev for note in row['background_notes'] if note['kind']=='mathlib' for ev in note['source']['evidence']]
        trace=stage/'tools.jsonl'
        if trace.is_file():
            shutil.copyfile(trace,target/'tools.jsonl')
            library_evidence.append({'path':str((target/'tools.jsonl').relative_to(case)),
                                     'sha256':bind(target/'tools.jsonl')['sha256']})
        row['replay']={'packet_sha256':packet['packet_sha256'],'mode':a.background.MODE,
                       'carrier':str(stage),'prior_exposure':[],'library_evidence':library_evidence,
                       'read_materials':['packet:'+packet['packet_sha256']]+['mathlib-evidence:'+ev['sha256'] for ev in library_evidence]}
        data['reviews'][rid]=row
    data['reviewer']={'identity':model_profile('translation-preparation')['id'],
        'mode':'retained_role_review' if sessions else 'fresh_model_review','independent':True,
        'disclosure':'Separate B0 reviewer; own incremental review history may be retained. Actual producer packets and source only; no author conversation.'}
    write(case/'producer-review.json',data)


def cut_reviews(case, plan, out, budget, *, sessions=None):
    reviews=ir.load(case/'cut-review.json')
    for index,key in enumerate(plan['cut_ids']):
        directory=out/f'{index+1:04d}';inputs=directory/'inputs';inputs.mkdir(parents=True)
        packet=case/'cut-packets'/f'{key.replace(":","-")}.json'
        shutil.copyfile(packet,inputs/'packet.json');manifest(inputs)
        required={'/before','/after','/contract','/old_derivation','/shared_statement',
                  '/producer_source_derivation','/input_statements_before','/input_statements_after','/global_context'}
        def validate(value):
            if not value['notes'].strip() or not required<=set(value['locations']):raise ValueError('Incomplete located cut review')
            for p in value['locations']:a.nl0.closure.resolve(ir.load(packet),p)
            if value['verdict']=='PASS' and any(v!='PASS' for v in value['checks'].values()):raise ValueError('Inconsistent cut PASS')
            return {'scope':'Completeness and locations only; no mathematical verdict generated'}
        prompt=('Independently review this bounded substitution against the supplied before/after, original derivation and global context. '
            'Read source-refactoring.md. Return verdict, specific notes, locations and checks for exactly '+', '.join(sorted(source.CUT_CHECKS))+'. '
            'Judgments are PASS/FAIL/UNVERIFIED. Required locations: '+', '.join(sorted(required))+'. Do not repair or assume the proposed producer is valid.')
        shape=protocol.obj({'verdict':protocol.VERDICT,'notes':protocol.TEXT,
            'locations':protocol.array(protocol.STRING,minItems=1),
            'checks':protocol.obj({key:protocol.VERDICT for key in source.CUT_CHECKS})})
        stage=ArtifactStage(directory/'stage',prompt,phase='translation-cut-review',
            inputs=inputs/'inputs.json',validator=protocol.Contract(shape,validate),budget=budget,library=True)
        if sessions:
            with sessions.use('lean-global-reviewer'):stage.execute()
        else:stage.execute()
        try:require_review_execution(ir.load(directory/'stage/result.json'),directory/'stage/result.json',phase='cut-review')
        except StageFailure as error:
            if error.result.get('record_context_qualified'):
                raise StageFailure('SOURCE_EXTRACTION_REVIEW_FAILED','Located incomplete substitution review',
                    phase='source-extraction-review',evidence=directory/'stage/accepted.json') from error
            raise
        row=ir.load(directory/'stage/accepted.json');target=case/'revision-evidence'/f'cut-{index+1:04d}';target.mkdir(parents=True)
        for name in ('accepted.json','result.json','exposure-audit.json','execution-manifest.json'):
            shutil.copyfile(directory/'stage'/name,target/name)
        reviews['cuts'][key]={**row,'packet_sha256':hashed(ir.load(packet)),
            'evidence':[{'path':str(p.relative_to(case)),'sha256':bind(p)['sha256']} for p in target.iterdir()]}
    reviews['reviewer']={'identity':model_profile('translation-preparation')['id'],
        'mode':'retained_role_review' if sessions else 'delta_review_with_baseline','independent':True,
        'disclosure':'Separate B0 role performing actual paired substitutions against the explicit baseline; own earlier findings may be retained when role sessions are used.'}
    write(case/'cut-review.json',reviews)
