"""Fresh bounded ps snapshots with small retained retry evidence, never raw argv."""
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime,timezone
from importlib.util import module_from_spec,spec_from_file_location
import os
from pathlib import Path
import subprocess
import uuid

_PATH=Path(__file__).resolve().parents[2]/'workflow/blocks/process_snapshots.py'
_SPEC=spec_from_file_location('yui_process_snapshot_rules',_PATH)
_rules=module_from_spec(_SPEC);_SPEC.loader.exec_module(_rules)
_history=ContextVar('yui_process_query_history',default=())
started=_rules.started
decision=_rules.decision


def history():return deepcopy(list(_history.get()))


def query(command, parse, *, check=True):
    def observe(value):
        from execution_state import current
        recorder,task=current()
        event={**deepcopy(value),'id':uuid.uuid4().hex,'at_utc':datetime.now(timezone.utc).isoformat(),
               'query':list(command),'timeout_seconds':list(_rules.TIMEOUTS),
               'run_id':recorder.state.get('run_id') if recorder else None,'task':task}
        _history.set((*_history.get(),event)[-128:])
        if recorder is not None and hasattr(recorder,'state'):
            with recorder.lock:
                rows=recorder.state.setdefault('process_query_recoveries',[])
                rows.append(event);recorder.dirty=True
    def fresh(limit):
        value=subprocess.run(command,capture_output=True,text=True,check=check,timeout=limit,
                             env=dict(os.environ,LC_ALL='C'))
        return parse(value)
    return _rules.retry(fresh,observe=observe)
