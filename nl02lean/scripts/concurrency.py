"""Role-scoped, case-local budgets. No subscription-cap guessing."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

import ir
from execution_state import current


def resolve(requested='auto', *, node_count=None, backend='isolated_codex_cli', known_limit=None):
    ir.need(known_limit is None or (type(known_limit) is int and known_limit > 0), 'invalid known backend limit')
    ir.need(node_count is None or (type(node_count) is int and node_count >= 0), 'invalid phase node count')
    if requested == 'auto':
        effective = node_count
        reason = 'awaiting current phase node count' if node_count is None else 'current phase node count'
        if effective is not None and known_limit is not None and effective > known_limit:
            effective = known_limit
            reason += ' constrained by confirmed backend hard limit'
    else:
        ir.need(not isinstance(requested, bool), 'concurrency must be auto or a positive integer')
        try:
            number = int(requested)
        except (TypeError, ValueError):
            raise ir.Invalid('concurrency must be auto or a positive integer')
        ir.need(str(number) == str(requested) and number > 0, 'concurrency must be auto or a positive integer')
        effective = min(number, known_limit) if known_limit is not None else number
        reason = 'user request constrained by confirmed backend hard limit' if effective != number else 'explicit user request'
    return {'requested': requested, 'effective': effective, 'backend': backend,
            'known_backend_limit': known_limit, 'reason': reason, 'node_count': node_count}


class Budget:
    """A bounded lane for one role; all lanes share the case execution ledger."""
    def __init__(self, configuration, *, execution=None, role='unspecified'):
        self.configuration = dict(configuration)
        self.execution = execution
        self.role = role
        self._lock = threading.Condition()
        self._private_width = 0
        self._local = threading.local()
        self._start = time.monotonic()
        self._active = self._peak = 0
        self._waiting = 0
        self._rows = []
        self._configurations = [{**self.configuration, 'started_offset_seconds': 0.}]

    def configure(self, node_count):
        """Resolve auto at a phase boundary; preserve an explicit numeric limit."""
        configuration = resolve(self.configuration['requested'], node_count=node_count,
            backend=self.configuration['backend'], known_limit=self.configuration['known_backend_limit'])
        with self._lock:
            if configuration != self.configuration:
                ir.need(self._active == self._waiting == 0, 'Cannot resize an active model lane')
                self.configuration = configuration
                self._configurations.append({**configuration, 'started_offset_seconds': time.monotonic()-self._start})
        if self.execution:
            self.execution.model_configuration(self.role, configuration)
        return configuration

    def __enter__(self):
        ir.need(not getattr(self._local, 'active', False), 'nested model-stage acquisition would deadlock')
        queued = time.monotonic()
        recorder, task = current()
        recorder = recorder or self.execution
        if recorder: recorder.activity(task,'WAITING_FOR_MODEL_SLOT')
        with self._lock:
            ir.need(self.configuration['effective'] and self.configuration['effective']>0,
                    'Resolve a nonempty phase node count before model dispatch')
            self._waiting += 1
            try:
                while self._active>=self.capacity():
                    self._lock.wait(.1)
                    if recorder:recorder.check(task)
                if recorder:recorder.check(task)
                self._active+=1
            finally:
                self._waiting-=1
        try:
            if recorder:recorder.model_slot(1,role=self.role)
        except BaseException:
            with self._lock:
                self._active-=1
                self._lock.notify_all()
            raise
        started=time.monotonic()
        with self._lock:
            self._peak=max(self._peak,self._active)
            row={'id':len(self._rows)+1,'queue_seconds':started-queued,
                 'started_offset_seconds':started-self._start,'finished_offset_seconds':None}
            self._rows.append(row)
        self._local.active=True
        self._local.row=row
        self._local.recorder=recorder
        return self

    def capacity(self):
        base=self.configuration['effective']
        if self.configuration['requested']!='auto':return base
        return min(base+self._private_width,self.configuration.get('known_backend_limit') or base+self._private_width)

    @contextmanager
    def private_batch(self, count):
        # The blocked public job already accounts for one slot in the base width.
        extra=max(0,count-1)
        with self._lock:
            self._private_width+=extra
            self._lock.notify_all()
        try:
            yield min(count,self.capacity())
        finally:
            with self._lock:
                self._private_width-=extra
                self._lock.notify_all()

    def __exit__(self, kind, value, traceback):
        if not getattr(self._local,'active',False):return
        with self._lock:
            self._local.row['finished_offset_seconds']=time.monotonic()-self._start
            self._local.row['raised']=kind.__name__ if kind else None
            self._active-=1
            self._lock.notify_all()
        self._local.active = False
        if self._local.recorder: self._local.recorder.model_slot(-1, role=self.role)

    @contextmanager
    def suspended(self):
        """A tool-blocked author keeps its session but lends its active slot."""
        held = getattr(self._local, 'active', False)
        if held:self.__exit__(None,None,None)
        try:
            yield
        finally:
            if held:self.__enter__()

    def report(self):
        with self._lock:
            return {**self.configuration, 'role': self.role, 'observed_peak_model_stages': self._peak,
                    'active_model_stages': self._active, 'model_stages': [dict(x) for x in self._rows],
                    'configuration_history': [dict(x) for x in self._configurations],
                    'summed_queue_seconds': sum(x['queue_seconds'] for x in self._rows),
                    'elapsed_seconds': time.monotonic() - self._start,
                    'scope': 'One controller/run; no distributed subscription-wide cap discovery.'}


class CaseBudgets:
    """Serial global work, then bounded local reviews or proofs per case."""
    def __init__(self, requested='auto', *, execution=None):
        self.serial = Budget(serial_configuration(), execution=execution, role='preparation_review')
        self.audit = Budget(resolve(requested), execution=execution, role='audit_r')
        self.proof = Budget(resolve(requested), execution=execution, role='proof')

    def report(self):
        return {'preparation_review': self.serial.report(), 'audit_r': self.audit.report(), 'proof': self.proof.report(),
                'proof_limit_applies_to': 'Auto uses each phase node count; explicit N caps local R reviews and local Lean proofs in separate phases; owner occupies no slot',
                'all_stage_accounting': 'One shared execution ledger includes all roles.'}


def serial_configuration():
    return {**resolve(1),'reason':'Phase policy: one author/review context per case, independent of the proof limit',
            'configured_by':'phase_policy'}


def serial_budget(budget=None):
    """Keep standalone reviewers serial too; do not borrow a proof-worker cap."""
    if budget is not None:
        ir.need(budget.configuration['effective'] == 1 and budget.role in {'unspecified','preparation_review'},
                'Preparation/review requires a serial non-proof budget')
        if budget.role=='unspecified':
            ir.need(budget.report()['active_model_stages']==0,'Cannot change the role of an active legacy budget')
            budget.role='preparation_review'
        return budget
    return Budget(serial_configuration(), role='preparation_review')
