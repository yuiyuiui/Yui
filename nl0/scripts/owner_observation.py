"""Bounded owner observations and an explicit handoff to the host scheduler.

No model, proof tool or scheduler is started here. A pending handoff is never
evidence that a host schedule was registered or a foreground turn ended.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from datetime import datetime

from controller_common import CORE, bind


def policy():
    value = json.loads((CORE/'config.json').read_text())['owner_observation']
    if (value.get('foreground') != 'end_turn_after_handoff'
            or value.get('scheduler') != 'host_heartbeat'
            or value.get('notifications') != 'meaningful_changes_only'
            or type(value.get('interval_seconds')) is not int
            or value['interval_seconds'] <= 0 or value['interval_seconds'] % 60):
        raise ValueError('Invalid owner observation policy: use a positive whole-minute host interval')
    return dict(value)


def owned_runs(runs):
    """Bind explicit marked runs without scanning parents or mathematical inputs."""
    result = []
    for directory in runs:
        root = Path(directory).resolve()
        job = json.loads((root/'job.json').read_text())
        marker = json.loads((root/'.yui-run.json').read_text())
        if (job['root'] != str(root) or marker.get('root') != str(root)
                or marker.get('run_id') != job['run_id']
                or marker.get('job') != bind(root/'job.json')):
            raise ValueError('Observation requires an unchanged explicitly owned run')
        if root not in result:
            result.append(root)
    if not result:
        raise ValueError('Supply at least one owned run to observe')
    return result


def handoff(runs):
    selected = owned_runs(runs)
    settings = policy()
    command = [sys.executable, '-B', str(CORE/'nl0/scripts/yui.py'),
               'observe', *map(str, selected)]
    prompt = (
        'For a permitted scheduled handoff, observe only the already-dispatched Yui runs below. Perform one bounded '
        'check per scheduled wake using the supplied command; do not sleep, poll '
        'in a loop, or redispatch the workflow. Preserve the exact run map and '
        'record the host automation ID in owner-only monitor metadata. '
        'Read execution/result metadata, counts, actual errors and recorded usage '
        'only. Never inspect unfinished proof arguments or send mathematical '
        'advice, other skills, old verdicts or cross-case material to workers. '
        'Do not launch model/Lean/probe sessions, change artifacts, restart a '
        'live/waiting run, or infer permission for a new attempt. '
        'Notify on a meaningful phase/coverage change, fault, completion or '
        'required action; stay quiet on unchanged routine checks unless the user '
        'explicitly requested a report at every interval. Use the user-requested '
        'language. Missing usage is unknown; cached/reasoning counts are subsets. '
        'A recorded PASS is not new verification. At termination, inspect the '
        'actual Yui gate reports and validate existing bound artifacts without '
        'a new model or Lean run. Once every current run is terminal, exact owned '
        'processes/groups have exited and no authorized continuation is pending, '
        'preserve the final report and delete this completed host heartbeat. '
        'End the foreground turn after each bounded check.\n'
        'Runs: '+json.dumps(list(map(str, selected)))+'\n'
        'Read-only command: '+shlex.join(command)
    )
    return {'schema': 'yui-owner-handoff-1', **settings,
            'registration': 'HOST_REGISTRATION_REQUIRED', 'automation_id': None,
            'interval_minutes': settings['interval_seconds']//60,
            'runs': list(map(str, selected)), 'observe_command': command,
            'host_tool': 'automation_update', 'host_kind': 'heartbeat',
            'prompt': prompt,
            'next_action': (
                'Follow the entry monitoring mode. Prefer a host-permitted scheduled wakeup '
                'and record its actual ID before ending the owner turn. If scheduling is restricted, '
                'unavailable or unsuccessful, continue the same run with ten-minute waits in the '
                'owning turn and one observation per interval. A scheduling failure must not stop '
                'the authorized run. If neither observation mode is available, return manual observe/cancel commands.'
            )}


def process_table():
    from process_queries import query, started
    def parse(raw):
        table = {}
        for line in raw.stdout.splitlines():
            parts = line.split(None, 2)
            if len(parts)!=3:raise ValueError('Incomplete observed process identity')
            pid,pgid=map(int,parts[:2])
            if pid in table or min(pid,pgid)<0:raise ValueError('Invalid observed process identity')
            table[pid]={'pid':pid,'pgid':pgid,'started':started(parts[2])}
        if os.getpid() not in table:raise ValueError('Incomplete observed process snapshot')
        return table
    return query(['ps','-axo','pid=,pgid=,lstart='],parse,timeout=10)


def matches(record, table):
    row = table.get(record.get('pid'))
    return bool(row and row['pgid'] == record.get('pgid')
                and row['started'] == ' '.join(str(record.get('started', '')).split()))


def group_present(group, records, table):
    if not any(row['pgid']==group for row in table.values()):return False
    known=[row for row in records if row.get('pid')==row.get('pgid')==group]
    leader=table.get(group)
    try:
        datetime.strptime(leader['started'],'%a %b %d %H:%M:%S %Y')
        identified=True
    except (KeyError,TypeError,ValueError):identified=False
    # A new leader with a different OS start proves numeric PGID reuse. It is
    # unrelated to the old run; neither signal it nor report it as an old child.
    if known and identified and leader['pgid']==group and not any(matches(row,table) for row in known):
        return False
    # Without such positive reuse evidence, surviving orphan members still block
    # an exit claim even when the original leader itself has disappeared.
    return True


def snapshot(runs):
    selected = owned_runs(runs)
    settings = policy()
    try:
        table = process_table()
        process_error = None
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        table = {}
        process_error = type(error).__name__+': '+str(error)
    cases = []
    for root in selected:
        def read(name):
            path = root/name
            return json.loads(path.read_text()) if path.is_file() else {}
        state = read('execution-status.json')
        result = read('case-result.json').get('result', {})
        from fault_control import pending
        errors=pending(root)
        records = list(state.get('processes', {}).values())
        controller = state.get('controller', {})
        records.extend(row for row in [controller, read('launch.json').get('controller'),
            read('batch.json').get('controller'), read('case-process.json').get('process')]
            if row and {'pid', 'pgid', 'started'} <= row.keys())
        live = {row['pid'] for row in records if matches(row, table)}
        groups = sorted({row['pgid'] for row in records
                         if group_present(row['pgid'],records,table)})
        never_started = not state and not records and not result
        cancelled_before_start = result.get('status') == 'CANCELLED' and result.get('model_worker_called') is False
        exited = not process_error and not live and not groups and bool(records or never_started or cancelled_before_start)
        counts = state.get('counts', {})
        proof_counts = state.get('proof_counts', {})
        usage = result.get('usage') or state.get('usage', {})
        phase = state.get('phase') or ('QUEUED' if live else
            'CONTROLLER_EXITED_BEFORE_CASE_START' if records else 'PREPARED_NOT_STARTED')
        cases.append({'run': str(root), 'phase': phase,
            'recorded_result': result.get('status'), 'terminal_record_present': bool(result) and not errors,
            'paused_errors':[{'incident':e['incident'],'category':e['fault']['category'],
                'path':e['path'],'notification':e.get('notification'),'resumable':e.get('resumable')} for e in errors],
            'completion': result.get('completion'),
            'recorded_audit_b': (result.get('audit_b') or {}).get('status'),
            'counts': {k: v for k, v in counts.items() if type(v) is int},
            'proof_counts': {k: v for k, v in proof_counts.items() if type(v) is int},
            'proof_total': state.get('proof_total') if type(state.get('proof_total')) is int else None,
            'controller_identity_matches': matches(controller, table) if controller else False,
            'live_owned_process_count': len(live), 'registered_groups_still_present': groups,
            'process_exit_verified': exited,
            'usage': {k: usage[k] for k in ['status', 'confirmed_tokens', 'requests',
                'requests_with_usage', 'in_flight_or_unreported_requests'] if k in usage},
            'error': str(result['error'])[:500] if result.get('error') else None})
    terminal = all(row['terminal_record_present'] for row in cases)
    exited = all(row['process_exit_verified'] for row in cases)
    return {'schema': 'yui-owner-observation-1', 'cases': cases,
            'all_terminal': terminal, 'all_process_exits_verified': exited,
            'process_inspection_error': process_error,
            'next_check_seconds': None if terminal and exited else settings['interval_seconds'],
            'process_query_recoveries':__import__('process_queries').history(),
            'scope': 'One read-only snapshot. Use proof_total and proof_counts for nodes in the current plan; counts also includes diagnosis and review tasks. After a terminal result, task counts are history. Acceptance requires the bound gate reports.'}
