"""Explicit portable external-library identities, separate from proof acceptance."""
from pathlib import Path
import re

SNAPSHOT='yui-lean-library-snapshot-1'
MODULE=re.compile(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*')
SHA=re.compile(r'[0-9a-f]{64}')
RESERVED={'Mathlib','Lean','Std','Init','Lake','Aesop','Batteries','Qq','ProofWidgets',
          'ImportGraph','Plausible','Cli','Challenge','Solution','YuiBasis','YuiClosed','AuditBExport'}
COMPANIONS={'.olean.private','.olean.server','.ir','.ir.sig'}


def module(name,prefix):
    if not isinstance(name,str) or not MODULE.fullmatch(name) or name.split('.')[0]!=prefix:
        raise ValueError('Lean library module escapes its declared namespace')
    return Path(name.replace('.','/'))


def validate(value,environment):
    if not isinstance(value,dict) or set(value)!={'version','name','lean_version','mathlib_commit','imports','modules'} or value['version']!=SNAPSHOT:
        raise ValueError('Invalid Lean library snapshot metadata')
    name=value['name']
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',name) or name in RESERVED:
        raise ValueError('Lean library namespace is invalid or reserved')
    if not isinstance(value['lean_version'],str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-rc\d+)?',value['lean_version']) or not isinstance(value['mathlib_commit'],str) or not re.fullmatch(r'[0-9a-f]{40}',value['mathlib_commit']):
        raise ValueError('Invalid Lean library environment identity')
    if any(value[k]!=environment[k] for k in ('lean_version','mathlib_commit')):
        raise ValueError('Lean library differs from the pinned Lean/Mathlib environment selected for this run')
    if not isinstance(value['modules'],list) or not value['modules']:
        raise ValueError('Lean library has no bound source/olean modules')
    seen=set()
    for row in value['modules']:
        if not isinstance(row,dict) or set(row)-{'module','source_sha256','olean_sha256','companions'} or not {'module','source_sha256','olean_sha256'}<=set(row):
            raise ValueError('Invalid Lean library module record')
        module(row['module'],name)
        if row['module'] in seen:raise ValueError('Duplicate Lean library module')
        seen.add(row['module'])
        if any(not isinstance(row[k],str) or not SHA.fullmatch(row[k]) for k in ('source_sha256','olean_sha256')):
            raise ValueError('Invalid Lean library content digest')
        companions=row.get('companions',{})
        if not isinstance(companions,dict) or any(k not in COMPANIONS or not isinstance(v,str) or not SHA.fullmatch(v) for k,v in companions.items()):
            raise ValueError('Invalid explicit compiler companion identity')
    if not isinstance(value['imports'],list) or not value['imports'] or any(not isinstance(v,str) for v in value['imports']) or len(set(value['imports']))!=len(value['imports']) or not set(value['imports'])<=seen:
        raise ValueError('Lean library imports must name bound modules')
    return value
