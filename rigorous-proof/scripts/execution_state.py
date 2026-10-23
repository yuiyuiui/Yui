"""Case-local execution snapshots and scoped cancellation. No model calls."""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone

from usage import normalize

_scope = contextvars.ContextVar('yui_execution_scope', default=(None, None))


class Cancelled(Exception):
    """An explicit external stop, never a model deadline or mathematical gap."""


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def identity(pid):
    """PID plus OS process-start identity; never authorize a signal by PID alone."""
    try:
        result = subprocess.run(['ps', '-p', str(int(pid)), '-o', 'lstart='],
                                capture_output=True, text=True, timeout=2)
        started = result.stdout.strip()
        if not started or result.returncode: return None
        return {'pid': int(pid), 'started': started, 'pgid': os.getpgid(int(pid))}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def same_process(record):
    current = identity(record['pid'])
    return current is not None and all(current.get(k) == record.get(k) for k in ('pid', 'started', 'pgid'))


def terminate_owned(process, record, grace=1):
    """Terminate/reap only the still-matching process registered by this owner."""
    if process.poll() is not None: return True
    if not same_process(record) or record['pid'] == os.getpid(): return False
    try:
        if record['pgid'] == record['pid']:
            os.killpg(record['pgid'], signal.SIGTERM)
        else: process.terminate()
        try: process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            if not same_process(record): return process.poll() is not None
            if record['pgid'] == record['pid']: os.killpg(record['pgid'], signal.SIGKILL)
            else: process.kill()
            process.wait(timeout=grace)
        return process.poll() is not None
    except (OSError, subprocess.TimeoutExpired):
        return process.poll() is not None


@contextlib.contextmanager
def activate(recorder, task=None):
    token = _scope.set((recorder, task))
    try: yield
    finally: _scope.reset(token)


def current():
    return _scope.get()


def request_cancel(directory, task=None):
    directory = Path(directory).resolve()
    status = json.loads((directory/'execution-status.json').read_text())
    if task is not None and task not in status['tasks']:
        raise ValueError('Unknown task in this run')
    name = 'stop.json' if task is None else hashlib.sha256(task.encode()).hexdigest()+'.json'
    path = directory/'control'/name
    request = {'run_id': status['run_id'], 'task': task, 'requested_at_utc': now()}
    if path.exists():
        prior = json.loads(path.read_text())
        if prior['run_id'] == request['run_id'] and prior['task'] == task: return prior
        raise ValueError('Preserve cancellation from a different run')
    atomic(path, request)
    return request


def inspect(directory):
    value = json.loads((Path(directory)/'execution-status.json').read_text())
    value['inspection'] = {'at_utc': now(), 'controller_identity_matches': same_process(value['controller']),
        'residual_owned_processes': [p for p in value['processes'].values() if p['state']=='ACTIVE' and same_process(p)]}
    if value['controller']['state'] == 'RUNNING' and not value['inspection']['controller_identity_matches']:
        value['inspection']['state'] = 'STALE_UNKNOWN_CLEANUP'
    elif value['controller']['state']=='RUNNING':
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(value['controller_heartbeat_at_utc'])).total_seconds()
        if age>15:value['inspection']['state']='STALE_HEARTBEAT'
    return value


