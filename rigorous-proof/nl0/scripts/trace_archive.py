#!/usr/bin/env python3
"""Lossless archives for completed large run trace files.

Packing keeps raw local evidence in place. A clone restores exact bytes before
validating receipts that refer to raw traces. No live trace or existing Git
history is rewritten, and a changed raw/archive file is never overwritten.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import lzma
from pathlib import Path
import shutil
import subprocess
import tempfile


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def resolve(base,relative):
    path=(base/relative).resolve()
    if not path.is_relative_to(base.resolve()):raise ValueError('Archive path escapes its evidence root')
    return path


def restore(manifest):
    manifest=Path(manifest).resolve();root=manifest.parent
    data=json.loads(manifest.read_text());restored=[]
    for row in data['archives']:
        raw=resolve(root,row['raw']);archive=resolve(root,row['archive'])
        if sha(archive)!=row['archive_sha256']:raise ValueError('Changed archive: '+row['archive'])
        if raw.exists():
            if sha(raw)!=row['raw_sha256']:raise ValueError('Preserve changed raw evidence: '+row['raw'])
            continue
        raw.parent.mkdir(parents=True,exist_ok=True)
        handle=tempfile.NamedTemporaryFile(prefix='.trace-restore-',dir=raw.parent,delete=False)
        temporary=Path(handle.name)
        try:
            opener=lzma.open if row.get('compression')=='lzma-xz' else gzip.open
            with handle,opener(archive,'rb') as source:shutil.copyfileobj(source,handle)
            if sha(temporary)!=row['raw_sha256'] or temporary.stat().st_size!=row['raw_bytes']:raise ValueError('Restored trace differs from recorded exact bytes')
            temporary.rename(raw);restored.append(row['raw'])
        finally:temporary.unlink(missing_ok=True)
    return {'restored':restored,'scope':'Exact evidence bytes only; no mathematical review or rerun is implied.'}


def pack(root,minimum=10*1024*1024):
    root=Path(root).resolve();manifest=root/'trace-archives.json'
    data=json.loads(manifest.read_text()) if manifest.exists() else {'version':2,'archives':[]}
    existing={row['raw']:row for row in data['archives']}
    # Verify all already archived raw bytes before adding anything.
    restore(manifest) if manifest.exists() else None
    obsolete=[]
    # XZ's larger dictionary captures repeated full request histories. Ordinary
    # gzip's 32 KiB dictionary can still leave a single trace above Git limits.
    for row in data['archives']:
        if row.get('compression')=='lzma-xz':continue
        raw=resolve(root,row['raw']);old=resolve(root,row['archive']);archive=raw.with_name(raw.name+'.xz')
        if archive.exists():raise ValueError('Preserve existing unregistered XZ archive')
        with raw.open('rb') as source,lzma.open(archive,'xb',preset=6) as target:shutil.copyfileobj(source,target)
        if sha(raw)!=row['raw_sha256']:raise ValueError('Raw evidence changed while transcoding')
        row.update(archive=str(archive.relative_to(root)),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,compression='lzma-xz')
        obsolete.append(old)
    for raw in sorted(root.rglob('*.jsonl')):
        if raw.stat().st_size<minimum or not (raw.parent/'result.json').is_file():continue
        relative=str(raw.relative_to(root))
        if relative in existing:continue
        archive=raw.with_name(raw.name+'.xz')
        if archive.exists():raise ValueError('Preserve existing unregistered archive: '+str(archive))
        before=sha(raw);size=raw.stat().st_size
        with raw.open('rb') as source,lzma.open(archive,'xb',preset=6) as target:shutil.copyfileobj(source,target)
        if sha(raw)!=before:raise ValueError('Trace changed while packing; not a completed stable stage')
        row={'raw':relative,'raw_sha256':before,'raw_bytes':size,
             'archive':str(archive.relative_to(root)),'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'compression':'lzma-xz'}
        existing[relative]=row;data['archives'].append(row)
    data['archives'].sort(key=lambda row:row['raw'])
    data['version']=2
    data['scope']='Lossless archival of completed large untracked traces; raw originals remain locally. Restore before validating raw-trace evidence after cloning. This neither publishes artifacts nor performs a public-release privacy audit.'
    temporary=manifest.with_name(manifest.name+'.pending');temporary.write_text(json.dumps(data,indent=2)+'\n');temporary.replace(manifest)
    # Only this tool's now-obsolete, verified derivative compression is removed;
    # original model traces remain untouched and the new exact archive is bound.
    for old in obsolete:old.unlink()
    return {'archives':len(data['archives']),'raw_bytes':sum(x['raw_bytes'] for x in data['archives']),
            'archive_bytes':sum(x['archive_bytes'] for x in data['archives']),'manifest':str(manifest)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['pack','restore']);p.add_argument('path');p.add_argument('--minimum-mib',type=float,default=10)
    args=p.parse_args();result=pack(args.path,int(args.minimum_mib*1024**2)) if args.command=='pack' else restore(args.path)
    print(json.dumps(result,indent=2))
