"""Discover, check and freeze host Lean/Mathlib pairs; installation is explicit."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


CORE = Path(__file__).resolve().parents[2]
_spec = spec_from_file_location('yui_lean_environment_rules', CORE/'workflow/blocks/lean_environments.py')
rules = module_from_spec(_spec)
_spec.loader.exec_module(rules)
SelectionRequired = rules.SelectionRequired
PROBE = 'import Mathlib\nexample (n : Nat) : n + 0 = n := by simp\n'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True,
                                   stderr=subprocess.PIPE, timeout=30).strip()


def _clean(root, revision):
    if _git(root, 'rev-parse', 'HEAD') != revision or _git(root, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Selected library/dependency changed tracked sources: ' + str(root))


def _root(path):
    path = Path(path).expanduser().resolve(strict=True)
    return path.parent.parent if path.name == 'lean' and path.parent.name == 'bin' else path


def _stamp(lean, library):
    paths = (lean/'bin/lean', library/'lean-toolchain', library/'lake-manifest.json')
    return (tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths),
            _git(library, 'rev-parse', 'HEAD'))


@lru_cache(maxsize=32)
def _describe(lean_name, library_name, stamp):
    lean, library = Path(lean_name), Path(library_name)
    version = subprocess.check_output([str(lean/'bin/lean'), '--version'], text=True, timeout=30).strip()
    found = re.search(r'^Lean \(version ([^,]+),', version)
    toolchain = (library/'lean-toolchain').read_text().strip()
    if not found or toolchain != 'leanprover/lean4:v' + found[1]:
        raise ValueError('Lean executable does not match Mathlib lean-toolchain: ' + toolchain)
    manifest = json.loads((library/'lake-manifest.json').read_text())
    revision = _git(library, 'rev-parse', 'HEAD')
    _clean(library, revision)
    tags = _git(library, 'tag', '--points-at', 'HEAD').splitlines()
    ref = 'v' + found[1] if 'v' + found[1] in tags else revision
    dependencies = []
    for row in manifest['packages']:
        if row.get('type') != 'git':
            raise ValueError('Select a Mathlib checkout with pinned Git dependencies: ' + row['name'])
        dependency = library/'.lake/packages'/row['name']
        _clean(dependency, row['rev'])
        # Tool-only dependencies need not have proof-module caches. The actual
        # import/proof below determines which compiled dependencies are needed.
        dependencies.append({key: row[key] for key in ('name', 'url', 'rev')})
    if not (library/'.lake/build/lib/lean/Mathlib.olean').is_file():
        raise ValueError('Missing Mathlib.olean; download the cache for the declared checkout first')
    value = {'version': rules.VERSION,
             'lean': {'toolchain': toolchain, 'version': version, 'version_number': found[1],
                      'local_path': str(lean), 'binary_sha256': digest(lean/'bin/lean')},
             'mathlib': {'url': 'https://github.com/leanprover-community/mathlib4.git',
                         'rev': revision, 'ref': ref, 'local_path': str(library),
                         'manifest_sha256': digest(library/'lake-manifest.json'),
                         'toolchain_sha256': digest(library/'lean-toolchain')},
             'dependencies': dependencies, 'compatibility': None}
    rules.validate(value, checked=False)
    return value


def describe(lean_root, mathlib_root):
    lean, library = _root(lean_root), Path(mathlib_root).expanduser().resolve(strict=True)
    return deepcopy(_describe(str(lean), str(library), _stamp(lean, library)))


def identity(value):
    return {'lean_version':value['lean']['version_number'],'lean_binary_sha256':value['lean']['binary_sha256'],
            'mathlib_commit':value['mathlib']['rev'],'dependency_manifest_sha256':value['mathlib']['manifest_sha256']}


def verify(value):
    """Recheck frozen files and source revisions without changing a run's selection."""
    rules.validate(value)
    lean, library = Path(value['lean']['local_path']), Path(value['mathlib']['local_path'])
    if (digest(lean/'bin/lean') != value['lean']['binary_sha256']
            or digest(library/'lake-manifest.json') != value['mathlib']['manifest_sha256']
            or digest(library/'lean-toolchain') != value['mathlib']['toolchain_sha256']
            or (library/'lean-toolchain').read_text().strip() != value['lean']['toolchain']):
        raise ValueError('Frozen Lean binary or Mathlib manifest/toolchain changed')
    _clean(library, value['mathlib']['rev'])
    manifest = json.loads((library/'lake-manifest.json').read_text())
    expected = [{key: row[key] for key in ('name', 'url', 'rev')} for row in manifest['packages']]
    if expected != value['dependencies']:
        raise ValueError('Frozen dependency inventory differs from Mathlib manifest')
    for row in expected:
        _clean(library/'.lake/packages'/row['name'], row['rev'])
    return deepcopy(value)


