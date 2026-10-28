"""Controller-only ownership records for reclaiming interrupted run resources.

These records contain no credentials, call no model, and never become task input.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import uuid

from execution_state import atomic, identity

MARKER = '.yui-workspace-owner.json'
SCHEMA = 'yui-workspace-owner-1'
CORE = Path(__file__).resolve().parents[2]


def check_cleanup_lock(output):
    output = Path(output).resolve()
    for root in (output,*output.parents):
        if (root/'.yui-run.json').is_file() and (root/'.cleanup.lock').exists():
            raise RuntimeError('Run cleanup is in progress; no new stage may start')


def register_workspace(work, logs):
    """Bind an exact temporary directory to its owning output directory."""
    work, logs = Path(work).resolve(), Path(logs).resolve()
    check_cleanup_lock(logs)
    owner = identity(os.getpid())
    if owner is None:
        raise RuntimeError('Cannot establish temporary workspace ownership')
    if work.parent != Path(tempfile.gettempdir()).resolve():
        raise ValueError('Only a direct child of the OS temporary directory is registered')
    existing = work/MARKER
    if existing.exists():
        row = json.loads(existing.read_text())
        if row['logs'] != str(logs):
            raise ValueError('Temporary workspace already belongs to another output')
        return row
    token = uuid.uuid4().hex
    row = {'schema_version': SCHEMA, 'token': token, 'workspace': str(work),
           'logs': str(logs), 'owner': owner}
    atomic(existing, row)
    atomic(logs/'resources'/('workspace-'+token+'.json'), row)
    return row


def register_child(work, process, kind):
    """Persist identity even when a stage has no case-level Recorder."""
    marker = Path(work).resolve()/MARKER
    if not marker.is_file():
        return
    row = json.loads(marker.read_text())
    child = identity(process.pid)
    if child is None:
        if process.poll() is None:
            raise RuntimeError('Cannot establish child process ownership')
        return
    atomic(Path(row['logs'])/'resources'/('process-'+uuid.uuid4().hex+'.json'),
           {'schema_version': 'yui-owned-process-1', 'workspace_token': row['token'],
            'kind': kind, 'process': child})
