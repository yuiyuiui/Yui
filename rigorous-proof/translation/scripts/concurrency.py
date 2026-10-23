"""Role-scoped, case-local budgets. No subscription-cap guessing."""
from __future__ import annotations

import threading
import time

import ir
from execution_state import current


def resolve(requested='auto', *, backend='isolated_codex_cli', known_limit=None, fallback=2):
    ir.need(known_limit is None or (type(known_limit) is int and known_limit > 0), 'invalid known backend limit')
    ir.need(type(fallback) is int and fallback > 0, 'invalid concurrency fallback')
    if requested == 'auto':
        effective = known_limit if known_limit is not None else fallback
        reason = 'confirmed backend hard limit' if known_limit is not None else 'backend hard limit unavailable; disclosed fallback, not a maximum'
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
            'known_backend_limit': known_limit, 'reason': reason, 'fallback': fallback}


class Budget:
    """A bounded lane for one role; all lanes share the case execution ledger."""
    def __init__(self, configuration, *, execution=None, role='unspecified'):
        self.configuration = dict(configuration)
        self.execution = execution
        self.role = role
        self._slots = threading.BoundedSemaphore(configuration['effective'])
        self._lock = threading.Lock()
        self._local = threading.local()
        self._start = time.monotonic()
        self._active = self._peak = 0
        self._rows = []

    def __enter__(self):
        ir.need(not getattr(self._local, 'active', False), 'nested model-stage acquisition would deadlock')
        queued = time.monotonic()
        recorder, task = current()
        recorder = recorder or self.execution
        if recorder: recorder.activity(task,'WAITING_FOR_MODEL_SLOT')
        while not self._slots.acquire(timeout=.1):
            if recorder: recorder.check(task)
        try:
            if recorder: recorder.check(task)
            if recorder: recorder.model_slot(1, role=self.role)
        except BaseException:
            self._slots.release(); raise
        started = time.monotonic()
        with self._lock:
            self._active += 1
            self._peak = max(self._peak, self._active)
            row = {'id': len(self._rows) + 1, 'queue_seconds': started - queued,
                   'started_offset_seconds': started - self._start, 'finished_offset_seconds': None}
            self._rows.append(row)
        self._local.active = True
        self._local.row = row
        self._local.recorder = recorder
        return self

    def __exit__(self, kind, value, traceback):
        with self._lock:
            self._local.row['finished_offset_seconds'] = time.monotonic() - self._start
            self._local.row['raised'] = kind.__name__ if kind else None
            self._active -= 1
        self._local.active = False
        if self._local.recorder: self._local.recorder.model_slot(-1, role=self.role)
        self._slots.release()

    def report(self):
        with self._lock:
            return {**self.configuration, 'role': self.role, 'observed_peak_model_stages': self._peak,
                    'active_model_stages': self._active, 'model_stages': [dict(x) for x in self._rows],
                    'summed_queue_seconds': sum(x['queue_seconds'] for x in self._rows),
                    'elapsed_seconds': time.monotonic() - self._start,
                    'scope': 'One controller/run; no distributed subscription-wide cap discovery.'}


class CaseBudgets:
    """Serial preparation/review and independently bounded proof work per case."""
    def __init__(self, requested='auto', *, execution=None):
        self.serial = Budget(serial_configuration(), execution=execution, role='preparation_review')
        self.proof = Budget(resolve(requested), execution=execution, role='proof')

    def report(self):
        return {'preparation_review': self.serial.report(), 'proof': self.proof.report(),
                'proof_limit_applies_to': 'Lean proof jobs only; Python owner occupies no slot',
                'all_stage_accounting': 'One shared execution ledger includes both roles.'}


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
