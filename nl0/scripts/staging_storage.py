"""Disk reservations shared by local workers and atomic independent input views."""
from contextlib import contextmanager
import ctypes
import errno
import fcntl
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

MIB = 1024**2
FREE_FLOOR = 512*MIB
NATIVE_RESERVE = 32*MIB


class StoragePressure(OSError):
    """A local execution fault; never evidence for an unresolved theorem."""


def available(path):
    return shutil.disk_usage(path).free


@contextmanager
def reserve(destination, size):
    if size < 0:
        raise ValueError('Negative disk reservation')
    path = Path(destination)
    while not path.exists():
        path = path.parent
    root = Path(os.environ.get('YUI_TEST_CLEANUP_ROOT','/tmp'))/f'yui-storage-{os.getuid()}-{path.stat().st_dev}'
    root.mkdir(mode=0o700,exist_ok=True)
    meta = root.lstat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid!=os.getuid() or meta.st_mode & 0o077:
        raise RuntimeError('Invalid disk reservation directory')
    with (root/'admission.lock').open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        total = 0
        for row in root.glob('lease-*'):
            with row.open('r') as handle:
                try:
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    total += int(handle.read())
                else:
                    row.unlink()
        free = available(path)
        if free-total-size < FREE_FLOOR:
            raise StoragePressure(errno.ENOSPC,f'Disk admission needs {size} bytes plus {FREE_FLOOR} reserve; {free} free and {total} reserved',str(path))
        lease = tempfile.NamedTemporaryFile(mode='w+',dir=root,prefix='lease-',delete=False)
        try:
            fcntl.flock(lease,fcntl.LOCK_EX)
            lease.write(str(size))
            lease.flush()
            fcntl.flock(guard,fcntl.LOCK_UN)
            yield
        finally:
            fcntl.flock(guard,fcntl.LOCK_EX)
            Path(lease.name).unlink(missing_ok=True)
            lease.close()


def clone(source, target):
    if sys.platform=='darwin':
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.clonefile(os.fsencode(source),os.fsencode(target),0)==0:
            return True
        error=ctypes.get_errno()
        if error==errno.ENOSPC:
            raise StoragePressure(error,'Insufficient space for input clone',str(target))
        if error not in {errno.EXDEV,errno.ENOTSUP,errno.EINVAL,errno.ENOSYS,errno.EPERM}:
            raise OSError(error,os.strerror(error),str(target))
    elif sys.platform=='linux':
        try:
            with Path(source).open('rb') as src,Path(target).open('xb') as dst:
                fcntl.ioctl(dst,0x40049409,src.fileno())  # FICLONE
            return True
        except OSError as error:
            Path(target).unlink(missing_ok=True)
            if error.errno not in {errno.EXDEV,errno.ENOTSUP,errno.EINVAL,errno.ENOTTY,errno.ENOSYS}:
                raise
    return False


def write_bytes(destination,data):
    destination=Path(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.yui-data-') as scratch:
        temp=Path(scratch)/'bytes'
        temp.write_bytes(data)
        temp.replace(destination)


def copy_input(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise ValueError('Expected an explicit input file: '+str(source))
    # Temporary on the destination volume. A failed copy never replaces prior evidence.
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.yui-input-') as stage:
        candidate = Path(stage)/'bytes'
        size=source.stat().st_size
        if size>=MIB:
            with reserve(destination.parent,0):pass
        if not clone(source,candidate):
            with reserve(destination.parent,size):
                shutil.copyfile(source,candidate)
        os.replace(candidate,destination)
    return str(destination)
