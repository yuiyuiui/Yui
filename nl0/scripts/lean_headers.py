"""Parse Lean headers with the selected compiler without loading their imports."""
from contextlib import contextmanager, suppress
from functools import lru_cache
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time

from execution_state import capture_process, current, terminate_owned
import native_workspace
import pilot_common


def describe(source):
    from runtime_config import load_lock
    return _description(load_lock()['lean']['binary_sha256'],source)


@lru_cache(maxsize=64)
def _description(_binary_sha256,source):
    with parser() as parse:
        [result]=parse([source])
    return result


@contextmanager
def parser(*, deadline=None):
    """One isolated Lean process for successive batches of a dependency scan."""
    from runtime_config import load_lock

    with native_workspace.temporary('yui-lean-headers-') as work:
        for name in ('home','tmp','input','output'):
            (work/name).mkdir()
        program=work/'input/LeanHeaders.lean'
        shutil.copyfile(Path(__file__).with_name(program.name),program)
        profile=work/'sandbox.sb'
        profile.write_text(pilot_common.sandbox_profile(work,library_paths=[]))
        binary=Path(load_lock()['lean']['local_path'])/'bin/lean'
        recorder,task=current()
        with (work/'output/parser.stderr').open('w+b') as stderr, selectors.DefaultSelector() as ready:
            process=subprocess.Popen(['/usr/bin/sandbox-exec','-f',str(profile),str(binary),'--run',str(program)],
                cwd=work/'output',env=pilot_common.lean_env(work,library_paths=[]),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=stderr,start_new_session=True)
            owner={'pid':process.pid,'pgid':process.pid,'started':None}
            registered=False
            try:
                native_workspace.record(work,confirmed=False,phase='lean-header-parser-started',process=owner)
                owner=(recorder.register_process(process,'lean-header-parser',task,private_group=True)
                       if recorder else capture_process(process,private_group=True))
                registered=recorder is not None
                ready.register(process.stdout,selectors.EVENT_READ)
                buffer=bytearray()

                def parse(sources):
                    names=[]
                    for index,source in enumerate(sources):
                        path=work/'input'/f'unit-{index}.lean'
                        path.write_bytes(source.encode())
                        names.append(str(path))
                    process.stdin.write((json.dumps(names)+'\n').encode())
                    process.stdin.flush()
                    until = min(deadline, time.monotonic()+30) if deadline is not None else time.monotonic()+30
                    while b'\n' not in buffer:
                        if recorder:
                            recorder.check(task)
                        remaining=until-time.monotonic()
                        if remaining <= 0:
                            raise ValueError('Lean header parser exceeded its time limit')
                        if not ready.select(min(.2,remaining)):
                            continue
                        chunk=os.read(process.stdout.fileno(),65536)
                        if not chunk:
                            stderr.seek(0)
                            raise ValueError('Lean header parser exited: '+stderr.read(4000).decode(errors='replace'))
                        buffer.extend(chunk)
                    end=buffer.index(b'\n')
                    line=bytes(buffer[:end])
                    del buffer[:end+1]
                    result=json.loads(line)
                    if not isinstance(result,list) or len(result)!=len(names):
                        raise ValueError('Lean header parser returned an invalid batch')
                    return result

                yield parse
            finally:
                with suppress(OSError):
                    process.stdin.close()
                with suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=.4)
                confirmed=(recorder.stop_process(process) if registered else terminate_owned(process,owner))
                process.stdout.close()
                native_workspace.record(work,confirmed=confirmed,phase='lean-header-parser-exit',
                                        process=owner,exit_code=process.returncode)
                if not confirmed:
                    raise native_workspace.unconfirmed('Lean header parser cleanup could not be confirmed',work)
