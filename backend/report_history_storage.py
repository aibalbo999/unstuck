"""Storage lookup helpers for report history services."""

from __future__ import annotations

import os
from typing import Any

from report_paths import report_storage_candidates_for_filename
from storage.report_storage import LocalFileStorage, ReportStorage


def storage_for_existing_output_dir(output_dir: str, storage: ReportStorage | None) -> ReportStorage | None:
    if storage is not None:
        return storage
    if not os.path.exists(output_dir):
        return None
    return LocalFileStorage(output_dir)


def should_sync_metadata(output_dir: str, storage: ReportStorage | None) -> bool:
    if storage is None:
        return os.path.exists(output_dir)
    return isinstance(storage, LocalFileStorage)


def repository_has_metadata(repository: Any, filename: str, output_dir: str) -> bool:
    exists = getattr(repository, "exists", None)
    return bool(callable(exists) and exists(filename, output_dir))


def existing_storage_key(storage: ReportStorage, filename: str, *, kind: str) -> str | None:
    for key in report_storage_candidates_for_filename(filename, kind=kind):
        if storage.exists(key):
            return key
    return None


def load_storage_item(storage: ReportStorage, filename: str, *, kind: str):
    for key in report_storage_candidates_for_filename(filename, kind=kind):
        item = storage.get_report(key)
        if item is not None:
            return item
    return None


__all__ = [
    "existing_storage_key",
    "load_storage_item",
    "repository_has_metadata",
    "should_sync_metadata",
    "storage_for_existing_output_dir",
]
