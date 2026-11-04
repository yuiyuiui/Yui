"""Shared test paths and synthetic profiles; never imported by the runtime."""
from pathlib import Path
import sys
import test_resources  # Install only inside the explicitly owned cleanup runner.

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
LEAN = CORE / 'nl02lean'
FIXTURES = TESTS / 'fixtures'

# Every test can be selected independently; no earlier test import is required.
for directory in (CORE / 'nl0/scripts', LEAN / 'scripts', TESTS / 'tooling'):
    value = str(directory)
    if value not in sys.path:
        sys.path.insert(0, value)

PROFILES={'nl0':{'id':'gpt-6.1-sol','reasoning_effort':'high','speed':'standard','automatic_fallback':False},
          'lean':{'id':'gpt-6-luna','reasoning_effort':'medium','speed':'standard','automatic_fallback':False}}

# A missed controller mock must fail the software test before authentication,
# process launch or provider access, rather than consume a real model request.
# Configuration tests explicitly mock Popen; local protocol tests replace the
# launch method with their deterministic local carrier.
import run_pilot as _carrier
import subprocess as _subprocess


class LiveModelAttemptBlocked(BaseException):
    """Fail fast outside ordinary retained-error handling; never a runtime policy."""


_original_popen=_subprocess.Popen
_original_start=_carrier.Trial.start_process
_original_pause=_carrier.Trial.pause_error


def _offline_start(stage):
    if _subprocess.Popen is _original_popen:
        stage._test_live_model_blocked=True
        raise LiveModelAttemptBlocked('Software test attempted an unmocked model carrier. Supply a deterministic stage or local protocol fixture.')
    return _original_start(stage)


def _offline_pause(stage,*args,**kwargs):
    if getattr(stage,'_test_live_model_blocked',False):
        raise LiveModelAttemptBlocked('Unmocked model launch blocked before service access; this is a test-isolation failure.')
    return _original_pause(stage,*args,**kwargs)


_carrier.Trial.start_process=_offline_start
_carrier.Trial.pause_error=_offline_pause

import fault_control as _faults
_original_gate_pause=_faults.Gate.pause


def _offline_gate_pause(gate,*args,**kwargs):
    active=sys.exception()
    if isinstance(active,LiveModelAttemptBlocked):raise active
    return _original_gate_pause(gate,*args,**kwargs)


_faults.Gate.pause=_offline_gate_pause

# Notification tests must mock the command explicitly. A missed error-path mock
# must not enqueue a real user message, including when a test inherits an owner ID.
_original_run=_subprocess.run
_original_notification=_faults.queue_notification


def _offline_notification(thread,message):
    if thread and _subprocess.run is _original_run:
        raise LiveModelAttemptBlocked('Software test attempted a real owner notification. Mock the local queue command or inject a notifier.')
    return _original_notification(thread,message)


_faults.queue_notification=_offline_notification
