"""Explicit, owned source/olean snapshots for non-Mathlib Lean dependencies.

Attachment establishes file identity and availability, not source fidelity or
mathematical acceptance. Existing native signature and trust gates still apply.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import hashlib
import json
import os
from pathlib import Path
import re

from controller_common import bind, write
from runtime_config import load_lock
from staging_storage import copy_input

VERSION = 'yui-lean-library-1'
SNAPSHOT = 'yui-lean-library-snapshot-1'
_spec=spec_from_file_location('yui_lean_library_rules',Path(__file__).resolve().parents[2]/'workflow/blocks/lean_library_manifests.py')
rules=module_from_spec(_spec);_spec.loader.exec_module(rules)
MODULE=rules.MODULE
_UNSET=object()
_selected=ContextVar('yui_lean_libraries',default=None)
_verified_files={}
_module=rules.module


def _metadata(value):
    lock=load_lock()
    if lock['lean'] is None:raise ValueError('An attached Lean library requires an explicitly selected Lean environment')
    rules.validate(value,{'lean_version':lock['lean']['version_number'],'mathlib_commit':lock['mathlib']['rev']})
    name=value['name'];ml=Path(lock['mathlib']['local_path'])
    pinned_roots=[ml/'.lake/build/lib/lean',Path(lock['lean']['local_path'])/'lib/lean']
    pinned_roots += [ml/'.lake/packages'/p['name']/'.lake/build/lib/lean' for p in lock['dependencies']]
    if any((p/name).exists() or (p/(name+'.olean')).exists() for p in pinned_roots):
        raise ValueError('Lean library would shadow a pinned library namespace')
    return value


def _input(root,relative):
    source=root/relative
    if any(p.is_symlink() for p in (source,*source.parents) if p!=root and p.is_relative_to(root)):
        raise ValueError('Lean library input contains a symlink')
    if not source.resolve(strict=True).is_relative_to(root) or not source.is_file():
        raise ValueError('Lean library input escapes its declared root')
    return source


def _artifacts(row):
    return [('.olean',row['olean_sha256']),*row.get('companions',{}).items()]


def capture(specification, run):
    """Copy only explicitly enumerated public modules; never scan sibling files."""
    specification = Path(specification).resolve(strict=True)
    value = json.loads(specification.read_text())
    if set(value) != {'version', 'name', 'lean_version', 'mathlib_commit',
                      'source_root', 'build_root', 'imports', 'modules'} or value['version'] != VERSION:
        raise ValueError('Invalid explicit Lean library specification')
    metadata = _metadata({k: v for k, v in value.items() if k not in {'source_root', 'build_root', 'version'}}
                         | {'version': SNAPSHOT})
    roots = {k: Path(value[k]).resolve(strict=True) for k in ('source_root', 'build_root')}
    destination = Path(run).resolve() / 'lean-libraries' / value['name']
    if destination.exists() or destination.is_symlink():
        raise ValueError('Lean library snapshot already exists')
    destination.mkdir(parents=True)
    for row in value['modules']:
        relative = _module(row['module'], value['name'])
        for root,folder,suffix,expected in [('source_root','source','.lean',row['source_sha256']),
                *[('build_root','lib',suffix,sha) for suffix,sha in _artifacts(row)]]:
            source=_input(roots[root],Path(str(relative)+suffix))
            if bind(source)['sha256']!=expected:raise ValueError('Lean library input changed: '+str(source))
            target=destination/folder/(str(relative)+suffix)
            target.parent.mkdir(parents=True,exist_ok=True);copy_input(source,target)
            if bind(target)['sha256']!=expected:raise ValueError('Lean library copy changed')
    write(destination / 'manifest.json', metadata)
    descriptor = {'name': value['name'], 'root': str(destination),
                  'manifest': bind(destination / 'manifest.json')}
    validate([descriptor], full=True)
    return descriptor


def _verify_file(path, expected, full):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or nonportable Lean library file: ' + str(path))
    stat = path.stat()
    identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    key = str(path)
    prior = _verified_files.get(key)
    if full or prior != (identity, expected):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen Lean library file changed: ' + str(path))
        _verified_files[key] = (identity, expected)


def validate(descriptors, *, full=False):
    if not isinstance(descriptors, list):
        raise ValueError('Lean library attachments must be a list')
    names = set()
    result = []
    for row in descriptors:
        if set(row) != {'name', 'root', 'manifest'} or row['name'] in names:
            raise ValueError('Invalid or duplicate Lean library attachment')
        names.add(row['name'])
        root = Path(row['root'])
        if (not root.is_absolute() or root.is_symlink() or root != root.resolve()
                or root.name != row['name'] or root.parent.name != 'lean-libraries'
                or row['manifest'].get('path') != str(root / 'manifest.json')):
            raise ValueError('Lean library snapshot escapes its owned directory')
        _verify_file(root / 'manifest.json', row['manifest']['sha256'], full)
        data = _metadata(json.loads((root / 'manifest.json').read_text()))
        if data['name'] != row['name']:
            raise ValueError('Lean library attachment namespace changed')
        expected = {'manifest.json'}
        for item in data['modules']:
            relative = _module(item['module'], data['name'])
            for folder,suffix,expected_sha in [('source','.lean',item['source_sha256']),
                    *[('lib',suffix,sha) for suffix,sha in _artifacts(item)]]:
                path=Path(folder)/(str(relative)+suffix)
                expected.add(str(path))
                _input(root,path)
                _verify_file(root/path,expected_sha,full)
        for path in root.rglob('*'):
            if path.is_symlink():raise ValueError('Nonportable Lean library snapshot member')
        actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
        if actual != expected:
            raise ValueError('Undeclared or missing Lean library snapshot files')
        result.append((row, data))
    return result


@contextmanager
def use(descriptors):
    validate(descriptors, full=True)
    token = _selected.set(deepcopy(descriptors))
    try:
        yield
    finally:
        _selected.reset(token)


def _static():
    chosen=_selected.get()
    return deepcopy(chosen) if chosen is not None else json.loads(os.environ.get('YUI_LEAN_LIBRARIES','[]'))


def current():
    chosen=_static();root=generated_root()
    return [*chosen,*read_generated(root,base=chosen)] if root is not None else chosen


def binding():
    return [row for row, _ in validate(current())]


def paths():
    return [str(Path(row['root']) / 'lib') for row, _ in validate(current())]


def permitted_imports():
    return {name for _, data in validate(current()) for name in data['imports']}


def summary():
    return [{'name': row['name'], 'imports': data['imports'],
             'source_modules': len(data['modules']), 'manifest_sha256': row['manifest']['sha256'],
             'scope': 'Explicit source/olean availability only; no semantic acceptance.'}
            for row, data in validate(current())]


def strip_attached_imports(header):
    """Retain the old header check after validating each explicit extra import."""
    if not isinstance(header, str) or not header.startswith('import Mathlib\n'):
        return header
    lines = header.splitlines(keepends=True)
    offset = 1
    allowed = permitted_imports()
    seen = set()
    while offset < len(lines) and lines[offset].startswith('import '):
        module = lines[offset][7:].strip()
        if module not in allowed or module in seen:
            raise ValueError('Basis import is not an explicitly attached Lean library module')
        seen.add(module)
        offset += 1
    return lines[0] + ''.join(lines[offset:])


def read_source(module, start=1, end=160, *, retained_at=None):
    if type(start) is not int or type(end) is not int or start < 1 or end < start or end-start >= 250:
        raise ValueError('Read at most 250 source lines using positive line numbers')
    for row, data in validate(current()):
        item = next((v for v in data['modules'] if v['module'] == module), None)
        if item:
            path = Path(row['root']) / 'source' / _module(module, row['name']).with_suffix('.lean')
            lines = path.read_text().splitlines()
            result = {'module': module, 'source_sha256': item['source_sha256'],
                    'start': start, 'end': min(end, len(lines)), 'total_lines': len(lines),
                    'lines': '\n'.join(f'{i}: {line}' for i, line in enumerate(lines, 1) if start <= i <= end)}
            if retained_at is not None:
                relative=Path('external-sources')/(item['source_sha256']+'.lean')
                destination=Path(retained_at)/relative
                destination.parent.mkdir(parents=True,exist_ok=True)
                if not destination.exists():copy_input(path,destination)
                if bind(destination)['sha256']!=item['source_sha256']:
                    raise ValueError('Retained attached-library source changed')
                result['evidence']={'path':str(relative),'sha256':item['source_sha256']}
            return result
    raise ValueError('Unknown bound Lean library module')


def search_source(query):
    if not isinstance(query, str) or not query or len(query) > 300:
        raise ValueError('Supply a nonempty literal source search of at most 300 characters')
    hits = []
    for row, data in validate(current()):
        for item in data['modules']:
            path = Path(row['root']) / 'source' / _module(item['module'], row['name']).with_suffix('.lean')
            for line, text in enumerate(path.read_text().splitlines(), 1):
                if query in text:
                    hits.append({'module': item['module'], 'line': line, 'text': text[:1200]})
                    if len(hits) == 100:
                        return {'matches': hits, 'truncated': True}
    return {'matches': hits, 'truncated': False}


def tools(*,force=False):
    if not force and not current():return []
    import native_carrier as carrier
    return [carrier.tool('read_lean_library',
        'Read a bound public non-Mathlib Lean source. Returns its complete retained source evidence and a bounded line view; availability is not semantic approval.',
        {'module':{'type':'string'},'start':{'type':'integer'},'end':{'type':'integer'}},['module','start','end']),
        carrier.tool('search_lean_library','Search explicitly bound public non-Mathlib Lean sources by literal text; at most 100 matches.',
        {'query':{'type':'string'}},['query'])]


def dispatch(name,args,logs):
    if name=='read_lean_library':return read_source(**args,retained_at=logs)
    if name=='search_lean_library':return search_source(**args)
    raise ValueError('Unknown attached Lean library tool')


def export_sources(directory):
    """Deliver sources for fresh builds, never compiler caches or personal files."""
    rows=validate(current(),full=True)
    if not rows:return []
    directory=Path(directory)/'lean-libraries';directory.mkdir()
    index=[]
    for row,data in rows:
        root=Path(row['root']);target=directory/row['name'];target.mkdir()
        copy_input(root/'manifest.json',target/'manifest.json')
        for item in data['modules']:
            relative=_module(item['module'],row['name']).with_suffix('.lean')
            source=target/'source'/relative;source.parent.mkdir(parents=True,exist_ok=True)
            copy_input(root/'source'/relative,source)
        if not any(item['module']==row['name'] for item in data['modules']):
            (target/'source'/(row['name']+'.lean')).write_text(
                ''.join('import '+module+'\n' for module in data['imports']))
        index.append({'name':row['name'],'manifest_sha256':row['manifest']['sha256']})
    write(directory/'index.json',{'version':'yui-delivery-lean-libraries-1','libraries':index})
    return index


def verify_export(directory, expected):
    directory=Path(directory)/'lean-libraries'
    if not expected:
        if directory.exists():raise ValueError('Unexpected delivered Lean libraries')
        return []
    value=json.loads((directory/'index.json').read_text())
    if value!={'version':'yui-delivery-lean-libraries-1','libraries':expected}:
        raise ValueError('Delivered Lean library inventory differs from native evidence')
    wanted={'index.json'};names=[]
    for row in expected:
        name=row['name']
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',name) or name in names:
            raise ValueError('Invalid delivered Lean library namespace')
        names.append(name);manifest=directory/name/'manifest.json'
        if bind(manifest)['sha256']!=row['manifest_sha256']:
            raise ValueError('Delivered Lean library manifest changed')
        data=json.loads(manifest.read_text())
        if data['version']!=SNAPSHOT or data['name']!=name:
            raise ValueError('Delivered Lean library source identity changed')
        wanted.add(str(Path(name)/'manifest.json'))
        for item in data['modules']:
            relative=Path(name)/'source'/_module(item['module'],name).with_suffix('.lean')
            wanted.add(str(relative))
            if bind(directory/relative)['sha256']!=item['source_sha256']:
                raise ValueError('Delivered Lean library source changed')
        if not any(item['module']==name for item in data['modules']):
            relative=Path(name)/'source'/(name+'.lean');wanted.add(str(relative))
            if (directory/relative).read_text()!=''.join('import '+module+'\n' for module in data['imports']):
                raise ValueError('Delivered Lean library root imports changed')
    if any(p.is_symlink() for p in directory.rglob('*')):
        raise ValueError('Nonportable delivered Lean library member')
    if {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file()}!=wanted:
        raise ValueError('Undeclared or missing delivered Lean library sources')
    return names


def identity():
    return [{'name':row['name'],'manifest_sha256':row['manifest']['sha256']} for row,_ in validate(current())]


def inherit(descriptors,run):
    """Clone frozen bytes instead of consulting a changed upstream checkout."""
    result=[]
    for row,data in validate(descriptors,full=True):
        specification=Path(run)/('inherit-'+row['name']+'.json')
        write(specification,{**data,'version':VERSION,'source_root':str(Path(row['root'])/'source'),
                             'build_root':str(Path(row['root'])/'lib')})
        try:result.append(capture(specification,run))
        finally:specification.unlink(missing_ok=True)
    return result


_generated=ContextVar('yui_generated_lean_library_root',default=_UNSET)


@contextmanager
def generated(root):
    token=_generated.set(str(Path(root).resolve()) if root is not None else None)
    try:yield
    finally:_generated.reset(token)


def generated_root():
    value=_generated.get()
    return os.environ.get('YUI_LEAN_IMPORT_ROOT') if value is _UNSET else value


def read_generated(root,*,base=None,full=False):
    root=Path(root).resolve();index=root/'index.json'
    if not index.exists():return []
    if root.name!='imported-lean' or index.is_symlink() or root.is_symlink():raise ValueError('Invalid generated Lean library registry')
    value=json.loads(index.read_text());job=json.loads((root.parent/'job.json').read_text())
    if (value.get('version')!='yui-imported-lean-registry-1' or set(value)!={'version','job','entries'}
            or value['job']!=bind(root.parent/'job.json') or job['root']!=str(root.parent)):
        raise ValueError('Generated Lean library registry belongs to another job')
    rows=[entry['library'] for entry in value['entries']]
    selected=validate(rows,full=full)
    base=_static() if base is None else base
    available={json.dumps({'name':row['name'],'manifest_sha256':row['manifest']['sha256']},sort_keys=True)
               for row in [*base,*rows]}
    import lean_environment
    from runtime_config import require_environment
    from pilot_common import native_succeeded
    expected=lean_environment.identity(require_environment())
    for entry,(row,metadata) in zip(value['entries'],selected):
        if set(entry)!={'library','check'} or Path(row['root']).parent!=root/'lean-libraries':
            raise ValueError('Generated Lean library escapes this case registry')
        path=Path(entry['check']['path'])
        if not path.resolve().is_relative_to(root.parent):raise ValueError('Generated Lean check belongs to another case')
        _verify_file(path,entry['check']['sha256'],full)
        check=json.loads(path.read_text())
        for binding in check['bindings']:_verify_file(Path(binding['path']),binding['sha256'],full)
        if (check.get('version')!='yui-imported-lean-1' or check.get('source_policy_passed') is not True
                or not native_succeeded(check.get('native',{})) or check['environment']!=expected
                or check['module']!=row['name'] or len(metadata['modules'])!=1
                or metadata['modules'][0]['module']!=row['name'] or metadata['imports']!=[row['name']]
                or metadata['modules'][0]['source_sha256']!=check['source']['sha256']
                or any(json.dumps(item,sort_keys=True) not in available for item in check['libraries'])):
            raise ValueError('Generated Lean library lost its completed current check')
        artifacts={Path(item['path']).name:item['sha256'] for item in check['artifacts']}
        if any(artifacts.get(row['name']+suffix)!=sha for suffix,sha in _artifacts(metadata['modules'][0])):
            raise ValueError('Generated Lean compiler artifacts differ from the bound library')
    return rows
