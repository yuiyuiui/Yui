#!/usr/bin/env python3
"""Isolated native Codex sessions managed through official stdio interfaces.

Codex owns model networking and context management. Dynamic
tools expose only the task, the pinned mathlib, and a sandboxed Lean checker.
No API keys, bearer tokens, or authorization headers are written into logs.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from pilot_common import transport_sandbox_profile
from runtime_config import model_profile
import remote_retry
from execution_state import CaseDeadlineExceeded, Cancelled

REMOTE_RETRY_POLICY = remote_retry.POLICY

MODEL = model_profile()['id']
# Give an executing native tool batch time to return its diagnostics on a protective stop.
REVIEW_FEEDBACK_DRAIN_SECONDS = 5


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append(path: Path, item: dict) -> None:
    with path.open('a') as f:
        f.write(json.dumps({'timestamp_utc': now(), **item}, ensure_ascii=False) + '\n')


def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {'type': 'function', 'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': properties, 'required': required,
                            'additionalProperties': False}}


CONTINUE_PROMPT = ('The requested artifact has not passed submission. '
                   'Continue with the same inputs and tools; preserve the fixed specification.')


def system_https_proxy() -> tuple[str, int] | None:
    config = subprocess.check_output(['/usr/sbin/scutil', '--proxy'], text=True)
    enabled = re.search(r'HTTPSEnable\s*:\s*(\d+)', config)
    host = re.search(r'HTTPSProxy\s*:\s*(\S+)', config)
    port = re.search(r'HTTPSPort\s*:\s*(\d+)', config)
    return (host[1], int(port[1])) if enabled and enabled[1] == '1' and host and port else None


TOOLS = [
    tool('search_mathlib', 'Search the selected Mathlib sources; at most 100 lines.',
         {'query': {'type': 'string'}}, ['query']),
    tool('read_mathlib', 'Read specified lines of a Mathlib source file.',
         {'path': {'type': 'string'}, 'start_line': {'type': 'integer'}, 'line_count': {'type': 'integer'}},
         ['path', 'start_line', 'line_count']),
]


class LocalProtocolRejection(PermissionError):
    """Deterministic own-history rejection, never a retryable network failure."""
    def __init__(self, reason, details=None):
        self.reason, self.details = reason, details or {}
        super().__init__('LOCAL_TOOL_FEEDBACK_REJECTED: ' + reason)


class NativeEventTimeout(TimeoutError):
    """The controller wait expired before the requested native event arrived."""


class NativeCarrier:
    """Shared native-session methods; concrete stages supply inputs and validators."""
    @property
    def model(self):
        return self.model_selection['id'] if hasattr(self, 'model_selection') else MODEL


    def lean_timeout(self) -> float | None:
        import lean_timeout_policy
        recorder = getattr(self,'execution',None)
        limit = (lean_timeout_policy.ceiling() if lean_timeout_policy.active.get() is not None
                 else __import__('runtime_config').configured_timeout('native'))
        case_left = recorder.remaining(limit) if recorder else limit
        if self.started is not None and self.timeout is not None:
            remaining = self.started + self.timeout - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('证明预算已耗尽，不再启动Lean检查。')
            return min(case_left, remaining) if case_left is not None else remaining
        return case_left

    def dispatch(self, name: str, args: dict) -> dict:
        """Serve the two source-reading tools shared by current stages."""
        started=time.monotonic()
        try:
            if name not in self.tool_names or self.phase!='proof':
                raise PermissionError('Tool is unavailable in this stage')
            from runtime_config import require_environment,load_lock
            require_environment()
            lock=load_lock();root=Path(lock['mathlib']['local_path'])
            if name=='search_mathlib':
                source=root/'Mathlib'
                found=subprocess.run([lock['tools']['ripgrep']['binary_path'],'--no-config','-n',
                    '--max-count','5','--glob','*.lean','--',args['query'],str(source)],
                    capture_output=True,text=True,
                    env={'PATH':'/usr/bin:/bin','HOME':str(self.work/'home'),'LANG':'en_US.UTF-8'})
                result={'matches':'\n'.join(found.stdout.replace(str(source)+'/', 'Mathlib/').splitlines()[:100])[:16000],
                        'exit_code':found.returncode,'stderr':found.stderr[-2000:]}
            elif name=='read_mathlib':
                path=(root/args['path']).resolve()
                if not path.is_relative_to(root/'Mathlib') or path.suffix!='.lean':
                    raise PermissionError('Only source files in the selected Mathlib are readable')
                start=max(1,int(args['start_line']));count=max(1,min(200,int(args['line_count'])))
                lines=path.read_text().splitlines()
                result={'path':str(path.relative_to(root)),'lines':'\n'.join(
                    f'{i+1}: {lines[i]}' for i in range(start-1,min(len(lines),start-1+count)))[:18000]}
            else:
                raise PermissionError('Tool is unavailable in this stage')
        except (CaseDeadlineExceeded,Cancelled):raise
        except Exception as error:
            result={'error':str(error),'error_type':type(error).__name__,'accepted':False,
                    'infrastructure_error':name=='search_mathlib' and isinstance(error,FileNotFoundError)}
        append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,
                                      'wall_seconds':time.monotonic()-started})
        return result


    def validate_tool_rpc(self, params):
        return __import__('native_client').validate_tool(self,params)

    def send(self, method: str, params: dict | None = None) -> int:
        self.rpc_id += 1
        msg = {'id': self.rpc_id, 'method': method, 'params': params or {}}
        if method == 'turn/start':
            self.active_turn_id = None
            self.pending_turn_start_id = self.rpc_id
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + '\n'); self.proc.stdin.flush()
        append(self.logs / 'client.jsonl', msg)
        return self.rpc_id

    def receive_until(self, predicate, deadline: float | None):
        while deadline is None or time.monotonic() < deadline:
            self.check_runtime_state()
            execution=getattr(self,'execution',None)
            if execution and not getattr(self,'_stopping',False):execution.check(self.execution_task)
            try: msg = self.inbox.get(timeout=1 if deadline is None else max(0, min(1, deadline - time.monotonic())))
            except queue.Empty:
                if self.proc.poll() is not None: raise RuntimeError('Codex 传输进程提前结束。')
                continue
            self.check_runtime_state()
            if not __import__('native_client').observe(self,msg):continue
            if msg.get('method') == 'turn/started':
                self.active_turn_id = msg.get('params', {}).get('turn', {}).get('id')
            if self.pending_turn_start_id is not None and msg.get('id') == self.pending_turn_start_id:
                self.pending_turn_start_id = None
                self.active_turn_id = msg.get('result', {}).get('turn', {}).get('id', self.active_turn_id)
            if msg.get('method') == 'turn/completed':
                turn_id=msg.get('params',{}).get('turn',{}).get('id')
                if not self.active_turn_id or turn_id==self.active_turn_id:
                    self.last_turn_event = msg
            if msg.get('method') == 'item/tool/call' and 'id' in msg:
                if ((getattr(self,'submission_closed',False) or getattr(self,'budget_exhausted',False)
                        or (getattr(self,'_stopping',False) and getattr(getattr(self,'review_guard',None),'blocked',None)))
                        and msg['params'].get('callId') not in self.tool_history
                        or getattr(self, '_stopping', False) and getattr(self,'native_infrastructure_fault',None)):
                    # A completed call can race with the protective interrupt.
                    # Do not execute it after deciding to preserve an unfinished attempt.
                    self.proc.stdin.write(json.dumps({'id': msg['id'], 'error': {
                        'code': -32800, 'message': 'Cancelled after a recorded protective output/protocol stop'}})+'\n')
                    self.proc.stdin.flush()
                    append(self.logs/'model-output-events.jsonl', {'event': 'LATE_TOOL_NOT_EXECUTED',
                        'tool': msg.get('params', {}).get('tool')})
                    continue
                params = msg['params']
                self.validate_tool_rpc(params)
                call_id=params['callId']
                if call_id in self.tool_history:
                    result=json.loads(json.dumps(self.tool_history[call_id]))
                    append(self.logs/'controller.jsonl',{'event':'exact_tool_result_redelivered',
                        'call_id':call_id,'tool':params['tool'],'dispatch_repeated':False})
                else:
                    try:result = self.dispatch(params['tool'], params['arguments'])
                    except CaseDeadlineExceeded:
                        self.budget_exhausted=True
                        self.proc.stdin.write(json.dumps({'id':msg['id'], 'error':{
                            'code':-32800,'message':'Explicit whole-case budget exhausted'}})+'\n')
                        self.proc.stdin.flush()
                        raise
                    self.completed_tool_calls=getattr(self,'completed_tool_calls',0)+1
                    if execution:execution.task(self.execution_task,completed_tool_calls=self.completed_tool_calls,
                        last_completed_tool=params['tool'],last_tool_completed_at_utc=now())
                if result.get('infrastructure_error') is True:
                    self.pause_error({'code':'harness_bug','message':'Local tool failed; no automatic tool replay',
                        'tool':params['tool'],'feedback':result},resumable=False)
                delivered = self.snapshot_tool_result(params['callId'],result)
                if (getattr(self,'stop_on_submission',False) and (self.accepted is not None or getattr(self,'repair_request',None))
                        and not getattr(self,'submission_completion',None)):
                    self.submission_closed=True
                    self.submission_completion={'at_utc':now(),'elapsed_seconds':time.monotonic()-self.started,
                        'tool':params['tool'],'call_id':params['callId'],
                        'scope':'Accepted stage artifact only; later mathematical gates remain required.'}
                    append(self.logs/'controller.jsonl',{'event':'stage_submission_completed',**self.submission_completion})
                    if not hasattr(self,'handoff_results'):self.handoff_results={}
                    self.handoff_results[call_id]={'call_id':call_id,'turn_id':self.active_turn_id,
                        'tool_result':json.loads(delivered),'confirmed':False}
                    # Cancel this submitted turn while the client is still awaiting
                    # its tool result. Sending the interrupt first prevents the
                    # successful result from launching an unnecessary model call.
                    # The artifact is already durable in the tool/controller logs.
                    if self.active_turn_id:
                        self.handoff_interrupt = self.send('turn/interrupt', {
                            'threadId':self.thread_id,'turnId':self.active_turn_id})
                response = {'id': msg['id'], 'result': {'success': 'error' not in result,
                    'contentItems': [{'type': 'inputText', 'text': delivered}]}}
                self.proc.stdin.write(json.dumps(response, ensure_ascii=False) + '\n'); self.proc.stdin.flush()
                delivered_at=now()
                append(self.logs/'request-lifecycle.jsonl',{'event':'TOOL_RESULT_DELIVERED',
                    'call_id':params['callId'],'tool':params['tool'],'at_utc':delivered_at,
                    'delivery_boundary':'actual tool response flushed to native carrier stdin'})
                if execution:
                    execution.task(self.execution_task,last_tool_result_at_utc=delivered_at,
                        activity='TOOL_RESULT_DELIVERED',
                        last_activity_at_utc=delivered_at)
            elif 'method' in msg and 'id' in msg:
                response = {'id': msg['id'], 'error': {'code': -32601, 'message': 'Not allowed by pilot harness'}}
                self.proc.stdin.write(json.dumps(response) + '\n'); self.proc.stdin.flush()
            if predicate(msg): return msg
        execution=getattr(self,'execution',None)
        if execution and not getattr(self,'_stopping',False):execution.check(self.execution_task)
        raise NativeEventTimeout('本轮达到预先设置的时间限制。')

    def snapshot_tool_result(self, call_id, result):
        """The provenance receipt is the immutable JSON value actually delivered."""
        delivered=json.dumps(result,ensure_ascii=False)
        self.tool_history[call_id]=json.loads(delivered)
        return delivered

    def check_runtime_state(self):
        reader_fault=getattr(self,'carrier_reader_fault',None)
        if reader_fault:raise RuntimeError('Local carrier message reader failed: '+json.dumps(reader_fault,ensure_ascii=False))
        if getattr(self,'_stopping',False) or getattr(self,'submission_closed',False):return
        fault=getattr(self,'native_infrastructure_fault',None)
        if fault:
            if not getattr(self,'native_fault_interrupt_attempted',False):
                self.native_fault_interrupt_attempted=True
                try:
                    self.interrupt_active_turn(reason='NATIVE_INFRASTRUCTURE_FAULT')
                    fault['current_generation_stop_confirmed']=True
                except Exception as error:
                    fault['current_generation_stop_confirmed']=False
                    fault['interrupt_error']=str(error)
            self.pause_error(fault,resumable=False)
        local=getattr(self,'local_protocol_fault',None)
        if local:raise LocalProtocolRejection(local['reason'],local.get('details'))

    def rpc(self, method: str, params: dict, seconds: float = 30) -> dict:
        rid = self.send(method, params)
        msg = self.receive_until(lambda m: m.get('id') == rid, time.monotonic() + seconds)
        if 'error' in msg: raise RuntimeError(json.dumps(msg['error'], ensure_ascii=False))
        return msg.get('result', {})

    def start_process(self) -> None:
        lock=__import__('runtime_config').host_tools()
        from native_runtime import for_stage
        for_stage(self.logs,lock['codex'])
        state=self.work/'state'
        for name in ('auth.json','models_cache.json'):
            source=__import__('runtime_config').auth_home()/name
            if source.is_file():shutil.copyfile(source,state/name);os.chmod(state/name,0o600)
        import native_client
        config=native_client.configuration(self)
        (state/'config.toml').write_text(config)
        (self.logs/'effective-config.toml').write_text(config)
        (self.logs/'native-client.json').write_text(json.dumps({
            'transport':native_client.TRANSPORT,'profile':self.model_selection,
            'config_sha256':hashlib.sha256(config.encode()).hexdigest(),
            'native_components':lock['codex'],
            'role_system_sha256':hashlib.sha256(self.system.encode()).hexdigest(),
            'retry_scope':'Python retries failed native work requests; native request/stream retries configured to zero.',
            'network_owner':'official Codex client; no Yui relay'},indent=2)+'\n')
        env={'PATH':'/usr/bin:/bin','HOME':str(self.work/'home'),'CODEX_HOME':str(state),
             'TMPDIR':str(self.work/'tmp'),'LANG':'en_US.UTF-8'}
        for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy'):
            if key in os.environ:env[key]=os.environ[key]
        command=[lock['codex']['binary_path'],'app-server','--stdio']
        profile=self.work/'transport.sb';profile.write_text(transport_sandbox_profile(self.work))
        shutil.copyfile(profile,self.logs/'transport-sandbox.sb')
        command=['/usr/bin/sandbox-exec','-f',str(profile)]+command
        with (self.logs/'transport-stderr.log').open('w') as error_log:
            self.proc=subprocess.Popen(command,cwd=self.work/'input',env=env,stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=error_log,text=True,bufsize=1,start_new_session=True)
        from run_resources import register_child
        self.process_owner=register_child(self.work,self.proc,'model-carrier',private_group=True)
        if getattr(self,'execution',None):
            self.process_owner=self.execution.register_process(self.proc,'model-carrier',self.execution_task,private_group=True)
        def reader():
            try:
                for line in self.proc.stdout:
                    msg=json.loads(line)
                    if not isinstance(msg,dict):raise ValueError('Native JSON RPC event must be an object')
                    append(self.logs/'events.jsonl',msg);self.inbox.put(msg)
                if not getattr(self,'_resources_released',False):raise EOFError('Native Codex stdout closed unexpectedly')
            except Exception as error:
                self.carrier_reader_fault={'code':'harness_bug','layer':'carrier_stdout',
                    'message':str(error),'exception_type':type(error).__name__}
                try:append(self.logs/'carrier-reader-errors.jsonl',self.carrier_reader_fault)
                except OSError as logging_error:self.carrier_reader_fault['evidence_error']=str(logging_error)
                self.inbox.put({'controller_reader_fault':True})
        self.reader_thread=threading.Thread(target=reader,daemon=True);self.reader_thread.start()
        self.rpc('initialize',{'clientInfo':{'name':'yui','version':self.harness_version},
                              'capabilities':{'experimentalApi':True}})
        self.proc.stdin.write(json.dumps({'method':'initialized'})+'\n');self.proc.stdin.flush()

    def wait_work_turn(self, review_guard, deadline):
        def finished(msg):
            return (getattr(self, 'submission_closed', False) or
                    (msg.get('method') == 'turn/completed' and
                     (not self.active_turn_id or msg.get('params', {}).get('turn', {}).get('id') == self.active_turn_id)))

        while True:
            event = self.receive_until(lambda msg: finished(msg) or (review_guard and review_guard.blocked), deadline)
            if finished(event) or not review_guard or not review_guard.blocked:
                return event
            # An inner RPC reply has been flushed. Code Mode still has to assemble the
            # outer result, possibly from several parallel checks. A corrected sibling
            # in that batch can also clear the stall or explicitly submit the review.
            pending = {call for call, row in getattr(self, 'native_code_calls', {}).items()
                       if call and row['turn_id'] == self.active_turn_id and not row.get('output_received')}
            if not pending:
                call = event.get('params', {}).get('callId')
                if not call:
                    return event
                pending.add(call)  # Direct dynamic tool, without a Code Mode wrapper.

            def delivered(msg):
                if msg.get('method') == 'rawResponseItem/completed':
                    params = msg['params']
                    item = params['item']
                    if (params.get('turnId') == self.active_turn_id and
                            item.get('type') in {'custom_tool_call_output', 'function_call_output'}):
                        pending.discard(item.get('call_id'))
                return not pending or finished(msg) or not review_guard.blocked

            drain_deadline = time.monotonic() + REVIEW_FEEDBACK_DRAIN_SECONDS
            try:
                event = self.receive_until(delivered, min(deadline, drain_deadline) if deadline is not None else drain_deadline)
            except NativeEventTimeout:
                if time.monotonic() < drain_deadline or (deadline is not None and time.monotonic() >= deadline):
                    raise
                append(self.logs/'controller.jsonl', {'event':'review_feedback_drain_timeout',
                       'turn_id':self.active_turn_id, 'pending_call_ids':sorted(pending)})
            else:
                if not pending:
                    self.check_runtime_state()
                    if review_guard.blocked and self.active_turn_id and not finished(event):
                        self.handoff_interrupt = self.send('turn/interrupt', {
                            'threadId':self.thread_id, 'turnId':self.active_turn_id})
                    append(self.logs/'controller.jsonl', {'event':'review_feedback_returned',
                           'turn_id':self.active_turn_id, 'call_id':event['params']['item']['call_id']})
            if finished(event) or review_guard.blocked:
                return event

    def solve_turns(self, user: str) -> dict:
        """Continue in the same isolated history; no deadline unless requested."""
        self.allowed_user_messages.add(user)
        self.initial_user_message = user
        self.started = time.monotonic()
        deadline = self.started + self.timeout if self.timeout is not None else None
        message = user
        continuation_prompt = getattr(self, 'continuation_prompt', CONTINUE_PROMPT)
        __import__('native_client').bind_inputs(self,user,continuation_prompt)
        self.remote_retry_count=0
        incident_retries=0
        review_guard = getattr(self, 'review_guard', None)
        while True:
            self.check_runtime_state()
            with self.request_lock:
                self.native_turn_generation+=1
                generation=self.native_turn_generation
            self.api_calls=getattr(self,'api_calls',0)+1
            self.last_native_error=None
            started = self.rpc('turn/start', {'threadId': self.thread_id, 'model': self.model, 'effort': getattr(self, 'model_selection', {}).get('reasoning_effort', 'high'),
                'input': [{'type': 'text', 'text': message}], 'environments': [],'serviceTierForTurn':'default'},
                seconds=30 if deadline is None else min(30, max(0.001, deadline - time.monotonic())))
            self.active_turn_id = started.get('turn', {}).get('id')
            done = self.wait_work_turn(review_guard, deadline)
            if getattr(self,'submission_closed',False):
                self.interrupt_active_turn(reason=getattr(self,'stage_close_reason','ACCEPTED_ARTIFACT'))
                event=self.last_turn_event or done
                self.turn_results.append(event)
                if getattr(self,'carrier_reader_fault',None):raise RuntimeError('Native reader failed during handoff')
                return event
            if review_guard and review_guard.blocked and done.get('method') != 'turn/completed':
                self.interrupt_active_turn(reason='REVIEW_NO_PROGRESS')
                done = self.last_turn_event
            self.turn_results.append(done)
            if review_guard and review_guard.blocked:
                self.pause_error(review_guard.blocked)
                review_guard.resume()
                message = continuation_prompt
                self.allowed_user_messages.add(message)
                continue
            turn = done.get('params', {}).get('turn', {})
            with self.request_lock:
                success=self.last_response_success
            if success and success['turn_generation']==generation and success['request_number']>0:
                if incident_retries:
                    append(self.logs/'remote-retries.jsonl',{'event':'remote_service_retry_streak_reset',
                        **success,'previous_incident_retries':incident_retries,'retry_number':self.remote_retry_count})
                incident_retries=0
                self.remote_incident_retries=0
            if turn.get('status') != 'completed':
                fault=__import__('native_client').fault(turn.get('error') or self.last_native_error)
                reason=remote_retry.classify(fault)
                if (reason and not getattr(self,'local_protocol_fault',None)
                        and not (self.logs/'isolation-violations.jsonl').exists()):
                    if incident_retries < REMOTE_RETRY_POLICY['maximum_attempts']:
                        incident_retries+=1;self.remote_retry_count+=1
                        self.remote_incident_retries=incident_retries
                        wait=remote_retry.delay(incident_retries)
                        self.wait_remote_retry(wait,reason,turn,deadline)
                    else:
                        self.pause_error(fault,retries=incident_retries)
                        incident_retries=0
                    self.allowed_user_messages.add(continuation_prompt)
                    message=continuation_prompt
                    continue
                fault=fault or {'code':'unknown','message':'Model turn ended without completion'}
                local=bool(getattr(self,'local_protocol_fault',None))
                if local:fault={'code':'harness_bug','cause':fault,'message':'A local protocol/provenance fault requires verified repair'}
                self.pause_error(fault,retries=incident_retries,resumable=not local)
                incident_retries=0
                self.allowed_user_messages.add(continuation_prompt);message=continuation_prompt
                continue
            incident_retries=0
            if self.accepted:
                return done
            hook=getattr(self,'after_unaccepted_turn',None)
            if hook and hook():
                append(self.logs/'controller.jsonl',{'event':'unaccepted_turn_routed_to_diagnosis',
                    'previous_turn_id':turn.get('id'),'elapsed_seconds':time.monotonic()-self.started})
                return done
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('本轮达到预先设置的时间限制。')
            if review_guard:
                review_guard.completed_turn()
                if review_guard.blocked:
                    self.pause_error(review_guard.blocked)
                    review_guard.resume()
            self.continuation_count += 1
            if getattr(self,'execution',None):
                self.execution.task(self.execution_task,continuations=self.continuation_count)
            append(self.logs / 'controller.jsonl', {'event': 'continue_after_unaccepted_turn',
                'continuation_number': self.continuation_count,
                'previous_turn_id': turn.get('id'), 'prompt': continuation_prompt,
                'elapsed_seconds': time.monotonic() - self.started})
            self.allowed_user_messages.add(continuation_prompt)
            message = continuation_prompt

    def pause_error(self,error,*,retries=0,resumable=True):
        from fault_control import gate_for
        gate=gate_for(self)
        gate.pause(error,retries=retries,resumable=resumable,
            checkpoint={'thread_id':getattr(self,'thread_id',None),'turn_id':getattr(self,'active_turn_id',None),
                'workspace':str(getattr(self,'work','')),'profile':getattr(self,'model_selection',{}),
                'preserve_tool_history':True,'restart_whole_workflow':False})
        if resumable and not (isinstance(error,dict) and error.get('reason')=='REVIEW_NO_PROGRESS'):
            self.refresh_after_error_pause()

    def refresh_after_error_pause(self):
        """Codex owns authentication and connection renewal; keep this exact role."""
        self.rpc('account/read',{'refreshToken':True})
        append(self.logs/'controller.jsonl',{'event':'explicit_native_resume',
            'thread_id':self.thread_id,'credential_handling':'official Codex client'})

    def wait_remote_retry(self, seconds, reason, turn, deadline):
        """Wait without model calls, retaining this exact thread and candidates."""
        record={'event':'remote_service_retry_wait','retry_number':self.remote_retry_count,
            'incident_retry_number':getattr(self,'remote_incident_retries',self.remote_retry_count),
            'thread_id':self.thread_id,'previous_turn_id':turn.get('id'),
            'request_number':self.api_calls,'delay_seconds':seconds,'reason':reason,
            'original_error':turn.get('error'),'policy':REMOTE_RETRY_POLICY['version']}
        append(self.logs/'remote-retries.jsonl',record)
        execution=getattr(self,'execution',None)
        if execution:execution.task(self.execution_task,activity='REMOTE_RETRY_WAIT',
            remote_retry_number=self.remote_retry_count,remote_retry_delay_seconds=seconds,
            remote_retry_reason=reason,last_activity_at_utc=now())
        end=time.monotonic()+seconds
        sleeper=threading.Event()
        while time.monotonic()<end:
            self.check_runtime_state()
            if execution:execution.check(self.execution_task)
            if deadline is not None and time.monotonic()>=deadline:
                raise TimeoutError('Explicit stage deadline reached during remote retry wait')
            if self.proc is not None and self.proc.poll() is not None:
                raise RuntimeError('Carrier exited during remote retry wait; not a remote-server retry')
            sleeper.wait(min(.25,max(0,end-time.monotonic())))
        if execution:execution.check(self.execution_task)
        if deadline is not None and time.monotonic()>=deadline:
            raise TimeoutError('Explicit stage deadline reached during remote retry wait')
        if execution:execution.task(self.execution_task,activity='MODEL_RUNNING',last_activity_at_utc=now())
        append(self.logs/'remote-retries.jsonl',{'event':'remote_service_retry_started',
            'retry_number':self.remote_retry_count,'thread_id':self.thread_id,
            'previous_turn_id':turn.get('id')})

    def interrupt_active_turn(self, reason='DEADLINE') -> None:
        prior=getattr(self,'_stopping',False);self._stopping=True
        try:return self._interrupt_active_turn(reason)
        finally:self._stopping=prior

    def _interrupt_active_turn(self, reason='DEADLINE') -> None:
        # turn/start may have been sent just before the deadline. Consume its
        # own acknowledgement before deciding which turn to interrupt.
        if self.pending_turn_start_id is not None:
            self.receive_until(lambda m: self.pending_turn_start_id is None,
                               time.monotonic() + 15)
        if not self.active_turn_id:
            raise RuntimeError('无法确认本题活动回合，不发送无turnId的中断请求。')
        pending=getattr(self,'handoff_interrupt',None)
        if not pending and (self.last_turn_event and self.last_turn_event.get('params', {}).get('turn', {}).get('id')
                == self.active_turn_id):
            return
        record=self.logs/('deadline.jsonl' if reason=='DEADLINE' else 'cancellation.jsonl')
        append(record, {'event': 'interrupt_requested','reason':reason,
            'thread_id': self.thread_id, 'turn_id': self.active_turn_id,
            'request_number': self.api_calls})
        if pending:
            reply=self.receive_until(lambda m:m.get('id')==pending,time.monotonic()+15)
            self.handoff_interrupt=None
            error=reply.get('error')
            if error and not (error.get('code')==-32600 and 'no active turn to interrupt' in error.get('message','').lower()):
                raise RuntimeError(json.dumps(error,ensure_ascii=False))
        else:
            try:self.rpc('turn/interrupt', {'threadId': self.thread_id, 'turnId': self.active_turn_id}, seconds=15)
            except RuntimeError as error:
                try:detail=json.loads(str(error))
                except ValueError:raise error
                if detail.get('code')!=-32600 or 'no active turn to interrupt' not in detail.get('message','').lower():raise
                # A matching terminal event must still confirm the race. The
                # RPC error alone is never evidence of successful completion.
        if not (self.last_turn_event and self.last_turn_event.get('params', {}).get('turn', {}).get('id')
                == self.active_turn_id):
            self.receive_until(lambda m: m.get('method') == 'turn/completed'
                and m.get('params', {}).get('turn', {}).get('id') == self.active_turn_id,
                time.monotonic() + 15)
        append(record, {'event': 'interrupt_completed','reason':reason,
            'thread_id': self.thread_id, 'turn_id': self.active_turn_id,
            'status': self.last_turn_event.get('params', {}).get('turn', {}).get('status')})
        for call_id,row in getattr(self,'handoff_results',{}).items():
            if row['turn_id']==self.active_turn_id and not row['confirmed']:
                row['confirmed']=True
                path=self.logs/'handoff-results'/(hashlib.sha256(call_id.encode()).hexdigest()+'.json')
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
                row['record']={'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
