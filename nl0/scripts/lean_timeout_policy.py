"""Diagnose actual translation wall timeouts and apply the workflow's bounded allowance."""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time

import runtime_config

active = ContextVar('translation_lean_check', default=None)
suppressed = ContextVar('translation_lean_check_suppressed', default=False)
REVIEW_PHASE = 'interface-lean-timeout-diagnosis'


@lru_cache(maxsize=1)
def rules():
    from workflow_execution import block_module
    return block_module(runtime_config.CORE / 'workflow', 'lean_limits')


@contextmanager
def scope(root, budget, *, key='', deadline=None, kind='local'):
    binding = (Path(root), budget, key, deadline, kind) if root is not None else None
    token = active.set(binding)
    suppression = suppressed.set(root is None)
    try:
        yield
    finally:
        active.reset(token)
        suppressed.reset(suppression)


@contextmanager
def whole_file_scope(root, *, key):
    """Use a separate whole-file ladder, retaining the enclosing budget/deadline.

    A stable operation key keeps the allowance after a code repair. Explicitly
    disabled/direct and diagnostic contexts must not acquire new model work.
    """
    if suppressed.get():
        yield
        return
    parent = active.get()
    with scope(parent[0] if parent else root, parent[1] if parent else None,
               key=key, deadline=parent[3] if parent else None, kind='whole_file'):
        yield


def stage_scope(stage, key=''):
    if getattr(stage, 'instruction_arm', None) != 'yui' or stage.mode == REVIEW_PHASE:
        return scope(None, None)
    if active.get() is None and stage.mode not in {'proof', 'interface', 'plan'}:
        return nullcontext()
    end = (getattr(stage, 'started', None) or time.monotonic()) + stage.timeout if stage.timeout is not None else None
    return scope(stage.logs / 'lean-timeouts', stage.budget, key=key, deadline=end)


def ceiling(kind='local'):
    initial, _, maximum = rules().limits(kind)
    try:
        configured = runtime_config.configured_timeout('whole_file' if kind == 'whole_file' else 'native')
    except KeyError:
        configured = initial  # Older frozen configurations have no whole-file field.
    return configured if configured is not None and configured < initial else maximum


PROMPT = """Inspect the exact Candidate.lean and native.json (including the compiler output) for
this one native wall timeout. Locate the expensive declaration with a line number and a verbatim
source quote. Look for unbounded search, implicit argument unfolding, over-broad simplification,
instance synthesis or other avoidable elaboration before attributing cost to volume. Explain
the evidence and give one concrete next action. Use workload_only only when the remaining cost
is explained by the workload and you found no obvious implementation problem. A silent compiler,
file length or elapsed time alone does not establish that. Use code_issue for a located problem
or uncertain for insufficient evidence. Submit only the diagnosis. The controller sets limits."""


def review_contract(source, native):
    import artifact_protocol as protocol
    schema = protocol.obj({'category': {'enum': list(rules().CATEGORIES), 'type': 'string'},
                           'line': {'type': 'integer', 'minimum': 1}, 'quote': protocol.TEXT,
                           'reason': protocol.TEXT, 'next_action': protocol.TEXT})
    lines = source.splitlines()
    def validate(value):
        n = value['line']
        if not 1 <= n <= len(lines) or not value['quote'].strip() or value['quote'] not in lines[n-1]:
            raise ValueError('Quote the actual Lean source on the supplied one-based line')
        compiler = native.get('stdout', '') + '\n' + native.get('stderr', '')
        if value['category'] == 'workload_only' and re.search(r'(?im)^.*:\s*error\s*:', compiler):
            raise ValueError('A reported Lean error needs a code diagnosis before extending time')
        return {'scope': 'Diagnosis only'}
    return protocol.Contract(schema, validate)


