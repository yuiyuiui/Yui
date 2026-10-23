"""Small pinned-source metadata catalog. Entries never grant mathematical PASS."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from runtime_config import CORE,load_lock

CATALOG=CORE/'library/foundations.json'


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


def lookup(query):
    if not isinstance(query,str) or not query.strip():raise ValueError('Give a source name or foundational tag')
    words=query.lower().split();rows=[]
    for entry in load()['entries']:
        text=' '.join([entry['declaration'],entry['module'],*entry['tags']]).lower()
        if all(word in text for word in words):
            row,_,_=verified(entry)
            rows.append({**row,'tags':entry['tags']})
    return {'sources':rows[:12], 'scope':'Exact proved declarations and full formal signatures only. Register an explicit M node and review its complete NL restatement/application; definitions or new results are not imported.'}


def cached_probe(identifier,declaration,module,lock):
    for entry in load()['entries']:
        if entry['declaration']==declaration and entry['module']==module:
            row,report,path=verified(entry,lock)
            clone=json.loads(json.dumps(report))
            clone['sources']={identifier:row}
            clone['metadata_reuse']={'original_source_id':entry['source_id'],
                'catalog_evidence_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'original_native_cost_seconds':report['result']['wall_seconds'],
                'scope':'Pinned verified metadata reused; this is not a fresh native query or a source/application audit.'}
            return row,clone
    return None
