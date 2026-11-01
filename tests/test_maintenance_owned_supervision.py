"""Real child deadline/cancellation without a ledger, provider or shared service."""
import sys
import time

import pytest
from test_maintenance_owned_process import CHILD, binding, module, wait_path


def test_deadline_stops_original_child_even_when_caller_never_waits(tmp_path):
    adapter = module()
    namespace = tmp_path / 'owner'; namespace.mkdir(mode=0o700)
    owner = adapter.OwnedProcess(namespace, binding())
    supervisor = None
    try:
        owner.start([sys.executable, '-I', '-B', '-c', CHILD, str(tmp_path)],
                    env={}, cwd=tmp_path, owned_session=True)
        wait_path(tmp_path / 'ready', owner.process)
        # An unresponsive caller/ledger is not on this timer's execution path.
        deadline = time.monotonic() + .15
        supervisor = adapter.OwnedProcessSupervisor(owner, deadline_monotonic=deadline)
        wait_path(tmp_path / 'signals.json', owner.process, seconds=2)
        assert (tmp_path / 'signals.json').read_text() == '1'
        assert owner.process.poll() is None  # No KILL escalation.
        supervisor.request_stop()
        time.sleep(.05)
        assert (tmp_path / 'signals.json').read_text() == '1'
        (tmp_path / 'finish').touch()
        state = supervisor.wait_for_exit(5)
        assert state['process_exited'] and state['process_group_absence_verified']
        assert state['supervision_complete'] and state['stop_reason'] == 'deadline'
        assert state['deadline_monotonic'] == deadline
        assert state['descendant_settlement_verified'] is state['handover_verified'] is False
    finally:
        (tmp_path / 'finish').touch()
        if owner.process is not None: owner.process.wait(timeout=5)
        if supervisor is not None: supervisor.wait_for_exit(5)
        owner.close()


@pytest.mark.parametrize('wait_via_owner', [False, True])
def test_cancellation_during_long_wait_is_not_delayed_by_wait_lock(tmp_path, wait_via_owner):
    import threading
    adapter = module()
    namespace = tmp_path / 'owner'; namespace.mkdir(mode=0o700)
    owner = adapter.OwnedProcess(namespace, binding())
    supervisor = None
    waiting = None
    waiter_errors = []
    try:
        owner.start([sys.executable, '-I', '-B', '-c', CHILD, str(tmp_path)],
                    env={}, cwd=tmp_path, owned_session=True)
        wait_path(tmp_path / 'ready', owner.process)
        supervisor = adapter.OwnedProcessSupervisor(owner, deadline_monotonic=time.monotonic() + 30)
        waiter = owner if wait_via_owner else supervisor
        def wait():
            try: waiter.wait_for_exit(5)
            except BaseException as error: waiter_errors.append(error)
        waiting = threading.Thread(target=wait)
        waiting.start()
        time.sleep(.03)
        supervisor.request_stop()
        wait_path(tmp_path / 'signals.json', owner.process, seconds=1)
        assert (tmp_path / 'signals.json').read_text() == '1'
        (tmp_path / 'finish').touch()
        state = supervisor.wait_for_exit(5)
        waiting.join(timeout=1)
        assert not waiting.is_alive() and not waiter_errors, waiter_errors
        assert state['supervision_complete'] and state['stop_reason'] == 'cancelled'
        assert state['process_group_absence_verified']
    finally:
        (tmp_path / 'finish').touch()
        if owner.process is not None: owner.process.wait(timeout=5)
        if waiting is not None: waiting.join(timeout=5)
        if supervisor is not None: supervisor.wait_for_exit(5)
        owner.close()


def test_supervisor_rejects_legacy_inherited_group(tmp_path):
    adapter = module()
    namespace = tmp_path / 'owner'; namespace.mkdir(mode=0o700)
    owner = adapter.OwnedProcess(namespace, binding())
    try:
        owner.start([sys.executable, '-I', '-B', '-c', 'pass'], env={}, cwd=tmp_path)
        with pytest.raises(adapter.ProcessUnavailable):
            adapter.OwnedProcessSupervisor(owner, deadline_monotonic=time.monotonic() + 1)
    finally:
        if owner.process is not None: owner.process.wait(timeout=5)
        owner.close()


def test_owner_cannot_disarm_or_replace_a_live_supervisor(tmp_path):
    adapter = module()
    namespace = tmp_path / 'owner'; namespace.mkdir(mode=0o700)
    owner = adapter.OwnedProcess(namespace, binding())
    supervisor = None
    try:
        owner.start([sys.executable, '-I', '-B', '-c', CHILD, str(tmp_path)],
                    env={}, cwd=tmp_path, owned_session=True)
        wait_path(tmp_path / 'ready', owner.process)
        supervisor = adapter.OwnedProcessSupervisor(owner, deadline_monotonic=time.monotonic() + .2)
        with pytest.raises(adapter.ProcessUnavailable): owner.close()
        with pytest.raises(adapter.ProcessUnavailable):
            adapter.OwnedProcessSupervisor(owner, deadline_monotonic=time.monotonic() + 60)
        wait_path(tmp_path / 'signals.json', owner.process)
        assert (tmp_path / 'signals.json').read_text() == '1'
        (tmp_path / 'finish').touch()
        assert supervisor.wait_for_exit(5)['supervision_complete']
    finally:
        (tmp_path / 'finish').touch()
        if owner.process is not None: owner.process.wait(timeout=5)
        if supervisor is not None: supervisor.wait_for_exit(5)
        owner.close()


def test_uncertain_stop_is_not_retried_or_reported_as_success(tmp_path, monkeypatch):
    adapter = module()
    namespace = tmp_path / 'owner'; namespace.mkdir(mode=0o700)
    owner = adapter.OwnedProcess(namespace, binding())
    supervisor = None
    calls = []
    try:
        owner.start([sys.executable, '-I', '-B', '-c', CHILD, str(tmp_path)],
                    env={}, cwd=tmp_path, owned_session=True)
        wait_path(tmp_path / 'ready', owner.process)
        def uncertain():
            calls.append('attempt')
            raise adapter.ProcessUnavailable('Signal acknowledgement lost')
        monkeypatch.setattr(owner, 'request_stop', uncertain)
        supervisor = adapter.OwnedProcessSupervisor(owner, deadline_monotonic=time.monotonic() + .1)
        with pytest.raises(adapter.ProcessUnavailable, match='supervision unconfirmed'):
            supervisor.wait_for_exit(2)
        time.sleep(.05)
        assert calls == ['attempt'] and owner.process.poll() is None
        with pytest.raises(adapter.ProcessUnavailable): supervisor.request_stop()
        assert calls == ['attempt']
    finally:
        (tmp_path / 'finish').touch()
        if owner.process is not None: owner.process.wait(timeout=5)
        owner.close()
