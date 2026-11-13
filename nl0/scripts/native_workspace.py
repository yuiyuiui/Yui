"""Owned transient native workspaces, retained until shutdown is confirmed."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from execution_state import atomic, current
from run_resources import MARKER, register_workspace

VERSION = 'yui-native-workspace-1'
FENCE = '.yui-native-cleanup.json'


def record(work, *, confirmed, phase, process=None, exit_code=None):
    work=Path(work).resolve()
    marker=work/MARKER
    atomic(work/FENCE,{'version':VERSION,'workspace':str(work),
        'owner_sha256':hashlib.sha256(marker.read_bytes()).hexdigest() if marker.is_file() else None,
        'cleanup_confirmed':confirmed,'phase':phase,'process':process,'exit_code':exit_code})


def read_cleanup(work):
    work=Path(work).resolve();marker=work/MARKER
    value=json.loads((work/FENCE).read_text())
    if (value.get('version')!=VERSION or value.get('workspace')!=str(work)
            or type(value.get('cleanup_confirmed')) is not bool or (work/FENCE).is_symlink()
            or not marker.is_file() or marker.is_symlink()
            or value.get('owner_sha256')!=hashlib.sha256(marker.read_bytes()).hexdigest()):
        raise ValueError('Native cleanup fence differs from its owned workspace')
    return value


def confirmed(work):
    try:
        return read_cleanup(work)['cleanup_confirmed']
    except (OSError,ValueError,TypeError):return False


def unconfirmed(message, work):
    error=RuntimeError(message)
    error.native_cleanup_confirmed=False
    error.native_workspace=str(Path(work).resolve())
    return error


def _retain(work, logs, error):
    receipt={'version':VERSION,'workspace':str(work),'cleanup_confirmed':False,
             'reason':type(error).__name__+': '+str(error),
             'owner':None}
    try:receipt['owner']=json.loads((work/MARKER).read_text())
    except (OSError,ValueError):pass
    if (work/FENCE).is_file():
        try:receipt['native_cleanup']=json.loads((work/FENCE).read_text())
        except (OSError,ValueError):pass
    try:
        atomic(work/'native-workspace-retained.json',receipt)
        token=(receipt['owner'] or {}).get('token','unknown')
        atomic(logs/'resources'/('retained-native-'+token+'.json'),receipt)
    except (OSError,ValueError):
        # The source and ownership marker remain even on a full disk.
        pass
    error.add_note('Retained native workspace: '+str(work))


@contextmanager
def temporary(prefix, *, logs=None):
    """A returned native call confirms exit; unknown exceptions retain evidence."""
    work=Path(tempfile.mkdtemp(prefix=prefix)).resolve()
    recorder,_=current()
    logs=(Path(logs).resolve() if logs is not None else
          recorder.root/'logs/native-workspaces' if recorder else work/'evidence')
    try:register_workspace(work,logs)
    except BaseException:
        shutil.rmtree(work)  # No native process has been started.
        raise
    try:
        yield work
    except BaseException as error:
        if confirmed(work) and getattr(error,'native_cleanup_confirmed',None) is not False:
            shutil.rmtree(work)
        else:_retain(work,logs,error)
        raise
    else:
        if (work/FENCE).exists() and not confirmed(work):
            error=unconfirmed('Native process cleanup could not be confirmed',work)
            _retain(work,logs,error)
            raise error
        shutil.rmtree(work)