def inspect_source(directory, source, native, budget, remaining, *, kind='local'):
    from clean_stage import ArtifactStage
    from controller_common import manifest
    from execution_health import require_review_execution
    from execution_state import activate, current
    from role_sessions import Sessions
    inputs = directory / 'inputs'
    manifest(inputs)
    sessions = Sessions()
    recorder, parent = current()
    task = 'lean-timeout-' + hashlib.sha256(str(directory).encode()).hexdigest()[:18]
    if recorder:
        recorder.task(task, parent_task=parent, state='PENDING')
    with budget.suspended() if budget is not None else nullcontext(), activate(recorder, task), scope(None, None):
        prompt = PROMPT
        if kind == 'whole_file':
            prompt += ('\nThis is a complete-file assembly, inspection or final basis-closure check. '
                       'Its allowance starts at 30 minutes and can increase by 15 minutes to 60. '
                       'Use workload_only after inspecting the actual source and compiler output '
                       'when no obvious repairable code issue was found and a long valid check is '
                       'plausible. This is a diagnosis of the next action, not a complexity proof. '
                       'Use uncertain if the examination itself is incomplete or its evidence '
                       'is unusable. A code_issue must return for repair at the current allowance.')
        stage = ArtifactStage(directory/'review', prompt, phase=REVIEW_PHASE, inputs=inputs/'inputs.json',
                              library=False, timeout=remaining, budget=budget,
                              validator=review_contract(source, native))
        with sessions.use('native-timeout-review'):
            result, _ = stage.execute()
        require_review_execution(result, stage.logs/'result.json', phase=REVIEW_PHASE)
        accepted = stage.logs/'accepted.json'
        value = json.loads(accepted.read_text())
        review_contract(source, native)(value)
        sessions.close_all('PRIVATE_WORK_DELIVERED', [accepted])
        return value


def run(file, requested, invoke):
    from controller_common import write
    from execution_state import current
    from strategy_bank import native_timeout_kind
    root, budget, key, deadline, kind = active.get()
    rule = rules()
    initial, _, maximum = rule.limits(kind)
    hard = min(ceiling(kind), runtime_config.time_limit(requested) or maximum)
    recorder, task = current()
    if recorder:
        recorder.check(task)
    identity = (kind, key or task or 'mechanical', Path(file).name if not key else '')
    directory = root / hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    state = directory / 'allowance.json'
    level = min(initial, hard)
    if state.is_file():
        stored = json.loads(state.read_text())
        saved = stored['seconds']
        if stored.get('kind') != kind or type(saved) not in (int, float) or not 0 < saved <= maximum:
            raise ValueError('Invalid saved native allowance')
        unchanged = stored['source_sha256'] == hashlib.sha256(Path(file).read_bytes()).hexdigest()
        if unchanged or key:
            level = min(max(level, saved), hard)
        if key and unchanged and stored.get('stopped') and hard == stored['ceiling']:
            prior = (directory / stored['stopped']).resolve()
            if prior.parent != directory.resolve() or not prior.name.startswith('attempt-'):
                raise ValueError('Invalid native timeout evidence location')
            result = json.loads((prior/'failure.json').read_text())
            result['timeout_replayed'] = True
            return result
    reviews = []
    while True:
        if recorder:
            recorder.check(task)
        left = deadline - time.monotonic() if deadline is not None else None
        if left is not None and left <= 0:
            raise TimeoutError('Translation stage deadline expired before the native check')
        result = invoke(min(level, left) if left is not None else level)
        if native_timeout_kind(result) != 'NATIVE_WALL_TIMEOUT':
            if reviews:
                result['timeout_reviews'] = reviews
            return result
        if left is not None and left <= level:
            result.update(error_kind='STAGE_DEADLINE', timeout_scope='stage')
            return result
        directory.mkdir(parents=True, exist_ok=True)
        attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=directory))
        inputs = attempt/'inputs'
        inputs.mkdir()
        source = Path(file).read_bytes().decode()
        (inputs/'Candidate.lean').write_text(source)
        write(inputs/'native.json', result)
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            raise TimeoutError('Translation stage deadline expired before timeout diagnosis')
        diagnosis = inspect_source(attempt, source, result, budget, remaining, kind=kind)
        review_contract(source, result)(diagnosis)
        action, following = rule.decision(level, diagnosis['category'], ceiling=hard, kind=kind)
        decision = dict(action=action, kind=kind, seconds=level, next_seconds=following,
                        diagnosis=diagnosis, evidence=str(attempt))
        write(attempt/'decision.json', decision)
        reviews.append(decision)
        allowance = dict(kind=kind, seconds=following, ceiling=hard, source_sha256=hashlib.sha256(source.encode()).hexdigest())
        if action != 'retry':
            result['timeout_reviews'] = reviews
            result['stderr'] += (f'\nNative timeout diagnosis ({action}, {level:g} seconds): '
                                 + diagnosis['reason'] + '\n' + diagnosis['next_action'])
            write(attempt/'failure.json', result)
            write(state, {**allowance, 'stopped': attempt.name})
            return result
        if Path(file).read_bytes() != source.encode():
            raise ValueError('Lean source changed after timeout review')
        write(state, allowance)
        level = following