class Recorder:
    def __init__(self, root, case_id, configuration, *, phase='proof'):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root/'execution-status.json'
        if self.path.exists(): raise ValueError('Preserve the existing run; use a new output directory')
        self.lock = threading.RLock(); self.done = threading.Event(); self.dirty = True
        self.started = time.monotonic(); self.last_write = 0.; self._heartbeat = 0.
        self._cancel_all = threading.Event(); self._cancel_tasks = set(); self._control_seen = set()
        self._handles = {}; self._requests = set(); self._covered = set(); self._responses = {}
        self._usage_errors = []; self._signals = {}; self._locals = threading.local()
        owner = identity(os.getpid())
        if owner is None: raise RuntimeError('Cannot establish controller process identity')
        self.state = {'schema_version': 'yui-execution-1', 'case_id': case_id, 'run_id': str(uuid.uuid4()),
            'updated_at_utc': now(), 'controller_heartbeat_at_utc': now(),
            'controller': {**owner, 'ppid': os.getppid(), 'state': 'RUNNING'}, 'phase': phase,
            'bindings': {}, 'model': {'id':'gpt-6-luna','effort':'high','speed':'standard'},
            'concurrency': {**configuration, 'active_model_stages':0,'observed_peak_model_stages':0},
            'tasks': {}, 'processes': {}, 'usage': {},
            'cancellation': {'requests':[], 'cleanup':'NOT_REQUESTED'}, 'result': {'status':'RUNNING'}}
        self.owner_lock = self.root/'.execution-owner.lock'
        fd = os.open(self.owner_lock, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle: json.dump({'run_id': self.state['run_id'], **owner}, handle)
        self.flush(force=True)
        self.thread = threading.Thread(target=self._loop, daemon=True); self.thread.start()

    def _loop(self):
        while not self.done.wait(.1):
            self.poll_control()
            self.flush()

    def poll_control(self):
        for path in (self.root/'control').glob('*.json'):
            if path.name in self._control_seen: continue
            try: value = json.loads(path.read_text())
            except (OSError, ValueError): continue
            if value.get('run_id') != self.state['run_id']: continue
            task = value.get('task')
            with self.lock:
                if path.name in self._control_seen:continue
                if task is not None and task not in self.state['tasks']: continue
                self._control_seen.add(path.name)
                if task is None: self._cancel_all.set()
                else: self._cancel_tasks.add(task)
                self.state['cancellation']['requests'].append(value)
                self.state['cancellation']['cleanup'] = 'REQUESTED'
                for key,row in self.state['tasks'].items():
                    if (task is None or key==task) and row['state'] in {'PENDING','RUNNING'}:
                        row['state']='CANCEL_REQUESTED'
                self.dirty = True
            self.flush(force=True)

    def cancelled(self, task=None):
        self.poll_control()
        return self._cancel_all.is_set() or task in self._cancel_tasks

    def check(self, task=None):
        if self.cancelled(task): raise Cancelled('External cancellation requested for this run/task')

    def update(self, **values):
        with self.lock: self.state.update(values); self.dirty = True

    def task(self, key, **values):
        with self.lock:
            row = self.state['tasks'].setdefault(key, {'id':key,'state':'PENDING','queued_at_utc':now(),
                'attempt_id':self.state['run_id']+':'+key})
            row.update(values); self.dirty = True

    def activity(self, key, activity):
        if key is not None: self.task(key, activity=activity, last_activity_at_utc=now())

    def model_slot(self, delta):
        with self.lock:
            c = self.state['concurrency']; c['active_model_stages'] += delta
            c['observed_peak_model_stages'] = max(c['observed_peak_model_stages'],c['active_model_stages'])
            self.dirty = True

    def register_process(self, process, kind, task=None):
        record = identity(process.pid)
        if record is None:
            if process.poll() is None:raise RuntimeError('Cannot establish child process ownership')
            record={'pid':process.pid,'started':None,'pgid':None}
        key = str(process.pid)
        with self.lock:
            self._handles[key] = process
            self.state['processes'][key] = {**record,'kind':kind,'task':task,'state':'ACTIVE' if process.poll() is None else 'EXITED',
                'run_id':self.state['run_id'],'registered_at_utc':now()}
            self.dirty = True
        return record

    def process_finished(self, process):
        with self.lock:
            row = self.state['processes'].get(str(process.pid))
            if row and process.poll() is not None:
                row.update(state='EXITED',exit_code=process.returncode,finished_at_utc=now()); self.dirty=True

    def stop_process(self, process):
        with self.lock: record = dict(self.state['processes'][str(process.pid)])
        confirmed = terminate_owned(process, record)
        self.process_finished(process)
        return confirmed

    def request_started(self, stage, number):
        with self.lock: self._requests.add((stage,number)); self.dirty=True

    def model_event(self, task, stage, number, event):
        if task: self.activity(task,'MODEL_RUNNING')
        if event.get('type') not in {'response.completed','response.incomplete','response.failed'}:return
        response = event.get('response') or {}
        if isinstance(response,dict):
            with self.lock:
                model=self.state['model']
                for field,value in [('observed_model_ids',response.get('model')),('observed_service_tiers',response.get('service_tier'))]:
                    if value is not None:model[field]=sorted(set(model.get(field,[]))|{value})
        if not isinstance(response,dict) or not isinstance(response.get('usage'),dict): return
        try:
            counts = normalize(response['usage']); rid = response['id']
        except (ValueError, KeyError):
            with self.lock: self._usage_errors.append('Invalid provider usage'); self.dirty=True
            return
        with self.lock:
            if rid in self._responses and self._responses[rid] != counts:
                self._usage_errors.append('Conflicting provider usage: '+rid)
            self._responses[rid] = counts; self._covered.add((stage,number))
            self.state['usage']['usage_last_observed_at_utc'] = now(); self.dirty=True

    def lean_started(self, task, file):
        check_id=uuid.uuid4().hex
        row={'check_id':check_id,'state':'CHECKING','started_at_utc':now(),
            'source_sha256':hashlib.sha256(Path(file).read_bytes()).hexdigest(),
            'log_path':str(self.root/'native-checks'/(check_id+'.json'))}
        if task:self.task(task,current_lean_check=row,activity='LEAN_CHECKING')
        else:self.update(current_lean_check=row)
        return row

    def lean_finished(self, task, check, result):
        atomic(check['log_path'],result)
        summary={**check,'state':'FINISHED','finished_at_utc':now(),
            **{k:result.get(k) for k in ['exit_code','wall_seconds','cancelled']}}
        if task:self.task(task,current_lean_check=None,latest_lean_check=summary,activity='CONTROLLER_CHECK')
        else:self.update(current_lean_check=None,latest_lean_check=summary)

    def flush(self, force=False):
        with self.lock:
            mono=time.monotonic(); heartbeat=mono-self._heartbeat>=5
            if not force and (mono-self.last_write<1 or not (self.dirty or heartbeat)): return
            if heartbeat:
                self.state['controller_heartbeat_at_utc']=now();self._heartbeat=mono
            totals=None
            if self._responses:
                totals={k:sum(x[k] for x in self._responses.values()) if all(x[k] is not None for x in self._responses.values()) else None
                    for k in next(iter(self._responses.values()))}
            complete=(self.done.is_set() and bool(self._requests) and self._requests<=self._covered and not self._usage_errors)
            self.state['usage'].update(status='COMPLETE' if complete else 'PARTIAL' if self._responses else 'UNKNOWN',
                confirmed_tokens=totals,requests=len(self._requests),requests_with_usage=len(self._requests & self._covered),
                in_flight_or_unreported_requests=len(self._requests-self._covered),errors=list(self._usage_errors))
            self.state['counts']={s:sum(t['state']==s for t in self.state['tasks'].values())
                for s in ['PENDING','RUNNING','LOCAL_CHECKED','UNFINISHED','BLOCKED','CANCEL_REQUESTED','CANCELLED','FINISHED']}
            self.state['updated_at_utc']=now();self.state['elapsed_seconds']=mono-self.started
            atomic(self.path,self.state);self.last_write=mono;self.dirty=False

    @contextlib.contextmanager
    def signals(self):
        if threading.current_thread() is not threading.main_thread():
            yield; return
        def stop(signum, frame): request_cancel(self.root)
        previous={s:signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM)}
        for s in previous:signal.signal(s,stop)
        try:yield
        finally:
            for s,handler in previous.items():signal.signal(s,handler)

    def close(self, status, **result):
        self.done.set();self.thread.join(timeout=2)
        residual=[]
        for key,process in list(self._handles.items()):
            if process.poll() is None and not self.stop_process(process):residual.append(int(key))
            self.process_finished(process)
        with self.lock:
            ledgers={row['usage_ledger'] for row in self.state['tasks'].values() if row.get('usage_ledger')}
            actual={};missing=[]
            for path in sorted(ledgers):
                ledger=Path(path).with_name('usage-ledger.jsonl')
                if not ledger.is_file():missing.append(path);continue
                for line in ledger.read_text().splitlines():
                    row=json.loads(line);actual[row['response_id']]=row['usage']
            if ledgers:
                matches=actual==self._responses and not missing
                self.state['usage']['final_ledger_reconciliation']={'status':'MATCHED' if matches else 'INCOMPLETE_OR_MISMATCH',
                    'stage_usage_files':sorted(ledgers),'missing_ledgers':missing}
                if not matches:self._usage_errors.append('Final ledger reconciliation incomplete/mismatched')
            self.state['controller']['state']='FINALIZED'
            self.state['result']={'status':status,**result}
            self.state['cancellation'].update(residual_owned_processes=residual,
                cleanup='UNKNOWN' if residual else 'CONFIRMED_NO_OWNED_PROCESSES')
        self.flush(force=True)
        self.owner_lock.unlink(missing_ok=True)
