"""Small pinned-source metadata catalog. Entries never grant mathematical PASS."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
import re

from runtime_config import CORE,load_lock

CATALOG=CORE/'library/foundations.json'
STOP=set('a an the and or for of on in to from into with without that this those is are be by using use find theorem lemma mathlib function functions'.split())
NORMAL={'compactness':'compact','integration':'integral','integrability':'integral','integrable':'integral',
        'continuity':'continuous','derivative':'deriv','derivatives':'deriv',
        'finitely':'finite','generation':'generated','generators':'generated'}


def load():
    return json.loads(CATALOG.read_text()) if CATALOG.is_file() else {'entries':[]}


def verified(entry,lock=None):
    lock=lock or load_lock()
    path=(CATALOG.parent/entry['evidence']['path']).resolve()
    if not path.is_relative_to(CATALOG.parent.resolve()):raise ValueError('Catalog evidence escapes its root')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['evidence']['sha256']:raise ValueError('Catalog evidence changed')
    report=json.loads(path.read_text());row=report['sources'][entry['source_id']]
    source=Path(lock['mathlib']['local_path'])/row['source_path']
    if (report['exit_code']!=0 or row['declaration_kind']!='theorem' or row['mathlib_commit']!=lock['mathlib']['rev']
            or report['lean_version']!=lock['lean']['version'] or report['result']['exit_code']!=0
            or row['source_sha256']!=hashlib.sha256(source.read_bytes()).hexdigest()
            or row['declaration']!=entry['declaration'] or row['module']!=entry['module']):
        raise ValueError('Catalog pin/declaration/source identity changed')
    return row,report,path


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
