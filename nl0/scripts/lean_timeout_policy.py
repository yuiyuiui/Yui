"""Select a native allowance without delegating execution control to a model."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
import time

import runtime_config

whole_file = ContextVar('whole_file_lean', default=False)
stage_deadline = ContextVar('lean_stage_deadline', default=None)


@contextmanager
def whole_file_scope():
    token = whole_file.set(True)
    try:
        yield
    finally:
        whole_file.reset(token)


@contextmanager
def stage_scope(stage):
    old = stage_deadline.get()
    end = (stage.started or time.monotonic()) + stage.timeout if stage.timeout is not None else None
    token = stage_deadline.set(min(old,end) if old is not None and end is not None else old or end)
    try:
        yield
    finally:
        stage_deadline.reset(token)


@lru_cache(maxsize=1)
def rules():
    from workflow_execution import block_module
    return block_module(runtime_config.CORE/'workflow','lean_limits')


def probe_seconds():
    return rules().PROBE_SECONDS


def allowance(requested=None):
    scope = 'whole_file' if whole_file.get() else 'native'
    try: configured = runtime_config.configured_timeout(scope)
    except KeyError:
        if scope!='whole_file':raise
        configured = rules().WHOLE_FILE_SECONDS
    deadline = stage_deadline.get()
    remaining = deadline-time.monotonic() if deadline is not None else None
    if remaining is not None and remaining <= 0:
        raise TimeoutError('Stage deadline elapsed before the Lean check')
    return rules().allowance(configured,runtime_config.time_limit(requested),remaining)
