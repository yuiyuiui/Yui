"""Select one explicitly compatible scientific environment before Lean work."""
from copy import deepcopy
from pathlib import PurePath
import re


VERSION = 'yui-lean-environment-1'
SHA256 = re.compile(r'^[0-9a-f]{64}$')
REVISION = re.compile(r'^[0-9a-f]{40}$')


class SelectionRequired(ValueError):
    def __init__(self, candidates=(), reason='Select a compatible Lean and Mathlib pair.'):
        self.request = {
            'status': 'LEAN_ENVIRONMENT_SELECTION_REQUIRED', 'reason': reason,
            'candidates': [deepcopy(row) for row in candidates],
            'choices': {
                'paths': 'Supply --lean-root and --mathlib-root for a matching local pair.',
                'versions': 'Supply --lean-version and --mathlib-version; use lean-environments --install to download and verify missing versions.'}}
        super().__init__(reason + ' ' + ' '.join(self.request['choices'].values()))


def validate(value, *, checked=True):
    if not isinstance(value, dict) or value.get('version') != VERSION:
        raise ValueError('Unsupported selected Lean environment')
    lean, library = value['lean'], value['mathlib']
    if (not isinstance(lean.get('version_number'), str)
            or lean.get('toolchain') != 'leanprover/lean4:v' + lean['version_number']
            or not lean.get('version', '').startswith('Lean (version ' + lean['version_number'] + ',')
            or not SHA256.fullmatch(lean.get('binary_sha256', ''))
            or not all(PurePath(row.get('local_path', '')).is_absolute() for row in (lean, library))
            or not REVISION.fullmatch(library.get('rev', ''))
            or not all(SHA256.fullmatch(library.get(key, ''))
                       for key in ('manifest_sha256', 'toolchain_sha256'))):
        raise ValueError('Invalid selected Lean/Mathlib identity')
    dependencies = value.get('dependencies')
    if (not isinstance(dependencies, list)
            or any(not isinstance(row, dict) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', row.get('name', ''))
                   or not REVISION.fullmatch(row.get('rev', '')) for row in dependencies)
            or len({row['name'] for row in dependencies}) != len(dependencies)):
        raise ValueError('Invalid selected dependency inventory')
    if checked:
        probe = value.get('compatibility') or {}
        if (probe.get('accepted') is not True or type(probe.get('exit_code')) is not int
                or probe['exit_code'] != 0 or probe.get('timed_out') or probe.get('cancelled')
                or not SHA256.fullmatch(probe.get('source_sha256', ''))):
            raise ValueError('A completed native compatibility check is required')
    return value


def select(candidates, *, lean_version=None, mathlib_ref=None):
    """Deduplicate aliases, honor requested versions, and never guess ambiguity."""
    choices = {}
    for row in candidates:
        validate(row)
        key = (row['lean']['local_path'], row['mathlib']['local_path'])
        choices.setdefault(key, row)
    matching = [row for row in choices.values()
                if (lean_version is None or row['lean']['version_number'] == lean_version.removeprefix('v'))
                and (mathlib_ref is None or mathlib_ref in {row['mathlib']['rev'], row['mathlib'].get('ref')})]
    if len(matching) != 1:
        raise SelectionRequired(list(choices.values()),
                                'No matching verified pair is installed.' if not matching else
                                'More than one compatible pair is installed; choose the intended versions or paths.')
    return deepcopy(matching[0])


def pins(value):
    if value is None:
        return dict.fromkeys(('lean_version', 'mathlib_commit', 'mathlib_root'), 'NOT_SELECTED')
    validate(value)
    return {'lean_version': value['lean']['version_number'],
            'mathlib_commit': value['mathlib']['rev'], 'mathlib_root': value['mathlib']['local_path']}
