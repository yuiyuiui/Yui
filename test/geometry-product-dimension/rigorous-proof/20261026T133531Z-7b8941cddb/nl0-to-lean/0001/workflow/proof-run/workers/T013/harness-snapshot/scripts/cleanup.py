#!/usr/bin/env python3
"""Preview or stop and remove explicit owned Yui runs; never call a model.

Run from any directory. Default is a read-only preview; --apply performs cleanup.
Problem inputs, installed code, regression fixtures and shared Lean
installations are preserved. Unconfirmed process ownership blocks deletion.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import shlex
import subprocess
import sys
import tempfile
import time

CORE = Path(__file__).resolve().parents[1]
REPO = CORE.parent
from execution_state import atomic, now, request_cancel
from run_resources import MARKER, SCHEMA


def process_table():
    result = subprocess.run(['ps', '-axww', '-o', 'pid=,ppid=,pgid=,stat=,lstart=,command='],
                            capture_output=True, text=True, check=True, timeout=10)
    rows = {}
    for line in result.stdout.splitlines():
        parts = line.split(None, 9)
        if len(parts) != 10:
            continue
        pid, ppid, pgid = map(int, parts[:3])
        rows[pid] = {'pid': pid, 'ppid': ppid, 'pgid': pgid, 'stat': parts[3],
                     'started': ' '.join(parts[4:9]), 'command': parts[9]}
    return rows


def matching(record, table):
    row = table.get(record.get('pid'))
    return bool(row and not row['stat'].startswith('Z') and
                all(row[k] == record.get(k) for k in ('pid', 'pgid')) and
                row['started'] == ' '.join(str(record.get('started', '')).split()))


def load(path):
    if path.stat().st_size > 2_000_000:
        raise ValueError('Oversized ownership record: '+str(path))
    return json.loads(path.read_text())


def generated_roots(repo):
    raise ValueError('Select explicit owned run directories; no global output tree is scanned')


def selected_roots(repo, outputs=None):
    if outputs is None:
        raise ValueError('Explicit --output run directories are required')
    selected = []
    for raw in outputs:
        path = Path(raw).absolute()
        if any(p.is_symlink() for p in [path,*path.parents]):
            raise ValueError('Refuse symlink selected output: '+str(path))
        path = path.resolve()
        import jobs
        if path.is_relative_to(CORE) or not (path/jobs.MARKER).is_file():
            raise ValueError('Select a marked Yui run outside the installed skill: '+str(path))
        from controller_common import bind
        job=json.loads((path/'job.json').read_text());marker=load(path/jobs.MARKER)
        if (str(path)!=job['root'] or marker.get('root')!=str(path)
                or marker.get('run_id')!=job.get('run_id') or marker.get('job')!=bind(path/'job.json')):
            raise ValueError('Output marker belongs to another directory or its job changed')
        if not any(parent == path or parent in path.parents for parent in selected):
            selected = [p for p in selected if path not in p.parents] + [path]
    if not selected:
        raise ValueError('An explicit cleanup selection cannot be empty')
    return selected


def inventory(repo, outputs=None):
    roots = selected_roots(repo, outputs)
    records, workspaces, snapshots, batches, errors = [], {}, [], [], []
    temp_root = Path(tempfile.gettempdir()).resolve()
    for root in roots:
        if root.is_symlink():
            errors.append('Refuse symlink output root: '+str(root)); continue
        if not root.exists():
            continue
        for directory, dirs, files in os.walk(root, followlinks=False):
            base = Path(directory)
            dirs[:] = [d for d in dirs if not (base/d).is_symlink()]
            for filename in files:
                path = base/filename
                if path.is_symlink():
                    continue
                try:
                    if filename == 'execution-status.json':
                        row = load(path)
                        if row.get('schema_version') != 'yui-execution-1':
                            raise ValueError('Unknown execution ownership schema: '+str(path))
                        records.extend([row['controller'], *row['processes'].values()])
                        snapshots.append(base)
                    elif filename == 'batch.json':
                        row = load(path)
                        if row.get('controller') and set(row.get('case_run_roots',[]))<=set(str(p) for p in roots):
                            records.append(row['controller'])
                        batches.append(base)
                    elif filename == 'case-process.json' or (base.name == 'resources' and filename.startswith('process-')):
                        row = load(path)
                        if row.get('schema_version') != 'yui-owned-process-1':
                            raise ValueError('Unknown child ownership schema: '+str(path))
                        records.append(row['process'])
                    elif base.name == 'resources' and filename.startswith('workspace-'):
                        row = load(path); work = Path(row['workspace'])
                        if (row.get('schema_version') != SCHEMA or work.is_symlink() or
                            work.resolve().parent != temp_root or
                            Path(row['logs']).resolve() != base.parent.resolve()):
                            raise ValueError('Invalid workspace binding: '+str(path))
                        if work.exists():
                            if not (work/MARKER).is_file() or (work/MARKER).is_symlink() or load(work/MARKER) != row:
                                raise ValueError('Workspace owner marker differs: '+str(work))
                            workspaces[work.resolve()] = str(path)
                        records.append(row['owner'])
                    elif filename == 'transport-sandbox.sb':
                        # Migration of old Yui stages before explicit workspace markers.
                        # Require an exact archived/live profile match and Yui carrier config.
                        text = path.read_text()
                        for raw in re.findall(r'\(subpath ("(?:[^"\\]|\\.)*")\)', text):
                            work = Path(json.loads(raw))
                            if not work.name.startswith('nl0-ir-model-') or work.resolve().parent != temp_root:
                                continue
                            if work.is_symlink() or not work.is_dir():
                                continue
                            profile, config = work/'transport.sb', work/'state/config.toml'
                            if (profile.is_file() and not profile.is_symlink() and
                                config.is_file() and not config.is_symlink() and
                                profile.read_text() == text and 'Yui isolated subscription carrier' in config.read_text()):
                                workspaces[work.resolve()] = str(path)
                except (OSError, ValueError, KeyError, TypeError) as error:
                    errors.append(str(error))
    return {'roots': roots, 'records': records, 'workspaces': workspaces,
            'snapshots': snapshots, 'batches': batches, 'errors': errors}


def discover(inv, table, repo):
    """Exact identities, their descendants, and processes using owned workspaces."""
    owned = {r['pid']: table[r['pid']] for r in inv['records'] if matching(r, table)}
    roots = [str(p.resolve())+'/' for p in inv['roots']]
    workspaces = [str(p)+'/' for p in inv['workspaces']]
    entries = [str(CORE/'scripts/case_runner.py')]
    for pid, row in table.items():
        if pid == os.getpid() or row['stat'].startswith('Z'):
            continue
        cmd = row['command']
        try:
            args = shlex.split(cmd)
        except ValueError:
            args = []
        if any(entry in args for entry in entries) and any(arg.startswith(root) for arg in args for root in roots):
            owned[pid] = row
        elif any(arg.startswith(work) for arg in args for work in workspaces):
            owned[pid] = row
        elif args and Path(args[0]).name in {'lean', 'sandbox-exec'} and any(arg.startswith(root) for arg in args for root in roots):
            owned[pid] = row
        elif workspaces and re.search(r'\bapp-server\b|/lean(?:\s|$)', cmd):
            # Old app-server argv can omit its sandbox profile after exec.
            cwd = subprocess.run(['lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'],
                                 capture_output=True, text=True, timeout=5)
            if any(line.startswith('n') and any(line[1:].rstrip('/')+'/' == work+'input/' or
                       line[1:].rstrip('/')+'/' == work+'output/' for work in workspaces)
                   for line in cwd.stdout.splitlines()):
                owned[pid] = row
    changed = True
    while changed:
        added = {pid: row for pid, row in table.items() if row['ppid'] in owned and
                 pid not in owned and not row['stat'].startswith('Z')}
        changed = bool(added); owned.update(added)
    return owned


@contextlib.contextmanager
def cleanup_lock(repo):
    path = Path(repo)/'.cleanup.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    table = process_table()
    if path.exists():
        previous = load(path)
        if previous.get('schema_version') != 'yui-run-cleanup-1' or matching(previous.get('owner', {}), table):
            raise ValueError('Another cleanup is active or lock ownership is unknown: '+str(path))
        path.unlink()  # Only a known schema with an expired exact identity.
    owner = table[os.getpid()]
    value = {'schema_version': 'yui-run-cleanup-1',
             'owner': {k: owner[k] for k in ('pid', 'started', 'pgid')}}
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(value, handle)
    try:
        yield
    finally:
        if path.is_file() and load(path) == value:
            path.unlink()


def signal_owned(rows, sig):
    table = process_table()
    for pid, row in rows.items():
        if pid == os.getpid():
            raise ValueError('Cleanup cannot delete a test owned by its own live process')
        if matching(row, table):
            try:
                # Signal identities individually: never kill an unrelated process group.
                os.kill(pid, sig)
            except ProcessLookupError:
                pass


def clean(repo=REPO, *, apply=False, grace=10, outputs=None):
    repo = Path(repo).resolve()
    if grace < 0 or grace > 60:
        raise ValueError('Grace must be between zero and sixty seconds')
    roots=selected_roots(repo,outputs)
    with contextlib.ExitStack() as locks:
        if apply:
            for root in sorted(roots):locks.enter_context(cleanup_lock(root))
        inv = inventory(repo, outputs)
        table = process_table(); owned = discover(inv, table, repo)
        report = {'mode': 'APPLY' if apply else 'PREVIEW', 'at_utc': now(),
                  'generated_roots': [str(p) for p in inv['roots'] if p.exists()],
                  'owned_temporary_directories': len(inv['workspaces']),
                  'matching_processes': [{k: row[k] for k in ('pid', 'started', 'pgid')}
                                         for row in owned.values()],
                  'errors': inv['errors'], 'warnings': [], 'removed_roots': [], 'removed_temporary_directories': 0,
                  'scope': 'Explicit owned runs and verifiably owned temporary resources only; no model calls.'}
        if not apply or inv['errors']:
            report['status'] = 'BLOCKED' if inv['errors'] else 'PREVIEW'
            return report
        if os.getpid() in owned:
            raise ValueError('Run cleanup in a separate process from the test owner')
        for root in inv['snapshots']:
            if matching(load(root/'execution-status.json')['controller'], table):
                try:
                    request_cancel(root)
                except (OSError, ValueError) as error:
                    report['warnings'].append('Cancellation request failed; use exact-identity signals: '+str(error))
        for root in roots:
            atomic(root/'cancel-request.json', {'external_cancel':True,'reason':'RUN_CLEANUP'})
        # A shared batch owner must acknowledge removing a queued case before
        # its directory is deleted; cancelling one case must not kill siblings.
        deadline=time.monotonic()+grace
        while True:
            table=process_table();waiting=[]
            for root in roots:
                batch=root/'batch.json'
                if not batch.is_file() or (root/'case-result.json').is_file() or (root/'case-process.json').is_file():continue
                row=load(batch)
                if matching(row.get('controller',{}),table):waiting.append(str(root))
            if not waiting:break
            if time.monotonic()>=deadline:
                report.update(status='BLOCKED',errors=['Queued-case cancellation not acknowledged'],waiting_runs=waiting)
                return report
            time.sleep(.1)
        signal_owned(owned, signal.SIGTERM)
        deadline = time.monotonic()+grace
        while owned and time.monotonic() < deadline:
            time.sleep(.1)
            inv = inventory(repo, outputs); table = process_table()
            found = discover(inv, table, repo)
            owned = {**{pid: r for pid, r in owned.items() if matching(r, table)}, **found}
        # Rescan after graceful shutdown to include children registered during cancellation.
        inv = inventory(repo, outputs); table = process_table()
        owned = {**{pid: r for pid, r in owned.items() if matching(r, table)}, **discover(inv, table, repo)}
        signal_owned(owned, signal.SIGKILL)
        deadline = time.monotonic()+3
        while owned and time.monotonic() < deadline:
            time.sleep(.05); table = process_table()
            owned = {pid: r for pid, r in owned.items() if matching(r, table)}
        inv = inventory(repo, outputs); table = process_table()
        owned.update(discover(inv, table, repo))
        if owned or inv['errors']:
            report.update(status='BLOCKED', errors=inv['errors'], residual_pids=sorted(owned))
            return report  # Keep every ownership record if shutdown is not confirmed.
        for work in inv['workspaces']:
            shutil.rmtree(work)
            report['removed_temporary_directories'] += 1
        for root in inv['roots']:
            if root.exists():
                shutil.rmtree(root); report['removed_roots'].append(str(root))
        caches = []
        for parent in (() if outputs is not None else (repo/'test', repo/'rigorous-proof')):
            for directory, dirs, _ in os.walk(parent, followlinks=False):
                dirs[:] = [d for d in dirs if not (Path(directory)/d).is_symlink()]
                if '__pycache__' in dirs:
                    caches.append(Path(directory)/'__pycache__'); dirs.remove('__pycache__')
        for path in caches:
            shutil.rmtree(path)
        report.update(status='CLEANED', residual_pids=[], removed_python_caches=len(caches))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Stop owned run processes and delete their generated outputs')
    parser.add_argument('--grace-seconds', type=float, default=10)
    parser.add_argument('--output', type=Path, action='append', required=True, help='Explicit owned run; repeat for several')
    args = parser.parse_args()
    try:
        result = clean(apply=args.apply, grace=args.grace_seconds, outputs=args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result = {'status': 'BLOCKED', 'error': str(error)}
    print(json.dumps(result, indent=2))
    return 1 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
