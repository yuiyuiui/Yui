"""Shared test paths and synthetic profiles; never imported by the runtime."""
from copy import deepcopy
from pathlib import Path
import os
import sys
import test_resources  # Install only inside the explicitly owned cleanup runner.

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
LEAN = CORE / 'nl02lean'
FIXTURES = Path(os.environ.get('YUI_TEST_FIXTURE_ROOT',str(TESTS/'fixtures')))

# Every test can be selected independently; no earlier test import is required.
for directory in (CORE / 'nl0/scripts', LEAN / 'scripts', TESTS / 'tooling'):
    value = str(directory)
    if value not in sys.path:
        sys.path.insert(0, value)

PROFILES={'nl0':{'id':'gpt-6.1-sol','reasoning_effort':'high','speed':'standard','automatic_fallback':False},
          'lean':{'id':'gpt-6-luna','reasoning_effort':'medium','speed':'standard','automatic_fallback':False}}


def elementary_outline(inferences):
    return {row['id']: {'steps':[{'conclusion':'Derive '+row['output']+' in this equality fixture.',
                'uses':list(row['inputs']), 'source_spans':[]}]} for row in inferences}


def addition_split(graph):
    """Extract the additive-identity argument from the closed-addition fixture."""
    consumer = deepcopy(next(row for row in graph['inferences'] if row['id']=='R002'))
    producer = {**deepcopy(consumer),'id':'R003','inputs':[],'output':'N002','locals':[],
                'applications':[],'argument':[{
                    'id':'S001','text':'The additive identity gives a+0=a.', 'objects':['a','0'],
                    'uses':[], 'uses_local':[], 'produces':[], 'introduces':[], 'discharges':[],
                }]}
    if consumer['applications']:
        applications = consumer['applications']
        producer['applications'] = [{**row,'at':'S001'} for row in applications]
        moved = list(dict.fromkeys(row['input'] for row in applications))
        producer['inputs'] = moved
        producer['argument'][0].update(uses=moved,
            text='Specialize the supplied additive identity at a to obtain a+0=a.')
        consumer['applications'] = []
        consumer['inputs'] = [pid for pid in consumer['inputs'] if pid not in moved]
    consumer['locals'] = []
    consumer['inputs'].append('N002')
    last = consumer['argument'][-1]
    last.update(id='S001',uses=[*last['uses'],'N002'],uses_local=[],objects=['a','b','0'],
        text='N002 gives a+0=a. By symmetry N001 gives a=b, hence a+0=b.')
    consumer['argument'] = [last]
    premise = {'id':'N002','kind':'internal','statement':'a+0=a.','origin':'The first part of R002.',
               'definitions':[],'binders':[],'objects':['a','0']}
    rows=[producer,consumer]
    return {'inference':'R002','propositions':[premise],'inferences':rows,
            'proof_outline':elementary_outline(rows)}


def native_available():
    import shutil
    binary=os.environ.get('YUI_CODEX_BINARY') or shutil.which('codex')
    return bool(binary and Path(binary).is_file())

# A missed controller mock must fail the software test before authentication,
# process launch or provider access, rather than consume a real model request.
# Configuration tests explicitly mock Popen; local protocol tests replace the
# launch method with their deterministic local carrier.
import native_carrier as _carrier
import subprocess as _subprocess


class LiveModelAttemptBlocked(BaseException):
    """Fail fast outside ordinary retained-error handling; never a runtime policy."""


_original_popen=_subprocess.Popen
_original_start=_carrier.NativeCarrier.start_process
_original_pause=_carrier.NativeCarrier.pause_error


def _offline_start(stage):
    if _subprocess.Popen is _original_popen:
        stage._test_live_model_blocked=True
        raise LiveModelAttemptBlocked('Software test attempted an unmocked model carrier. Supply a deterministic stage or local protocol fixture.')
    return _original_start(stage)


def _offline_pause(stage,*args,**kwargs):
    if getattr(stage,'_test_live_model_blocked',False):
        raise LiveModelAttemptBlocked('Unmocked model launch blocked before service access; this is a test-isolation failure.')
    return _original_pause(stage,*args,**kwargs)


_carrier.NativeCarrier.start_process=_offline_start
_carrier.NativeCarrier.pause_error=_offline_pause

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


def _offline_notification(thread,message,**kwargs):
    if thread and _subprocess.run is _original_run:
        raise LiveModelAttemptBlocked('Software test attempted a real owner notification. Mock the local queue command or inject a notifier.')
    return _original_notification(thread,message,**kwargs)


_faults.queue_notification=_offline_notification

def direct_controller_job(*args, **kwargs):
    """Exercise the shared continuation controller without the public stage graph."""
    from unittest.mock import patch
    import jobs
    bound=jobs.runtime_bindings()
    previous=[row for row in bound if not Path(row['path']).is_relative_to(CORE/'workflow')]
    with patch.object(jobs,'runtime_bindings',return_value=previous):
        return jobs.prepare(*args,**kwargs)
