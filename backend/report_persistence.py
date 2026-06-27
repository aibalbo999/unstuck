"""Persist rendered report bundles through report content storage."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from data_trust import data_snapshot_filename_for_report
from report_repository import DEFAULT_REPORT_REPOSITORY, ReportRepository
from storage.report_storage import ReportStorage


HTML_CONTENT_TYPE = "text/html"
MARKDOWN_CONTENT_TYPE = "text/markdown"
DATA_SNAPSHOT_CONTENT_TYPE = "application/json"


@dataclass(frozen=True)
class ReportBundleKeys:
    html_key: str
    md_key: str
    data_key: str

    @property
    def filename(self) -> str:
        return self.html_key

    @property
    def md_filename(self) -> str:
        return self.md_key

    @property
    def data_filename(self) -> str:
        return self.data_key


def report_bundle_keys_for_filename(filename: str) -> ReportBundleKeys:
    stem, extension = os.path.splitext(filename)
    html_key = filename if extension == ".html" else f"{stem}.html"
    html_stem = html_key[:-5] if html_key.endswith(".html") else os.path.splitext(html_key)[0]
    return ReportBundleKeys(
        html_key=html_key,
        md_key=f"{html_stem}.md",
        data_key=data_snapshot_filename_for_report(html_key),
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
    data_bytes = json.dumps(data_snapshot, ensure_ascii=False, indent=2).encode("utf-8")
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
            data_trust=data_snapshot.get("data_trust") if isinstance(data_snapshot, dict) else None,
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
        "data_trust": data_snapshot.get("data_trust") if isinstance(data_snapshot, dict) else None,
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
