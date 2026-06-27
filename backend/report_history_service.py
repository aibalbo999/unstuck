"""Report history, file download, and cleanup services."""

from __future__ import annotations

import os
import time
from contextlib import nullcontext
from typing import Any

from fastapi.responses import HTMLResponse, Response

from config import REPORT_RETENTION_DAYS
from data_trust import data_snapshot_filename_for_report
from report_index import is_safe_report_filename, normalize_recommendation_label, parse_recommendation_summary as parse_report_recommendation_summary
from report_index_maintenance import cleanup_empty_report_directories
from report_history_storage import (
    existing_storage_key,
    load_storage_item,
    repository_has_metadata,
    should_sync_metadata,
    storage_for_existing_output_dir,
)
from report_repository import DEFAULT_REPORT_REPOSITORY, ReportListQuery, ReportRepository
from report_view_repair import repair_report_html_for_view
from storage.report_storage import ReportStorage


def parse_recommendation_summary(filename: str, output_dir: str) -> dict:
    return parse_report_recommendation_summary(filename, output_dir=output_dir)


def cleanup_expired_reports(
    output_dir: str,
    report_cache: dict,
    retention_days: int = REPORT_RETENTION_DAYS,
    repository: ReportRepository = DEFAULT_REPORT_REPOSITORY,
    report_cache_lock: Any = None,
) -> list[str]:
    """Delete old HTML/Markdown/data snapshots so output does not grow forever."""
    if not os.path.exists(output_dir) or retention_days <= 0:
        return []

    cutoff = time.time() - retention_days * 24 * 60 * 60
    deleted = []
    for filename in os.listdir(output_dir):
        if not filename.endswith((".html", ".md", ".data.json")):
            continue
        path = os.path.join(output_dir, filename)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                deleted.append(filename)
                if filename.endswith(".html"):
                    repository.delete(filename, output_dir)
        except OSError:
            pass

    if deleted:
        with report_cache_lock or nullcontext():
            for ticker, cached_filename in list(report_cache.items()):
                if cached_filename in deleted:
                    del report_cache[ticker]
    return deleted


def cleanup_orphan_markdown_reports(output_dir: str) -> list[str]:
    """Remove Markdown/data snapshots that no longer have a matching HTML report."""
    if not os.path.exists(output_dir):
        return []

    html_stems = {
        os.path.splitext(filename)[0]
        for filename in os.listdir(output_dir)
        if filename.endswith(".html")
    }
    deleted = []
    for filename in os.listdir(output_dir):
        if not filename.endswith((".md", ".data.json")):
            continue
        stem = filename[:-10] if filename.endswith(".data.json") else os.path.splitext(filename)[0]
        if stem in html_stems:
            continue
        path = os.path.join(output_dir, filename)
        try:
            os.remove(path)
            deleted.append(filename)
        except OSError:
            pass
    return deleted


def _normalize_include_versions(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


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
    report_cache: dict,
    repository: ReportRepository = DEFAULT_REPORT_REPOSITORY,
    storage: ReportStorage | None = None,
) -> dict:
    query = q.strip().lower()
    pipeline_filter = pipeline.strip().lower()
    if pipeline_filter in {"mode_a", "a", "academic"}:
        pipeline_filter = "v1"
    elif pipeline_filter in {"mode_b", "b", "trading"}:
        pipeline_filter = "v2"
    elif pipeline_filter in {"mode_c", "c", "contrarian", "bubble", "short"}:
        pipeline_filter = "v3"
    elif pipeline_filter in {"mode_d", "d", "swing", "short_term", "short-term", "momentum"}:
        pipeline_filter = "v4"
    if pipeline_filter not in {"all", "v1", "v2", "v3", "v4"}:
        pipeline_filter = "all"

    recommendation_filter = normalize_recommendation_label(recommendation)
    if recommendation_filter not in {"買入", "買進", "持有", "避免", "強烈放空"}:
        recommendation_filter = "all"
    data_trust_value = data_trust if isinstance(data_trust, str) else "all"
    data_trust_filter = data_trust_value.strip().lower()
    if data_trust_filter not in {"all", "fresh", "partial", "stale", "error", "unknown"}:
        data_trust_filter = "all"
    include_versions_filter = _normalize_include_versions(include_versions)

    if storage is None and not os.path.exists(output_dir):
        reports, total = [], 0
    else:
        reports, total = repository.query(
            ReportListQuery(
                page=page,
                limit=limit,
                q=query,
                pipeline=pipeline_filter,
                recommendation=recommendation_filter,
                data_trust=data_trust_filter,
                include_versions=include_versions_filter,
                output_dir=output_dir,
                sync_metadata=should_sync_metadata(output_dir, storage),
            )
        )

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
            "pipeline": pipeline_filter,
            "recommendation": recommendation_filter,
            "data_trust": data_trust_filter,
            "include_versions": include_versions_filter,
        },
    }


def delete_report_files(
    filename: str,
    output_dir: str,
    report_cache: dict,
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

    with report_cache_lock or nullcontext():
        for ticker, cached_filename in list(report_cache.items()):
            if cached_filename == filename:
                del report_cache[ticker]
    return {"success": True, "deleted": deleted}


def get_report_file(filename: str, output_dir: str, storage: ReportStorage | None = None):
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is None:
        return HTMLResponse("<h1>找不到報告</h1>", status_code=404)
    item = load_storage_item(content_storage, filename, kind="html")
    if item is None:
        return HTMLResponse("<h1>找不到報告</h1>", status_code=404)
    html = repair_report_html_for_view(item.content.decode("utf-8"))
    return HTMLResponse(html, media_type="text/html")


def download_report_file(filename: str, output_dir: str, kind: str, storage: ReportStorage | None = None):
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is None:
        if kind == "md":
            return HTMLResponse("<h1>找不到報告 Markdown 版本</h1>", status_code=404)
        if kind == "data":
            return HTMLResponse("<h1>找不到報告資料快照</h1>", status_code=404)
        if kind == "html":
            return HTMLResponse("<h1>找不到報告</h1>", status_code=404)
        raise ValueError(f"Unknown report download kind: {kind}")
    if kind == "html":
        item = load_storage_item(content_storage, filename, kind="html")
        if item is None:
            return HTMLResponse("<h1>找不到報告</h1>", status_code=404)
        html = repair_report_html_for_view(item.content.decode("utf-8"))
        return HTMLResponse(
            html,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if kind == "md":
        md_filename = filename[:-5] + ".md"
        item = load_storage_item(content_storage, filename, kind="md")
        if item is not None:
            return Response(
                content=item.content,
                media_type=item.metadata.content_type,
                headers={"Content-Disposition": f"attachment; filename={md_filename}"},
            )
        return HTMLResponse("<h1>找不到報告 Markdown 版本</h1>", status_code=404)
    if kind == "data":
        data_filename = data_snapshot_filename_for_report(filename)
        item = load_storage_item(content_storage, filename, kind="data")
        if item is not None:
            return Response(
                content=item.content,
                media_type=item.metadata.content_type,
                headers={"Content-Disposition": f"attachment; filename={data_filename}"},
            )
        return HTMLResponse("<h1>找不到報告資料快照</h1>", status_code=404)
    raise ValueError(f"Unknown report download kind: {kind}")
