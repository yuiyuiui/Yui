"""Local fault treatment and operator controls, independent of model availability.

Neither a fault nor exhausted retries authorize workflow termination or cleanup.
Only an explicit cancel or the actual acceptance/finalization boundary does.
"""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid

import execution_state as execution
import remote_retry


VERSION = 'yui-fault-lifecycle-1'
BLOCKERS = {'SUBSTANTIVE_GAP','SUSPECTED_GAP','SOURCE_UNAVAILABLE','MISSING_SOURCE_STATEMENT',
    'INPUT_CONFLICT','SOURCE_CHANGE_REQUIRES_USER','AUDIT_A_NONPASS','MATHEMATICAL_REVIEW_FAILED',
    'REVIEW_UNVERIFIED','REVIEW_INCOMPLETE','PROOF_REPAIR_STALLED','REPAIR_UNCHANGED','REPAIR_CYCLE',
    'FINAL_FIDELITY_NOT_ACCEPTED','FROZEN_INTERFACE_REQUIRES_USER','INTERNAL_INTERFACE_REPAIR_REQUIRED','PROOF_REVIEW_REQUIRED',
    'INTERFACE_REVIEW_FAILED','BASIS_SEMANTIC_NONPASS','BASIS_REVISION_REQUIRED'}
SECRET = re.compile(r'(Bearer\s+)[^\s\"\']+|\bsk-[A-Za-z0-9_-]+|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', re.I)


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if any(w in re.sub('[^a-z0-9]','',k.lower()) for w in
                ('authorization', 'accesstoken', 'refreshtoken', 'idtoken', 'apikey', 'cookie'))
                else redact(v) for k, v in value.items()}
    if isinstance(value, list):return [redact(v) for v in value]
    if isinstance(value, str):return SECRET.sub('[REDACTED]', value)
    return value


def run_root(logs):
    logs = Path(logs).resolve()
    return next((p for p in (logs, *logs.parents) if (p/'.yui-run.json').is_file()), logs)


def outcome_error(result):
    deadline=result.get('status')=='UNFINISHED' and result.get('stop_reason')=='CASE_DEADLINE'
    code='workflow_blocked' if deadline or result.get('status') in BLOCKERS or result.get('status')=='BLOCKED' else 'harness_bug'
    if result.get('execution_fault'):code='harness_bug'
    return {'code':code,'message':result.get('error') or result.get('task_outcome') or result.get('status'),
            'outcome':result}


def case_deadline_error(error):
    return (isinstance(error,dict) and isinstance(error.get('outcome'),dict)
            and error['outcome'].get('stop_reason')=='CASE_DEADLINE')


def capture_owner(root):
    """Owner-only routing; never add the foreground task to mathematical input."""
    thread = os.environ.get('YUI_OWNER_THREAD_ID') or os.environ.get('CODEX_THREAD_ID')
    execution.atomic(Path(root)/'owner-context.json', {'version': VERSION, 'thread_id': thread})


def validate_context(root, binding, required=False):
    root=Path(root).resolve();job=root/'job.json';marker=root/'.yui-run.json'
    if required or job.is_file() or marker.is_file():
        if job.is_symlink() or marker.is_symlink() or not job.is_file() or not marker.is_file():
            raise ValueError('The paused run lost its unchanged ownership/job metadata')
        if (not binding or binding.get('path')!=str(job)
                or hashlib.sha256(job.read_bytes()).hexdigest()!=binding.get('sha256')):
            raise ValueError('The paused job binding changed; no profile/input replacement is allowed')
        import jobs
        jobs.validate(json.loads(job.read_text()))


def verify_basis_choice(checkpoint):
    from controller_common import verify_bindings
    bindings=[checkpoint['basis']]
    if 'semantic_review' in checkpoint:bindings.append(checkpoint['semantic_review'])
    verify_bindings(bindings)


def queue_notification(thread, message):
    if not thread:return {'status': 'PENDING', 'reason': 'No owner task ID; use YUI_OWNER_THREAD_ID at dispatch'}
    binary = os.environ.get('YUI_CODEX_BINARY') or os.environ.get('CODEX_CLI_PATH') or shutil.which('codex')
    if not binary:
        try:
            from runtime_config import load_lock
            binary = load_lock()['codex']['binary_path']
        except (OSError, ValueError, KeyError):pass
    if not binary:return {'status': 'PENDING', 'reason': 'No local Codex queue executable'}
    try:
        value = subprocess.run([str(binary), 'queue', '--thread', thread, '--message', message],
                               capture_output=True, text=True, timeout=15)
        return redact({'status': 'QUEUED' if value.returncode == 0 else 'PENDING',
                       'exit_code': value.returncode, 'stdout': value.stdout, 'stderr': value.stderr})
    except (OSError, subprocess.SubprocessError) as error:
        return {'status': 'PENDING', 'reason': redact(type(error).__name__+': '+str(error))}


