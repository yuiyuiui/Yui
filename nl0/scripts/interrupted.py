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
    expected={'version','prior_run','mode','author_directory','campaigns'}
    if value.get('mode')=='author-repair':expected.add('repair_directory')
    if (set(value)!=expected
            or value['version']!=VERSION or value['mode'] not in {'author','audit-a','author-repair'}
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
    if previous['max_concurrency']!=job['max_concurrency'] or previous['policy']!=job['policy']:
        raise ValueError('Resume cannot change the worker count or execution policy')
    if previous['documents'][0]['sha256']!=job['documents'][0]['sha256']:
        raise ValueError('Resume cannot change the original problem')
    if previous.get('target_selection')!=job.get('target_selection'):
        raise ValueError('Resume cannot change or drop the selected target')
    required={str(prior/'job.json'),str(prior/'case-result.json'),str(author/'stage/result.json')}
    for campaign in value['campaigns']:
        path=Path(campaign).resolve()
        if not path.is_relative_to(prior/'audit-a') and str(path) not in inherited.get('campaigns',[]):
            raise ValueError('Resume campaign escapes its bound case lineage')
        required.add(str(path/'campaign.json'))
    if value['mode']=='author-repair':
        result=json.loads((prior/'case-result.json').read_text());result=result.get('result',result)
        boundary=local_tool_boundary(prior,previous,result)
        if (str(boundary['author'])!=str(author) or str(boundary['repair'])!=value['repair_directory']
                or boundary['campaigns']!=value['campaigns']):
            raise ValueError('Resume differs from the verified located author-repair boundary')
        required.update(str(p) for p in boundary['files'])
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


def last_tool_call(stage):
    """Read a bounded metadata suffix, never replay model-generated code."""
    path=Path(stage)/'events.jsonl'
    with path.open('rb') as stream:
        size=stream.seek(0,2);offset=max(0,size-262144);stream.seek(offset)
        if offset:stream.readline()
        lines=stream.read().splitlines()
    for line in reversed(lines):
        try:event=json.loads(line)
        except (ValueError,UnicodeError):continue
        if event.get('method')=='item/tool/call':return event.get('params',{})
    raise ValueError('No actual terminal tool call for local-tool recovery')


def local_tool_boundary(prior,old,result):
    """Recognize only inherited probe collisions before a repair draft exists."""
    import re
    import full_workflow
    import case_runner
    import source_preparation
    from execution_health import record_qualification
    from owner_observation import snapshot
    ownership=snapshot([prior])
    if not ownership['all_terminal'] or not ownership['all_process_exits_verified']:
        raise ValueError('Local-tool recovery requires verified owned process and group exits')
    evidence=Path(result.get('evidence') or '').resolve()
    try:relative=evidence.relative_to(prior)
    except ValueError:raise ValueError('Local-tool evidence escapes the prior run')
    if (len(relative.parts)!=4 or relative.parts[0]!='nl0'
            or relative.parts[2:]!=('stage','result.json') or old['policy']!='normal'):
        raise ValueError('Local-tool recovery requires a located normal-policy author repair')
    stage=evidence.parent;repair=stage.parent
    failure=json.loads(evidence.read_text())
    if (failure.get('status')!='UNFINISHED' or failure.get('isolation_violation')
            or failure.get('temporary_workspace_removed') is not True
            or not record_qualification(failure)['identity_and_input_boundary_verified']
            or any((stage/name).exists() for name in ['tool-provenance-rejections.jsonl','isolation-violations.jsonl'])
            or list((stage/'case').glob('candidate-*.json'))):
        raise ValueError('Unsupported local-tool failure or nonempty draft checkpoint')
    call=last_tool_call(stage);args=call.get('arguments',{})
    if isinstance(args,str):args=json.loads(args)
    identifier=args.get('id','')
    if call.get('tool')!='probe_library' or not re.fullmatch(r'M\d{3,}',identifier):
        raise ValueError('The terminal call is not a verified library probe')
    calls=[json.loads(line) for line in (stage/'tools.jsonl').read_text().splitlines() if line.strip()]
    sequence=1+sum(row.get('tool') in {'probe_library','probe_background'}
                   and row.get('result',{}).get('feedback_kind')!='tool_execution_fault' for row in calls)
    collision=stage/'case/library'/f'{identifier}-{sequence:04d}'
    expected='FileExistsError: [Errno 17] File exists: '+repr(str(collision))
    if failure.get('execution_fault')!=expected:
        raise ValueError('Not the verified inherited probe-directory collision')
    origin_path=repair/'input-origin.json';origin=json.loads(origin_path.read_text())
    if origin.get('warm_repair') is not True or origin.get('inputs')!=bind(prior/'inputs/inputs.json'):
        raise ValueError('No bound original inputs for the interrupted repair')
    number=int(repair.name)
    if number<2:raise ValueError('No prior Audit A boundary for local-tool recovery')
    author,source,campaigns=audit_boundary(prior,old,prior/'audit-a'/f'{number-1:04d}')
    if origin.get('baseline')!=str(source):raise ValueError('Repair baseline differs from the released source')
    inputs=repair/'inputs';manifest=inputs/'inputs.json';files={evidence,stage/'events.jsonl',stage/'tools.jsonl',origin_path,manifest,prior/'execution-status.json'}
    for row in json.loads(manifest.read_text())['inputs']:
        path=(inputs/row['path']).resolve()
        if not path.is_relative_to(inputs) or bind(path)['sha256']!=row['sha256']:
            raise ValueError('Interrupted repair input binding changed')
        files.add(path)
    baseline={'spec':json.loads((source/'spec.json').read_text()),'graph':json.loads((source/'nl0.json').read_text())}
    if json.loads((inputs/'baseline.json').read_text())!=baseline:
        raise ValueError('Saved repair baseline differs from its actual released author')
    obligations=json.loads((inputs/'repair-obligations.json').read_text())
    if obligations!=case_runner.repair_obligations(source,prior/'audit-a'/f'{number-1:04d}') or not obligations['issues']:
        raise ValueError('Saved repair obligations differ from actual located review findings')
    original=source/'library'/collision.name/'library-sources.json'
    copied=collision/'library-sources.json'
    if (collision.is_symlink() or original.is_symlink() or copied.is_symlink()
            or original not in source_preparation.evidence_paths(baseline['graph'],source)
            or not original.is_file() or not copied.is_file()
            or original.read_bytes()!=copied.read_bytes()):
        raise ValueError('The occupied probe directory lacks intact inherited evidence')
    files.update({original,copied})
    return {'author':author,'source':source,'repair':repair,'campaigns':campaigns,'files':files,
            'collision':str(collision),'obligations':obligations}


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


def prepare(prior_run, *, repair_evidence=False, repair_local_tool=False):
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
    if repair_evidence and repair_local_tool:raise ValueError('Select one explicit repair mode')
    campaigns=[];mode='author';index_faults=[];local=None
    if repair_local_tool:
        local=local_tool_boundary(prior,old,result)
        author,source,campaigns=local['author'],local['source'],local['campaigns']
        evidence=Path(result['evidence']);mode='author-repair'
    elif repair_evidence:
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
    if local:paths.update(local['files'])
    elif repair_evidence:paths.add(prior/'execution-status.json')
    else:paths.add(evidence.parent/'events.jsonl')
    if mode in {'audit-a','author-repair'}:
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
    if local:descriptor['repair_directory']=str(local['repair'])
    job=jobs.prepare(old['problem'],track=old['track'],profiles=old['profiles'],
        max_concurrency=old['max_concurrency'],policy=old['policy'],
        materials=[row['original']['path'] for row in old['documents'][1:] if row.get('extraction')!='target-selection'],
        time_budget_seconds=remaining,resume=descriptor,
        resume_bindings=[bind(p) for p in sorted(paths)],target=old.get('target_selection'))
    write(Path(job['root'])/'resumption.json',{'kind':'DISCLOSED_OPERATIONAL_CONTINUATION',
        'prior_run':str(prior),'mode':mode,'original_outcome_preserved':True,
        'new_runtime_bound':True,'partial_reviews_are_not_inherited':True,
        'prior_judgments_visible_to_fresh_reviewers':False,'old_usage_included_in_new_usage':False,
        'evidence_index_recovery':index_faults,'recovery_requires_new_model_reviews':not repair_evidence,
        **({'local_tool_recovery':{'kind':'INHERITED_PROBE_DIRECTORY_COLLISION','collision':local['collision'],
             'checkpoint':'RELEASED_BASELINE_AND_LOCATED_REPAIR_OBLIGATIONS',
             'original_repair_directory':str(local['repair']),'old_partial_usage':result.get('usage'),
             'qualified_unchanged_scopes_may_be_reused':True}} if local else {})})
    jobs.validate(job)
    return job


def restore_repair(job):
    """Restore an actual located repair, without treating its baseline as PASS."""
    jobs.validate(job)
    value=job['resume'];source=Path(value['author_directory'])/'stage/case'
    original=Path(value['repair_directory'])/'inputs/repair-obligations.json'
    write(Path(job['root'])/'resumed-repair.json',{'original_source':bind(source/'nl0.json'),
        'original_spec':bind(source/'spec.json'),'original_obligations':bind(original),
        'new_author_required':True,'fresh_review_of_changed_context_required':True})
    return source,json.loads(original.read_text()),list(value['campaigns'])


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