@lru_cache(maxsize=32)
def _checked(serialized):
    value = json.loads(serialized)
    # The candidate context is local to this probe, including nested load_lock calls.
    import runtime_config
    from pilot_common import run_lean, native_succeeded
    work = Path(tempfile.mkdtemp(prefix='yui-environment-probe-')).resolve()
    try:
        from run_resources import register_workspace
        register_workspace(work, work/'evidence')
        (work/'input').mkdir()
        (work/'output').mkdir()
        source = work/'output/Environment.lean'
        source.write_text(PROBE)
        import lean_libraries
        with runtime_config.use_environment(value, checked=False),lean_libraries.use([]),lean_libraries.generated(None):
            result = run_lean(source, work, timeout=360)
    except BaseException as error:
        (work/'environment-probe-retained.json').write_text(json.dumps({
            'reason': type(error).__name__ + ': ' + str(error), 'cleanup_confirmed': False,
            'environment': value}, indent=2) + '\n')
        raise
    else:
        shutil.rmtree(work)
    value['compatibility'] = {**result, 'accepted': native_succeeded(result),
                              'source_sha256': hashlib.sha256(PROBE.encode()).hexdigest()}
    if not value['compatibility']['accepted']:
        raise SelectionRequired([value], 'The selected pair failed its actual import-Mathlib compatibility check: '
                                + (result.get('stdout', '') + '\n' + result.get('stderr', ''))[-3000:])
    rules.validate(value)
    return value


def checked(value):
    return deepcopy(_checked(json.dumps(value, sort_keys=True)))


def discover(*, lean_roots=None, mathlib_roots=None):
    """Scan only declared tool locations, not personal projects or task history."""
    shared = Path.home()/'formalization-tools'
    libraries = list(mathlib_roots) if mathlib_roots is not None else list(shared.glob('lean-mathlib*/mathlib'))
    libraries += [Path(p).expanduser() for p in os.environ.get('YUI_MATHLIB_SEARCH_PATH', '').split(os.pathsep) if p]
    leans = list(lean_roots) if lean_roots is not None else [p.parent.parent for p in
             (Path.home()/'.elan/toolchains').glob('*/bin/lean')]
    if lean_roots is None:
        leans += [p for p in shared.glob('lean-mathlib*/lean') if p.exists()]
    result, failures, seen = [], [], set()
    for library in libraries:
        for lean in leans:
            try:
                key = (str(_root(lean)), str(Path(library).expanduser().resolve(strict=True)))
                if key in seen:
                    continue
                seen.add(key)
                value = describe(*key)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                failures.append({'lean_root': str(lean), 'mathlib_root': str(library), 'error': str(error)})
                continue
            try:
                result.append(checked(value))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                failures.append({'lean_root': str(lean), 'mathlib_root': str(library), 'error': str(error)})
    return result, failures


