import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from worker_child_processes import (  # noqa: E402
    all_children_exited,
    has_nonzero_exit,
    join_children,
    terminate_live_children,
)


class FakeProcess:
    def __init__(self, *, alive=False, exitcode=None):
        self._alive = alive
        self.exitcode = exitcode
        self.joined = []
        self.terminated = False

    def is_alive(self):
        return self._alive

    def terminate(self):
        self.terminated = True

    def join(self, timeout=None):
        self.joined.append(timeout)


def test_terminate_live_children_only_terminates_alive_processes():
    alive = FakeProcess(alive=True)
    exited = FakeProcess(alive=False)

    terminate_live_children([alive, exited])

    assert alive.terminated is True
    assert exited.terminated is False


def test_child_process_exit_helpers_match_supervisor_semantics():
    running = FakeProcess(exitcode=None)
    success = FakeProcess(exitcode=0)
    failed = FakeProcess(exitcode=1)

    join_children([running, success], timeout=2.5)

    assert running.joined == [2.5]
    assert success.joined == [2.5]
    assert has_nonzero_exit([running, success]) is False
    assert has_nonzero_exit([running, failed]) is True
    assert all_children_exited([success, failed]) is True
    assert all_children_exited([running, success]) is False
