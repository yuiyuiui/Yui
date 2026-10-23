"""One disclosed, run-local model-stage budget. No subscription-cap guessing."""
from __future__ import annotations

import threading
import time

import ir


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
    """Context-manager replacement for the previous shared semaphore.

    Every actual model stage, including a retry or diagnostic stage, must use
    this same instance. Source lookup/compiler work is not a model stage.
    """
    def __init__(self, configuration):
        self.configuration = dict(configuration)
        self._slots = threading.BoundedSemaphore(configuration['effective'])
        self._lock = threading.Lock()
        self._local = threading.local()
        self._start = time.monotonic()
        self._active = self._peak = 0
        self._rows = []

    def __enter__(self):
        ir.need(not getattr(self._local, 'active', False), 'nested model-stage acquisition would deadlock')
        queued = time.monotonic()
        self._slots.acquire()
        started = time.monotonic()
        with self._lock:
            self._active += 1
            self._peak = max(self._peak, self._active)
            row = {'id': len(self._rows) + 1, 'queue_seconds': started - queued,
                   'started_offset_seconds': started - self._start, 'finished_offset_seconds': None}
            self._rows.append(row)
        self._local.active = True
        self._local.row = row
        return self

    def __exit__(self, kind, value, traceback):
        with self._lock:
            self._local.row['finished_offset_seconds'] = time.monotonic() - self._start
            self._local.row['raised'] = kind.__name__ if kind else None
            self._active -= 1
        self._local.active = False
        self._slots.release()

    def report(self):
        with self._lock:
            return {**self.configuration, 'observed_peak_model_stages': self._peak,
                    'active_model_stages': self._active, 'model_stages': [dict(x) for x in self._rows],
                    'summed_queue_seconds': sum(x['queue_seconds'] for x in self._rows),
                    'elapsed_seconds': time.monotonic() - self._start,
                    'scope': 'One controller/run; no distributed subscription-wide cap discovery.'}
