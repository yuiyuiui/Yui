"""Resolve host tools separately from portable scientific pins; never load personal instructions."""
from __future__ import annotations

import hashlib
from copy import deepcopy
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
_UNSELECTED = object()
_environment = ContextVar('yui_scientific_environment', default=_UNSELECTED)


@contextmanager
def use_environment(environment, *, checked=True):
    """Freeze the run's choice, including an explicitly Lean-free NL0 context."""
    if environment is not None:
        import lean_environment
        lean_environment.rules.validate(environment, checked=checked)
    token = _environment.set(deepcopy(environment))
    try:
        yield
    finally:
        _environment.reset(token)


def selected_environment():
    selected = _environment.get()
    if selected is _UNSELECTED:
        raw = os.environ.get('YUI_LEAN_ENVIRONMENT')
        if raw is not None:
            selected = json.loads(raw)
            if selected is not None:
                import lean_environment
                lean_environment.rules.validate(selected)
        else:
            import lean_environment
            selected = lean_environment.resolve()
    return deepcopy(selected)


def require_environment():
    selected = selected_environment()
    if selected is None:
        from lean_environment import SelectionRequired
        raise SelectionRequired(reason='This NL0-only run has no Lean environment. Select one explicitly before using native library tools.')
    return selected


def scientific_pins():
    import lean_environment
    return lean_environment.rules.pins(selected_environment())


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
        ('interface-', 'audit-b', 'translation-', 'nl0-to-lean', 'frozen-lean-', 'basis-final-'))
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
def host_tools():
    """Native carrier/host tools do not require a scientific installation."""
    lock = json.loads((CORE / 'toolchain/lock.json').read_text())
    codex = choose('YUI_CODEX_BINARY', [shutil.which('codex'),
        '/Applications/Codex.app/Contents/Resources/codex',
        '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'])
    rg = choose('YUI_RG_BINARY', [shutil.which('rg'),
        '/Applications/ChatGPT.app/Contents/Resources/codex-cli/codex-path/rg'])
    for name in ('lean', 'mathlib', 'dependencies'):
        lock.pop(name, None)
    from native_runtime import resolve
    lock['codex'] = resolve(codex,subprocess.check_output([str(codex), '--version'], text=True).strip())
    lock['tools'] = {'ripgrep': {'binary_path': str(rg), 'sha256': digest(rg)},
                     'python': {'binary_path': sys.executable}}
    return lock


def load_lock():
    lock = deepcopy(host_tools())
    selected = selected_environment()
    lock.update({key: deepcopy(selected[key]) if selected is not None else ([] if key == 'dependencies' else None)
                 for key in ('lean', 'mathlib', 'dependencies')})
    lock['scientific_environment'] = selected
    return lock


def verify():
    selected = selected_environment()
    if selected is not None:
        import lean_environment
        lean_environment.verify(selected)
    if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').is_file():
        raise RuntimeError('Strong isolation currently requires macOS sandbox-exec; no silent unrestricted fallback')
    return load_lock()
