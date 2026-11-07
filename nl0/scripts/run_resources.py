"""Controller-only ownership records for reclaiming interrupted run resources.

These records contain no credentials, call no model, and never become task input.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import uuid
import hashlib

from execution_state import atomic, identity, capture_process

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


def register_child(work, process, kind, *, private_group=False):
    """Persist identity even when a stage has no case-level Recorder."""
    marker = Path(work).resolve()/MARKER
    if not marker.is_file():
        return
    row = json.loads(marker.read_text())
    child = capture_process(process, private_group=private_group)
    atomic(Path(row['logs'])/'resources'/('process-'+uuid.uuid4().hex+'.json'),
           {'schema_version': 'yui-owned-process-1', 'workspace_token': row['token'],
            'kind': kind, 'process': child})
    return child


def retention(work, logs):
    work,logs=Path(work).resolve(),Path(logs).resolve()
    marker=Path(work)/MARKER
    return {'status':'OWNED_RETAINED','workspace':str(work),'logs':str(logs),
            'owner':identity(os.getpid()),'marker_sha256':hashlib.sha256(marker.read_bytes()).hexdigest()}


def safe_stage_workspace(result, *, archived=None):
    """Accept retained ownership or its separate authorized release receipt."""
    if result.get('temporary_workspace_removed') is not False:return True
    row=result.get('workspace_retention',{})
    if row.get('status')!='OWNED_RETAINED':return False
    work=Path(row['workspace']);logs=Path(row['logs'])
    if archived is None and work.is_dir() and not work.is_symlink():
        try:
            marker=work/MARKER;owner=json.loads(marker.read_text())
            from execution_state import same_process
            return (hashlib.sha256(marker.read_bytes()).hexdigest()==row['marker_sha256']
                    and owner['workspace']==str(work) and owner['logs']==str(logs)
                    and owner['owner']==row['owner'] and same_process(row['owner']))
        except (OSError,ValueError,KeyError):return False
    try:
        release_file, result_file = ((logs/'resources/release.json', logs/'result.json')
                                     if archived is None else (archived[0]/'release.json', archived[1]))
        released=json.loads(release_file.read_text())
        return (released['workspace_retention']==row and released['cleanup_confirmed'] is True
                and released['authorization'] in {'AUDIT_A_FINALIZED','WORKFLOW_FINALIZED','USER_CANCELLED','ROLE_COMPLETED'}
                and hashlib.sha256(result_file.read_bytes()).hexdigest()==released['result_sha256'])
    except (OSError,ValueError,KeyError):return False