def resolve(*, lean_root=None, mathlib_root=None, lean_version=None, mathlib_ref=None):
    lean_root = lean_root or os.environ.get('YUI_LEAN_ROOT')
    mathlib_root = mathlib_root or os.environ.get('YUI_MATHLIB_ROOT')
    lean_version = lean_version or os.environ.get('YUI_LEAN_VERSION')
    mathlib_ref = mathlib_ref or os.environ.get('YUI_MATHLIB_VERSION')
    if lean_root and mathlib_root:
        try:
            choices = [checked(describe(lean_root, mathlib_root))]
        except SelectionRequired:
            raise
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            raise SelectionRequired(reason='The supplied pair is unavailable or incompatible: ' + str(error)) from error
        failures = []
    else:
        choices, failures = discover(lean_roots=[lean_root] if lean_root else None,
                                     mathlib_roots=[mathlib_root] if mathlib_root else None)
    try:
        return rules.select(choices, lean_version=lean_version, mathlib_ref=mathlib_ref)
    except SelectionRequired as error:
        error.request['discovery_errors'] = failures
        raise


def legacy(lock=None):
    """Old jobs have their own portable version pin; discovery cannot replace it."""
    lock = lock or json.loads((CORE/'toolchain/lock.json').read_text())
    version = lock['lean']['toolchain'].split(':v', 1)[1]
    shared = Path.home()/('formalization-tools/lean-mathlib-v' + version)
    value = resolve(lean_root=shared/'lean', mathlib_root=shared/'mathlib', lean_version=version,
                    mathlib_ref=lock['mathlib']['rev'])
    return value


def install(*, lean_version, mathlib_ref, directory=None):
    """Download only explicitly named versions into a new shared installation."""
    version = lean_version.removeprefix('v')
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-rc\d+)?', version):
        raise ValueError('Select an exact Lean release version')
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-rc\d+)?|[0-9a-f]{40}', mathlib_ref):
        raise ValueError('Select an exact Mathlib release tag or full commit')
    root = Path(directory).expanduser().absolute() if directory else Path.home()/('formalization-tools/lean-mathlib-v' + version)
    if root.exists() or root.is_symlink():
        raise ValueError('Preserve the existing installation; select a new directory: ' + str(root))
    root.mkdir(parents=True, exist_ok=False)
    elan = shutil.which('elan') or str(Path.home()/'.elan/bin/elan')
    toolchain = 'leanprover/lean4:v' + version
    subprocess.run([elan, 'toolchain', 'install', toolchain], check=True)
    lean = Path.home()/('.elan/toolchains/leanprover--lean4---v' + version)
    (root/'lean').symlink_to(lean, target_is_directory=True)
    command = ['git', 'clone', '--depth', '1']
    if mathlib_ref.startswith('v'):
        command += ['--branch', mathlib_ref]
    subprocess.run([*command, 'https://github.com/leanprover-community/mathlib4.git', str(root/'mathlib')], check=True)
    if not mathlib_ref.startswith('v'):
        subprocess.run(['git', '-C', str(root/'mathlib'), 'fetch', '--depth', '1', 'origin', mathlib_ref], check=True)
        subprocess.run(['git', '-C', str(root/'mathlib'), 'checkout', '--detach', mathlib_ref], check=True)
    if (root/'mathlib/lean-toolchain').read_text().strip() != toolchain:
        raise ValueError('Requested Mathlib and Lean versions do not match; installation retained for inspection')
    env = dict(os.environ, PATH=str(lean/'bin') + os.pathsep + os.environ.get('PATH', ''))
    subprocess.run([str(lean/'bin/lake'), 'exe', 'cache', 'get'], cwd=root/'mathlib', env=env, check=True)
    packages = root/'packages'
    packages.mkdir()
    (packages/'mathlib').symlink_to(root/'mathlib', target_is_directory=True)
    manifest = json.loads((root/'mathlib/lake-manifest.json').read_text())
    for row in manifest['packages']:
        (packages/row['name']).symlink_to(root/'mathlib/.lake/packages'/row['name'], target_is_directory=True)
    selected = resolve(lean_root=root/'lean', mathlib_root=root/'mathlib', lean_version=version, mathlib_ref=mathlib_ref)
    (root/'environment.json').write_text(json.dumps(selected, indent=2) + '\n')
    (root/'README.md').write_text('# Shared Lean/Mathlib ' + version + '\n\n'
        'Exact environment and native compatibility receipt: `environment.json`.\n'
        'Older installations were retained. Link a compatible project `.lake/packages` to `packages/`; '
        'do not change existing pinned projects or run lake update to use this cache.\n')
    return selected
