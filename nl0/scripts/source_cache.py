"""Reuse a requested public URL within one case; each role receives independent evidence files."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from controller_common import bind, verify_bindings, write
from staging_storage import copy_input

LIMIT=256*1024**2


@contextmanager
def lock(path):
    with path.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        yield


def collect(root):
    """Called under the index lock. Readers clone their bytes under this same lock."""
    entries=sorted((p for p in root.glob('entry-*') if p.is_dir() and not p.is_symlink()),
                   key=lambda p:p.stat().st_mtime_ns,reverse=True)
    used=0
    for directory in entries:
        used+=sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
        if used>LIMIT:
            shutil.rmtree(directory)


def fetch(directory,url,browser,root,download):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(json.dumps([url,browser]).encode()).hexdigest()
    # Fixed lock stripes bound metadata even after a long search campaign.
    with lock(root/(key[:2]+'.lock')):
        entry=root/('entry-'+key)
        with lock(root/'index.lock'):
            if entry.is_symlink():raise RuntimeError('Unsafe cached source directory')
            if entry.is_dir():
                record=json.loads((entry/'record.json').read_text())
                if record['url']!=url or record['status']!='READABLE':raise ValueError('Wrong cached public source')
                for field in ('document','text','screenshot'):
                    if field in record:
                        ref=record[field];src=Path(ref['path'])
                        if src.parent!=entry or src.is_symlink():raise ValueError('Invalid cached source path')
                        verify_bindings([ref])
                        dst=directory/('access-'+key+'-'+src.name)
                        copy_input(src,dst);record[field]=bind(dst)
                file=directory/('access-'+key+'.json')
                write(file,record);entry.touch()
                return {**record,'record':bind(file)}
        result=download(directory,url,browser=browser)
        if result['status']!='READABLE':return result
        record={k:v for k,v in result.items() if k!='record'}
        with tempfile.TemporaryDirectory(dir=root,prefix='building-') as scratch:
            incoming=Path(scratch)/'bytes';incoming.mkdir()
            for field in ('document','text','screenshot'):
                if field in record:
                    ref=record[field];src=Path(ref['path']);dst=incoming/(field+src.suffix)
                    verify_bindings([ref]);copy_input(src,dst)
                    record[field]={'path':str(entry/dst.name),'sha256':bind(dst)['sha256']}
            write(incoming/'record.json',record)
            with lock(root/'index.lock'):
                incoming.rename(entry)
                collect(root)
        return result
