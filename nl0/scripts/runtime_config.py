"""Resolve host tools separately from portable scientific pins; never load personal instructions."""
from __future__ import annotations

import hashlib
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from contextlib import contextmanager
from contextvars import ContextVar

CORE = Path(__file__).resolve().parents[2]
_profiles = ContextVar('yui_phase_profiles', default=None)


def validate_profile(profile):
    """Validate explicit carrier choices without substituting model or effort."""
    if (not isinstance(profile, dict) or set(profile) != {'id', 'reasoning_effort', 'speed', 'automatic_fallback'}
            or not isinstance(profile['id'], str) or not profile['id'].strip()
            or any(c in profile['id'] for c in '\n\r"\\')
            or profile['reasoning_effort'] not in {'none','minimal','low','medium','high','xhigh','max','ultra'}
            or profile['speed'] != 'standard' or profile['automatic_fallback'] is not False):
        raise ValueError('Select an explicit model and reasoning effort; this isolated carrier currently supports Standard speed only, without fallback')
    return dict(profile)


@contextmanager
def use_profiles(profiles):
    if set(profiles) != {'nl0','lean'}:
        raise ValueError('Two explicit phase profiles are required: nl0 and lean')
    value = {key: validate_profile(row) for key,row in profiles.items()}
    token = _profiles.set(value)
    try:
        yield
    finally:
        _profiles.reset(token)


def time_limit(value):
    """None means unlimited; finite limits require explicit positive seconds."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('A time limit must be null (unlimited) or positive finite seconds')
    return value


def configured_timeout(scope):
    return time_limit(json.loads((CORE / 'config.json').read_text())['timeouts'][scope + '_seconds'])


def native_timeout(requested=None):
    """Bound one native call without introducing a case or model deadline."""
    limits = [value for value in (time_limit(requested), configured_timeout('native'))
              if value is not None]
    return min(limits) if limits else None


def native_heartbeats():
    """Controller-owned budget for one elaboration; never a model-turn cap."""
    value = json.loads((CORE / 'config.json').read_text())['lean']['max_heartbeats']
    if type(value) is not int or value <= 0:
        raise ValueError('lean.max_heartbeats must be a positive integer')
    return value


def model_profile(phase=None):
    """Resolve a declared phase without changing another live stage's model."""
    raw = (CORE / 'config.json').read_bytes()
    config = json.loads(raw)
    name = str(phase or '').lower().replace('_', '-')
    translation = name in {'proof', 'plan', 'interface', 'assembly'} or name.startswith(
        ('interface-', 'audit-b', 'translation-', 'nl0-to-lean', 'frozen-lean-'))
    key = 'nl0_to_lean' if translation else 'model'
    selected = _profiles.get()
    profile = validate_profile(selected['lean' if translation else 'nl0'] if selected else
                               config['phase_models'][key] if translation else config['model'])
    return {**profile, 'profile_key': key, 'config_sha256': hashlib.sha256(raw).hexdigest(),
            'selection_origin': 'explicit_run' if selected else 'installation_defaults'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def choose(variable, candidates):
    explicit = os.environ.get(variable)
    options = [Path(explicit).expanduser()] if explicit else [Path(x).expanduser() for x in candidates if x]
    for path in options:
        if path.exists():
            return path.resolve()
    raise FileNotFoundError(f'{variable}: configure an existing compatible installation')


def auth_home():
    return Path(os.environ.get('YUI_CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()


@lru_cache(maxsize=1)
def load_lock():
    lock = json.loads((CORE / 'toolchain/lock.json').read_text())
    shared = Path.home() / 'formalization-tools/lean-mathlib-v4.32.2'
    ml = choose('YUI_MATHLIB_ROOT', [shared / 'mathlib'])
    lean = choose('YUI_LEAN_ROOT', [shared / 'lean', Path.home() / '.elan/toolchains/leanprover--lean4---v4.32.2'])
    codex = choose('YUI_CODEX_BINARY', [shutil.which('codex'),
        '/Applications/Codex.app/Contents/Resources/codex',
        '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'])
    rg = choose('YUI_RG_BINARY', [shutil.which('rg'),
        '/Applications/ChatGPT.app/Contents/Resources/codex-cli/codex-path/rg'])
    lock['lean']['local_path'] = str(lean)
    lock['mathlib']['local_path'] = str(ml)
    lock['lean']['binary_sha256'] = digest(lean / 'bin/lean')
    from native_runtime import resolve
    lock['codex'] = resolve(codex,subprocess.check_output([str(codex), '--version'], text=True).strip())
    lock['tools'] = {'ripgrep': {'binary_path': str(rg), 'sha256': digest(rg)},
                     'python': {'binary_path': sys.executable}}
    return lock


def verify():
    lock = load_lock()
    actual = subprocess.check_output(['git', '-C', lock['mathlib']['local_path'], 'rev-parse', 'HEAD'], text=True).strip()
    if actual != lock['mathlib']['rev']:
        raise ValueError('mathlib revision differs from the frozen pin')
    library = Path(lock['mathlib']['local_path'])
    if digest(library/'lake-manifest.json') != lock['mathlib']['manifest_sha256']:
        raise ValueError('mathlib dependency manifest differs from the frozen pin')
    for path, revision in [(library, lock['mathlib']['rev']),
            *((library/'.lake/packages'/d['name'], d['rev']) for d in lock['dependencies'])]:
        observed = subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        dirty = subprocess.run(['git','-C',str(path),'diff','--quiet','HEAD','--'],capture_output=True)
        if observed != revision or dirty.returncode:
            raise ValueError('A pinned library/dependency has changed tracked sources: '+path.name)
    version = subprocess.check_output([str(Path(lock['lean']['local_path']) / 'bin/lean'), '--version'], text=True)
    if 'version 4.32.2,' not in version:
        raise ValueError('Lean version differs from the frozen pin')
    if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').is_file():
        raise RuntimeError('Strong isolation currently requires macOS sandbox-exec; no silent unrestricted fallback')
    return lock
