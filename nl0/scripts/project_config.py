"""Project-owned settings and their immutable per-run copy."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

CORE = Path(__file__).resolve().parents[2]
NAME = 'yui-config.json'
STAGES = ('2basis', 'nl0', 'audit-a', 'nl02lean', 'audit-b', 'b2lean')
_active = ContextVar('yui_project_configuration', default=None)
_stage = ContextVar('yui_project_stage', default=None)


def template(core=CORE):
    return Path(core)/'nl0'/'templates'/NAME


def source(core=CORE):
    path = _active.get()
    if path is not None:
        return path
    frozen = Path(core)/NAME
    return frozen if frozen.is_file() else template(core)


def runtime_files(core, paths):
    for path in paths:
        yield path, path.relative_to(core)
    yield source(core), Path(NAME)


def for_run(job):
    runtime = Path(job['root'])/'runtime'
    path = runtime/NAME
    # Existing immutable jobs captured the former installation file by this name.
    if not path.exists() and (runtime/'config.json').is_file():
        return runtime/'config.json'
    return path


@contextmanager
def use(path):
    token = _active.set(Path(path))
    try:
        yield
    finally:
        _active.reset(token)


@contextmanager
def stage(name):
    token = _stage.set(name)
    try:
        yield
    finally:
        _stage.reset(token)


def stage_name(phase, translation):
    if _stage.get():
        return _stage.get()
    if phase in STAGES:
        return phase
    if phase.startswith('basis-final-') or phase.startswith('b2lean'):
        return 'b2lean'
    if phase.startswith('basis-'):
        return '2basis'
    if phase.startswith('audit-b'):
        return 'audit-b'
    if phase.startswith('audit-a'):
        return 'audit-a'
    return 'nl02lean' if translation else 'nl0'


def groups(config):
    return {'nl0': config['model'], 'lean': config['phase_models']['nl0_to_lean']}


def set_groups(config, profiles):
    config['model'] = dict(profiles['nl0'])
    config['phase_models']['nl0_to_lean'] = dict(profiles['lean'])


def validate(config):
    import concurrency
    from runtime_config import time_limit, validate_profile
    factory = json.loads(template().read_bytes())
    if (not isinstance(config, dict) or set(config) != set(factory)
            or type(config['version']) is not int or config['version'] != 1):
        raise ValueError('Invalid project configuration fields or version')
    for key in ('phase_models','stages','timeouts','lean','owner_observation'):
        if not isinstance(config[key],dict):
            raise ValueError('Expected an object for '+key)
    if set(config['phase_models']) != {'nl0_to_lean'} or set(config['stages']) - set(STAGES):
        raise ValueError('Unknown project stage or model group')
    bases = groups(config)
    for base in bases.values():
        validate_profile(base)
    for name, fields in config['stages'].items():
        if not isinstance(fields, dict):
            raise ValueError('Expected model settings for '+name)
        validate_profile({**bases['nl0'], **fields})
    concurrency.resolve(config['max_concurrency'])
    if set(config['timeouts']) != set(factory['timeouts']):
        raise ValueError('Invalid project timeout settings')
    for value in config['timeouts'].values():
        time_limit(value)
    beats = config['lean'].get('max_heartbeats')
    if set(config['lean']) != {'max_heartbeats'} or type(beats) is not int or beats <= 0:
        raise ValueError('lean.max_heartbeats must be a positive integer')
    policy = config['owner_observation']
    interval = policy.get('interval_seconds')
    default_policy = factory['owner_observation']
    if (type(interval) is not int or interval <= 0 or interval % 60
            or {**policy,'interval_seconds':default_policy['interval_seconds']} != default_policy):
        raise ValueError('Invalid project owner observation settings')
    if config['isolation'] != factory['isolation'] or config['token_budget'] is not None:
        raise ValueError('Unsupported isolation policy or token budget')
    return config


def directory_for(input_file):
    directory = Path(input_file).resolve().parent
    for parent in (directory, *directory.parents):
        if parent.parent == parent or (parent == Path.home() and parent != directory):
            break
        if os.path.lexists(parent/NAME):
            return parent
        if (parent/'.git').exists():
            break
    return directory


def open_project(directory, *, profiles=None, model_overrides=None, workers=None, seconds=None):
    """Create once without clobbering another prepare or a user-edited file."""
    import local_config
    directory = Path(directory).expanduser().resolve(strict=True)
    if not directory.is_dir() or directory.is_relative_to(CORE):
        raise ValueError('Choose a project directory outside the installed Yui skill')
    path = directory/NAME
    if not path.exists() and not path.is_symlink():
        config = json.loads(template().read_bytes())
        local = local_config.current() if profiles is None else None
        bases = profiles or (local['profiles'] if local else groups(config))
        set_groups(config, {k:{**v, **(model_overrides or {}).get(k,{})} for k,v in bases.items()})
        if workers is not None:
            config['max_concurrency'] = workers
        if seconds is not None:
            config['timeouts']['case_seconds'] = seconds
        validate(config)
        with NamedTemporaryFile(dir=directory, prefix='.'+NAME+'-', delete=False) as tmp:
            candidate = Path(tmp.name)
            try:
                tmp.write((json.dumps(config,indent=2)+'\n').encode())
                tmp.flush()
                try:
                    os.link(candidate, path)
                except FileExistsError:
                    pass
            finally:
                candidate.unlink(missing_ok=True)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected a regular project configuration file: '+str(path))
    return validate(json.loads(path.read_bytes()))


def effective(config, profiles, workers, seconds):
    result = deepcopy(config)
    set_groups(result, profiles)
    result['max_concurrency'] = workers
    result['timeouts']['case_seconds'] = seconds
    return validate(result)
