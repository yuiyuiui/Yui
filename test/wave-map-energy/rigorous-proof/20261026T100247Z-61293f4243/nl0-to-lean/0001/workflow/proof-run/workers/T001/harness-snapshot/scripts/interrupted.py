"""Explicit new-run recovery from interrupted NL0/Audit A, retaining old evidence."""
from pathlib import Path
import json
import shutil

from controller_common import bind,write
import jobs
from execution_state import inspect
import remote_retry

VERSION='yui-service-resume-1'


def remote_stop(stage):
    """Require the actual last failed turn, not an earlier recovered fault."""
    path=Path(stage)/'events.jsonl'
    if not path.is_file():return None
    with path.open('rb') as stream:
        size=stream.seek(0,2);offset=max(0,size-131072);stream.seek(offset)
        if offset:stream.readline()
        lines=stream.read().splitlines()
    for line in reversed(lines):
        try:event=json.loads(line)
        except (ValueError,UnicodeError):continue
        if event.get('method')!='turn/completed':continue
        turn=event.get('params',{}).get('turn',{})
        if turn.get('status')!='failed':return None
        return remote_retry.classify(turn.get('error'))
    return None


def validate_descriptor(job):
    value=job['resume']
    if (set(value)!={'version','prior_run','mode','author_directory','campaigns'}
            or value['version']!=VERSION or value['mode'] not in {'author','audit-a'}
            or job['track'] not in {'nl0','full'}):raise ValueError('Unsupported service-resume contract')
    prior=Path(value['prior_run']).resolve();author=Path(value['author_directory']).resolve()
    if prior==Path(job['root']).resolve():
        raise ValueError('Resume authority must belong to the explicitly named prior run')
    previous=json.loads((prior/'job.json').read_text())
    inherited=previous.get('resume',{})
    if not author.is_relative_to(prior/'nl0') and str(author)!=inherited.get('author_directory'):
        raise ValueError('Resume author is outside its bound authority lineage')
    if previous['case']!=job['case'] or previous['profiles']!=job['profiles']:
        raise ValueError('Resume cannot change the case identity or model profiles')
    if previous['documents'][0]['sha256']!=job['documents'][0]['sha256']:
        raise ValueError('Resume cannot change the original problem')
    required={str(prior/'job.json'),str(prior/'case-result.json'),str(author/'stage/result.json')}
    for campaign in value['campaigns']:
        path=Path(campaign).resolve()
        if not path.is_relative_to(prior/'audit-a') and str(path) not in inherited.get('campaigns',[]):
            raise ValueError('Resume campaign escapes its bound case lineage')
        required.add(str(path/'campaign.json'))
    if not required<={row['path'] for row in job['authority_bindings']}:
        raise ValueError('Missing prior-run authority binding')


def audit_boundary(prior,old,campaign):
    """Resolve the original released author through an existing bound lineage."""
    import full_workflow
    campaign=Path(campaign).resolve()
    if not campaign.is_relative_to(prior/'audit-a'):raise ValueError('Audit campaign escapes its run')
    plan=json.loads((campaign/'campaign.json').read_text());source=Path(plan['case']).resolve()
    if source.is_relative_to(prior/'nl0'):
        author=source.parent.parent
    elif source==prior/'resumed-source' and old.get('resume',{}).get('mode')=='audit-a':
        author=Path(old['resume']['author_directory']).resolve()
        for name in ['nl0.json','spec.json']:
            if (source/name).read_bytes()!=(author/'stage/case'/name).read_bytes():
                raise ValueError('Restored source changed from its bound released author')
    else:raise ValueError('No bound released author for this audit campaign')
    full_workflow.nl0_artifact_for_audit(author)
    campaigns=list(dict.fromkeys([*old.get('resume',{}).get('campaigns',[]),
        *[str(p.parent) for p in sorted((prior/'audit-a').glob('*/campaign.json'))]]))
    return author,source,campaigns


