#!/usr/bin/env python3
"""Three isolated trials using Codex only as an authenticated model transport.

The local relay fixes the actual instructions/tools sent upstream. Dynamic
tools expose only the task, the pinned mathlib, and a sandboxed Lean checker.
No API keys, bearer tokens, or authorization headers are written into logs.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import http.client
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
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pilot_common import ROOT, load_lock, run_lean, sha256, transport_sandbox_profile

MODEL = 'gpt-6-luna'
PERSISTENT_VERSIONS = {'0.4.0', '0.4.1'}
CURRENT_VERSION = '0.4.1'
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
CONTINUE_PROMPT = ('最终目标P尚未通过提交验收，本次试验仍有剩余预算。请继续利用本题已有上下文和工具修复并提交完整证明。'
                   '目标、定义和许可前提不变；本条不提供新的数学事实。')
SYSTEM_PERSISTENT = SYSTEM_WITH_AUXILIARY + (
    '本题Target.lean.txt中theorem P已经声明的参数和假设，在最终证明体开头已位于Lean上下文中，不要再次intro这些参数。'
    '最终证明体不要以额外的by开头；只有新建的have子证明需要自己的by。辅助命题的全称量词仍需在辅助证明内引入。'
    '最终提交未通过时应继续修复；单次回合结束不代表任务完成，管理程序可能在总预算内发出固定继续指令。')
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


def validate_model_event(event: dict, allowed_names: set[str] | None = None, *, strict: bool = False) -> None:
    allowed_names = TOOL_NAMES if allowed_names is None else allowed_names
    items = [event.get('item', {})] + event.get('response', {}).get('output', [])
    for item in items:
        if strict and item and item.get('type') not in {'reasoning', 'message', 'function_call'}:
            raise PermissionError('上游返回了未许可的输出项类型：' + str(item.get('type')))
        if strict and item.get('type') == 'message' and item.get('role') != 'assistant':
            raise PermissionError('上游消息角色不属于本题模型。')
        if item.get('type') == 'function_call' and item.get('name') not in allowed_names:
            raise PermissionError('上游返回了非白名单工具调用：' + str(item.get('name')))
    if strict and event.get('response', {}).get('model') not in [None, MODEL]:
        raise PermissionError('上游实际返回了其他模型。')
    if strict and event.get('type') in {'response.completed', 'response.incomplete', 'response.failed'}:
        tier = event.get('response', {}).get('service_tier')
        if tier not in [None, 'default', 'standard', 'auto']:
            raise PermissionError('The actual model response used a non-Standard service tier.')


def system_https_proxy() -> tuple[str, int] | None:
    config = subprocess.check_output(['/usr/sbin/scutil', '--proxy'], text=True)
    enabled = re.search(r'HTTPSEnable\s*:\s*(\d+)', config)
    host = re.search(r'HTTPSProxy\s*:\s*(\S+)', config)
    port = re.search(r'HTTPSPort\s*:\s*(\d+)', config)
    return (host[1], int(port[1])) if enabled and enabled[1] == '1' and host and port else None


class Trial:
    def __init__(self, case: str, run_dir: Path, timeout: float, suite: str = 'pilot-v1',
                 harness_version: str = '0.2.0'):
        self.harness_version = harness_version
        self.strict = harness_version in PERSISTENT_VERSIONS
        self.system, self.tools = harness_policy(harness_version)
        self.tool_names = {t['name'] for t in self.tools}
        self.case, self.logs, self.timeout = case, run_dir / case, timeout
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
            shutil.copyfile(p, self.work / 'input' / p.name)
        (self.logs / 'input').mkdir()
        for p in (self.work / 'input').iterdir(): shutil.copyfile(p, self.logs / 'input' / p.name)
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
        self.rpc_id = 0
        self.inbox: queue.Queue = queue.Queue()
        self.started: float | None = None
        self.allowed_user_messages: set[str] = set()
        self.proc = None
        self.relay = None
        self.model_history: dict[str, dict] = {}
        self.model_calls: dict[str, dict] = {}
        self.tool_history: dict[str, dict] = {}
        self.prompt_cache_key = 'nl2lean-' + str(uuid.uuid4())
        self.phase = 'proof'
        self.continuation_count = 0
        self.turn_results: list[dict] = []
        self.last_turn_event = None
        self.active_turn_id = None
        self.pending_turn_start_id = None
        self.cancelled_requests: dict[int, dict] = {}
        self.initial_user_message = None

    def lean_timeout(self) -> float:
        if self.strict and self.started is not None and self.phase == 'proof':
            remaining = self.started + self.timeout - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('证明预算已耗尽，不再启动Lean检查。')
            return min(120, remaining)
        return 120

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
                ml = Path(load_lock()['mathlib']['local_path']) / 'Mathlib'
                rg = load_lock()['tools']['ripgrep']['binary_path']
                p = subprocess.run([rg, '--no-config', '-n', '--max-count', '5', '--glob', '*.lean',
                                    '--', args['query'], str(ml)], capture_output=True, text=True, timeout=12,
                                   env={'PATH': '/usr/bin:/bin', 'HOME': str(self.work / 'home'), 'LANG': 'en_US.UTF-8'})
                result = {'matches': '\n'.join(p.stdout.replace(str(ml) + '/', 'Mathlib/').splitlines()[:100])[:16000],
                          'exit_code': p.returncode, 'stderr': p.stderr[-2000:]}
            elif name == 'read_mathlib':
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
        except Exception as e:
            result = {'error': str(e), 'error_type': type(e).__name__, 'accepted': False,
                      'infrastructure_error': name == 'search_mathlib' and isinstance(e, FileNotFoundError)}
        append(self.logs / 'tools.jsonl', {'tool': name, 'arguments': args, 'result': result,
                                         'wall_seconds': time.monotonic() - started})
        return result

    def reserve_request_number(self):
        # The relay is multithreaded (including compaction/continuation). Never
        # recover a request's identity later from the mutable global counter.
        with self.request_lock:
            self.api_calls += 1
            number=self.api_calls
            append(self.logs/'request-lifecycle.jsonl',{'request_number':number,'event':'ALLOCATED','at_utc':now()})
            return number

    def normalize_request(self, payload: dict, *, request_number=None) -> dict:
        if payload.get('model') != MODEL:
            raise ValueError('禁止替换指定模型：' + str(payload.get('model')))
        if payload.get('reasoning', {}).get('effort') != 'high':
            raise ValueError('推理档位不是 high。')
        # Only these explicit instructions, user messages and within-trial
        # model/tool history are submitted. The pre-normalization request is
        # retained to make every removal auditable.
        result = dict(payload)
        result['instructions'] = self.system
        result['tools'] = [{'type': 'function', 'name': t['name'], 'description': t['description'],
                            'parameters': t['inputSchema'], 'strict': False} for t in self.tools]
        kept, removed = [], []
        for item in payload.get('input', []):
            role = item.get('role')
            text = '\n'.join(c.get('text', '') for c in item.get('content', []) if isinstance(c, dict))
            if role in ['developer', 'system'] or role == 'user' and text not in self.allowed_user_messages:
                removed.append(item)
            else:
                kept.append(item)
        result['input'] = kept
        result['store'] = False
        if self.strict:
            if payload.get('conversation') or payload.get('previous_response_id'):
                raise PermissionError('新基线只接受显式本题历史，不继承服务器会话或响应。')
            if not any(i.get('role') == 'user' and '\n\n'.join(
                    c.get('text', '') for c in i.get('content', []) if isinstance(c, dict)
                    ) in ({self.initial_user_message} if self.initial_user_message else self.allowed_user_messages)
                    for i in kept):
                raise PermissionError('请求缺少本题已授权输入。')
            for item in kept:
                if item.get('role') == 'user':
                    if item.get('type') != 'message' or any(
                            c.get('type') != 'input_text' for c in item.get('content', [])):
                        raise PermissionError('本题只允许冻结的纯文本用户消息。')
                elif item.get('type') == 'function_call_output':
                    origin = self.tool_history.get(item.get('call_id'))
                    if (origin is None or set(item) - {'type', 'id', 'call_id', 'output'}
                            or json.loads(item['output']) != origin):
                        raise PermissionError('工具反馈不属于本题真实执行结果。')
                else:
                    origin = self.model_history.get(item.get('id'))
                    if origin is None or any(origin.get(k) != v for k, v in item.items() if k != 'status'):
                        raise PermissionError('模型历史不属于本题已接收输出。')
            kept = [({'type': 'message', 'role': 'user', 'content':
                      [{'type': 'input_text', 'text': c['text']} for c in i['content']]}
                     if i.get('role') == 'user' else i) for i in kept]
            # Construct the complete semantic request, rather than forwarding
            # unreviewed provider fields such as client_metadata.
            result = {'model': MODEL, 'stream': True, 'input': kept, 'instructions': self.system,
                      'tools': result['tools'], 'tool_choice': 'auto', 'parallel_tool_calls': False,
                      'reasoning': {'effort': 'high', 'context': 'all_turns'},
                      'include': ['reasoning.encrypted_content'], 'store': False,
                      'text': {'verbosity': 'low'}, 'prompt_cache_key': self.prompt_cache_key,
                      'service_tier': 'default'}
        # Native compaction summaries remain untrusted and removed. Restore only
        # machine facts about this stage's own immutable checked drafts, rather
        # than forwarding an opaque summary or silently losing working state.
        checkpoint=None
        hook=getattr(self,'controller_checkpoint',None)
        if hook is not None:
            checkpoint=hook()
            if checkpoint is not None:
                text='Current-stage machine checkpoint (no new mathematical premise): '+json.dumps(checkpoint['data'],ensure_ascii=False,sort_keys=True)
                checkpoint={**checkpoint,'text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest()}
                self.allowed_user_messages.add(text)
                result['input'].append({'type':'message','role':'user','content':[{'type':'input_text','text':text}]})
        if request_number is None:request_number=self.reserve_request_number()
        append(self.logs / 'requests.jsonl', {'request_number': request_number,
            'transport': 'Codex subscription authentication via documented custom provider',
            'upstream_host': 'chatgpt.com', 'upstream_path': '/backend-api/codex/responses',
            'original_payload': payload, 'removed_items': removed, 'sent_payload': result,
            'controller_checkpoint': checkpoint,
            'dropped_top_level_fields': sorted(set(payload) - set(result)),
            'sent_body_sha256': hashlib.sha256(json.dumps(result, ensure_ascii=False).encode()).hexdigest()})
        # A mistaken adapter must fail before sending an empty first problem.
        if request_number == 1 and not any(i.get('role') == 'user' for i in kept):
            raise ValueError('首个请求缺少冻结题目，拒绝发送。')
        append(self.logs/'request-lifecycle.jsonl',{'request_number':request_number,'event':'NORMALIZED','at_utc':now()})
        return result

    def observe_model_event(self, event: dict, request_number=None) -> None:
        validate_model_event(event, self.tool_names, strict=self.strict)
        execution=getattr(self,'execution',None)
        if execution:
            execution.model_event(self.execution_task,str(self.logs),request_number,event)
        if event.get('type') == 'response.output_item.done':
            item = event['item']
            self.model_history[item['id']] = item
            if item.get('type') == 'function_call':
                self.model_calls[item['call_id']] = item
        if request_number is not None and event.get('type') in {'response.completed','response.failed','response.incomplete'}:
            append(self.logs/'request-lifecycle.jsonl',{'request_number':request_number,'event':'PROVIDER_TERMINAL',
                'response_type':event['type'],'response_id':event.get('response',{}).get('id'),'at_utc':now()})

    def validate_tool_rpc(self, params: dict) -> None:
        if not self.strict:
            return
        origin = self.model_calls.get(params.get('callId'))
        if (origin is None or origin.get('name') != params.get('tool')
                or json.loads(origin['arguments']) != params.get('arguments')):
            raise PermissionError('工具RPC与本题模型输出不对应。')

    def start_relay(self) -> int:
        trial = self
        self.relay_streams={}
        self.relay_stream_lock=threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def forward_sse(self, block: bytes, request_number: int) -> bool:
                try:
                    self.wfile.write(block); self.wfile.flush()
                    return True
                except (BrokenPipeError, ConnectionResetError) as e:
                    cancellation = trial.cancelled_requests.get(request_number)
                    if cancellation is None:
                        raise
                    # Only a downstream write for the exact request explicitly
                    # interrupted by this controller is a local cancellation.
                    append(trial.logs / 'local-cancellations.jsonl', {
                        'request_number': request_number, 'layer': 'relay_to_carrier_sse_write',
                        'error': str(e), 'error_type': type(e).__name__, **cancellation})
                    self.close_connection = True
                    return False

            def do_GET(self):
                if not self.path.startswith('/models'):
                    self.send_error(403); return
                cached = json.loads((trial.work / 'state/models_cache.json').read_text())
                models = [m for m in cached['models'] if m.get('slug') == MODEL]
                data = json.dumps({'models': models}).encode()
                append(trial.logs / 'http.jsonl', {'path': self.path, 'status': 200, 'source': 'local pinned model catalog; no upstream request'})
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

            def do_POST(self):
                execution=getattr(trial,'execution',None)
                if getattr(trial,'submission_closed',False) or (execution and execution.cancelled(trial.execution_task)):
                    length=int(self.headers.get('Content-Length','0'))
                    self.rfile.read(length)
                    append(trial.logs/'local-cancellations.jsonl',{
                        'layer':'post_submission_request_suppressed','upstream_transmitted':False,
                        'reason':'ACCEPTED_ARTIFACT' if getattr(trial,'submission_closed',False) else 'EXTERNAL_CANCEL'})
                    body=b'{"error":{"message":"Stage closed after accepted submission"}}'
                    self.send_response(409);self.send_header('Content-Type','application/json')
                    self.send_header('Content-Length',str(len(body)));self.send_header('Connection','close')
                    self.end_headers();self.wfile.write(body);self.close_connection=True
                    return
                upstream = None
                stream_done=None
                request_number=None
                try:
                    if self.path.rstrip('/') != '/responses':
                        raise PermissionError('只允许指定模型的 responses 路径。')
                    body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                    if self.headers.get('Content-Encoding') == 'gzip': body = gzip.decompress(body)
                    request_number=trial.reserve_request_number()
                    payload = trial.normalize_request(json.loads(body),request_number=request_number)
                    if execution: execution.request_started(str(trial.logs),request_number)
                    stream_done=threading.Event()
                    with trial.relay_stream_lock:
                        trial.relay_streams[request_number]=stream_done
                    data = json.dumps(payload, ensure_ascii=False).encode()
                    # Authentication/account routing are required by the subscription.
                    # No carrier conversation/session/state or speed headers cross this boundary.
                    header_allowlist = {'authorization', 'chatgpt-account-id', 'openai-beta',
                                        'user-agent', 'originator', 'content-type', 'accept'}
                    headers = {k: v for k, v in self.headers.items() if k.lower() in header_allowlist}
                    headers['Content-Length'] = str(len(data))
                    headers['Accept-Encoding'] = 'identity'
                    append(trial.logs / 'request-headers.jsonl', {'request_number':request_number,
                        'forwarded_names':sorted(k.lower() for k in headers),
                        'removed_names':sorted(k.lower() for k in self.headers if k.lower() not in header_allowlist),
                        'policy':'Names only; credential/header values are never logged.'})
                    if trial.network_proxy:
                        host, port = trial.network_proxy
                        upstream = http.client.HTTPSConnection(host, port, timeout=90)
                        upstream.set_tunnel('chatgpt.com', 443)
                    else:
                        upstream = http.client.HTTPSConnection('chatgpt.com', timeout=90)
                    upstream.request('POST', '/backend-api/codex/responses', body=data, headers=headers)
                    append(trial.logs/'request-lifecycle.jsonl',{'request_number':request_number,'event':'FORWARDED','at_utc':now()})
                    response = upstream.getresponse()
                    append(trial.logs / 'http.jsonl', {'status': response.status,
                        'request_id': response.getheader('x-request-id'), 'path': self.path,
                        'request_number': request_number})
                    append(trial.logs/'request-lifecycle.jsonl',{'request_number':request_number,'event':'HTTP_RESPONSE',
                        'status':response.status,'at_utc':now()})
                    self.send_response(response.status)
                    self.send_header('Content-Type', response.getheader('Content-Type', 'text/event-stream'))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    with (trial.logs / f'response-{request_number:04d}.sse').open('wb') as log:
                        pending = b''
                        while True:
                            chunk = response.read1(65536)
                            if not chunk: break
                            pending += chunk
                            while (separator := re.search(rb'\r?\n\r?\n', pending)) is not None:
                                block, pending = pending[:separator.end()], pending[separator.end():]
                                for line in block.splitlines():
                                    if line.startswith(b'data: '):
                                        try: event = json.loads(line[6:])
                                        except json.JSONDecodeError: continue
                                        trial.observe_model_event(event,request_number)
                                log.write(block); log.flush()
                                if not self.forward_sse(block, request_number):
                                    return
                        if pending:
                            for line in pending.splitlines():
                                if line.startswith(b'data: '):
                                    try: event = json.loads(line[6:])
                                    except json.JSONDecodeError: continue
                                    trial.observe_model_event(event,request_number)
                            log.write(pending)
                            if not self.forward_sse(pending, request_number):
                                return
                    self.close_connection = True
                except Exception as e:
                    append(trial.logs / 'relay-errors.jsonl', {'request_number':request_number,'error': str(e)})
                    if trial.strict and isinstance(e, (PermissionError, ValueError)):
                        append(trial.logs / 'isolation-violations.jsonl', {'error': str(e), 'error_type': type(e).__name__})
                    try:
                        message = json.dumps({'error': {'message': str(e)}}).encode()
                        self.send_response(502); self.send_header('Content-Type', 'application/json')
                        self.send_header('Content-Length', str(len(message))); self.end_headers(); self.wfile.write(message)
                    except OSError:
                        pass
                finally:
                    if upstream: upstream.close()
                    if request_number is not None:
                        append(trial.logs/'request-lifecycle.jsonl',{'request_number':request_number,'event':'STREAM_CLOSED','at_utc':now()})
                    if stream_done is not None:stream_done.set()

        self.relay = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.relay.daemon_threads = True
        threading.Thread(target=self.relay.serve_forever, daemon=True).start()
        return self.relay.server_port

    def drain_relay_streams(self,timeout=10):
        """Finish logging already transmitted responses before usage readback."""
        deadline=time.monotonic()+timeout
        lock=getattr(self,'relay_stream_lock',None)
        if lock is None:return
        with lock:pending=list(self.relay_streams.items())
        unfinished=[]
        for number,event in pending:
            if not event.wait(max(0,deadline-time.monotonic())):unfinished.append(number)
        if unfinished:
            raise RuntimeError('Response logging did not finish before bounded shutdown: '+str(unfinished))

    def send(self, method: str, params: dict | None = None) -> int:
        self.rpc_id += 1
        msg = {'id': self.rpc_id, 'method': method, 'params': params or {}}
        if method == 'turn/start':
            self.active_turn_id = None
            self.pending_turn_start_id = self.rpc_id
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + '\n'); self.proc.stdin.flush()
        append(self.logs / 'client.jsonl', msg)
        return self.rpc_id

    def receive_until(self, predicate, deadline: float):
        while time.monotonic() < deadline:
            execution=getattr(self,'execution',None)
            if execution and not getattr(self,'_stopping',False):execution.check(self.execution_task)
            try: msg = self.inbox.get(timeout=min(1, deadline - time.monotonic()))
            except queue.Empty:
                if self.proc.poll() is not None: raise RuntimeError('Codex 传输进程提前结束。')
                continue
            if msg.get('method') == 'turn/started':
                self.active_turn_id = msg.get('params', {}).get('turn', {}).get('id')
            if self.pending_turn_start_id is not None and msg.get('id') == self.pending_turn_start_id:
                self.pending_turn_start_id = None
                self.active_turn_id = msg.get('result', {}).get('turn', {}).get('id', self.active_turn_id)
            if msg.get('method') == 'turn/completed':
                self.last_turn_event = msg
            if msg.get('method') == 'item/tool/call' and 'id' in msg:
                params = msg['params']
                self.validate_tool_rpc(params)
                result = self.dispatch(params['tool'], params['arguments'])
                self.tool_history[params['callId']] = result
                if (getattr(self,'stop_on_submission',False) and self.accepted is not None
                        and not getattr(self,'submission_closed',False)):
                    self.submission_closed=True
                    self.submission_completion={'at_utc':now(),'elapsed_seconds':time.monotonic()-self.started,
                        'tool':params['tool'],'call_id':params['callId'],
                        'scope':'Accepted stage artifact only; later mathematical gates remain required.'}
                    append(self.logs/'controller.jsonl',{'event':'stage_submission_completed',**self.submission_completion})
                response = {'id': msg['id'], 'result': {'success': 'error' not in result,
                    'contentItems': [{'type': 'inputText', 'text': json.dumps(result, ensure_ascii=False)}]}}
                self.proc.stdin.write(json.dumps(response, ensure_ascii=False) + '\n'); self.proc.stdin.flush()
            elif 'method' in msg and 'id' in msg:
                response = {'id': msg['id'], 'error': {'code': -32601, 'message': 'Not allowed by pilot harness'}}
                self.proc.stdin.write(json.dumps(response) + '\n'); self.proc.stdin.flush()
            if predicate(msg): return msg
        raise TimeoutError('本轮达到预先设置的时间限制。')

    def rpc(self, method: str, params: dict, seconds: float = 30) -> dict:
        rid = self.send(method, params)
        msg = self.receive_until(lambda m: m.get('id') == rid, time.monotonic() + seconds)
        if 'error' in msg: raise RuntimeError(json.dumps(msg['error'], ensure_ascii=False))
        return msg.get('result', {})

    def start_process(self) -> None:
        lock = load_lock()
        self.network_proxy = system_https_proxy()
        port = self.start_relay()
        (self.logs / 'network-routing.json').write_text(json.dumps({'upstream': 'chatgpt.com:443',
            'system_https_proxy': self.network_proxy, 'tools_network_access': False,
            'carrier_peer': f'127.0.0.1:{port}', 'carrier_os_sandbox': self.strict}, indent=2))
        state = self.work / 'state'
        for name in ['auth.json', 'models_cache.json']:
            source = __import__('runtime_config').auth_home() / name
            if source.exists(): shutil.copyfile(source, state / name); os.chmod(state / name, 0o600)
        if self.strict and (state / 'models_cache.json').exists():
            cache = json.loads((state / 'models_cache.json').read_text())
            cache['models'] = [m for m in cache['models'] if m.get('slug') == MODEL]
            if not cache['models']:
                raise ValueError('本机缓存中缺少指定模型，禁止改用其他模型。')
            (state / 'models_cache.json').write_text(json.dumps(cache))
        config = f'''model = "{MODEL}"
model_provider = "pilot-relay"
model_reasoning_effort = "high"
web_search = "disabled"
project_doc_max_bytes = 0
[model_providers.pilot-relay]
name = "Yui isolated subscription carrier"
base_url = "http://127.0.0.1:{port}"
wire_api = "responses"
requires_openai_auth = true
supports_websockets = false
[features]
apps = false
plugins = false
memories = false
hooks = false
multi_agent = false
multi_agent_v2 = false
shell_tool = false
shell_snapshot = false
view_image = false
image_generation = false
computer_use = false
browser_use = false
in_app_browser = false
daemon_auto_start = false
enable_request_compression = false
recommended_plugins = false
tool_suggest = false
'''
        if self.strict:
            # A separate network sandbox makes the carrier's only reachable
            # peer its own loopback relay. Authentication refresh is not an
            # unrestricted fallback; expired credentials must fail visibly.
            config = config.replace('project_doc_max_bytes = 0\n',
                'project_doc_max_bytes = 0\nmodel_auto_compact_token_limit = 1000000\n')
        (state / 'config.toml').write_text(config)
        (self.logs / 'effective-config.toml').write_text(config)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(self.work / 'home'), 'CODEX_HOME': str(state),
               'TMPDIR': str(self.work / 'tmp'), 'LANG': 'en_US.UTF-8'}
        if self.network_proxy:
            host, proxy_port = self.network_proxy
            env.update({'HTTPS_PROXY': f'http://{host}:{proxy_port}', 'HTTP_PROXY': f'http://{host}:{proxy_port}',
                        'NO_PROXY': '127.0.0.1,localhost'})
        err = (self.logs / 'transport-stderr.log').open('w')
        command = [lock['codex']['binary_path'], 'app-server', '--stdio']
        if self.strict:
            profile = self.work / 'transport.sb'
            profile.write_text(transport_sandbox_profile(self.work, port))
            shutil.copyfile(profile, self.logs / 'transport-sandbox.sb')
            command = ['/usr/bin/sandbox-exec', '-f', str(profile)] + command
        self.proc = subprocess.Popen(command,
            cwd=self.work / 'input', env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=err, text=True, bufsize=1, start_new_session=True)
        from run_resources import register_child
        register_child(self.work, self.proc, 'model-carrier')
        if getattr(self,'execution',None):
            self.execution.register_process(self.proc,'model-carrier',self.execution_task)

        def reader():
            for line in self.proc.stdout:
                try:
                    msg = json.loads(line)
                    append(self.logs / 'events.jsonl', msg)
                    self.inbox.put(msg)
                except json.JSONDecodeError:
                    append(self.logs / 'invalid-events.jsonl', {'text': line})
        self.reader_thread=threading.Thread(target=reader, daemon=True)
        self.reader_thread.start()
        self.rpc('initialize', {'clientInfo': {'name': 'yui', 'version': self.harness_version},
                                'capabilities': {'experimentalApi': True}})
        self.proc.stdin.write(json.dumps({'method': 'initialized'}) + '\n'); self.proc.stdin.flush()

    def solve_turns(self, user: str, *, smoke: bool = False) -> dict:
        """Keep the same isolated history until acceptance or the fixed deadline."""
        self.allowed_user_messages.add(user)
        self.initial_user_message = user
        self.started = time.monotonic()
        deadline = self.started + self.timeout
        message = user
        continuation_prompt = getattr(self, 'continuation_prompt', CONTINUE_PROMPT)
        while True:
            started = self.rpc('turn/start', {'threadId': self.thread_id, 'model': MODEL, 'effort': 'high',
                'input': [{'type': 'text', 'text': message}], 'environments': []},
                seconds=min(30, max(0.001, deadline - time.monotonic())))
            self.active_turn_id = started.get('turn', {}).get('id')
            done = self.receive_until(lambda m: m.get('method') == 'turn/completed'
                or getattr(self,'submission_closed',False), deadline)
            if getattr(self,'submission_closed',False):
                try:
                    self.drain_relay_streams()
                    self.interrupt_active_turn(reason='ACCEPTED_ARTIFACT')
                except Exception as error:self.post_acceptance_closing_error=type(error).__name__+': '+str(error)
                event=self.last_turn_event or done
                self.turn_results.append(event)
                return event
            self.turn_results.append(done)
            turn = done.get('params', {}).get('turn', {})
            if turn.get('status') != 'completed':
                raise RuntimeError('模型回合未正常完成：' + json.dumps(turn.get('error'), ensure_ascii=False))
            if smoke or self.accepted or not self.strict:
                return done
            if time.monotonic() >= deadline:
                raise TimeoutError('本轮达到预先设置的时间限制。')
            self.continuation_count += 1
            append(self.logs / 'controller.jsonl', {'event': 'continue_after_unaccepted_turn',
                'continuation_number': self.continuation_count,
                'previous_turn_id': turn.get('id'), 'prompt': continuation_prompt,
                'elapsed_seconds': time.monotonic() - self.started})
            self.allowed_user_messages.add(continuation_prompt)
            message = continuation_prompt

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
        if (self.last_turn_event and self.last_turn_event.get('params', {}).get('turn', {}).get('id')
                == self.active_turn_id):
            return
        record=self.logs/('deadline.jsonl' if reason=='DEADLINE' else 'cancellation.jsonl')
        append(record, {'event': 'interrupt_requested','reason':reason,
            'thread_id': self.thread_id, 'turn_id': self.active_turn_id,
            'request_number': self.api_calls})
        self.cancelled_requests[self.api_calls] = {'thread_id': self.thread_id,
            'turn_id': self.active_turn_id, 'interrupt_requested_at_utc': now(),'reason':reason}
        self.rpc('turn/interrupt', {'threadId': self.thread_id, 'turnId': self.active_turn_id}, seconds=15)
        if not (self.last_turn_event and self.last_turn_event.get('params', {}).get('turn', {}).get('id')
                == self.active_turn_id):
            self.receive_until(lambda m: m.get('method') == 'turn/completed'
                and m.get('params', {}).get('turn', {}).get('id') == self.active_turn_id,
                time.monotonic() + 15)
        append(record, {'event': 'interrupt_completed','reason':reason,
            'thread_id': self.thread_id, 'turn_id': self.active_turn_id,
            'status': self.last_turn_event.get('params', {}).get('turn', {}).get('status')})

    def run(self, *, smoke: bool = False) -> dict:
        result = {'case': self.case, 'suite': self.suite, 'model': MODEL, 'effort': 'high', 'status': 'STARTING',
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
            t = self.rpc('thread/start', {'model': MODEL, 'modelProvider': 'pilot-relay',
                'allowProviderModelFallback': False, 'ephemeral': True, 'cwd': str(self.work / 'input'),
                'approvalPolicy': 'never', 'sandbox': 'read-only', 'baseInstructions': self.system,
                'developerInstructions': '', 'dynamicTools': self.tools, 'environments': [], 'experimentalRawEvents': True})
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
                self.rpc('turn/start', {'threadId': self.thread_id, 'effort': 'high',
                    'input': [{'type': 'text', 'text': AUDIT_QUESTION}], 'environments': []})
                self.receive_until(lambda m: m.get('method') == 'turn/completed', time.monotonic() + 180)
                result['environment_audit_status'] = 'COMPLETED'
        except Exception as e:
            result['status'] = 'TIMEOUT' if isinstance(e, TimeoutError) else 'ERROR'
            result['error'] = str(e)
            result['failure_phase'] = self.phase
        finally:
            result['continuation_count'] = self.continuation_count
            result['proof_turns'] = self.turn_results
            result.update({'finished_at_utc': now(), 'api_calls': self.api_calls, 'lean_calls': self.lean_calls})
            if self.started: result['total_elapsed_seconds'] = time.monotonic() - self.started
            if self.proc:
                self.proc.terminate()
                try: self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired: self.proc.kill(); self.proc.wait()
            if self.relay: self.relay.shutdown()
            # Authentication is ephemeral and never part of the experiment artifact.
            for name in ['auth.json', 'models_cache.json']:
                (self.work / 'state' / name).unlink(missing_ok=True)
            (self.logs / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        return result

