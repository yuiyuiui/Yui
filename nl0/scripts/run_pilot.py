#!/usr/bin/env python3
"""Isolated native Codex sessions managed through official stdio interfaces.

Codex owns model networking and context management. Dynamic
tools expose only the task, the pinned mathlib, and a sandboxed Lean checker.
No API keys, bearer tokens, or authorization headers are written into logs.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import textwrap
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from staging_storage import copy_input

from pilot_common import ROOT, load_lock, run_lean, sha256, transport_sandbox_profile
from runtime_config import model_profile
import remote_retry
from execution_state import CaseDeadlineExceeded, Cancelled

REMOTE_RETRY_POLICY = remote_retry.POLICY

MODEL = model_profile()['id']
PERSISTENT_VERSIONS = {'0.4.0', '0.4.1'}
CURRENT_VERSION = '0.4.1'
# Give an executing native tool batch time to return its diagnostics on a protective stop.
REVIEW_FEEDBACK_DRAIN_SECONDS = 5
SYSTEM = ('你是 Lean 4 证明形式化模型。只依据本次任务提供的定义、允许前提、自然语言证明和固定版本的 mathlib，'
          '完成精确目标 P。可以使用提供的工具查阅 mathlib 并检查证明。不得增加目标假设、使用未授权公理或占位证明。'
          'check_proof 和 submit_proof 接收 := by 之后的 Lean 证明体，不接收整个文件。'
          '检查失败时自行修复；完成后调用 submit_proof。不要尝试查阅其他任务、参考答案、记忆、skill 或外部服务。')
AUDIT_QUESTION = ('证明阶段已经结束，本轮仅作环境自述，不再修改证明。请分别说明：'
                  '1. 本轮你实际使用了哪些工具和信息来源；2. 是否看到旧会话、个人记忆或 skill 内容；'
                  '3. 是否调用过额外模型、网页或其他网络 API；4. 对运行程序通过何种网络接口调用你，'
                  '以及宿主机是否还存在不可见文件，哪些是你无法独立核实的。请区分亲自观察和无法验证。')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append(path: Path, item: dict) -> None:
    with path.open('a') as f:
        f.write(json.dumps({'timestamp_utc': now(), **item}, ensure_ascii=False) + '\n')


def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {'type': 'function', 'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': properties, 'required': required,
                            'additionalProperties': False}}


TOOLS = [
    tool('search_mathlib', '在固定 mathlib 的 Lean 源码中搜索正则表达式，返回至多 100 行。',
         {'query': {'type': 'string'}}, ['query']),
    tool('read_mathlib', '读取固定 mathlib 中一个 Mathlib/...lean 文件的指定行。',
         {'path': {'type': 'string'}, 'start_line': {'type': 'integer'}, 'line_count': {'type': 'integer'}},
         ['path', 'start_line', 'line_count']),
    tool('check_proof', '将提供的证明体放入不可改动的目标包装中，以 Lean 编译并检查公理依赖。',
         {'proof': {'type': 'string'}}, ['proof']),
    tool('submit_proof', '提交最终证明体并执行相同验收；成功时结束证明阶段。',
         {'proof': {'type': 'string'}}, ['proof']),
]
TOOL_NAMES = {t['name'] for t in TOOLS}
SYSTEM_WITH_AUXILIARY = SYSTEM + (
    'check_auxiliary 可单独检查一个全称量化的辅助命题及其证明体；该检查不会把结果加入前提或最终目标。'
    '最终提交仍须在 P 的证明体中包含所有自建辅助结果的证明。')
CONTINUE_PROMPT = ('最终目标P尚未通过提交验收。请继续利用本题已有上下文和工具修复并提交完整证明。'
                   '目标、定义和许可前提不变；本条不提供新的数学事实。')
SYSTEM_PERSISTENT = SYSTEM_WITH_AUXILIARY + (
    '本题Target.lean.txt中theorem P已经声明的参数和假设，在最终证明体开头已位于Lean上下文中，不要再次intro这些参数。'
    '最终证明体不要以额外的by开头；只有新建的have子证明需要自己的by。辅助命题的全称量词仍需在辅助证明内引入。'
    '最终提交未通过时应继续修复；单次回合结束不代表任务完成，管理程序可能发出固定继续指令。')
TOOLS_WITH_AUXILIARY = TOOLS + [
    tool('check_auxiliary', '在同一前提下独立编译一个辅助命题，不接受最终目标，也不扩充后续上下文。'
         'statement 只填命题类型（含全部量词），proof 只填 := by 之后的证明体。',
         {'statement': {'type': 'string'}, 'proof': {'type': 'string'}}, ['statement', 'proof']),
]


def harness_policy(version: str) -> tuple[str, list[dict]]:
    if version in ['0.1.0', '0.2.0']:
        return SYSTEM, TOOLS
    if version == '0.3.0':
        return SYSTEM_WITH_AUXILIARY, TOOLS_WITH_AUXILIARY
    if version in PERSISTENT_VERSIONS:
        return SYSTEM_PERSISTENT, TOOLS_WITH_AUXILIARY
    raise ValueError('未知 harness 版本：' + version)


FOUNDATIONS = {'propext', 'Classical.choice', 'Quot.sound'}
FORBIDDEN = re.compile(r'\b(sorry|admit|axiom|unsafe|run_meta|run_elab|run_tac|native_decide|set_option)\b|(^|\n)\s*#', re.M)
AUXILIARY_COMMANDS = re.compile(
    r'\b(theorem|lemma|def|abbrev|opaque|instance|namespace|section|end|import|open|'
    r'attribute|syntax|macro|elab|initialize|export|variable|universe)\b|:=')
PROOF_FORMAT = 'dedent_then_indent_2'


def format_proof_body(proof: str) -> str:
    """Embed a standalone tactic body without requiring outer file indentation."""
    return textwrap.indent(textwrap.dedent(proof).strip('\n'), '  ')




def system_https_proxy() -> tuple[str, int] | None:
    config = subprocess.check_output(['/usr/sbin/scutil', '--proxy'], text=True)
    enabled = re.search(r'HTTPSEnable\s*:\s*(\d+)', config)
    host = re.search(r'HTTPSProxy\s*:\s*(\S+)', config)
    port = re.search(r'HTTPSPort\s*:\s*(\d+)', config)
    return (host[1], int(port[1])) if enabled and enabled[1] == '1' and host and port else None


class LocalProtocolRejection(PermissionError):
    """Deterministic own-history rejection, never a retryable network failure."""
    def __init__(self, reason, details=None):
        self.reason, self.details = reason, details or {}
        super().__init__('LOCAL_TOOL_FEEDBACK_REJECTED: ' + reason)


class NativeEventTimeout(TimeoutError):
    """The controller wait expired before the requested native event arrived."""


class Trial:
    @property
    def model(self):
        return self.model_selection['id'] if hasattr(self, 'model_selection') else MODEL

    def __init__(self, case: str, run_dir: Path, timeout: float | None = None, suite: str = 'pilot-v1',
                 harness_version: str = '0.2.0'):
        self.harness_version = harness_version
        self.model_selection = model_profile()
        self.strict = harness_version in PERSISTENT_VERSIONS
        self.system, self.tools = harness_policy(harness_version)
        self.tool_names = {t['name'] for t in self.tools}
        self.case, self.logs, self.timeout = case, run_dir / case, __import__('runtime_config').time_limit(timeout)
        self.logs.mkdir(parents=True)
        self.work = Path(tempfile.mkdtemp(prefix=f'nl2lean-{case}-')).resolve()
        from run_resources import register_workspace
        register_workspace(self.work, self.logs)
        for name in ['input', 'output', 'tmp', 'home', 'state']:
            (self.work / name).mkdir(mode=0o700)
        self.suite = suite
        self.taskdir = ROOT / 'benchmarks' / suite / case
        self.task = json.loads((self.taskdir / 'task.json').read_text())
        for p in self.taskdir.iterdir():
            if self.strict and p.name not in {'task.md', 'Premises.lean', 'Target.lean.txt'}:
                continue
            copy_input(p, self.work / 'input' / p.name)
        (self.logs / 'input').mkdir()
        for p in (self.work / 'input').iterdir(): copy_input(p, self.logs / 'input' / p.name)
        if self.strict:
            # Archive manager metadata for verification, without exposing it
            # through the model/compiler's own runtime input directory.
            shutil.copyfile(self.taskdir / 'task.json', self.logs / 'input/task.json')
            (self.logs / 'runtime-input-manifest.json').write_text(json.dumps(
                {p.name: sha256(p) for p in (self.work / 'input').iterdir()}, indent=2) + '\n')
        (self.logs / 'input-manifest.json').write_text(json.dumps(
            {p.name: sha256(p) for p in (self.logs / 'input').iterdir()}, indent=2) + '\n')
        self.prefix = (self.work / 'input/Target.lean.txt').read_text().split(' := by\n')[0] + ' := by\n'
        self.accepted = None
        self.lean_calls = 0
        self.api_calls = 0
        self.request_lock = threading.Lock()
        self.native_turn_generation = 0
        self.request_turns = {}
        self.last_response_success = None
        self.rpc_id = 0
        self.inbox: queue.Queue = queue.Queue()
        self.started: float | None = None
        self.allowed_user_messages: set[str] = set()
        self.proc = None
        self.model_calls: dict[str, dict] = {}
        self.tool_history: dict[str, dict] = {}
        self.phase = 'proof'
        self.continuation_count = 0
        self.turn_results: list[dict] = []
        self.last_turn_event = None
        self.active_turn_id = None
        self.pending_turn_start_id = None
        self.initial_user_message = None

    def lean_timeout(self) -> float | None:
        import lean_timeout_policy
        recorder = getattr(self,'execution',None)
        limit = (lean_timeout_policy.ceiling() if lean_timeout_policy.active.get() is not None
                 else __import__('runtime_config').configured_timeout('native'))
        case_left = recorder.remaining(limit) if recorder else limit
        if self.strict and self.started is not None and self.timeout is not None:
            remaining = self.started + self.timeout - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('证明预算已耗尽，不再启动Lean检查。')
            return min(case_left, remaining) if case_left is not None else remaining
        return case_left

    def check(self, proof: str, submit: bool = False) -> dict:
        if self.strict and re.match(r'^\s*by(?:\s|$)', proof):
            return {'accepted': False, 'error': '只填固定目标 := by 之后的证明体，请去掉开头多余的by。已声明参数已在上下文中。'}
        if len(proof) > 100_000 or FORBIDDEN.search(proof):
            return {'accepted': False, 'error': '证明体包含被禁止的占位符、公理、元编程命令或超出长度限制。'}
        p = self.work / 'output/Candidate.lean'
        compiled_body = format_proof_body(proof)
        p.write_text(self.prefix + compiled_body + '\n\nend\nend Pilot\n\n#print axioms Pilot.P\n#check @Pilot.P\n')
        self.lean_calls += 1
        result = run_lean(p, self.work, extra=[self.work / 'input'], timeout=self.lean_timeout())
        match = re.search(r"'Pilot.P' depends on axioms: \[([^]]*)\]", result['stdout'])
        actual = {s.strip() for s in match[1].split(',') if s.strip()} if match else set()
        if "'Pilot.P' does not depend on any axioms" in result['stdout']:
            match = True
        allowed = FOUNDATIONS | {'Pilot.' + f for f in self.task['allowed_premises']}
        unexpected = actual - allowed
        ok = result['exit_code'] == 0 and bool(match) and not unexpected
        record = {**result, 'accepted': ok, 'axioms': sorted(actual), 'unexpected_axioms': sorted(unexpected),
                  'proof_sha256': hashlib.sha256(proof.encode()).hexdigest(), 'submission': submit}
        record.update({'proof_body_format': PROOF_FORMAT,
                       'compiled_proof_body_sha256': hashlib.sha256(compiled_body.encode()).hexdigest()})
        append(self.logs / 'lean.jsonl', record)
        if submit and ok:
            self.accepted = {'solve_seconds': time.monotonic() - self.started,
                             'accepted_at_utc': now(), 'proof_sha256': record['proof_sha256'], 'axioms': sorted(actual),
                             'proof_body_format': PROOF_FORMAT,
                             'compiled_proof_body_sha256': record['compiled_proof_body_sha256']}
            (self.logs / 'proof.txt').write_text(proof)
            (self.logs / 'CompiledProof.txt').write_text(compiled_body)
            shutil.copyfile(p, self.logs / 'Submitted.lean')
        return {**record, 'stdout': result['stdout'][-14000:], 'stderr': result['stderr'][-2000:]}

    def check_auxiliary(self, statement: str, proof: str) -> dict:
        if (not statement.strip() or len(statement) > 20_000 or len(proof) > 100_000
                or FORBIDDEN.search(statement) or FORBIDDEN.search(proof)
                or AUXILIARY_COMMANDS.search(statement)):
            return {'auxiliary_valid': False, 'error': '辅助命题只接受命题类型及无占位符的证明体。'}
        header, marker, _ = self.prefix.partition('theorem P')
        if not marker:
            raise ValueError('固定目标缺少 theorem P。')
        compiled_body = format_proof_body(proof)
        p = self.work / 'output/Auxiliary.lean'
        p.write_text(header + 'theorem auxiliaryCheck : ' + statement + ' := by\n' + compiled_body
                     + '\n\nend\nend Pilot\n\n#print axioms Pilot.auxiliaryCheck\n#check @Pilot.auxiliaryCheck\n')
        self.lean_calls += 1
        result = run_lean(p, self.work, extra=[self.work / 'input'], timeout=self.lean_timeout())
        match = re.search(r"'Pilot.auxiliaryCheck' depends on axioms: \[([^]]*)\]", result['stdout'])
        actual = {s.strip() for s in match[1].split(',') if s.strip()} if match else set()
        if "'Pilot.auxiliaryCheck' does not depend on any axioms" in result['stdout']:
            match = True
        allowed = FOUNDATIONS | {'Pilot.' + f for f in self.task['allowed_premises']}
        unexpected = actual - allowed
        record = {**result, 'auxiliary_valid': result['exit_code'] == 0 and bool(match) and not unexpected,
                  'scope': 'auxiliary_only; not added to premises or final target',
                  'axioms': sorted(actual), 'unexpected_axioms': sorted(unexpected),
                  'statement_sha256': hashlib.sha256(statement.encode()).hexdigest(),
                  'proof_sha256': hashlib.sha256(proof.encode()).hexdigest(),
                  'proof_body_format': PROOF_FORMAT,
                  'compiled_proof_body_sha256': hashlib.sha256(compiled_body.encode()).hexdigest(),
                  'kind': 'auxiliary', 'submission': False}
        append(self.logs / 'lean.jsonl', record)
        return {**record, 'stdout': result['stdout'][-14000:], 'stderr': result['stderr'][-2000:]}

    def dispatch(self, name: str, args: dict) -> dict:
        started = time.monotonic()
        try:
            if name not in self.tool_names:
                raise PermissionError('工具不在本次实验白名单内。')
            if self.strict and self.phase != 'proof':
                raise PermissionError('证明阶段已经结束，环境自述阶段不执行工具。')
            if self.accepted and name in ['check_proof', 'submit_proof', 'check_auxiliary']:
                raise PermissionError('证明已验收，禁止覆盖该次提交。')
            if name in ['check_proof', 'submit_proof']:
                result = self.check(args['proof'], name == 'submit_proof')
            elif name == 'check_auxiliary':
                result = self.check_auxiliary(args['statement'], args['proof'])
            elif name == 'search_mathlib':
                __import__('runtime_config').require_environment()
                ml = Path(load_lock()['mathlib']['local_path']) / 'Mathlib'
                rg = load_lock()['tools']['ripgrep']['binary_path']
                p = subprocess.run([rg, '--no-config', '-n', '--max-count', '5', '--glob', '*.lean',
                                    '--', args['query'], str(ml)], capture_output=True, text=True,
                                   env={'PATH': '/usr/bin:/bin', 'HOME': str(self.work / 'home'), 'LANG': 'en_US.UTF-8'})
                result = {'matches': '\n'.join(p.stdout.replace(str(ml) + '/', 'Mathlib/').splitlines()[:100])[:16000],
                          'exit_code': p.returncode, 'stderr': p.stderr[-2000:]}
            elif name == 'read_mathlib':
                __import__('runtime_config').require_environment()
                ml = Path(load_lock()['mathlib']['local_path'])
                path = (ml / args['path']).resolve()
                if not path.is_relative_to(ml / 'Mathlib') or path.suffix != '.lean':
                    raise PermissionError('只能读取固定 mathlib 的 Mathlib/*.lean 源码。')
                start = max(1, int(args['start_line']))
                count = max(1, min(200, int(args['line_count'])))
                lines = path.read_text().splitlines()
                result = {'path': str(path.relative_to(ml)), 'lines': '\n'.join(
                    f'{i + 1}: {lines[i]}' for i in range(start - 1, min(len(lines), start - 1 + count)))[:18000]}
            else:
                raise PermissionError('工具不在本次实验白名单内。')
        except (CaseDeadlineExceeded, Cancelled):raise
        except Exception as e:
            result = {'error': str(e), 'error_type': type(e).__name__, 'accepted': False,
                      'infrastructure_error': name == 'search_mathlib' and isinstance(e, FileNotFoundError)}
        append(self.logs / 'tools.jsonl', {'tool': name, 'arguments': args, 'result': result,
                                         'wall_seconds': time.monotonic() - started})
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
        if self.strict:
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

    def solve_turns(self, user: str, *, smoke: bool = False) -> dict:
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
            if smoke or self.accepted or not self.strict:
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

    def run(self, *, smoke: bool = False) -> dict:
        result = {'case': self.case, 'suite': self.suite, 'model': self.model, 'effort': getattr(self, 'model_selection', {}).get('reasoning_effort', 'high'), 'status': 'STARTING',
                  'harness_version': self.harness_version,
                  'runtime_directory': str(self.work), 'started_at_utc': now(), 'smoke': smoke}
        try:
            prep = run_lean(self.work / 'input/Premises.lean', self.work,
                            output=self.work / 'output/Premises.olean')
            if prep['exit_code'] != 0: raise RuntimeError('前提文件编译失败：' + str(prep))
            for path in (self.work / 'output').glob('Premises.*'):
                shutil.move(path, self.work / 'input' / path.name)
            self.start_process()
            inventory = self.rpc('skills/list', {'cwds': [str(self.work / 'input')], 'forceReload': True})
            (self.logs / 'skills-inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2))
            t = self.rpc('thread/start',__import__('native_client').thread_parameters(self))
            __import__('native_client').verify_thread(self,t)
            self.thread_id = t['thread']['id']
            if smoke:
                user = ('本轮是工具链连接测试，不做数学任务。请先调用 search_mathlib 搜索 '
                        'hasDerivAt_tsum_of_isPreconnected，再调用 read_mathlib 读取 '
                        'Mathlib/Analysis/Calculus/SmoothSeries.lean 第85至110行，最后仅回复：连接正常。')
                if 'check_auxiliary' in self.tool_names:
                    user += ('回复前还须调用 check_auxiliary，statement 为 ∀ n : Nat, n = n，'
                             'proof 为 intro n 后换行 rfl。这只是独立编译工具的连接检查。')
            else:
                user = '\n\n'.join((self.work / 'input' / p).read_text()
                                    for p in ['task.md', 'Premises.lean', 'Target.lean.txt'])
            try:
                done = self.solve_turns(user, smoke=smoke)
                result['turn_result'] = done
            except TimeoutError as e:
                if not self.strict:
                    raise
                result.update({'status': 'TIMEOUT', 'error': str(e)})
                result['proof_elapsed_seconds'] = time.monotonic() - self.started
                result['proof_stage_status'] = 'TIMEOUT'
                self.phase = 'closing'
                self.interrupt_active_turn()
                result['deadline_interrupt_status'] = 'PASS'
            result.setdefault('proof_elapsed_seconds', time.monotonic() - self.started)
            if smoke:
                result['status'] = 'SMOKE_COMPLETED'
            elif self.accepted:
                result.update(self.accepted)
                result['status'] = 'PROOF_ACCEPTED'
                # Recompile the submission in a newly created verifier root.
                v = Path(tempfile.mkdtemp(prefix=f'nl2lean-verify-{self.case}-')).resolve()
                for n in ['input', 'output', 'home', 'tmp']: (v / n).mkdir()
                for p in (self.work / 'input').glob('Premises.*'): shutil.copyfile(p, v / 'input' / p.name)
                shutil.copyfile(self.logs / 'Submitted.lean', v / 'output/Submitted.lean')
                verification = run_lean(v / 'output/Submitted.lean', v, extra=[v / 'input'])
                (self.logs / 'independent-verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2))
                result['independent_verification_exit_code'] = verification['exit_code']
                if verification['exit_code'] != 0: result['status'] = 'VALIDATION_FAILED'
            elif result['status'] != 'TIMEOUT':
                result['status'] = 'NO_ACCEPTED_PROOF'
            result['proof_stage_status'] = result['status']
            if not smoke and (self.accepted or self.strict):
                self.phase = 'audit'
                self.allowed_user_messages.add(AUDIT_QUESTION)
                self.rpc('turn/start', {'threadId': self.thread_id, 'effort': getattr(self, 'model_selection', {}).get('reasoning_effort', 'high'),
                    'input': [{'type': 'text', 'text': AUDIT_QUESTION}], 'environments': []})
                self.receive_until(lambda m: m.get('method') == 'turn/completed',
                    self.started + self.timeout if self.timeout is not None else None)
                result['environment_audit_status'] = 'COMPLETED'
        except Exception as e:
            result['status'] = 'TIMEOUT' if isinstance(e, TimeoutError) else 'ERROR'
            result['error'] = str(e)
            result['failure_phase'] = self.phase
        finally:
            if result.get('status') not in {'SMOKE_COMPLETED','PROOF_ACCEPTED','CANCELLED'}:
                try:self.pause_error({'code':'harness_bug','message':'Legacy carrier did not complete',
                    'outcome':dict(result)},resumable=False)
                except __import__('execution_state').Cancelled:
                    result.update(status='CANCELLED',stop_reason='EXTERNAL_CANCEL')
            result['continuation_count'] = self.continuation_count
            result['remote_retries'] = getattr(self,'remote_retry_count',0)
            result['remote_retry_policy'] = REMOTE_RETRY_POLICY
            result['proof_turns'] = self.turn_results
            result.update({'finished_at_utc': now(), 'api_calls': self.api_calls, 'lean_calls': self.lean_calls})
            if self.started: result['total_elapsed_seconds'] = time.monotonic() - self.started
            if self.proc:
                self.proc.terminate()
                try: self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired: self.proc.kill(); self.proc.wait()
            # Authentication is ephemeral and never part of the experiment artifact.
            for name in ['auth.json', 'models_cache.json']:
                (self.work / 'state' / name).unlink(missing_ok=True)
            (self.logs / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        return result

