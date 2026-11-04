"""Test-only resource bookkeeping. Never imported by a runtime snapshot."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import threading

_installed = False


def install():
    global _installed
    root = os.environ.get('YUI_TEST_CLEANUP_ROOT')
    if _installed or not root:return
    _installed = True
    original = subprocess.Popen
    lock = threading.Lock()

    class OwnedPopen(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Use the unwrapped constructor for identity lookup: no recursion.
            try:
                query = original(['ps','-p',str(self.pid),'-o','pid=,ppid=,pgid=,stat=,lstart=,command='],
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                output, _ = query.communicate(timeout=3)
                fields = output.strip().split(None,9)
                if len(fields)==10:
                    row={'pid':int(fields[0]),'ppid':int(fields[1]),'pgid':int(fields[2]),
                        'stat':fields[3],'started':' '.join(fields[4:9]),'command':fields[9]}
                    with lock:
                        with (Path(root)/'processes.jsonl').open('a') as stream:
                            stream.write(json.dumps(row)+'\n')
            except (OSError,subprocess.SubprocessError,ValueError):
                pass  # Parent also observes the live process tree.
    subprocess.Popen = OwnedPopen


install()
