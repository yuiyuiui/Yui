#!/usr/bin/env python3
"""Inverted-index retrieval; only shortlisted full strategy cards are read."""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import time

HERE=Path(__file__).resolve().parents[1]
BANK=HERE/'bank'
FAMILIES={'representation','analysis','calculation','interface','provenance','execution','unknown'}
MAX_SCORED=64


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(bank=BANK):
    bank=Path(bank)
    cards=json.loads((bank/'strategies.json').read_text())
    ids=set()
    meta={}
    postings={}
    (bank/'cards').mkdir(exist_ok=True)
    for card in cards:
        sid=card['id']
        if sid in ids: raise ValueError('duplicate strategy ID')
        ids.add(sid)
        if card['family'] not in FAMILIES-{'unknown'}: raise ValueError('unknown family')
        for key in ('title','obstacle','procedure','preconditions','contraindications','verification','positive_example','negative_example','evidence','lean_versions','tags','status'):
            if key not in card: raise ValueError('missing card field: '+key)
        if not card['evidence'] or not card['procedure']: raise ValueError('unsubstantiated card')
        path=bank/'cards'/f'{sid}.json'
        path.write_text(json.dumps(card,ensure_ascii=False,indent=2)+'\n')
        meta[sid]={k:card[k] for k in ('title','family','tags','preconditions','contraindications','lean_versions','status')}
        meta[sid].update({'path':str(path.relative_to(bank)),'sha256':sha(path)})
        keys=['family:'+card['family']]+['tag:'+t.lower() for t in card['tags']]
        for key in keys: postings.setdefault(key,[]).append(sid)
    index={'version':1,'source_sha256':sha(bank/'strategies.json'),'metadata':meta,
           'postings':{k:sorted(v) for k,v in postings.items()}}
    (bank/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    _index.cache_clear()
    return {'strategies':len(cards),'posting_keys':len(postings)}


@lru_cache(maxsize=8)
def _index(path,mtime,size):
    return json.loads(Path(path).read_text())


def search(query,bank=BANK,limit=3):
    start=time.perf_counter()
    bank=Path(bank)
    family=query.get('family','unknown')
    if family not in FAMILIES: raise ValueError('invalid problem family')
    limit=max(1,min(int(limit),3))
    path=bank/'index.json'
    stat=path.stat()
    index=_index(str(path),stat.st_mtime_ns,stat.st_size)
    counts={'bank_size':len(index['metadata']),'metadata_scored':0,'full_cards_read':0,'truncated':False}
    if family=='unknown':
        return {'status':'ABSTAIN','reason':'insufficient diagnosis; supply an observed family and tags','counts':counts,'strategies':[]}
    family_ids=set(index['postings'].get('family:'+family,[]))
    tags={str(x).lower() for x in query.get('tags',[])}
    sets=[family_ids & set(index['postings'].get('tag:'+t,[])) for t in tags]
    nonempty=[s for s in sets if s]
    if tags and not nonempty:
        return {'status':'ABSTAIN','reason':'no indexed observed tag matched; refine the diagnostic',
                'counts':counts,'strategies':[]}
    candidates=set.intersection(*nonempty) if nonempty else family_ids
    if not candidates and nonempty: candidates=set.union(*nonempty)
    counts['posting_candidates']=len(candidates)
    # Bound scoring, report truncation honestly; no exhaustive LLM comparison.
    chosen=sorted(candidates)[:MAX_SCORED]
    counts['truncated']=len(candidates)>MAX_SCORED
    facts=set(query.get('facts',[]))
    excluded=set(query.get('contraindications',[]))
    version=query.get('lean_version')
    ranked=[]
    rejected=[]
    for sid in chosen:
        meta=index['metadata'][sid]
        counts['metadata_scored']+=1
        if version not in meta['lean_versions']:
            rejected.append({'id':sid,'reason':'toolchain not checked'})
            continue
        if excluded & set(meta['contraindications']):
            rejected.append({'id':sid,'reason':'reported contraindication'})
            continue
        missing=set(meta['preconditions'])-facts
        overlap=len(tags & {t.lower() for t in meta['tags']})
        score=4*overlap+len(set(meta['preconditions'])&facts)-len(missing)
        ranked.append((score,sid,sorted(missing)))
    result=[]
    for score,sid,missing in sorted(ranked,key=lambda x:(-x[0],x[1]))[:limit]:
        meta=index['metadata'][sid]
        file=bank/meta['path']
        if sha(file)!=meta['sha256']: raise ValueError('stale/modified strategy card')
        card=json.loads(file.read_text())
        counts['full_cards_read']+=1
        # Evidence excerpts may contain an original reference proof. They are
        # owner-only retrospective data, never delivered to measured workers.
        public={k:v for k,v in card.items() if k!='evidence'}
        public['evidence']=[{k:v for k,v in e.items() if k!='excerpt'} for e in card['evidence']]
        result.append({'id':sid,'score':score,'applicability':'CONDITIONAL' if missing else 'PRECONDITIONS_REPORTED',
                       'missing_preconditions':missing,'preconditions_independently_verified':False,'card':public})
    return {'status':'CANDIDATES' if result else 'NO_APPLICABLE_CANDIDATE',
            'strategies':result,'rejected':rejected,'counts':counts,
            'wall_milliseconds':1000*(time.perf_counter()-start),
            'boundary':'Recipes are proposals, not new mathematical facts or guaranteed fixes.'}


def diagnose(observation):
    """Conservative observed-feature routing; not semantic root-cause inference."""
    if observation.get('transport_fault') or observation.get('environment_fault'):
        return {'family':'execution','tags':['transport','environment'],'facts':[],
                'lean_version':observation.get('lean_version'),'confidence':'observed_fault_not_math_gap'}
    text=' '.join(str(observation.get(k,'')) for k in ('goal','context','diagnostic')).lower()
    tags=[]
    if ('ennreal' in text or 'ₑ' in text) and '‖' in text:
        family='representation';tags=['norm','supremum','ENNReal']
    elif ('=ᵐ' in text or 'almost everywhere' in text or 'ae_eq' in text) and ('continuous' in text or 'pointwise' in text):
        family='representation';tags=['ae','representative']
    elif 'fourier' in text and ('2 *' in text or 'normalization' in text or '2π' in text):
        family='representation';tags=['Fourier','normalization']
    elif 'memlp' in text and ('aestronglymeasurable' in text or 'rpow' in text or '^ s' in text):
        family='analysis';tags=['weight','Lp','measurability','domination']
    else:
        family='unknown'
    return {'family':family,'tags':tags,'facts':[],
            'lean_version':observation.get('lean_version'),
            'confidence':'candidate_observation_route_only','root_cause_confirmed':False}


def grounded_query(query,goal,context,lean_version,diagnostic=''):
    """Use actual immutable version/state instead of requiring model spelling.

    This only grounds observations. It does not prove strategy preconditions.
    """
    routed=diagnose({'goal':goal,'context':context,'diagnostic':diagnostic,'lean_version':lean_version})
    q=dict(query)
    reported={'family':q.get('family'),'lean_version':q.get('lean_version'),'tags':q.get('tags',[])}
    q['lean_version']=lean_version
    if routed['family']!='unknown':
        q['family']=routed['family']
        q['tags']=routed['tags']
    # Existing model-written facts remain unverified claims; the returned card
    # must not mark a missing mathematical condition as established.
    q.setdefault('facts',[])
    return q,{'reported_query':reported,'observed_route':routed,
              'version_source':'immutable interface contract',
              'precondition_verification':'not performed by routing'}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('command',choices=['build','query','diagnose'])
    ap.add_argument('--json',default='{}')
    a=ap.parse_args()
    if a.command=='build': result=build()
    elif a.command=='diagnose': result=diagnose(json.loads(a.json))
    else: result=search(json.loads(a.json))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
