#!/usr/bin/env python3
"""Inverted-index retrieval; only shortlisted full strategy cards are read."""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import time

HERE=Path(__file__).resolve().parents[1]
BANK=HERE/'bank'
FAMILIES={'representation','analysis','calculation','interface','provenance','execution','unknown'}
MAX_SCORED=64
DOMAINS={'general','analysis','algebra','geometry','probability','number_theory',
         'combinatorics','topology','logic'}
CARD_FIELDS={'id','revision','title','family','domains','tags','obstacle','preconditions',
             'contraindications','procedure','verification','positive_example',
             'negative_example','evidence','lean_versions','status'}
EVIDENCE_KINDS={'design_rule','generalized_observation','synthetic_control'}
CASE_ID=re.compile(r'\b(?:[HRNTD]\d{3,}|bench_case_\d+|20\d{6}T\d{6}Z)\b')
NATIVE_TIMEOUT_POLICY='native-timeout-st020-1'
NATIVE_TIMEOUT_CARD='ST020'
HEARTBEAT_ERROR=re.compile(
    r'^.*\.lean:\d+:\d+:\s+error(?:\([^\n)]*\))?:[^\n]*'
    r'(?:\(deterministic\) timeout|\(kernel\) deterministic timeout)[^\n]*'
    r'maximum number of heartbeats \([0-9]+\) has been reached',re.MULTILINE)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_timeout_kind(result):
    """Classify actual native results, never model prose or generic exit codes."""
    if (not isinstance(result,dict) or result.get('cancelled')
            or result.get('error_kind') not in {None,'LEAN_TIMEOUT'}
            or result.get('feedback_kind')=='candidate_rejected'):
        return None
    if (result.get('exit_code')==124 and result.get('timed_out') is True
            and result.get('error_kind')=='LEAN_TIMEOUT'
            and result.get('timeout_scope')=='native_call'):
        return 'NATIVE_WALL_TIMEOUT'
    if result.get('exit_code')!=1:
        return None
    diagnostics='\n'.join(result.get(k,'') for k in ('stdout','stderr')
                          if isinstance(result.get(k,''),str))
    if HEARTBEAT_ERROR.search(diagnostics):
        return 'NATIVE_HEARTBEAT_EXHAUSTED'
    return None


