"""Periodic controller snapshots and local delivery to the case owner."""
import json
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from owner_observation import owner_thread, policy, progress, REPORT_LOG


def publish_report(root, *, result_status=None):
    """Journal the recorded snapshot before submitting it to the local app queue."""
    from fault_control import queue_notification

    try:
        state = json.loads((root/'execution-status.json').read_bytes())
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    observed = datetime.now(timezone.utc)
    report = {'case': state.get('case_id', root.name), 'run': str(root),
              'phase': state.get('phase', 'QUEUED'), 'result': result_status,
              'proof_total': state.get('proof_total'), 'task_counts': state.get('counts', {}),
              'last_model_event_at_utc': max((task['last_model_event_at_utc']
                  for task in state.get('tasks', {}).values()
                  if task.get('state') == 'RUNNING' and task.get('last_model_event_at_utc')), default=None),
              'progress': progress(state, observed=observed, identity_matches=True,
                  process_error=None, state_error=None, result_status=result_status)}
    path = root/REPORT_LOG
    path.parent.mkdir(exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'report': report}, ensure_ascii=False)+'\n')
    thread = owner_thread(root)
    if thread:
        message = ('[Yui STATUS] Local controller report\n'
                   + json.dumps(report, ensure_ascii=False, indent=2)
                   + '\nInterpret this snapshot for the owner. For a terminal result follow the existing entry’s validation and cleanup. End this turn after reporting.')
        receipt = queue_notification(thread, message, resume=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'report_at_utc': observed.isoformat(), 'delivery': receipt},
                                    ensure_ascii=False)+'\n')


def send_report(root, *, result_status=None):
    try:
        publish_report(root, result_status=result_status)
    except Exception as error:
        print(f'Yui status report failed for {root}: {type(error).__name__}: {error}', file=sys.stderr)


@contextmanager
def controller_reports(runs):
    stop = threading.Event()
    workers = []

    def tick(root, interval):
        due = time.monotonic()+interval
        while not stop.wait(max(0, due-time.monotonic())):
            if (root/'case-result.json').is_file() or (root/'cancel-request.json').is_file():
                return
            send_report(root)
            due += interval
            if due <= time.monotonic():
                due = time.monotonic()+interval

    try:
        for root in runs:
            try:
                interval = policy(root)['interval_seconds']
                worker = threading.Thread(target=tick, args=(root, interval), daemon=True)
                worker.start()
                workers.append(worker)
            except (OSError, ValueError, KeyError, RuntimeError) as error:
                print(f'Yui status reporting unavailable for {root}: {error}', file=sys.stderr)
        yield
    finally:
        stop.set()
        for worker in workers:
            worker.join(16)  # The local queue call is bounded to 15 seconds.
