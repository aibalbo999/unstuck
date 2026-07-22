"""Storage-key helpers for report history cleanup and downloads."""

from __future__ import annotations

import os

from data_trust import data_snapshot_filename_for_report
from storage.report_storage import ReportStorage


def basename_for_storage_key(key: str) -> str:
    return str(key or "").rsplit("/", 1)[-1]


def dirname_for_storage_key(key: str) -> str:
    parts = str(key or "").rsplit("/", 1)
    return parts[0] if len(parts) == 2 else ""


def join_storage_key(prefix: str, basename: str) -> str:
    return f"{prefix}/{basename}" if prefix else basename


def bundle_keys_for_html_key(key: str) -> list[str]:
    prefix = dirname_for_storage_key(key)
    filename = basename_for_storage_key(key)
    markdown = filename[:-5] + ".md" if filename.endswith(".html") else f"{filename}.md"
    return [
        key,
        join_storage_key(prefix, markdown),
        join_storage_key(prefix, data_snapshot_filename_for_report(filename)),
    ]


def html_key_for_related_storage_key(key: str) -> str:
    prefix = dirname_for_storage_key(key)
    filename = basename_for_storage_key(key)
    html = filename[:-10] + ".html" if filename.endswith(".data.json") else os.path.splitext(filename)[0] + ".html"
    return join_storage_key(prefix, html)


def delete_storage_key(storage: ReportStorage, key: str, deleted: list[str]) -> None:
    try:
        if storage.delete_report(key):
            deleted.append(key)
    except OSError:
        pass
