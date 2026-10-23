"""Pinned Lean invocation and the native, offline execution boundary."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from runtime_config import load_lock




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


def transport_sandbox_profile(work: Path, relay_port: int) -> str:
    """Restrict the subscription carrier to its own files and local relay."""
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
        '(deny network-outbound (require-not (remote ip "localhost:' + str(relay_port) + '")))',
        '(deny process-exec (require-not (literal ' + json.dumps(str(binary)) + ')))',
        '(deny file-read-data (require-not (require-any (subpath "/System") '
        '(subpath "/usr/lib") (subpath "/usr/share") (subpath "/private/var/db/dyld") '
        '(literal "/dev/null") (literal "/dev/random") (literal "/dev/urandom") '
        '(literal "/private/etc/localtime") ' + read + ')))',
        '(deny file-write* (require-not (require-any (literal "/dev/null") ' + write + ')))',
    ]) + '\n'


def run_lean(file: Path, work: Path, *, extra: list[Path] = (), sandbox: bool = True,
             output: Path | None = None, timeout: float = 120) -> dict:
    lock = load_lock()
    for name in ['home', 'tmp', 'output']:
        (work / name).mkdir(parents=True, exist_ok=True)
    cmd = [str(Path(lock['lean']['local_path']) / 'bin/lean'), '-R', str(file.parent), '-j', '1', '-M', '8192']
    if output: cmd += ['-o', str(output)]
    cmd += [str(file)]
    if sandbox:
        profile = work / 'sandbox.sb'
        profile.write_text(sandbox_profile(work))
        cmd = ['/usr/bin/sandbox-exec', '-f', str(profile)] + cmd
    started = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=work / 'output', env=lean_env(work, extra),
                           capture_output=True, text=True, timeout=timeout)
        return {'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr,
                'wall_seconds': time.monotonic() - started}
    except subprocess.TimeoutExpired as e:
        return {'exit_code': 124, 'stdout': str(e.stdout or ''), 'stderr': 'Lean timeout',
                'wall_seconds': time.monotonic() - started}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
