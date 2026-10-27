"""Explicit primary-source uncertainty; never convert a failed check to PASS."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

POLICY='explicit-unverified-primary-1'


def load_bound(base,reference):
    base=Path(base).resolve();path=(base/reference['path']).resolve()
    if not path.is_relative_to(base) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=reference['sha256']:
        raise ValueError('Deferred source evidence missing, escaped or changed')
    return path


def deferred(pid,source,base):
    qualification=source.get('verification')
    if not qualification:return None
    if set(qualification)!={'status','record'} or qualification['status']!='UNVERIFIED_PRIMARY':
        raise ValueError('Unknown external-source qualification')
    path=load_bound(base,qualification['record'])
    if not str(path.relative_to(Path(base).resolve())).startswith('external-sources/deferred-'):
        raise ValueError('Expected an own-stage deferred-source record')
    record=json.loads(path.read_text())
    if record.get('version')!='yui-deferred-source-1' or record.get('source_id')!=pid or record.get('statement')!=source['statement']:
        raise ValueError('Deferred source statement or identity changed')
    if source.get('primary_evidence'):raise ValueError('Deferred primary source cannot claim verified primary evidence')
    basis=load_bound(base,record['basis']).read_text()
    if not record.get('quote') or record['quote'] not in basis or ' '.join(record['quote'].split())!=' '.join(source['statement'].split()):
        raise ValueError('Deferred source must preserve the explicit secondary statement')
    if not record.get('attempts'):raise ValueError('Missing actual source-access attempts')
    attempts=[]
    for attempt in record['attempts']:
        access_path=load_bound(base,attempt)
        if not access_path.is_relative_to(Path(base).resolve()/'external-sources') or not access_path.name.startswith('access-'):
            raise ValueError('Expected an own source-access record')
        access=json.loads(access_path.read_text())
        if access.get('version')!='yui-source-access-1' or access.get('origin')!='controller_https' or access.get('status') not in {
                'HTTP_ERROR','HUMAN_ACCESS_REQUIRED','BROWSER_REQUIRED','UNAVAILABLE','NO_EXTRACTABLE_TEXT'}:
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
