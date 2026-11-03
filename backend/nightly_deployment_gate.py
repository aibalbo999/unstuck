"""Kernel fence for a nightly source claim through its final queue dispatch.

RQ suspension stops new ticks; this fence closes the check/enqueue race. The
deployment controller holds EX from source drain through preservation/resume.
No timeout, Redis mutation, cache change or work deletion occurs here.
"""
import fcntl
import os
from pathlib import Path
import stat

from deployment_rq_pause import PauseError


def lock_path():
    from nightly_analysis_store import path
    return path().parent / 'nightly-deployment-admission.lock'


class NightlyWorkFence:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else lock_path()
        self.fd = None
        self.mode = None

    def __enter__(self):
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            self.check()
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise
        return self

    def check(self):
        if self.fd is None:
            raise PauseError('Nightly admission fence is closed')
        held, current = os.fstat(self.fd), self.path.lstat()
        if not stat.S_ISREG(held.st_mode) or (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino):
            raise PauseError('Nightly admission fence identity changed')

    def acquire(self, *, shared=False):
        self.check()
        mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        if self.mode is not None:
            if self.mode != mode:
                raise PauseError('Nightly admission fence cannot change ownership mode')
            return True
        try:
            fcntl.flock(self.fd, mode | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        self.mode = mode
        self.check()
        return True

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            self.mode = None
