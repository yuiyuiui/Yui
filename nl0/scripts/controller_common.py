"""Portable controller paths and explicit input bindings; no mathematical judgments."""
from pathlib import Path
from staging_storage import copy_input
import hashlib
import json
import sys

CORE = Path(__file__).resolve().parents[2]
for directory in (CORE/'nl0/scripts', CORE/'nl02lean/scripts'):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))


def write(path, value):
    from execution_state import atomic
    atomic(Path(path), value)


def final_write(path, value, *, recorder=None):
    """A report-write failure retains the controller; only an operator retries it."""
    from fault_control import Gate
    from execution_state import Cancelled
    path=Path(path)
    while True:
        try:
            write(path,value)
            return True
        except Exception as error:
            try:
                Gate(path.parent/'logs/final-write-errors',recorder=recorder,stage='final-report').pause(
                    error,resumable=True,checkpoint={'destination':str(path),
                        'retry_scope':'atomic final metadata write only','new_model_or_lean_call':False})
            except Cancelled:return False


def bind(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def manifest(directory):
    directory = Path(directory).resolve()
    rows = [{'id': p.name, 'path': p.name, 'sha256': bind(p)['sha256']}
            for p in sorted(directory.iterdir()) if p.is_file() and p.name != 'inputs.json']
    write(directory/'inputs.json', {'inputs': rows})
    return rows


def runtime_bindings():
    paths = [CORE/'SKILL.md', CORE/'config.json', CORE/'toolchain/lock.json']
    for folder in ('nl0/scripts', 'nl0/references', 'nl0/templates', 'nl02lean/scripts',
                   'nl02lean/references', 'nl02lean/templates', 'nl02lean/bank'):
        paths.extend(p for p in (CORE/folder).rglob('*')
                     if p.is_file() and p.suffix in {'.py', '.mjs', '.lean', '.json', '.md'})
    from library_catalog import catalog_files
    paths.extend(catalog_files())
    return [bind(p) for p in sorted(set(paths))]


def verify_bindings(rows):
    for row in rows:
        if bind(row['path']) != row:
            raise ValueError('Frozen input/runtime changed: '+row['path'])


def copy_problem_documents(problem, destination):
    """Copy the explicitly frozen problem manifest, never sibling files/history."""
    import shutil
    problem,destination=Path(problem),Path(destination)
    declared=problem/'inputs.json'
    rows=json.loads(declared.read_text())['inputs'] if declared.is_file() else [
        {'id':name,'path':name,'sha256':bind(problem/name)['sha256']}
        for name in ('problem.md','source-context.md','frozen-target.md') if (problem/name).is_file()]
    for row in rows:
        source=(problem/row['path']).resolve()
        if (not source.is_relative_to(problem.resolve()) or Path(row['id']).name!=row['id']
                or bind(source)['sha256']!=row['sha256']):
            raise ValueError('Invalid explicit problem input binding')
        if (destination/row['id']).exists():raise ValueError('Problem document collides with derived inputs')
        copy_input(source,destination/row['id'])
