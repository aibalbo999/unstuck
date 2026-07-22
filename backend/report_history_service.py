"""Report history, file download, and cleanup services."""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from contextlib import nullcontext
from typing import Any

from config import REPORT_RETENTION_DAYS
from report_history_downloads import (
    download_report_response,
    missing_report_response,
    report_file_response,
    secure_html_response,
)
from report_history_query import normalize_report_list_filters
from report_history_storage_keys import (
    basename_for_storage_key as _basename_for_storage_key,
    bundle_keys_for_html_key as _bundle_keys_for_html_key,
    delete_storage_key as _delete_storage_key,
    html_key_for_related_storage_key as _html_key_for_related_storage_key,
)
from report_index import is_safe_report_filename, parse_recommendation_summary as parse_report_recommendation_summary
from report_index_maintenance import cleanup_empty_report_directories
from report_history_storage import (
    existing_storage_key,
    load_storage_item,
    repository_has_metadata,
    should_sync_metadata,
    storage_for_existing_output_dir,
)
from report_repository import DEFAULT_REPORT_REPOSITORY, ReportListQuery, ReportRepository
from storage.report_storage import ReportStorage


LOGGER = logging.getLogger(__name__)

def parse_recommendation_summary(filename: str, output_dir: str) -> dict:
    return parse_report_recommendation_summary(filename, output_dir=output_dir)


def cleanup_expired_reports(
    output_dir: str,
    report_cache: dict | None = None,
    retention_days: int = REPORT_RETENTION_DAYS,
    repository: ReportRepository = DEFAULT_REPORT_REPOSITORY,
    report_cache_lock: Any = None,
    storage: ReportStorage | None = None,
) -> list[str]:
    """Delete old HTML/Markdown/data snapshots so output does not grow forever."""
    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is None or retention_days <= 0:
        return []

    cutoff = time.time() - retention_days * 24 * 60 * 60
    deleted = []
    for item in content_storage.list_reports():
        key = item.key
        if not key.endswith((".html", ".md", ".data.json")):
            continue
        if item.updated_at.timestamp() >= cutoff:
            continue
        if key.endswith(".html"):
            for bundle_key in _bundle_keys_for_html_key(key):
                _delete_storage_key(content_storage, bundle_key, deleted)
            repository.delete(_basename_for_storage_key(key), output_dir)
        else:
            _delete_storage_key(content_storage, key, deleted)

    if deleted:
        if report_cache is not None:
            with report_cache_lock or nullcontext():
                for ticker, cached_filename in list(report_cache.items()):
                    if cached_filename in {_basename_for_storage_key(key) for key in deleted}:
                        del report_cache[ticker]
        cleanup_empty_report_directories(output_dir)
    return deleted


def cleanup_orphan_markdown_reports(output_dir: str, storage: ReportStorage | None = None) -> list[str]:
    """Remove Markdown/data snapshots that no longer have a matching HTML report."""
    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is None:
        return []

    reports = content_storage.list_reports()
    report_keys = {item.key for item in reports}
    deleted = []
    for item in reports:
        key = item.key
        if not key.endswith((".md", ".data.json")):
            continue
        if _html_key_for_related_storage_key(key) in report_keys:
            continue
        _delete_storage_key(content_storage, key, deleted)
    if deleted:
        cleanup_empty_report_directories(output_dir)
    return deleted


def list_reports(
    *,
    page: int,
    limit: int,
    q: str,
    pipeline: str,
    recommendation: str,
    data_trust: str,
    include_versions: bool = False,
    output_dir: str,
    report_cache: dict | None = None,
    repository: ReportRepository = DEFAULT_REPORT_REPOSITORY,
    storage: ReportStorage | None = None,
    sync_metadata: bool | None = None,
) -> dict:
    filters = normalize_report_list_filters(
        q=q,
        pipeline=pipeline,
        recommendation=recommendation,
        data_trust=data_trust,
        include_versions=include_versions,
    )
    sync_metadata_filter = should_sync_metadata(output_dir, storage) if sync_metadata is None else bool(sync_metadata)

    if storage is None and not os.path.exists(output_dir):
        reports, total = [], 0
    else:
        try:
            reports, total = repository.query(
                ReportListQuery(
                    page=page,
                    limit=limit,
                    q=filters["query"],
                    pipeline=filters["pipeline"],
                    recommendation=filters["recommendation"],
                    data_trust=filters["data_trust"],
                    include_versions=filters["include_versions"],
                    output_dir=output_dir,
                    sync_metadata=sync_metadata_filter,
                )
            )
        except sqlite3.Error as exc:
            LOGGER.warning("Report history listing skipped because report index is unavailable: %s", exc)
            reports, total = [], 0

    total_pages = max((total + limit - 1) // limit, 1)
    return {
        "reports": reports,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "query": q,
            "pipeline": filters["pipeline"],
            "recommendation": filters["recommendation"],
            "data_trust": filters["data_trust"],
            "include_versions": filters["include_versions"],
        },
    }


def delete_report_files(
    filename: str,
    output_dir: str,
    report_cache: dict | None = None,
    repository: ReportRepository = DEFAULT_REPORT_REPOSITORY,
    report_cache_lock: Any = None,
    storage: ReportStorage | None = None,
) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        return {"success": False, "error": "Invalid filename"}

    content_storage = storage_for_existing_output_dir(output_dir, storage)

    existing_keys = []
    if content_storage is not None:
        for kind in ("html", "md", "data"):
            key = existing_storage_key(content_storage, filename, kind=kind)
            if key is not None:
                existing_keys.append(key)
    metadata_exists = repository_has_metadata(repository, filename, output_dir)
    if not existing_keys and not metadata_exists:
        return {"success": False, "error": "File not found"}

    try:
        repository.delete(filename, output_dir)
    except Exception as exc:
        return {"success": False, "error": str(exc), "deleted": []}

    deleted = []
    errors = []
    for key in existing_keys:
        try:
            if content_storage is not None and content_storage.delete_report(key):
                deleted.append(key)
        except Exception as exc:
            errors.append(f"{key}: {exc}")

    if errors:
        return {"success": False, "error": "; ".join(errors), "deleted": deleted}
    if deleted:
        cleanup_empty_report_directories(output_dir)

    if report_cache is not None:
        with report_cache_lock or nullcontext():
            for ticker, cached_filename in list(report_cache.items()):
                if cached_filename == filename:
                    del report_cache[ticker]
    return {"success": True, "deleted": deleted}


def get_report_file(filename: str, output_dir: str, storage: ReportStorage | None = None):
    if not is_safe_report_filename(filename, ".html"):
        return secure_html_response("<h1>Invalid filename</h1>", status_code=400)
    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is None:
        return missing_report_response("html")
    return report_file_response(filename, content_storage)


def download_report_file(filename: str, output_dir: str, kind: str, storage: ReportStorage | None = None):
    if not is_safe_report_filename(filename, ".html"):
        return secure_html_response("<h1>Invalid filename</h1>", status_code=400)
    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is None:
        return missing_report_response(kind)
    return download_report_response(filename, kind, content_storage)
