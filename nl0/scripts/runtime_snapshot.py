"""Owned executable snapshots; installation updates never rewrite active jobs."""
from pathlib import Path
from staging_storage import copy_input
import json
import shutil

from controller_common import CORE,bind,write,verify_bindings

VERSION='yui-runtime-snapshot-3'


def capture(run,rows,*,core=CORE):
    run,core=Path(run).resolve(),Path(core).resolve()
    destination=run/'runtime';destination.mkdir(exist_ok=False)
    files=[];seen=set()
    for row in rows:
        original=Path(row['path']).resolve()
        if bind(original)!=row:raise ValueError('Runtime changed while preparing snapshot')
        if original.is_relative_to(core):relative=original.relative_to(core)
        else:raise ValueError('Executable input is outside the declared skill')
        if relative in seen:raise ValueError('Runtime snapshot path collision')
        seen.add(relative);target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        copy_input(original,target)
        if bind(target)['sha256']!=row['sha256']:raise ValueError('Runtime snapshot copy changed')
        files.append({'relative_path':str(relative),'sha256':row['sha256'],'original':row})
    path=run/'runtime-manifest.json'
    write(path,{'version':VERSION,'original_core':str(core),'runtime_root':str(destination),
                'files':files,'scope':'Declared executable data only; no credentials, memories or task outputs.'})
    descriptor={'root':str(destination),'manifest':bind(path)}
    runtime=[bind(destination/row['relative_path']) for row in files]
    return descriptor,runtime


def validate(job):
    descriptor=job['runtime_snapshot'];run=Path(job['root']).resolve()
    fields={'root','manifest'}
    if (set(descriptor)!=fields
            or Path(descriptor['root'])!=run/'runtime'
            or Path(descriptor['manifest']['path'])!=run/'runtime-manifest.json'
            or (run/'runtime').is_symlink() or (run/'runtime-manifest.json').is_symlink()):
        raise ValueError('Runtime snapshot escapes its owned run')
    verify_bindings([descriptor['manifest']])
    manifest=json.loads((run/'runtime-manifest.json').read_text())
    if (manifest.get('version')!=VERSION
            or manifest.get('runtime_root')!=descriptor['root']):
        raise ValueError('Invalid executable snapshot manifest')
    expected=[];seen=set()
    for row in manifest['files']:
        relative=Path(row['relative_path']);path=run/'runtime'/relative
        if (relative.is_absolute() or '..' in relative.parts or relative in seen
                or not path.resolve().is_relative_to(run/'runtime') or path.is_symlink()):
            raise ValueError('Unsafe executable snapshot file')
        seen.add(relative);expected.append({'path':str(path),'sha256':row['sha256']})
    if expected!=job['runtime']:raise ValueError('Executable snapshot binding changed')
    actual={p.relative_to(run/'runtime') for p in (run/'runtime').rglob('*')
            if p.is_file() and '__pycache__' not in p.parts}
    if actual!=seen:raise ValueError('Executable snapshot has undeclared or missing files')
    verify_bindings(expected)
    return descriptor


def root_for(job):
    return Path(validate(job)['root'])


def environment(job):
    import os
    env=dict(os.environ)
    env['YUI_FROZEN_LOCAL_CONFIG']=json.dumps(job.get('local_configuration'),sort_keys=True)
    env.pop('YUI_LIBRARY_ROOT',None)
    if job.get('root') is not None:
        env['YUI_LEAN_IMPORT_ROOT']=str(Path(job['root'])/'imported-lean')
    else:
        env.pop('YUI_LEAN_IMPORT_ROOT',None)
    env['YUI_LEAN_LIBRARIES']=json.dumps(job.get('lean_libraries',[]),sort_keys=True)
    if 'lean_environment' in job:
        env['YUI_LEAN_ENVIRONMENT']=json.dumps(job['lean_environment'],sort_keys=True)
    if 'runtime_snapshot' in job:
        validate(job)
    return env
