"""Local runtime instance lock helpers."""

from __future__ import annotations

import fcntl
import os
from contextlib import suppress


_LOCK_PATHS_HELD: set[str] = set()


class LocalRuntimeInstanceLock:
    def __init__(self, path: str, instance_id: str):
        self.path = path
        self.instance_id = instance_id
        self.file = None
        self.acquired = False

    def acquire(self) -> bool:
        if self.acquired:
            return True
        normalized_path = os.path.abspath(self.path)
        if normalized_path in _LOCK_PATHS_HELD:
            return False
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.file = open(self.path, "a+", encoding="utf-8")
        try:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close()
            self.file = None
            return False
        self.file.seek(0)
        self.file.truncate()
        self.file.write(f"{self.instance_id}\n")
        self.file.flush()
        self.acquired = True
        _LOCK_PATHS_HELD.add(normalized_path)
        return True

    def close(self) -> None:
        normalized_path = os.path.abspath(self.path)
        if self.file is None:
            _LOCK_PATHS_HELD.discard(normalized_path)
            return
        with suppress(OSError):
            if self.acquired:
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        with suppress(OSError):
            self.file.close()
        self.file = None
        self.acquired = False
        _LOCK_PATHS_HELD.discard(normalized_path)


def acquire_local_runtime_instance_lock(path: str, instance_id: str) -> LocalRuntimeInstanceLock:
    lock = LocalRuntimeInstanceLock(path, instance_id)
    lock.acquire()
    return lock
