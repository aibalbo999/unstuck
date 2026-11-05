"""Owned children receive only explicit read-only storage capabilities."""
import errno
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest


@pytest.fixture
def owned(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'scripts/maintenance_owned_process.py'
    spec = importlib.util.spec_from_file_location('readonly_owned_tested', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    namespace = tmp_path / 'owner'
    namespace.mkdir(mode=0o700)
    owner = module.OwnedProcess(namespace, {
        'operation_id': 'readonly-capacity', 'control_sha256': 'a' * 64,
        'backend_revision': 'b' * 40})
    yield module, owner, namespace
    if owner.process is not None:
        owner.process.wait(timeout=5)
    owner.close()


def claim_fd(path):
    path.touch(mode=0o600)
    return os.open(path, os.O_RDONLY | os.O_NOFOLLOW)


def test_real_child_inherits_readonly_claim_and_lifetime_not_other_writable_fds(owned, tmp_path):
    module, owner, namespace = owned
    claim = claim_fd(tmp_path / 'lease.lock')
    lifetime, writer = os.pipe()
    admission, auth_writer = os.pipe()
    secret = os.open(tmp_path / 'must-not-inherit', os.O_RDWR | os.O_CREAT, 0o600)
    extra = fcntl.fcntl(secret, fcntl.F_DUPFD, 200)
    child = '''import errno, fcntl, json, os, sys, time
from pathlib import Path
rows=[]
for text in sys.argv[2:5]:
 fd=int(text)
 assert fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE == os.O_RDONLY
 try: os.write(fd,b'x')
 except OSError as error: assert error.errno == errno.EBADF
 else: raise AssertionError('writable inherited capability')
 rows.append(fd)
try: os.fstat(int(sys.argv[5]))
except OSError as error: assert error.errno == errno.EBADF
else: raise AssertionError('unrelated writable descriptor inherited')
Path(sys.argv[1]).write_text(json.dumps(rows))
time.sleep(.15)
'''
    result = tmp_path / 'child.json'
    try:
        owner.start([sys.executable, '-I', '-B', '-c', child, str(result),
                     str(claim), str(lifetime), str(admission), str(extra)],
                    env={'PATH': '/usr/bin:/bin'}, cwd=tmp_path, owned_session=True,
                    admission_fd=admission, readonly_fds=(claim, lifetime))
        state = owner.wait_for_exit(5)
        assert state['returncode'] == 0
        assert json.loads(result.read_text()) == [claim, lifetime, admission]
        assert state['pid'] == state['process_group_id']
        assert [r['kind'] for r in state['readonly_descriptor_identities']] == ['regular', 'pipe']
        assert module.read_process_record(namespace)['readonly_descriptor_identities'] == state['readonly_descriptor_identities']
    finally:
        for fd in (claim, lifetime, writer, admission, auth_writer, secret, extra):
            os.close(fd)


@pytest.mark.parametrize('kind', ['writable', 'directory', 'duplicate', 'duplicate_inode',
                                 'admission_duplicate', 'too_many', 'boolean', 'nonempty', 'public_readable'])
def test_invalid_capabilities_refuse_before_launch_intent(owned, tmp_path, kind):
    module, owner, namespace = owned
    claim = claim_fd(tmp_path / 'lease.lock')
    writable = os.open(tmp_path / 'writable', os.O_RDWR | os.O_CREAT, 0o600)
    directory = os.open(tmp_path, os.O_RDONLY)
    reader, writer = os.pipe()
    alias = os.dup(claim)
    if kind == 'nonempty': (tmp_path / 'lease.lock').write_bytes(b'not a lease lock')
    if kind == 'public_readable': (tmp_path / 'lease.lock').chmod(0o644)
    values = {'writable': (writable,), 'directory': (directory,), 'duplicate': (claim, claim),
              'duplicate_inode': (claim, alias), 'admission_duplicate': (reader,),
              'too_many': (claim,) * 9, 'boolean': (True,), 'nonempty': (claim,), 'public_readable': (claim,)}
    try:
        with pytest.raises(module.ProcessUnavailable):
            owner.start([sys.executable, '-I', '-B', '-c', 'pass'], env={}, cwd=tmp_path,
                        admission_fd=reader, readonly_fds=values[kind])
        assert owner.process is None
        assert module.read_process_record(namespace)['phase'] == 'reserved'
    finally:
        for fd in (claim, writable, directory, reader, writer, alias): os.close(fd)


def test_descriptor_swap_after_durable_intent_prevents_spawn(owned, tmp_path, monkeypatch):
    module, owner, namespace = owned
    claim = claim_fd(tmp_path / 'lease.lock')
    replacement = claim_fd(tmp_path / 'different.lock')
    original = owner._append
    def append(event, data):
        original(event, data)
        if event == 'launch_intent': os.dup2(replacement, claim)
    monkeypatch.setattr(owner, '_append', append)
    try:
        with pytest.raises(module.ProcessUnavailable):
            owner.start([sys.executable, '-I', '-B', '-c', 'pass'], env={}, cwd=tmp_path,
                        readonly_fds=(claim,))
        assert owner.process is None
        assert module.read_process_record(namespace)['phase'] == 'launch_unconfirmed'
        with pytest.raises(module.ProcessUnavailable):
            owner.start([sys.executable, '-I', '-B', '-c', 'pass'], env={}, cwd=tmp_path)
    finally:
        os.close(claim); os.close(replacement)


def test_existing_journal_without_capacity_descriptors_stays_readable(owned, tmp_path):
    module, owner, namespace = owned
    owner.start([sys.executable, '-I', '-B', '-c', 'pass'], env={}, cwd=tmp_path)
    assert owner.wait_for_exit(5)['returncode'] == 0
    assert module.read_process_record(namespace)['readonly_descriptor_identities'] == []
