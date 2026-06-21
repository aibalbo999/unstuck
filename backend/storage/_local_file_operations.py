"""Durable filesystem primitives used by local report storage."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows uses the in-process lock.
    fcntl = None


_METADATA_SUFFIX = ".onstock-metadata.json"
_TEMP_PREFIX = ".onstock-storage-"
_TEMP_SUFFIX = ".tmp"
_ROOT_LOCKS: dict[Path, threading.RLock] = {}
_ROOT_LOCKS_GUARD = threading.Lock()


@contextmanager
def exclusive_storage_lock(root: Path):
    """Serialize access across threads and, on POSIX, worker processes."""
    with _ROOT_LOCKS_GUARD:
        thread_lock = _ROOT_LOCKS.setdefault(root, threading.RLock())
    with thread_lock:
        directory_fd = None
        try:
            if fcntl is not None:
                directory_fd = os.open(root, os.O_RDONLY)
                fcntl.flock(directory_fd, fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None and directory_fd is not None:
                fcntl.flock(directory_fd, fcntl.LOCK_UN)
                os.close(directory_fd)


def fsync_directory(directory: Path) -> None:
    """Persist directory-entry changes after an atomic replace or unlink."""
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    directory_fd = os.open(directory, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def atomic_write(target: Path, payload: bytes) -> None:
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=_TEMP_PREFIX,
            suffix=_TEMP_SUFFIX,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, target)
        fsync_directory(target.parent)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def metadata_path(target: Path) -> Path:
    return target.with_name(f".{target.name}{_METADATA_SUFFIX}")


def is_internal_storage_file(path: Path) -> bool:
    return (
        path.name.startswith(_TEMP_PREFIX) and path.name.endswith(_TEMP_SUFFIX)
    ) or (path.name.startswith(".") and path.name.endswith(_METADATA_SUFFIX))
