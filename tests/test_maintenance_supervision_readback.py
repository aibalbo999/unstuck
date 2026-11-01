"""Supervisor status is never a substitute for the original durable journal."""
from contextlib import contextmanager
import sys
import time

import pytest
from test_maintenance_owned_process import binding, module


@contextmanager
def completed(tmp_path):
    adapter = module()
    namespace = tmp_path / 'owner'; namespace.mkdir(mode=0o700)
    owner = adapter.OwnedProcess(namespace, binding())
    supervisor = None
    try:
        owner.start([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(.1)'],
                    env={}, cwd=tmp_path, owned_session=True)
        supervisor = adapter.OwnedProcessSupervisor(owner, deadline_monotonic=time.monotonic() + 5)
        state = supervisor.wait_for_exit(2)
        assert state['process_exited'] and state['process_group_absence_verified']
        yield adapter, owner, supervisor, namespace, state
    finally:
        if owner.process is not None: owner.process.wait(timeout=3)
        owner.close()


@pytest.mark.parametrize('reader', ['owner_wait', 'supervisor_snapshot'])
def test_every_supervised_readback_revalidates_original_journal(tmp_path, reader):
    with completed(tmp_path) as (adapter, owner, supervisor, namespace, state):
        journal = namespace / adapter.JOURNAL
        journal.write_bytes(journal.read_bytes() + b'corrupt retained journal\n')
        with pytest.raises(adapter.ProcessUnavailable):
            owner.wait_for_exit(0) if reader == 'owner_wait' else supervisor.snapshot()


def test_returned_nested_binding_cannot_change_future_readback(tmp_path):
    with completed(tmp_path) as (_, owner, supervisor, _, state):
        state['binding']['operation_id'] = 'different-operation'
        assert owner.snapshot()['binding'] == binding()
        assert owner.wait_for_exit(0)['binding'] == binding()
        assert supervisor.snapshot()['binding'] == binding()