def freeze_native_timeout_policy(destination,bank=None):
    """Snapshot one advice card at stage entry; no search or model call."""
    bank=Path(bank or BANK).resolve();destination=Path(destination).resolve()
    state={'policy':NATIVE_TIMEOUT_POLICY,'card_id':NATIVE_TIMEOUT_CARD,
           'status':'UNAVAILABLE','files':[],'bank_root':str(destination)}
    try:
        index=json.loads((bank/'index.json').read_text())
        if index.get('version')!=2 or index['source_sha256']!=sha(bank/'strategies.json'):
            raise ValueError('stale strategy index')
        meta=index['metadata'][NATIVE_TIMEOUT_CARD]
        relative=Path(meta['path']);card_path=(bank/relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not card_path.is_relative_to(bank):
            raise ValueError('card escapes the bank')
        if sha(card_path)!=meta['sha256']:raise ValueError('stale/modified strategy card')
        card=json.loads(card_path.read_text());validate_card(card,bank)
        source=json.loads((bank/'strategies.json').read_text())
        if card['id']!=NATIVE_TIMEOUT_CARD or [c for c in source if c['id']==NATIVE_TIMEOUT_CARD]!=[card]:
            raise ValueError('timeout card differs from its source')
        paths=[Path('strategies.json'),Path('index.json'),relative,
               *(Path(e['path']) for e in card['evidence'])]
        for path in dict.fromkeys(paths):
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('timeout evidence path escapes its snapshot')
            data=(bank/path).read_bytes();target=destination/path
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            state['files'].append({'path':str(path),'sha256':hashlib.sha256(data).hexdigest()})
        # Recheck the retained copies, including evidence, before declaring ready.
        validate_card(json.loads((destination/relative).read_text()),destination)
        if sha(destination/'strategies.json')!=index['source_sha256']:
            raise ValueError('strategy source changed during snapshot')
        if (sha(destination/relative)!=meta['sha256']
                or json.loads((destination/'index.json').read_text())!=index):
            raise ValueError('timeout card/index changed during snapshot')
        state.update(status='READY',card_revision=card['revision'],card_sha256=meta['sha256'])
    except (OSError,ValueError,KeyError,TypeError) as error:
        state['reason']=f'{type(error).__name__}: {error}'
    return state


def native_timeout_feedback(result,lean_version,snapshot):
    """Deliver frozen ST020 only after native resource failure; no LLM call."""
    kind=native_timeout_kind(result)
    if kind is None:return None
    feedback={'policy':NATIVE_TIMEOUT_POLICY,'trigger':kind,'status':'UNAVAILABLE',
              'card_id':NATIVE_TIMEOUT_CARD,
              'next_action':('Localize and repair this candidate in the same stage, then recheck '
                             'the unchanged target and inputs. Advice grants no premise or acceptance.')}
    if not snapshot or snapshot.get('status')!='READY':
        feedback['reason']=(snapshot or {}).get('reason','No frozen timeout advice is available')
        return feedback
    feedback.update({k:snapshot[k] for k in ('card_revision','card_sha256')})
    try:
        bank=Path(snapshot['bank_root'])
        for row in snapshot['files']:
            if sha(bank/row['path'])!=row['sha256']:raise ValueError('frozen timeout advice changed')
        query={'family':'execution','tags':['native_timeout'],'lean_version':lean_version,
               'facts':['native_resource_failure_recorded','exact_target_and_inputs_retained',
                        'pinned_environment_available']}
        found=search(query,bank,limit=1)
        cards=found['strategies']
        if not cards or cards[0]['id']!=NATIVE_TIMEOUT_CARD:
            feedback['reason']='No timeout card in the declared toolchain scope'
            return feedback
        feedback.update(status='ADVICE_DELIVERED',strategy=cards[0],
            next_action=('First use the applicable ST020 diagnostic branch to locate and repair '
                         'this native failure. Check a small typed fragment, then recheck the '
                         'complete unchanged target with the same permitted inputs. If that branch '
                         'does not help, revisit the diagnosis and continue normal local repair; '
                         'do not blindly repeat it, raise limits, or add assumptions.'))
    except (OSError,ValueError,KeyError,TypeError) as error:
        feedback['reason']=f'{type(error).__name__}: {error}'
    return feedback


def validate_card(card,bank):
    """Check the storage contract, not generality or mathematical correctness."""
    if not isinstance(card,dict) or set(card)!=CARD_FIELDS:
        raise ValueError('strategy fields do not match the current card contract')
    if not isinstance(card['id'],str) or not re.fullmatch(r'ST\d{3,}',card['id']):
        raise ValueError('invalid strategy ID')
    if type(card['revision']) is not int or card['revision']<1:
        raise ValueError('invalid strategy revision')
    if card['family'] not in FAMILIES-{'unknown'}: raise ValueError('unknown family')
    for key in ('title','obstacle','verification','positive_example','negative_example'):
        if not isinstance(card[key],str) or not card[key].strip():
            raise ValueError('missing card text: '+key)
    for key in ('domains','tags','preconditions','contraindications','procedure','lean_versions'):
        values=card[key]
        if not isinstance(values,list) or any(not isinstance(v,str) or not v.strip() for v in values):
            raise ValueError('invalid card list: '+key)
        if key not in {'preconditions','contraindications'} and not values:
            raise ValueError('empty card list: '+key)
    if not set(card['domains'])<=DOMAINS: raise ValueError('use only broad domain labels')
    if card['status'] not in {'GENERAL_GUIDANCE','OBSERVED_PATTERN'}:
        raise ValueError('invalid guidance evidence status')
    if CASE_ID.search(json.dumps(card,ensure_ascii=False)):
        raise ValueError('case or proof-node identifier in a reusable card')
    if not isinstance(card['evidence'],list) or not card['evidence']:
        raise ValueError('missing guidance evidence')
    for evidence in card['evidence']:
        if not isinstance(evidence,dict) or set(evidence)!={'kind','path','sha256','note'}:
            raise ValueError('evidence must be a sanitized record without proof excerpts')
        if evidence['kind'] not in EVIDENCE_KINDS:
            raise ValueError('unknown evidence kind')
        if not isinstance(evidence['note'],str) or not evidence['note'].strip():
            raise ValueError('missing evidence qualification')
        if not isinstance(evidence['path'],str) or Path(evidence['path']).is_absolute():
            raise ValueError('evidence path must be relative to the bank')
        path=(bank/evidence['path']).resolve()
        if not path.is_relative_to(bank.resolve()) or not path.is_file():
            raise ValueError('evidence must stay inside the bank')
        if sha(path)!=evidence['sha256']: raise ValueError('stale guidance evidence')
    if card['status']=='OBSERVED_PATTERN' and not any(
            e['kind']=='generalized_observation' for e in card['evidence']):
        raise ValueError('observed pattern needs a qualified observation record')


def build(bank=BANK):
    bank=Path(bank)
    cards=json.loads((bank/'strategies.json').read_text())
    ids=set()
    meta={}
    postings={}
    if not isinstance(cards,list): raise ValueError('strategies must be a list')
    for card in cards:
        validate_card(card,bank)
        sid=card['id']
        if sid in ids: raise ValueError('duplicate strategy ID')
        ids.add(sid)
    # Validate every input before replacing any generated output.
    (bank/'cards').mkdir(exist_ok=True)
    for card in cards:
        sid=card['id']
        path=bank/'cards'/f'{sid}.json'
        path.write_text(json.dumps(card,ensure_ascii=False,indent=2)+'\n')
        meta[sid]={k:card[k] for k in ('title','revision','family','domains','tags','preconditions','contraindications','lean_versions','status')}
        meta[sid].update({'path':str(path.relative_to(bank)),'sha256':sha(path)})
        keys=['family:'+card['family']]+['tag:'+t.lower() for t in card['tags']]
        for key in keys: postings.setdefault(key,[]).append(sid)
    index={'version':2,'source_sha256':sha(bank/'strategies.json'),'metadata':meta,
           'postings':{k:sorted(v) for k,v in postings.items()}}
    (bank/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    for path in (bank/'cards').glob('ST*.json'):
        if re.fullmatch(r'ST\d{3,}',path.stem) and path.stem not in ids: path.unlink()
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
    if index.get('version')!=2 or sha(bank/'strategies.json')!=index['source_sha256']:
        raise ValueError('stale strategy index; rebuild from the current source')
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
            rejected.append({'id':sid,'reason':'outside declared toolchain scope'})
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
        validate_card(card,bank)
        counts['full_cards_read']+=1
        # No proof excerpts or historical source paths are stored in live cards.
        # Worker results need only the evidence qualification, not its locator.
        public={k:v for k,v in card.items() if k!='evidence'}
        public['evidence']=[{'kind':e['kind'],'note':e['note']} for e in card['evidence']]
        result.append({'id':sid,'score':score,'applicability':'CONDITIONAL' if missing else 'PRECONDITIONS_REPORTED',
                       'missing_preconditions':missing,'preconditions_independently_verified':False,'card':public})
    return {'status':'CANDIDATES' if result else 'NO_APPLICABLE_CANDIDATE',
            'strategies':result,'rejected':rejected,'counts':counts,
            'wall_milliseconds':1000*(time.perf_counter()-start),
            'boundary':'Recipes are proposals, not new mathematical facts or guaranteed fixes.'}


def diagnose(observation):
    """Recognize explicit execution faults; never infer a subject from notation."""
    if observation.get('transport_fault') or observation.get('environment_fault'):
        return {'family':'execution','tags':['transport','environment'],'facts':[],
                'lean_version':observation.get('lean_version'),'confidence':'observed_fault_not_math_gap'}
    return {'family':'unknown','tags':[],'facts':[],
            'lean_version':observation.get('lean_version'),
            'confidence':'explicit_diagnosis_required','root_cause_confirmed':False}


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