class Gate:
    def __init__(self, logs, *, recorder=None, task=None, stage=None, notify=None, wait=None):
        self.logs = Path(logs).resolve();self.logs.mkdir(parents=True, exist_ok=True)
        self.root = run_root(self.logs);self.recorder = recorder;self.task = task
        self.stage = stage or task or self.logs.name
        self.notify = notify or queue_notification
        self.wait = wait or threading.Event().wait
        self.state = None;self.notification_attempts = 0
        self.resumed = []
        self.path = self.logs/'error-state.json'
        self.requires_job=(self.root/'.yui-run.json').is_file()
        self.job_binding=None
        try:
            path=self.root/'job.json'
            if path.is_file():self.job_binding={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        except OSError:pass

    def cancelled(self):
        return ((self.root/'cancel-request.json').is_file() or
                (self.recorder is not None and self.recorder.cancelled(self.task)))

    def check_cancel(self):
        if self.cancelled():
            if self.state:
                self.state.update(state='CANCELLED',cancelled_at_utc=execution.now())
                self.persist()
            raise execution.Cancelled('Explicit user cancellation while retaining an error checkpoint')

    def persist(self):
        try:
            execution.atomic(self.path, self.state)
            execution.atomic(self.logs/'error-incidents'/(self.state['incident']+'.json'), self.state)
        except OSError as error:
            self.state['persistence_error'] = type(error).__name__+': '+str(error)
            # A full disk is itself a reason to retain the process, never to exit.

    def owner(self):
        path = self.root/'owner-context.json'
        try:return json.loads(path.read_text()).get('thread_id')
        except (OSError, ValueError):return os.environ.get('YUI_OWNER_THREAD_ID') or os.environ.get('CODEX_THREAD_ID')

    def report(self):
        """A persisted bounded outbox; no LLM, no repeated successful messages."""
        if self.state.get('notification', {}).get('status') == 'QUEUED':return
        for receipt in self.state.get('checkpoint',{}).get('source_issue_notices',[]):
            try:
                path=Path(receipt['path'])
                if (path.is_relative_to(self.root/'source-issues') and
                    hashlib.sha256(path.read_bytes()).hexdigest()==receipt['sha256'] and
                    json.loads(path.read_text())['notification']['status']=='QUEUED'):
                    self.state['notification']={'status':'QUEUED','earlier_source_notice':receipt}
                    self.persist();return
            except (OSError,ValueError,KeyError):pass
        if self.notification_attempts >= 3:return
        self.notification_attempts += 1
        text = ('[Yui ERROR PAUSED] '+self.state['fault']['category']+'; stage='+self.stage+
                '; HTTP='+str(self.state['fault']['http_statuses'])+
                '; automatic retries='+str(self.state['retries'])+'.\n'
                'Task is paused, not finished. Existing drafts, checkpoints and owned temporary resources are preserved; no automatic cleanup.\n'
                'Run: '+str(self.root)+'\nFull diagnostic: '+str(self.path)+'\n'
                'Controller logs: '+str(self.logs)+
                ('\nResume: '+shlex.join(self.state['resume_command']) if self.state['resumable'] else
                 '\nAutomatic resume is unavailable; inspect the diagnostic and choose an authorized repair or user action.')+
                '\nCancel: '+shlex.join(self.state['cancel_command'])+
                '\nThis is a fixed local Python alert; no model response is required.')
        details=self.state.get('error',{})
        if isinstance(details,dict) and details.get('reason')=='REVIEW_NO_PROGRESS' and 'last_validation' in details:
            text += ('\nReview waiting for correction: '+details['message']+
                     '\nLatest feedback: '+' '.join(details['last_validation']['message'].split())[:400]+
                     '\nSaved judgments: '+details['progress'])
        if self.stage=='basis-decision' and self.state['checkpoint'].get('semantic_review'):
            checkpoint=self.state['checkpoint']
            text+='\nReviewed residual premises '+', '.join(checkpoint['residual_class4'])+' in '+checkpoint['basis']['path']
            text+='\nStatement/type/source review: '+checkpoint['semantic_review']['path']
        if self.state.get('decisions'):
            text+='\nExplicit user choices:\n'+'\n'.join(shlex.join(cmd) for cmd in self.state['decisions'].values())
        if case_deadline_error(self.state.get('error')):
            text+='\nThe explicit whole-case budget is exhausted. Ordinary resume cannot extend it; preserve this checkpoint or explicitly cancel. Any continuation needs a separately authorized budget and supported checkpoint.'
        try:result = self.notify(self.owner(), text)
        except Exception as error:result = {'status':'PENDING', 'reason':redact(str(error))}
        self.state['notification'] = {**result, 'attempts':self.notification_attempts, 'at_utc':execution.now()}
        self.persist()

    def pause(self, error, *, retries=0, resumable=True, checkpoint=None, decisions=()):
        """Block locally until an exact-incident resume or explicit cancellation."""
        incident = uuid.uuid4().hex
        details = ({'exception_type':type(error).__name__, 'message':str(error),
                    'traceback':''.join(traceback.format_exception(error))}
                   if isinstance(error, BaseException) else error)
        entry = Path(__file__).with_name('yui.py')
        self.state = {'version':VERSION, 'incident':incident, 'state':'PAUSED_ERROR',
            'stage':self.stage, 'root':str(self.root), 'logs':str(self.logs),
            'owner_process':execution.identity(os.getpid()), 'at_utc':execution.now(),
            'fault':remote_retry.diagnose(error), 'error':redact(details), 'retries':retries,
            'resumable':resumable, 'checkpoint':redact(checkpoint or {}),
            'requires_job_binding':self.requires_job, 'job_binding':self.job_binding,
            'cleanup_authorized':False, 'notification':{'status':'PENDING'},
            'resume_command':[sys.executable, '-B', str(entry), 'resume-error', str(self.root), '--incident', incident],
            'cancel_command':[sys.executable, '-B', str(entry), 'cancel', str(self.root)]}
        if self.stage=='source-material':
            self.state['resume_command']=[sys.executable,'-B',str(entry),'supply-material',str(self.root),'--incident',incident,'--file','<attached-file>']
        if decisions:
            basis_choices=set(decisions)=={'stop','continue','accept-conditional'} and self.stage=='basis-decision'
            if resumable or not (basis_choices or set(decisions)=={'deliver-actual','recheck','reset-translation'}):
                raise ValueError('Only explicit B-final or basis user decisions are supported')
            command='basis-decision' if basis_choices else 'final-decision'
            self.state['decisions']={action:[sys.executable,'-B',str(entry),command,str(self.root),
                '--incident',incident,'--action',action] for action in decisions}
            self.state['resume_command']=[sys.executable,'-B',str(entry),'errors',str(self.root)]
        self.notification_attempts = 0
        self.persist();self.check_cancel();self.report()
        if self.recorder is not None:
            if self.task:self.recorder.task(self.task, state='PAUSED_ERROR', activity='PAUSED_ERROR', error_state=str(self.path))
            self.recorder.flush(force=True)
        outbox_due = time.monotonic()+60
        seen_controls=set()
        while True:
            self.check_cancel()
            if self.stage in {'basis-decision','source-material'} and self.recorder is not None:
                try:self.recorder.check()
                except execution.CaseDeadlineExceeded:
                    self.state.update(state='EXPIRED',expired_at_utc=execution.now())
                    self.persist()
                    raise
            control = self.logs/'error-control'/(incident+'.json')
            try:request = json.loads(control.read_text()) if control.is_file() else {}
            except (OSError, ValueError):request = {}
            if request.get('incident')==incident and request.get('action') in decisions:
                validate_context(self.root,self.job_binding,self.requires_job)
                if self.stage=='basis-decision':
                    verify_basis_choice(self.state['checkpoint'])
                self.state.update(state='USER_DECIDED',control=request,decided_at_utc=execution.now())
                self.persist()
                if self.recorder is not None and self.task:
                    self.recorder.task(self.task,state='RUNNING',activity='USER_DECIDED')
                    self.recorder.flush(force=True)
                return self.state
            if request.get('incident') == incident and request.get('action') == 'resume' and resumable:
                key=request.get('id') or json.dumps(request,sort_keys=True)
                if key in seen_controls:
                    self.wait(1);continue
                seen_controls.add(key)
                try:
                    validate_context(self.root,self.job_binding,self.requires_job)
                    if self.stage=='source-material':
                        from material_exchange import received
                        received(self.logs,incident,self.job_binding)
                except (OSError,ValueError,KeyError) as error:
                    self.state['resume_rejected']=redact(str(error));self.persist()
                    self.wait(1);continue
                self.state.update(state='RESUMED', resumed_at_utc=execution.now(), control=request)
                self.persist()
                path=self.logs/'error-incidents'/(incident+'.json')
                if path.is_file():
                    import hashlib
                    self.resumed.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
                if self.recorder is not None and self.task:
                    self.recorder.task(self.task, state='RUNNING', activity='ERROR_RESUMED')
                    self.recorder.flush(force=True)
                return self.state
            if request and not resumable:
                self.state['resume_rejected'] = 'Verified software repair and an explicit supported checkpoint are required; no blind phase replay'
                self.persist()
            if time.monotonic() >= outbox_due:
                self.report();outbox_due = time.monotonic()+60
            self.wait(1)


def gate_for(stage):
    gate = getattr(stage, '_fault_gate', None)
    if gate is None:
        gate = Gate(stage.logs, recorder=getattr(stage, 'execution', None),
                    task=getattr(stage, 'execution_task', None), stage=getattr(stage, 'mode', None))
        stage._fault_gate = gate
    return gate


def pending(root):
    """Read only error metadata; never traverse runtime snapshots or arguments."""
    rows=[]
    for directory, children, files in os.walk(Path(root).resolve()):
        children[:] = [n for n in children if n not in {'runtime','harness-snapshot','.git'}]
        if 'error-state.json' not in files:continue
        path=Path(directory)/'error-state.json'
        try:value=json.loads(path.read_text())
        except (OSError, ValueError):continue
        if value.get('state')=='PAUSED_ERROR':rows.append({**value, 'path':str(path)})
    return rows


def resume(root, incident):
    matches=[row for row in pending(root) if row['incident']==incident]
    if len(matches)!=1:raise ValueError('Select exactly one current paused incident from errors RUN')
    row=matches[0]
    root=Path(root).resolve()
    if Path(row['root']).resolve()!=root or not Path(row['logs']).resolve().is_relative_to(root):
        raise ValueError('Error checkpoint escapes its explicitly selected run')
    if row.get('stage')=='source-material':
        raise ValueError('Use supply-material with the received attachment for this incident')
    if not row.get('resumable'):
        if case_deadline_error(row.get('error')):
            raise ValueError('The whole-case budget is exhausted; ordinary resume cannot extend it')
        raise ValueError('This checkpoint needs an explicit supported user action or verified repair; automatic phase replay is unsupported')
    if not row.get('owner_process') or not execution.same_process(row['owner_process']):
        raise ValueError('Paused owner process has exited or changed; do not silently start a new attempt')
    validate_context(root,row.get('job_binding'),row.get('requires_job_binding',False))
    path=Path(row['logs'])/'error-control'/(incident+'.json')
    execution.atomic(path, {'incident':incident, 'action':'resume', 'requested_at_utc':execution.now(), 'id':uuid.uuid4().hex})
    return {'status':'RESUME_REQUESTED', 'incident':incident, 'root':str(root)}


def final_decision(root,incident,action):
    """Request one human-selected B-final action; never decides mathematical truth."""
    root=Path(root).resolve();matches=[r for r in pending(root) if r['incident']==incident]
    if len(matches)!=1:raise ValueError('Select exactly one current B-final incident')
    row=matches[0]
    if action not in row.get('decisions',{}) or Path(row['root']).resolve()!=root:
        raise ValueError('This checkpoint does not authorize that final decision')
    logs=Path(row['logs']).resolve()
    if not logs.is_relative_to(root) or not execution.same_process(row.get('owner_process',{})):
        raise ValueError('Final decision owner has exited or changed')
    validate_context(root,row.get('job_binding'),row.get('requires_job_binding',False))
    if row.get('stage')=='basis-decision':
        verify_basis_choice(row['checkpoint'])
    path=logs/'error-control'/(incident+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    request={'incident':incident,'action':action,'requested_at_utc':execution.now(),'id':uuid.uuid4().hex}
    temporary=path.with_name('.decision-'+request['id']+'.tmp')
    try:
        temporary.write_text(json.dumps(request)+'\n')
        # Publish complete bytes once. Simultaneous stop/continue must never replace a winner.
        try:os.link(temporary,path)
        except FileExistsError as error:
            raise ValueError('A decision was already requested for this incident') from error
    finally:temporary.unlink(missing_ok=True)
    return {'status':'USER_DECISION_REQUESTED','incident':incident,'action':action,'root':str(root)}


def cancel_paused(root):
    root=Path(root).resolve();rows=pending(root)
    if not rows or any(Path(row['root'])!=root or not row.get('owner_process')
                       or not execution.same_process(row['owner_process']) for row in rows):
        raise ValueError('No matching live owned error checkpoint at the selected path')
    execution.atomic(root/'cancel-request.json',{'external_cancel':True,'id':uuid.uuid4().hex,
        'requested_at_utc':execution.now()})
    return {'status':'CANCEL_REQUESTED','runs':[str(root)]}
