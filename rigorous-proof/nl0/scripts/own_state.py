"""Bounded reminders from actual same-author tool records, never proof judgments."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re


POLICY={'version':'own-stage-state-2','source_probe_limit':32,'open_issue_limit':32,
        'progress_origin':'actual same-stage tool result','extra_model_calls':0,
        'mathematical_acceptance':False}
_FIELDS=['remaining_packet_reads','required_output_notes','required_inference_notes',
         'author_release_ready','next_actions','acceptance_contract']
SOURCE_PATH_PATTERN = r'case/library/(?:M[0-9]{3,}-[0-9]{4,}|bound-M[0-9]{3,}-[a-f0-9]{16})/library-sources\.json'


def source_report(directory, relative, pin, *, seen=None):
    """Validate the same-stage native origin chain, including exact ID aliases."""
    if not isinstance(relative,str) or not re.fullmatch(SOURCE_PATH_PATTERN,relative):
        raise ValueError('OWN_STATE: unsupported same-stage source path')
    root=Path(directory).resolve();path=root/relative
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=root and p.is_relative_to(root)) or not path.resolve().is_relative_to(root/'case/library'):
        raise ValueError('OWN_STATE: source probe escapes the current author stage')
    seen=set() if seen is None else seen
    if relative in seen:raise ValueError('OWN_STATE: cyclic native source alias')
    report=json.loads(path.read_text())
    if report.get('exit_code')!=0 or report.get('probe_version')!=1:
        raise ValueError('OWN_STATE: source is not a successful native probe')
    if report.get('mathlib_commit')!=pin:raise ValueError('OWN_STATE: own source probe pin differs')
    if path.parent.name.startswith('bound-'):
        reuse=report.get('metadata_reuse',{});parent=reuse.get('stage_evidence_path')
        if not isinstance(parent,str):raise ValueError('OWN_STATE: bound source has no actual stage origin')
        parent_relative='case/'+parent
        previous=source_report(root,parent_relative,pin,seen=seen|{relative})
        original=root/parent_relative
        if hashlib.sha256(original.read_bytes()).hexdigest()!=reuse.get('stage_evidence_sha256'):
            raise ValueError('OWN_STATE: native alias origin hash differs')
        expected='bound-'+next(iter(report.get('sources',{})),'')+'-'+reuse['stage_evidence_sha256'][:16]
        before=previous.get('sources',{}).get(reuse.get('previous_bound_source_id'))
        if path.parent.name!=expected or len(report.get('sources',{}))!=1 or before!=next(iter(report['sources'].values())):
            raise ValueError('OWN_STATE: native alias changed source identity/content')
    return report


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                                    separators=(',',':')).encode()).hexdigest()


def progress_from_result(tool,result):
    if not isinstance(result,dict):return None
    if tool in {'check_draft','submit_draft','check_artifact','submit_artifact'}:
        row=result.get('author_closing_check')
    elif tool=='record_author_checks':row=result
    elif tool=='read_author_packet':
        row={'candidate':result.get('candidate'),'content_sha256':result.get('content_sha256'),
             'acceptance_contract':result.get('acceptance_contract'),
             **result.get('closing_progress',{})}
    else:return None
    if not isinstance(row,dict) or not {'candidate','content_sha256','open_issues',*_FIELDS}<=row.keys():return None
    if type(row['candidate']) is not int or row['candidate']<1:return None
    if not isinstance(row['content_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',row['content_sha256']):return None
    issues=row['open_issues']
    if not isinstance(issues,list):return None
    return {'candidate':row['candidate'],'content_sha256':row['content_sha256'],
        **{key:deepcopy(row[key]) for key in _FIELDS},
        'open_issues':[{key:issue[key] for key in ['id','criterion','location']}
                       for issue in issues[:POLICY['open_issue_limit']]],
        'open_issue_total':len(issues),'open_issues_truncated':len(issues)>POLICY['open_issue_limit']}


def displayed_progress(tool,result):
    progress=progress_from_result(tool,result)
    return ({'tool':tool,'result_sha256':digest(result),'progress':progress}
            if progress is not None else None)


def source_index(stage):
    root=stage.logs.resolve();case=stage.validator.directory.resolve()
    manifest=json.loads((root/'execution-manifest.json').read_text())
    pin=manifest['resolved_environment']['mathlib']['rev']
    entries=[];seen=set()
    paths=sorted((case/'library').glob('*/library-sources.json'),
                 key=lambda p:p.stat().st_mtime_ns,reverse=True)
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(case):
            raise ValueError('OWN_STATE: source probe escapes the current author stage')
        report=json.loads(path.read_text())
        if report.get('exit_code')!=0 or report.get('probe_version')!=1:continue
        report=source_report(root,str(path.relative_to(root)),pin)
        if report.get('exit_code')!=0 or report.get('probe_version')!=1:continue
        if report.get('mathlib_commit')!=pin:raise ValueError('OWN_STATE: own source probe pin differs')
        for identifier,row in report.get('sources',{}).items():
            key=(identifier,row.get('declaration'))
            if key in seen or row.get('declaration_kind')!='theorem':continue
            if not re.fullmatch(r'M\d{3,}',identifier):raise ValueError('OWN_STATE: invalid own probe ID')
            seen.add(key)
            entries.append({'id':identifier,'declaration':row['declaration'],'module':row['module'],
                'evidence':{'path':str(path.relative_to(root)),
                            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}})
    return entries[:POLICY['source_probe_limit']],len(entries)


def snapshot(stage,number):
    index,total=source_index(stage)
    authority=json.loads((stage.logs/'execution-manifest.json').read_text()).get('acceptance_contract')
    shown=getattr(stage,'last_own_progress',None)
    state={'schema':POLICY['version'],'candidate':number,
        'progress':deepcopy(shown['progress']) if shown else None,
        'progress_origin':{k:shown[k] for k in ['tool','result_sha256']} if shown else None,
        'progress_matches_current_candidate':bool(shown and shown['progress']['candidate']==number),
        'progress_matches_current_authority':bool(shown and shown['progress']['acceptance_contract']==authority),
        'source_probe_index':index,'source_probe_total':total,
        'source_probe_index_truncated':total>len(index),'mathematical_acceptance':False}
    path=stage.validator.directory/('own-state-'+digest(state)+'.json')
    text=json.dumps(state,sort_keys=True,ensure_ascii=False,indent=2)+'\n'
    if path.exists() and path.read_text()!=text:raise ValueError('OWN_STATE: immutable snapshot changed')
    if not path.exists():path.write_text(text)
    sources=[{'path':str(path.relative_to(stage.logs)),
              'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},
             *[row['evidence'] for row in index]]
    return state,sources


def verify(directory,data,records,tool_results,manifest):
    """Read back every transmitted reminder against its actual local origin."""
    state=data.get('own_state');number=data.get('candidate_number')
    expected={'schema','candidate','progress','progress_origin','progress_matches_current_candidate','progress_matches_current_authority',
              'source_probe_index','source_probe_total','source_probe_index_truncated','mathematical_acceptance'}
    if manifest.get('own_state_policy')!=POLICY or data.get('checkpoint_version')!=2:return False
    if not isinstance(state,dict) or set(state)!=expected:return False
    if state['schema']!=POLICY['version'] or state['candidate']!=number or state['mathematical_acceptance'] is not False:return False
    if records.get('case/own-state-'+digest(state)+'.json')!=state:return False
    origin=state['progress_origin'];progress=state['progress']
    if origin is None:
        if (progress is not None or state['progress_matches_current_candidate'] is not False
                or state['progress_matches_current_authority'] is not False):return False
    else:
        if not isinstance(origin,dict) or set(origin)!={'tool','result_sha256'}:return False
        result=tool_results.get((origin['tool'],origin['result_sha256']))
        if result is None or progress_from_result(origin['tool'],result)!=progress:return False
        if not 1<=progress['candidate']<=number:return False
        candidate=Path(directory)/'case'/f"candidate-{progress['candidate']:04d}.json"
        if not candidate.is_file() or digest(json.loads(candidate.read_text()))!=progress['content_sha256']:return False
        if state['progress_matches_current_candidate']!=(progress['candidate']==number):return False
        if state['progress_matches_current_authority']!=(progress['acceptance_contract']==manifest.get('acceptance_contract')):return False
    index=state['source_probe_index']
    if not isinstance(index,list) or len(index)>POLICY['source_probe_limit']:return False
    if type(state['source_probe_total']) is not int or state['source_probe_total']<len(index):return False
    if state['source_probe_index_truncated']!=(state['source_probe_total']>len(index)):return False
    pin=manifest.get('resolved_environment',{}).get('mathlib',{}).get('rev')
    for entry in index:
        if not isinstance(entry,dict) or set(entry)!={'id','declaration','module','evidence'}:return False
        proof=entry['evidence']
        if not isinstance(proof,dict) or set(proof)!={'path','sha256'}:return False
        if not isinstance(proof['path'],str) or not re.fullmatch(SOURCE_PATH_PATTERN,proof['path']):return False
        report=records.get(proof['path'])
        path=Path(directory)/proof['path']
        if path.is_symlink() or not path.resolve().is_relative_to(Path(directory).resolve()/'case'):return False
        if not report or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=proof['sha256']:return False
        if source_report(directory,proof['path'],pin)!=report:return False
        if report.get('exit_code')!=0 or report.get('probe_version')!=1 or report.get('mathlib_commit')!=pin:return False
        row=report.get('sources',{}).get(entry['id'],{})
        if any(row.get(key)!=entry[key] for key in ['declaration','module']):return False
        if row.get('declaration_kind')!='theorem':return False
    return True
