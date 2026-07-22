"""Child-process lifecycle helpers for worker supervision."""

from __future__ import annotations


def terminate_live_children(processes) -> None:
    for process in processes:
        if process.is_alive():
            process.terminate()


def join_children(processes, timeout: float | None = None) -> None:
    for process in processes:
        process.join(timeout=timeout)


def has_nonzero_exit(processes) -> bool:
    return any(process.exitcode not in (None, 0) for process in processes)


def all_children_exited(processes) -> bool:
    return all(process.exitcode is not None for process in processes)