def bookkeeping_boundary(prior,old,result):
    """Recognize only the recorded index fault with intact complete review scopes."""
    import audit_reuse
    import nl0
    if (result.get('status')!='EXECUTION_FAULT' or
            result.get('error')!='ValueError: BACKGROUND: no matching successful native/catalog probe' or
            'audit_reuse.py' not in result.get('traceback','')):
        raise ValueError('Not a known recoverable evidence-index fault')
    state=json.loads((prior/'execution-status.json').read_text())
    campaign=Path(state.get('stage_artifacts',{}).get('directory','')).resolve()
    author,source,campaigns=audit_boundary(prior,old,campaign)
    plan=json.loads((campaign/'campaign.json').read_text());data=nl0.validate(source/'nl0.json',source/'spec.json')
    faults=[]
    for scope,binding in plan.get('inherited',{}).items():
        try:audit_reuse.validate(source,binding,data,scope)
        except audit_reuse.EvidenceIndexError:
            _,changes=audit_reuse.checked_reindex(source,binding,data,scope)
            faults.append({'scope':scope,'changes':changes})
    if not faults:raise ValueError('The recorded index fault is not reproducible from bound evidence')
    hits=audit_reuse.select(data,campaigns)
    required={'target','structure',*['definition:'+key for key in data[5]],
        *['source:'+key for key,p in data[3].items() if p['kind'] in {'external','mathlib'}],
        *['packet:'+key for key in data[4]]}
    if not required<=set(hits):
        raise ValueError('Evidence recovery requires complete qualified retained reviews: '+str(sorted(required-set(hits))))
    return author,source,campaigns,faults


