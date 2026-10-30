"""Pinned Lean invocation and the native, offline execution boundary."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from runtime_config import load_lock
from execution_state import current, Cancelled, terminate_owned, identity




def lean_paths(extra: list[Path] = ()) -> list[str]:
    lock = load_lock()
    ml = Path(lock['mathlib']['local_path'])
    paths = [str(p) for p in extra] + [str(ml / '.lake/build/lib/lean')]
    paths += [str((ml / '.lake/packages' / p['name']).resolve() / '.lake/build/lib/lean')
              for p in lock['dependencies']]
    return paths


def lean_env(work: Path, extra: list[Path] = ()) -> dict[str, str]:
    lock = load_lock()
    return {'PATH': str(Path(lock['lean']['local_path']) / 'bin') + ':/usr/bin:/bin',
            'HOME': str(work / 'home'), 'TMPDIR': str(work / 'tmp'),
            'LEAN_PATH': ':'.join(lean_paths(extra)), 'LANG': 'en_US.UTF-8'}


def sandbox_profile(work: Path) -> str:
    lock = load_lock()
    ml = Path(lock['mathlib']['local_path'])
    roots = [Path(lock['lean']['local_path']), ml]
    roots += [(ml / '.lake/packages' / p['name']).resolve() for p in lock['dependencies']]
    roots += [work / 'input', work / 'output', work / 'tmp', work / 'home']
    read = ' '.join('(subpath ' + json.dumps(str(p.resolve())) + ')' for p in roots)
    parents = {str(q) for p in roots for q in p.resolve().parents}
    parents.update(['/', '/usr', '/private', '/private/var', '/private/var/db'])
    read += ' ' + ' '.join('(literal ' + json.dumps(q) + ')' for q in sorted(parents))
    return '\n'.join([
        '(version 1)', '(allow default)', '(deny network*)',
        '(deny process-exec (require-not (literal ' + json.dumps(str(Path(lock['lean']['local_path']) / 'bin/lean')) + ')))',
        '(deny file-read-data (require-not (require-any (subpath "/System") (subpath "/usr/lib") (subpath "/usr/share") '
        '(literal "/dev/null") (literal "/dev/random") (literal "/dev/urandom") '
        '(subpath "/private/var/db/dyld") (literal "/private/etc/localtime") ' + read + ')))',
        '(deny file-write* (require-not (require-any (literal "/dev/null") (subpath ' + json.dumps(str((work / 'output').resolve())) + ') '
        '(subpath ' + json.dumps(str((work / 'tmp').resolve())) + '))))',
    ]) + '\n'


def transport_sandbox_profile(work: Path) -> str:
    """Restrict native Codex files/processes; Codex owns outbound model connections."""
    binary = Path(load_lock()['codex']['binary_path']).resolve()
    roots = [binary.parent, work.resolve()]
    read = ' '.join('(subpath ' + json.dumps(str(p)) + ')' for p in roots)
    parents = {str(q) for p in roots for q in p.parents}
    parents.update(['/', '/usr', '/private', '/private/var', '/private/var/db'])
    read += ' ' + ' '.join('(literal ' + json.dumps(q) + ')' for q in sorted(parents))
    write = ' '.join('(subpath ' + json.dumps(str((work / name).resolve())) + ')'
                     for name in ['state', 'home', 'tmp'])
    return '\n'.join([
        '(version 1)', '(allow default)',
        '(deny network-inbound)', '(deny network-bind)',
        '(deny process-exec (require-not (literal ' + json.dumps(str(binary)) + ')))',
        '(deny file-read-data (require-not (require-any (subpath "/System") '
        '(subpath "/usr/lib") (subpath "/usr/share") (subpath "/private/var/db/dyld") (subpath "/private/etc/ssl") '
        '(literal "/dev/null") (literal "/dev/random") (literal "/dev/urandom") '
        '(literal "/private/etc/localtime") ' + read + ')))',
        '(deny file-write* (require-not (require-any (literal "/dev/null") ' + write + ')))',
    ]) + '\n'


def run_lean(file: Path, work: Path, *, extra: list[Path] = (), sandbox: bool = True,
             output: Path | None = None, timeout: float | None = None) -> dict:
    timeout = __import__('runtime_config').native_timeout(timeout)
    lock = load_lock()
    for name in ['home', 'tmp', 'output']:
        (work / name).mkdir(parents=True, exist_ok=True)
    cmd = [str(Path(lock['lean']['local_path']) / 'bin/lean'), '-R', str(file.parent), '-j', '1']
    if output: cmd += ['-o', str(output)]
    cmd += [str(file)]
    if sandbox:
        profile = work / 'sandbox.sb'
        profile.write_text(sandbox_profile(work))
        cmd = ['/usr/bin/sandbox-exec', '-f', str(profile)] + cmd
    started = time.monotonic()
    recorder, task = current()
    if recorder:
        recorder.check(task)
        timeout = recorder.remaining(timeout)
    from run_resources import MARKER, register_workspace, register_child
    if (recorder and not (work/MARKER).exists() and
        work.resolve().parent == Path(__import__('tempfile').gettempdir()).resolve()):
        register_workspace(work, recorder.root)
    check = recorder.lean_started(task,file) if recorder else None
    process = None; owner = None
    try:
        process = subprocess.Popen(cmd, cwd=work/'output', env=lean_env(work,extra),
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        owner = recorder.register_process(process,'lean',task) if recorder else identity(process.pid)
        register_child(work, process, 'lean')
        while True:
            try:
                stdout,stderr=process.communicate(timeout=.1)
                result={'exit_code':process.returncode,'stdout':stdout,'stderr':stderr,'wall_seconds':time.monotonic()-started}
                break
            except subprocess.TimeoutExpired:
                cancelled=recorder is not None and recorder.cancelled(task)
                if cancelled or (timeout is not None and time.monotonic()-started>=timeout):
                    stopped=recorder.stop_process(process) if recorder else terminate_owned(process,owner)
                    if not stopped: raise RuntimeError('Native process cleanup could not be confirmed')
                    stdout,stderr=process.communicate()
                    diagnostic = ('\nExternal cancellation' if cancelled else
                        f'\nLean timeout: this native check exceeded {timeout:g} seconds. '
                        'The candidate was not accepted. Isolate a smaller typed application or proof '
                        'fragment, repair it and recheck the unchanged target. '
                        'A timeout does not establish a mathematical failure.')
                    result={'exit_code':130 if cancelled else 124,'stdout':stdout,
                        'stderr':stderr+diagnostic,
                        'wall_seconds':time.monotonic()-started,'cancelled':cancelled}
                    if not cancelled:
                        result.update(timed_out=True,error_kind='LEAN_TIMEOUT',
                                      timeout_seconds=timeout,timeout_scope='native_call')
                    break
        if recorder: recorder.lean_finished(task,check,result)
        if result.get('cancelled'): raise Cancelled('Native Lean check cancelled externally')
        return result
    finally:
        if process is not None:
            if process.poll() is None:
                if recorder: recorder.stop_process(process)
                elif owner: terminate_owned(process,owner)
            if recorder: recorder.process_finished(process)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
