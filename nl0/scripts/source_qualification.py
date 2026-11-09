"""Explicit primary-source uncertainty; never convert a failed check to PASS."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

POLICY='explicit-unverified-primary-1'


def load_bound(base,reference):
    if (not isinstance(reference,dict) or set(reference)!={'path','sha256'}
            or not isinstance(reference['path'],str) or Path(reference['path']).is_absolute()
            or not isinstance(reference['sha256'],str)):
        raise ValueError('Expected a case-relative deferred source reference and sha256')
    base=Path(base).resolve();path=(base/reference['path']).resolve()
    if not path.is_relative_to(base) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=reference['sha256']:
        raise ValueError('Deferred source evidence missing, escaped or changed')
    return path


def deferred(pid,source,base):
    if 'verification' not in source:return None
    qualification=source.get('verification')
    if not isinstance(qualification,dict) or set(qualification)!={'status','record'} or qualification['status']!='UNVERIFIED_PRIMARY':
        raise ValueError('Unknown external-source qualification')
    path=load_bound(base,qualification['record'])
    if not str(path.relative_to(Path(base).resolve())).startswith('external-sources/deferred-'):
        raise ValueError('Expected an own-stage deferred-source record')
    record=json.loads(path.read_text())
    if (not isinstance(record,dict) or record.get('version')!='yui-deferred-source-1'
            or record.get('source_id')!=pid or record.get('statement')!=source.get('statement')
            or 'basis' not in record or not isinstance(record.get('attempts'),list)
            or not isinstance(record.get('qualification'),str)):
        raise ValueError('Deferred source statement or identity changed')
    if source.get('primary_evidence'):raise ValueError('Deferred primary source cannot claim verified primary evidence')
    basis=load_bound(base,record['basis']).read_text()
    if not isinstance(record.get('quote'),str) or not record['quote'] or record['quote'] not in basis or ' '.join(record['quote'].split())!=' '.join(source['statement'].split()):
        raise ValueError('Deferred source must preserve the explicit secondary statement')
    if not record.get('attempts'):raise ValueError('Missing actual source-access attempts')
    attempts=[]
    for attempt in record['attempts']:
        access_path=load_bound(base,attempt)
        if not access_path.is_relative_to(Path(base).resolve()/'external-sources') or not access_path.name.startswith('access-'):
            raise ValueError('Expected an own source-access record')
        access=json.loads(access_path.read_text())
        from source_access import failed_access
        if not isinstance(access,dict) or not failed_access(access):
            raise ValueError('Source deferral is not supported by recorded unavailable access')
        attempts.append({key:access.get(key) for key in ('url','status','http_status','reason')})
    return {'source_id':pid,'statement':source['statement'],'record':qualification['record'],
            'record_path':str(path),'qualification':record['qualification'],
            'retrieval_attempts':record['attempts'],'access_outcomes':attempts}


def classify(unresolved,props,base):
    warnings=[row for pid,p in props.items() if p['kind']=='external'
              for row in [deferred(pid,p['source'],base)] if row]
    allowed={row['source_id'] for row in warnings}
    eligible=bool(warnings and unresolved)
    for row in unresolved:
        parts=row['review'].split('.')
        eligible=eligible and row['verdict']=='UNVERIFIED' and parts[0] in allowed and (
            len(parts)==1 or len(parts)==3 and parts[1]=='citation_checks')
    # A reviewer must disclose source uncertainty, even if other proof checks pass.
    for pid in allowed:
        if not any(r['review']==pid and r['verdict']=='UNVERIFIED' for r in unresolved):
            raise ValueError('Deferred primary source was incorrectly reported as verified')
    return bool(eligible),warnings


def relabel(directory, source, previous, current):
    """Reissue the same verified deferral for a renamed graph node; retain all original evidence."""
    from controller_common import write
    import re
    if not all(isinstance(label,str) and re.fullmatch(r'E\d{3,}',label) for label in (previous,current)):
        raise ValueError('Expected external graph labels for a deferred source')
    warning=deferred(previous,source,directory)
    if not warning:
        raise ValueError('Expected a validated deferral before reissuing its graph label')
    old=source['verification']['record']
    value=json.loads(load_bound(directory,old).read_text())
    value['source_id']=current
    dest=Path(directory)/'external-sources'/f'deferred-{current}-{old["sha256"]}.json'
    if dest.exists() and json.loads(dest.read_text())!=value:
        raise ValueError('Changed previously bound source deferral')
    write(dest,value)
    ref={'path':str(dest.relative_to(directory)), 'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
    source['verification']['record']=ref
    refs=source.get('evidence',[])
    if not isinstance(refs,list):
        raise ValueError(f'{previous}.source.evidence must be a list')
    source['evidence']=[ref if item==old else item for item in refs]
    deferred(current,source,directory)


def usable(result):
    return bool(result.get('current_standard_receipt_valid') or result.get('current_conditional_receipt_valid'))


def source_only_finding(finding,data,base):
    """Only located UNVERIFIED source warnings may accompany conditional work."""
    if finding.get('verdict')!='UNVERIFIED' or not finding.get('locations'):return False
    _,graph,_,props,*_=data
    prefixes=['nl0.json#/propositions/'+str(i)+'/source' for i,p in enumerate(graph['propositions'])
              if p['kind']=='external' and deferred(p['id'],p['source'],base)]
    return bool(prefixes) and all(any(loc==p or loc.startswith(p+'/') for p in prefixes)
                                  for loc in finding['locations'])


def publish(directory,data):
    from controller_common import write
    result,_,spec,props,*_=data
    warnings=result.get('source_warnings')
    if warnings is None:
        warnings=[row for pid,p in props.items() if p['kind']=='external'
                  for row in [deferred(pid,p['source'],Path(directory))] if row]
    if not warnings:return None
    payload={'policy':POLICY,'status':'UNVERIFIED_PRIMARY_SOURCES','full_target':spec['full_target'],
             'source_hashes':{'graph':result['graph_sha256'],'spec':result['spec_sha256']},
             'warnings':warnings,'unqualified_pass':False,
             'message':'Primary texts were not verified. Any completed Lean result is conditional on the listed external statements.'}
    directory=Path(directory);write(directory/'warn.json',payload)
    (directory/'warn.md').write_text('# Unverified primary sources\n\n'+payload['message']+'\n\n'+
        '\n\n'.join('## '+w['source_id']+'\n\n'+w['statement']+'\n\n'+w['qualification']+
            '\n\nRecord: ['+w['source_id']+']('+w['record_path']+')\n\n'+
            '\n'.join('- '+str(a['status'])+': '+str(a['url'])+
                      (' (HTTP '+str(a['http_status'])+')' if a['http_status'] else '') for a in w['access_outcomes'])
            for w in warnings)+'\n')
    return payload