def prepare(prior_run, *, repair_evidence=False):
    """No model calls; reuse only explicit, unchanged, completed review scopes."""
    import full_workflow
    import source_preparation
    prior=Path(prior_run).resolve()
    old=jobs.validate(json.loads((prior/'job.json').read_text()),verify_runtime=False)
    result_path=prior/'case-result.json'
    if not result_path.is_file():raise ValueError('Resume requires a terminated run with an actual result')
    owner=inspect(prior).get('inspection',{})
    if owner.get('controller_identity_matches') or owner.get('residual_owned_processes'):
        raise ValueError('Prior run or its owned processes are still active')
    result=json.loads(result_path.read_text());result=result.get('result',result)
    if old['track'] not in {'nl0','full'} or result.get('completion',{}).get('acceptance_target_satisfied'):
        raise ValueError('Use this recovery only for interrupted NL0/Audit A work')
    campaigns=[];mode='author';index_faults=[]
    if repair_evidence:
        author,source,campaigns,index_faults=bookkeeping_boundary(prior,old,result)
        evidence=result_path;mode='audit-a'
    else:
        evidence=Path(result.get('evidence') or '').resolve()
        if not evidence.is_relative_to(prior) or evidence.name!='result.json':
            raise ValueError('No exact interrupted model-stage evidence; do not restart an unknown failure')
        failure=json.loads(evidence.read_text())
        rows=(failure.get('transport_health') or {})
        remote=[row for key in ['faults','uncertainty'] for row in rows.get(key,[])
                if row.get('kind')=='PROVIDER_ERROR' and remote_retry.classify(row.get('details'))]
        if (failure.get('isolation_violation') or failure.get('status')=='CANCELLED'
                or (evidence.parent/'tool-provenance-rejections.jsonl').exists()
                or (evidence.parent/'isolation-violations.jsonl').exists()
                or not remote or not remote_stop(evidence.parent)):
            raise ValueError('Prior failure is not a positively identified remote provider fault')
        relative=evidence.relative_to(prior).parts
        if relative[0]=='audit-a' and len(relative)>=5:
            author,source,campaigns=audit_boundary(prior,old,prior/relative[0]/relative[1])
            mode='audit-a'
        elif relative[0]=='nl0' and len(relative)>=4:
            author=prior/relative[0]/relative[1]
            if failure.get('status')=='ACCEPTED':
                raise ValueError('A released author requires its exact subsequent audit recovery boundary')
        else:raise ValueError('This explicit resume supports authoring/Audit A; later-stage recovery is not inferred')
    remaining=old['time_budget_seconds']
    if remaining is not None:
        from datetime import datetime,timezone
        state=json.loads((prior/'execution-status.json').read_text())
        deadline=(state.get('time_budget') or {}).get('deadline_at_utc')
        if not deadline:raise ValueError('Original explicit deadline is unavailable; resume cannot reset its budget')
        remaining=(datetime.fromisoformat(deadline.replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds()
        if remaining<=0:raise ValueError('The explicit case deadline is exhausted; resume cannot reset it')
    paths={prior/'job.json',result_path,evidence,author/'stage/result.json'}
    if repair_evidence:paths.add(prior/'execution-status.json')
    else:paths.add(evidence.parent/'events.jsonl')
    if mode=='audit-a':
        source=author/'stage/case'
        _,files=source_preparation.read_source(source/'nl0.json',source/'spec.json')
        paths.update(files)
        paths.update([source/'author-check-progress.json',author/'stage/accepted.json',author/'stage/tools.jsonl'])
        for campaign in campaigns:
            paths.update(p for p in Path(campaign).rglob('*') if p.is_file() and p.name in {
                'campaign.json','spec.json','nl0.json','packet.json','accepted.json','result.json',
                'execution-manifest.json','exposure-audit.json','tools.jsonl'})
            for raw in Path(campaign).glob('*/stage/accepted.json'):
                paths.update(source_preparation.evidence_paths(json.loads(raw.read_text()),raw.parent))
            plan=json.loads((Path(campaign)/'campaign.json').read_text())
            previous_case=Path(plan['case'])
            for binding in plan.get('inherited',{}).values():
                import audit_reuse
                record,stored=audit_reuse.read_binding(previous_case,binding)
                paths.add(previous_case/binding['path']);paths.update(stored.values())
    descriptor={'version':VERSION,'prior_run':str(prior),'mode':mode,
                'author_directory':str(author),'campaigns':campaigns}
    job=jobs.prepare(old['problem'],track=old['track'],profiles=old['profiles'],
        max_concurrency=old['max_concurrency'],policy=old['policy'],
        materials=[row['original']['path'] for row in old['documents'][1:]],
        time_budget_seconds=remaining,resume=descriptor,
        resume_bindings=[bind(p) for p in sorted(paths)])
    write(Path(job['root'])/'resumption.json',{'kind':'DISCLOSED_OPERATIONAL_CONTINUATION',
        'prior_run':str(prior),'mode':mode,'original_outcome_preserved':True,
        'new_runtime_bound':True,'partial_reviews_are_not_inherited':True,
        'prior_judgments_visible_to_fresh_reviewers':False,'old_usage_included_in_new_usage':False,
        'evidence_index_recovery':index_faults,'recovery_requires_new_model_reviews':not repair_evidence})
    jobs.validate(job)
    return job


def restore_source(job):
    """Restore exact released source bytes; this creates no new author verdict."""
    import full_workflow
    import source_preparation
    value=job['resume'];author=Path(value['author_directory'])
    full_workflow.nl0_artifact_for_audit(author)
    source=author/'stage/case';_,files=source_preparation.read_source(source/'nl0.json',source/'spec.json')
    destination=Path(job['root'])/'resumed-source';destination.mkdir(exist_ok=False)
    for path in files:
        target=destination/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
    source_preparation.read_source(destination/'nl0.json',destination/'spec.json')
    write(destination/'source-origin.json',{'original_author_directory':str(author),
        'original_graph':bind(source/'nl0.json'),'original_spec':bind(source/'spec.json'),
        'mathematical_fields_changed':False,'new_author_model_called':False})
    return destination
