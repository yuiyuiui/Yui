"""One ignored local default; frozen jobs never reread a changed default."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path

CORE = Path(__file__).resolve().parents[2]
_spec = spec_from_file_location('yui_local_setup_rules', CORE/'workflow/blocks/local_setup.py')
rules = module_from_spec(_spec)
_spec.loader.exec_module(rules)
_UNSET = object()
_selected = ContextVar('yui_local_configuration', default=_UNSET)
_provisional = ContextVar('yui_setup_in_progress', default=False)


def path():
    return CORE/'.runtime/local-config.json'


def scoped():
    return _selected.get() is not _UNSET or 'YUI_FROZEN_LOCAL_CONFIG' in os.environ


def provisional():
    return _provisional.get()


def current():
    selected = _selected.get()
    if selected is not _UNSET:
        return deepcopy(selected)
    raw = os.environ.get('YUI_FROZEN_LOCAL_CONFIG')
    if raw is not None:
        value = json.loads(raw)
        if value is not None:
            (rules.validate_runtime if value.get('version')==rules.RUN_VERSION else rules.validate_config)(value)
        return value
    file = path()
    if not file.is_file():
        return None
    if file.is_symlink():
        raise rules.SetupRequired('Local configuration must not be a symlink')
    value = rules.validate_config(json.loads(file.read_text()))
    if Path(value['root']).resolve() != CORE.resolve():
        raise rules.SetupRequired('The installation moved; execute setup/README.md again')
    return value


@contextmanager
def use(value, *, provisional=False):
    if value is not None and not provisional:
        (rules.validate_runtime if value.get('version')==rules.RUN_VERSION else rules.validate_config)(value)
    token = _selected.set(deepcopy(value))
    pending = _provisional.set(provisional)
    try:
        yield
    finally:
        _selected.reset(token)
        _provisional.reset(pending)


def verify(value, *, evidence=True):
    """Check frozen identities; authentication content is never captured."""
    frozen=value.get('version')==rules.RUN_VERSION
    (rules.validate_runtime if frozen else rules.validate_config)(value)
    import native_runtime
    from controller_common import verify_bindings
    native_runtime.verify(value['host']['codex'])
    verify_bindings([value['host']['ripgrep']])
    if not Path(value['host']['python']).is_file():
        raise rules.SetupRequired('The configured Python interpreter is missing')
    if value['lean_environment'] is not None:
        import lean_environment
        lean_environment.verify(value['lean_environment'])
    if evidence and not frozen:
        verify_bindings([item for row in value['checks'].values() for item in row['evidence']])
        verify_bindings([{'path':str(Path(value['root'])/name),'sha256':sha}
                         for name,sha in value['implementation'].items()])
    if evidence and not frozen:
        verify_bindings([row['specification'] for row in value['libraries']])
    return deepcopy(value)


def for_job(value, profiles, selected, *, host=None):
    if value is None:return None
    return {'version':rules.RUN_VERSION,'host':deepcopy(value['host'] if host is None else host),
            'profiles':deepcopy(profiles),'lean_environment':deepcopy(selected)}
