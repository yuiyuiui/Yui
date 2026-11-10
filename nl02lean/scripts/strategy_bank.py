#!/usr/bin/env python3
"""Inverted-index retrieval; only shortlisted full strategy cards are read."""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time

HERE=Path(__file__).resolve().parents[1]
BANK=HERE/'bank'
BASIS_BANK=HERE.parent/'nl0/basis-bank'
FAMILIES={'representation','analysis','calculation','interface','provenance','execution','unknown'}
MAX_SCORED=64
DOMAINS={'general','analysis','algebra','geometry','probability','number_theory',
         'combinatorics','topology','logic','algorithms'}
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


@lru_cache(maxsize=1)
def reference_policy():
    from workflow_execution import block_module
    return block_module(HERE.parent / 'workflow', 'strategy_reference')


def _inside(bank, relative):
    path = (bank / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(bank.resolve()):
        raise ValueError('Strategy reference escapes its bank')
    return path


@lru_cache(maxsize=4)
def _case_digests(core, manifest_digest):
    raw = (core.parent / 'runtime-manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest_digest:
        raise ValueError('Run manifest changed')
    manifest = json.loads(raw)
    if Path(manifest['runtime_root']) != core:
        raise ValueError('Wrong runtime root')
    return {row['relative_path']:row['sha256'] for row in manifest['files']}


def _standalone_binding(bank, frozen):
    """Publish one complete snapshot; retained and simultaneous authors reuse its original pins."""
    marker = 'reference-binding.json'
    if not frozen.exists():
        frozen.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=frozen.parent) as staging:
            snapshot = Path(staging) / 'bank'
            snapshot.mkdir()
            for name in ('strategies.json', 'index.json'):
                shutil.copyfile(_inside(bank, name), snapshot/name)
            cards = json.loads((snapshot/'strategies.json').read_bytes())
            paths = {f"cards/{card['id']}.json" for card in cards}
            paths.update(e['path'] for card in cards for e in card['evidence'])
            for relative in sorted(paths):
                target = _inside(snapshot, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(_inside(bank, relative), target)
            pins = {'source':sha(snapshot/'strategies.json'), 'index':sha(snapshot/'index.json')}
            (snapshot/marker).write_text(json.dumps(pins))
            try:
                snapshot.rename(frozen)
            except OSError:
                if not frozen.is_dir():
                    raise
    pins = json.loads(_inside(frozen, marker).read_bytes())
    return {'path':str(frozen), 'source':pins['source'], 'index':pins['index']}


def reference_bindings(names, destination):
    roots = {'basis': BASIS_BANK, 'lean': BANK}
    core = HERE.parent
    job_path = core.parent / 'job.json'
    case_runtime = core.name == 'runtime' and (job_path.exists() or (core.parent/'runtime-manifest.json').exists())
    bindings = {}
    for name in names:
        bank = roots[name]
        try:
            if case_runtime:
                job = json.loads(job_path.read_bytes())
                pins = _case_digests(core, job['runtime_snapshot']['manifest']['sha256'])
                rel = bank.relative_to(core)
                bindings[name] = {'path':str(bank), 'source':pins[str(rel/'strategies.json')],
                                  'index':pins[str(rel/'index.json')]}
            else:
                bindings[name] = _standalone_binding(bank, Path(destination) / name)
        except (OSError, ValueError, TypeError, KeyError):
            bindings[name] = {'error':'The optional bank could not be bound to this run.'}
    return bindings


def install_reference(stage, bindings=None):
    policy = reference_policy()
    names = policy.banks_for(stage.mode, stage.instruction_arm)
    if names:
        stage.strategy_banks = bindings if bindings is not None else reference_bindings(
            names, stage.logs/'strategy-reference')
        stage.tools.append(policy.tool(names))


def consult(stage, query):
    """The stage supplies permissions and version. A card read confers no proof authority."""
    import artifact_protocol as protocol
    policy = reference_policy()
    names = policy.banks_for(stage.mode, stage.instruction_arm)
    try:
        protocol.validate(query, policy.query_schema(names))
    except ValueError as error:
        result = {'status':'invalid_query', 'error':str(error)}
        protocol.validate(result, policy.contracts()['StrategyReply@1'])
        return result
    name = query['bank']
    binding = stage.strategy_banks[name]
    try:
        version = stage.native_timeout_lean_version
        if version is None:
            lock = json.loads((HERE.parent/'toolchain/lock.json').read_bytes())
            version = lock['lean']['toolchain'].split(':v')[-1]
        result = _consult_bank(name, binding, version, query.get('ids'))
    except (OSError, ValueError, TypeError, KeyError) as error:
        result = {'bank':name, 'status':'unavailable',
                  'reason':error.strerror if isinstance(error, OSError) else str(error)}
    protocol.validate(result, policy.contracts()['StrategyReply@1'])
    return result


def bound_bank_data(binding):
    if 'error' in binding:
        raise ValueError(binding['error'])
    bank = Path(binding['path'])
    raw_index = _inside(bank, 'index.json').read_bytes()
    if hashlib.sha256(raw_index).hexdigest() != binding['index']:
        raise ValueError('Pinned strategy index changed')
    index = json.loads(raw_index)
    source = _inside(bank, 'strategies.json').read_bytes()
    if (index['version'] != 2 or index['source_sha256'] != binding['source'] or
            hashlib.sha256(source).hexdigest() != binding['source']):
        raise ValueError('Pinned strategy source changed')
    return bank, index, source


def _consult_bank(name, binding, version, ids):
    bank, index, source = bound_bank_data(binding)
    metadata = {sid:row for sid,row in index['metadata'].items() if version in row['lean_versions']}
    reply = {'bank':name, 'revision':binding['source']}
    if ids is None:
        fields = ('revision', 'title', 'family', 'obstacle')
        return {**reply, 'status':'catalog',
                'catalog':[{'id':sid, **{key:row[key] for key in fields}} for sid,row in metadata.items()]}
    unknown = [sid for sid in ids if sid not in metadata]
    if unknown:
        return {**reply, 'status':'not_in_catalog', 'ids':unknown}
    cards = {c['id']:c for c in json.loads(source) if c['id'] in ids} if ids else {}
    selected = []
    for sid in ids:
        meta = index['metadata'][sid]
        if meta['path'] != f'cards/{sid}.json':
            raise ValueError('Indexed strategy path differs from its card ID')
        data = _inside(bank, meta['path']).read_bytes()
        card = json.loads(data)
        if hashlib.sha256(data).hexdigest() != meta['sha256'] or card != cards[sid]:
            raise ValueError('Selected strategy differs from its bound source')
        validate_card(card, bank)
        selected.append(public_card(card))
    kept, omitted = reference_policy().bounded_cards(selected)
    return {**reply, 'status':'cards', 'cards':kept, 'omitted':omitted}


def public_card(card):
    return {**card, 'evidence':[{k:e[k] for k in ('kind','note')} for e in card['evidence']]}


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
            next_action=('ST020 offers optional diagnostics for this native failure. '
                         'You may use a small typed fragment or your own repair method. '
                         'Recheck the complete target with its original inputs.'))
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
        meta[sid]={k:card[k] for k in ('title','revision','family','obstacle','domains','tags','preconditions','contraindications','lean_versions','status')}
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
        public=public_card(card)
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
    ap.add_argument('--bank',choices=('basis','lean'),default='lean')
    a=ap.parse_args()
    bank=BASIS_BANK if a.bank=='basis' else BANK
    if a.command=='build': result=build(bank)
    elif a.command=='diagnose': result=diagnose(json.loads(a.json))
    else: result=search(json.loads(a.json),bank)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
