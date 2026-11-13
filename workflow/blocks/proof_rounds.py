"""Proof-graph states and owned retained-round selection inside translation.

Locally complete rounds may enter assembly repair without compiler acceptance.
The default path also serves unstarted/partial status and recovery callers;
each such consumer retains its own evidence and readiness gate.
"""
import hashlib
import json
from pathlib import Path


COMPLETE = frozenset({'FRAGMENT_ASSEMBLED', 'GRAPH_ASSEMBLY_REPAIR_REQUIRED'})
PARTIAL = frozenset({'GRAPH_REPAIR_REQUIRED', 'GRAPH_UNFINISHED'})
KNOWN = COMPLETE | PARTIAL
ARTIFACTS = ('report.json', 'proofs.json', 'inputs/contract.json', 'inputs/plan.json')


def locally_complete(status):
    return isinstance(status, str) and status in COMPLETE


def compiler_accepted(status):
    return isinstance(status, str) and status == 'FRAGMENT_ASSEMBLED'


def retains_bodies(status):
    """A known graph may retain bodies; callers must still qualify each candidate."""
    return isinstance(status, str) and status in KNOWN


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def state_for(*, complete, accepted, repair_requested):
    _need(all(type(v) is bool for v in (complete, accepted, repair_requested))
          and (not accepted or complete) and not (complete and repair_requested),
          'Inconsistent proof-graph outcome')
    if accepted:
        return 'FRAGMENT_ASSEMBLED'
    if repair_requested:
        return 'GRAPH_REPAIR_REQUIRED'
    return 'GRAPH_ASSEMBLY_REPAIR_REQUIRED' if complete else 'GRAPH_UNFINISHED'


def _unique(pairs):
    value = {}
    for key, item in pairs:
        _need(key not in value, 'duplicate JSON key: ' + key)
        value[key] = item
    return value


def _load(path):
    return json.loads(path.read_text(), object_pairs_hook=_unique)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _owned_round(root, selected):
    _need(selected.is_relative_to(root) and selected != root, 'Unsafe proof-round selection')


def _artifacts(selected):
    paths = tuple(selected / name for name in ARTIFACTS)
    for path in paths:
        _need(path.is_file() and path.resolve() == path,
              'Missing or unsafe selected proof-round artifact: ' + str(path))
    return paths


def _complete_report(selected, message):
    path = selected / 'report.json'
    _need(path.is_file() and path.resolve() == path, 'Missing or unsafe selected proof-round report')
    report = _load(path)
    _need(isinstance(report, dict) and locally_complete(report.get('status')), message)


def selection(directory, selected, version):
    """Validate a complete local round before the host publishes its selection."""
    root, selected = Path(directory).resolve(), Path(selected).resolve()
    _owned_round(root, selected)
    _complete_report(selected, 'Cannot select missing local proof bodies')
    paths = _artifacts(selected)
    return {'version': version, 'directory': str(selected.relative_to(root)),
            'evidence': [{'path': str(path), 'sha256': _digest(path)} for path in paths],
            'scope': 'Selected complete local proofs; the retained report records whether whole-file compilation still needs repair.'}


def read(directory, version):
    """Return the selected directory with exact evidence, or the default location.

    Reading a location or a repairable round never grants final acceptance.
    Frozen source/plan authority remains the host consumer's responsibility.
    """
    root = Path(directory).resolve()
    record = root / 'proof-selection.json'
    _need(not record.is_symlink(), 'Unsafe proof-round selection record')
    if not record.exists():
        default = root / 'proof-run'
        _need(default.resolve() == default, 'Unsafe default proof-round location')
        return default
    value = _load(record)
    _need(isinstance(value, dict) and value.get('version') == version,
          'Unsafe proof-round selection version')
    name = value.get('directory')
    _need(isinstance(name, str) and bool(name), 'Unsafe proof-round selection directory')
    relative = Path(name)
    selected = (root / relative).resolve()
    _need(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe proof-round selection')
    _owned_round(root, selected)
    paths = _artifacts(selected)
    evidence = value.get('evidence')
    _need(isinstance(evidence, list) and len(evidence) == len(paths),
          'Missing or duplicate proof-round selection evidence')
    seen = set()
    for item in evidence:
        _need(isinstance(item, dict) and set(item) == {'path', 'sha256'}
              and isinstance(item['path'], str) and isinstance(item['sha256'], str),
              'Invalid proof-round selection evidence')
        path = Path(item['path'])
        _need(path in paths and path not in seen, 'Missing or duplicate proof-round selection evidence')
        _need(_digest(path) == item['sha256'], 'stale bound artifact: ' + str(path))
        seen.add(path)
    _complete_report(selected, 'Selected proof round has missing local proof bodies')
    return selected
