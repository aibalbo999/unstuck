"""Persist rendered report bundles through report content storage."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from data_trust import data_snapshot_filename_for_report, sanitize_for_snapshot
from report_paths import report_markdown_filename_for_report, report_storage_key_for_filename
from report_repository import DEFAULT_REPORT_REPOSITORY, ReportRepository
from storage.report_storage import ReportStorage


HTML_CONTENT_TYPE = "text/html"
MARKDOWN_CONTENT_TYPE = "text/markdown"
DATA_SNAPSHOT_CONTENT_TYPE = "application/json"


@dataclass(frozen=True)
class ReportBundleKeys:
    filename: str
    md_filename: str
    data_filename: str
    html_key: str
    md_key: str
    data_key: str


def report_bundle_keys_for_filename(filename: str) -> ReportBundleKeys:
    stem, extension = os.path.splitext(filename)
    html_filename = filename if extension == ".html" else f"{stem}.html"
    md_filename = report_markdown_filename_for_report(html_filename)
    data_filename = data_snapshot_filename_for_report(html_filename)
    html_key = report_storage_key_for_filename(html_filename)
    storage_prefix = os.path.dirname(html_key)
    return ReportBundleKeys(
        filename=html_filename,
        md_filename=md_filename,
        data_filename=data_filename,
        html_key=html_key,
        md_key=f"{storage_prefix}/{md_filename}" if storage_prefix else md_filename,
        data_key=f"{storage_prefix}/{data_filename}" if storage_prefix else data_filename,
    )


def persist_report_bundle(
    *,
    filename: str,
    html_content: str,
    markdown_content: str,
    data_snapshot: dict,
    storage: ReportStorage,
    output_dir: str | None = None,
    repository: ReportRepository = DEFAULT_REPORT_REPOSITORY,
) -> dict[str, Any]:
    """Save report content first, then index metadata after all content is durable."""

    keys = report_bundle_keys_for_filename(filename)
    data_snapshot_payload = sanitize_for_snapshot(data_snapshot)
    if not isinstance(data_snapshot_payload, dict):
        data_snapshot_payload = {}
    data_trust = data_snapshot_payload.get("data_trust")
    data_bytes = json.dumps(data_snapshot_payload, ensure_ascii=False, indent=2).encode("utf-8")
    saved_keys: list[str] = []

    try:
        storage.save_report(
            keys.html_key,
            str(html_content or "").encode("utf-8"),
            content_type=HTML_CONTENT_TYPE,
        )
        saved_keys.append(keys.html_key)
        storage.save_report(
            keys.md_key,
            str(markdown_content or "").encode("utf-8"),
            content_type=MARKDOWN_CONTENT_TYPE,
        )
        saved_keys.append(keys.md_key)
        storage.save_report(keys.data_key, data_bytes, content_type=DATA_SNAPSHOT_CONTENT_TYPE)
        saved_keys.append(keys.data_key)

        metadata = repository.upsert(
            keys.filename,
            output_dir=output_dir,
            html_content=html_content,
            markdown_content=markdown_content,
            data_trust=data_trust,
        )
    except Exception:
        for saved_key in reversed(saved_keys):
            try:
                storage.delete_report(saved_key)
            except Exception:
                pass
        raise
    return {
        "filename": keys.filename,
        "md_filename": keys.md_filename,
        "data_filename": keys.data_filename,
        "html_key": keys.html_key,
        "md_key": keys.md_key,
        "data_key": keys.data_key,
        "data_trust": data_trust,
        "metadata": metadata or {},
    }


__all__ = [
    "DATA_SNAPSHOT_CONTENT_TYPE",
    "HTML_CONTENT_TYPE",
    "MARKDOWN_CONTENT_TYPE",
    "ReportBundleKeys",
    "persist_report_bundle",
    "report_bundle_keys_for_filename",
]
