"""Capacity-only companion for a directly owned no-spawn child.

No provider, socket, file writing or PID adoption. The companion holds inherited
kernel lease descriptors. Loss of all readonly lifetime-pipe ends is a kernel
lifetime observation; elapsed time alone never releases the claim.
"""
import fcntl
import hashlib
import os
import select
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time


_LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def hold_until_readers_close(writer, ready, leases):
    if not stat.S_ISFIFO(os.fstat(writer).st_mode):
        raise ValueError('Explicit anonymous lifetime pipe required')
    if not leases or fcntl.fcntl(writer, fcntl.F_GETFL) & os.O_ACCMODE != os.O_WRONLY:
        raise ValueError('Writable lifetime pipe and explicit kernel leases required')
    seen = set()
    for fd in leases:
        info = os.fstat(fd)
        identity = (info.st_dev, info.st_ino)
        if (not stat.S_ISREG(info.st_mode) or info.st_size or info.st_nlink != 1
                or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600
                or identity in seen or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDWR):
            raise ValueError('Private inherited mirrored lease descriptor required')
        seen.add(identity)
    os.write(ready, b'R')
    os.close(ready)
    os.set_blocking(writer, False)
    while True:
        try:
            os.write(writer, b'.')
        except BrokenPipeError:
            return
        except BlockingIOError:
            pass  # A full pipe is still alive, never an expiry condition.
        time.sleep(.05)


class CapacityCompanion:
    """Parent keeps this exact Popen/lease until original cleanup is verified."""
    def __init__(self, output, job_id, manifest_sha256, review):
        from .capacity_delegation import prepare_parent_claim
        self.reader, writer = os.pipe()
        ready_reader, ready_writer = os.pipe()
        info = os.fstat(self.reader)
        self.lease = self.readonly_fd = self.process = None
        self.closed = False
        try:
            self.lease, self.readonly_fd, self.capability = prepare_parent_claim(
                output, job_id, manifest_sha256, review,
                lifetime_identity={'device':info.st_dev, 'inode':info.st_ino})
            source = Path(__file__).read_bytes()
            expected = globals().get('_control_source_sha256', _LOADED_SOURCE_SHA256)
            if hashlib.sha256(source).hexdigest() != expected:
                raise RuntimeError('Capacity companion source changed before launch')
            # Execute the verified buffer, not a second filesystem read. This
            # preserves a controller snapshot across the keeper launch boundary.
            bootstrap = '__file__=' + repr(str(Path(__file__).resolve())) + '\n' + source.decode('utf-8')
            self.process = subprocess.Popen([sys.executable, '-I', '-B', '-c', bootstrap,
                '--hold', str(writer), str(ready_writer), *map(str,self.lease.claim_fds())], close_fds=True,
                pass_fds=(*self.lease.claim_fds(), writer, ready_writer), start_new_session=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env={'PATH':'/usr/bin:/bin'})
            os.close(ready_writer);ready_writer=None
            readable,_,_=select.select([ready_reader],[],[],5)
            if not readable or os.read(ready_reader,2)!=b'R':
                raise RuntimeError('Capacity companion readiness was not confirmed')
            self.ensure_ready()
        except BaseException:
            # No true child has been launched. Reap our exact keeper before
            # releasing its mirrored ownership; an uncertain reap retains it.
            if self.process is not None:
                if self.process.poll() is None:self.process.terminate()
                self.process.wait(timeout=5)

            os.close(self.reader);self.reader=None
            if self.readonly_fd is not None:os.close(self.readonly_fd);self.readonly_fd=None
            if self.lease is not None:self.lease.__exit__(*sys.exc_info())
            raise
        finally:
            os.close(writer)
            os.close(ready_reader)
            if ready_writer is not None:os.close(ready_writer)

    def ensure_ready(self):
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError('Capacity companion exited before child handoff')

    def handoff_complete(self):
        """Only after the exact true child's Popen inherited both readonly FDs."""
        self.ensure_ready()
        self._close_readers()

    def _close_readers(self):
        for field in ('reader','readonly_fd'):
            fd=getattr(self,field)
            if fd is not None:
                os.close(fd);setattr(self,field,None)

    def finish(self, *, child_group_absent=False, child_never_started=False):
        """Unknown cleanup keeps the claim. Caller uses original OwnedProcess proof."""
        if self.closed:return self.lease.receipt()
        if child_group_absent is not True and child_never_started is not True:
            raise RuntimeError('Original child group cleanup is not verified')
        self._close_readers()
        # The exact companion is never reaped before the final signal. No PID
        # file, old journal or time limit authorizes taking another process.
        if self.process.returncode is None:
            try:self.process.terminate()
            except ProcessLookupError:pass
            self.process.wait(timeout=5)
        self.lease.check(remaining_bytes=0)
        self.lease.__exit__(None,None,None)
        self.closed=True
        return self.lease.receipt()


if __name__=='__main__':
    if len(sys.argv)<5 or sys.argv[1]!='--hold':raise SystemExit(2)
    hold_until_readers_close(int(sys.argv[2]),int(sys.argv[3]),tuple(map(int,sys.argv[4:])))
