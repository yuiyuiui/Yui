"""Replace the live provider with the local native protocol fixture below the real Yui CLI."""
from pathlib import Path
import json
import subprocess
import sys
from unittest.mock import patch

tests=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(tests))
import harness_support
import queue_controller
import fault_control
import yui


def launch(path,root):
    with (root/'fixture.log').open('w') as log:
        return subprocess.Popen([sys.executable,'-B',str(tests/'tooling/basis_path_control.py'),
                                  str(path),mode],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)


def unexpected(gate,error,**kw):
    raise AssertionError(str(error)[:1500]+' '+(gate.root/'fixture.log').read_text()[:4000])


if __name__=='__main__':
    mode=sys.argv.pop(1)
    with patch.object(queue_controller,'launch_case',launch),patch.object(fault_control.Gate,'pause',unexpected):
        raise SystemExit(yui.main())
