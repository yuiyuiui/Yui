"""Optional user-maintained source catalog. Entries never grant mathematical PASS."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import re
import uuid

from runtime_config import CORE,load_lock

_selected_root=ContextVar('yui_library_root',default=None)
STOP=set('a an the and or for of on in to from into with without that this those is are be by using use find theorem lemma mathlib function functions'.split())
NORMAL={'compactness':'compact','integration':'integral','integrability':'integral','integrable':'integral',
        'continuity':'continuous','derivative':'deriv','derivatives':'deriv',
        'finitely':'finite','generation':'generated','generators':'generated'}


def catalog_path():
    selected=_selected_root.get()
    if selected is not None:return selected/'foundations.json'
    override=os.environ.get('YUI_LIBRARY_ROOT')
    root=Path(override).expanduser().resolve() if override else CORE/'library'
    return root.resolve()/'foundations.json'


@contextmanager
def use_library(root):
    token=_selected_root.set(Path(root).resolve())
    try:yield
    finally:_selected_root.reset(token)


def load():
    path=catalog_path()
    if not path.is_file():return {'version':1,'entries':[]}
    value=json.loads(path.read_text())
    if value.get('version')!=1 or not isinstance(value.get('entries'),list):
        raise ValueError('Unsupported user library catalog')
    names=[entry['declaration'] for entry in value['entries']]
    if len(names)!=len(set(names)):raise ValueError('Duplicate library declaration')
    return value


def evidence_path(entry):
    root=catalog_path().parent.resolve()
    relative=Path(entry['evidence']['path'])
    path=root/relative
    if relative.is_absolute() or not path.resolve().is_relative_to(root):
        raise ValueError('Catalog evidence escapes its root')
    return path


def catalog_files():
    path=catalog_path()
    if not path.is_file():return []
    return sorted({path.resolve(),*(evidence_path(entry) for entry in load()['entries'])})


def binding():
    """Bind the selected catalog, including its absence, without importing notes."""
    return {'path':str(catalog_path().resolve()),'files':[
        {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in catalog_files()]}


def source_record(report,identifier,lock):
    row=report['sources'][identifier]
    root=Path(lock['mathlib']['local_path']).resolve()
    source=(root/row['source_path']).resolve()
    if (not source.is_relative_to(root/'Mathlib') or source.suffix!='.lean'
            or row['source_path']!=row['module'].replace('.','/')+'.lean'):
        raise ValueError('Catalog source is outside its declared Mathlib module')
    if (report.get('probe_version')!=1 or report['exit_code']!=0
            or report.get('mathlib_commit')!=lock['mathlib']['rev']
            or row['declaration_kind']!='theorem' or row['mathlib_commit']!=lock['mathlib']['rev']
            or report['lean_version']!=lock['lean']['version'] or report['result']['exit_code']!=0
            or row['source_sha256']!=hashlib.sha256(source.read_bytes()).hexdigest()
            or not re.match(r'^@?'+re.escape(row['declaration'])+r'(?:\.\{|\s|:)',row['signature'])
            or not isinstance(row.get('axioms'),str) or not row['axioms']):
        raise ValueError('Catalog pin/declaration/source identity changed')
    return row


def verified(entry,lock=None):
    lock=lock or load_lock()
    path=evidence_path(entry)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['evidence']['sha256']:raise ValueError('Catalog evidence changed')
    report=json.loads(path.read_text());row=source_record(report,entry['source_id'],lock)
    if row['declaration']!=entry['declaration'] or row['module']!=entry['module']:
        raise ValueError('Catalog pin/declaration/source identity changed')
    return row,report,path


def write_catalog(value):
    path=catalog_path();temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def add(receipt,identifier,tags):
    """Explicit post-run import of intact metadata; no model or Lean invocation."""
    raw=Path(receipt).read_bytes();report=json.loads(raw)
    row=source_record(report,identifier,load_lock())
    if not tags or any(not isinstance(tag,str) or not tag.strip() for tag in tags):
        raise ValueError('Supply nonempty search tags')
    root=catalog_path().parent;root.mkdir(parents=True,exist_ok=True)
    lock_path=root/'.maintenance.lock'
    with lock_path.open('x'):
        try:
            value=load()
            for entry in value['entries']:
                if entry['declaration']!=row['declaration']:continue
                previous,_,_=verified(entry)
                if previous!=row:
                    raise ValueError('Existing declaration differs; review and version it explicitly')
                combined=list(dict.fromkeys([*entry['tags'],*tags]))
                if combined==entry['tags']:return {'status':'ALREADY_PRESENT','declaration':row['declaration']}
                entry['tags']=combined;write_catalog(value)
                return {'status':'TAGS_UPDATED','declaration':row['declaration']}
            digest=hashlib.sha256(raw).hexdigest()
            relative=Path('evidence')/(digest+'.json');destination=root/relative
            destination.parent.mkdir(exist_ok=True)
            if destination.exists() and destination.read_bytes()!=raw:
                raise ValueError('Existing evidence bytes differ; refusing to overwrite')
            if not destination.exists():destination.write_bytes(raw)
            value['entries'].append({'declaration':row['declaration'],'module':row['module'],
                'source_id':identifier,'tags':list(dict.fromkeys(tags)),
                'evidence':{'path':str(relative),'sha256':digest}})
            write_catalog(value)
            return {'status':'ADDED','declaration':row['declaration'],'evidence':str(relative)}
        finally:
            lock_path.unlink(missing_ok=True)


def terms(text):
    text=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',text)
    return {NORMAL.get(word,word) for word in re.findall(r'[a-z][a-z0-9]*',text.lower())
            if word not in STOP and len(word)>1}


def ranked(entries,query):
    exact=[entry for entry in entries if entry['declaration']==query.strip()]
    if exact:return [(entry,[],True) for entry in exact[:12]]
    wanted=terms(query);prepared=[];frequency=Counter()
    for entry in entries:
        groups=[terms(entry['declaration']),terms(' '.join(entry['tags'])),terms(entry['module'])]
        vocabulary=set().union(*groups);frequency.update(vocabulary)
        prepared.append((entry,groups,vocabulary))
    scored=[]
    for entry,groups,vocabulary in prepared:
        matched=wanted & vocabulary
        if not matched:continue
        score=sum(sum(weight for weight,group in zip([4,3,1],groups) if word in group)*
                  max(1,len(entries)//(frequency[word]+1)) for word in matched)
        scored.append((score,entry,sorted(matched)))
    scored.sort(key=lambda row:(-row[0],row[1]['declaration']))
    return [(entry,matched,False) for _,entry,matched in scored[:12]]


def lookup(query):
    if not isinstance(query,str) or not query.strip():raise ValueError('Give a source name or mathematical search terms')
    rows=[]
    for entry,matched,exact in ranked(load()['entries'],query):
        row,_,_=verified(entry)
        rows.append({**row,'tags':entry['tags'],'matched_terms':matched,
                     'match_kind':'exact_declaration' if exact else 'keyword_candidate'})
    return {'sources':rows, 'scope':'Ranked discovery candidates with exact proved native metadata. Keyword overlap does not prove relevance or applicability. Register an explicit M node and review its complete NL restatement/application; definitions or new results are not imported.'}


def cached_probe(identifier,declaration,module,lock):
    for entry in load()['entries']:
        # A caller's locator is only a hint. Native evidence fixes the actual
        # module; never copy a guessed importing module into the source record.
        if entry['declaration']==declaration:
            row,report,path=verified(entry,lock)
            clone=json.loads(json.dumps(report))
            clone['sources']={identifier:row}
            clone['metadata_reuse']={'original_source_id':entry['source_id'],
                'catalog_evidence_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'original_native_cost_seconds':report['result']['wall_seconds'],
                'scope':'Pinned verified metadata reused; this is not a fresh native query or a source/application audit.'}
            return row,clone
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library-root',type=Path,help='Optional catalog directory outside the skill')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('check',help='Check existing receipt hashes and pinned source metadata; no new Lean run')
    search=commands.add_parser('search');search.add_argument('query')
    insert=commands.add_parser('add',help='Import a selected source from an existing native probe receipt')
    insert.add_argument('--receipt',type=Path,required=True)
    insert.add_argument('--source-id',required=True)
    insert.add_argument('--tag',action='append',required=True,dest='tags')
    args=parser.parse_args()
    if args.library_root is not None:os.environ['YUI_LIBRARY_ROOT']=str(args.library_root)
    try:
        from runtime_config import verify
        verify()
        if args.command=='search':result=lookup(args.query)
        elif args.command=='add':result=add(args.receipt,args.source_id,args.tags)
        else:
            entries=load()['entries']
            for entry in entries:verified(entry)
            result={'status':'CATALOG-CHECKED','entries':len(entries),'catalog':str(catalog_path()),
                    'scope':'Existing metadata checked; no fresh Lean check or mathematical acceptance.'}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({'status':'CATALOG-ERROR','error':str(error)},ensure_ascii=False))
        return 1


if __name__=='__main__':raise SystemExit(main())
