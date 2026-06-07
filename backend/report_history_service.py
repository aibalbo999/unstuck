"""Report history, file download, and cleanup services."""

from __future__ import annotations

import os
import time

from fastapi.responses import FileResponse, HTMLResponse

from config import REPORT_RETENTION_DAYS
from data_trust import data_snapshot_filename_for_report
from report_index import is_safe_report_filename, normalize_recommendation_label, parse_recommendation_summary as parse_report_recommendation_summary
from report_repository import DEFAULT_REPORT_REPOSITORY, ReportListQuery, ReportRepository


def parse_recommendation_summary(filename: str, output_dir: str) -> dict:
    return parse_report_recommendation_summary(filename, output_dir=output_dir)


def cleanup_expired_reports(
    output_dir: str,
    report_cache: dict,
    retention_days: int = REPORT_RETENTION_DAYS,
    repository: ReportRepository = DEFAULT_REPORT_REPOSITORY,
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
) -> dict:
    cleanup_expired_reports(output_dir, report_cache)
    cleanup_orphan_markdown_reports(output_dir)
    query = q.strip().lower()
    pipeline_filter = pipeline.strip().lower()
    if pipeline_filter in {"mode_a", "a", "academic"}:
        pipeline_filter = "v1"
    elif pipeline_filter in {"mode_b", "b", "trading"}:
        pipeline_filter = "v2"
    if pipeline_filter not in {"all", "v1", "v2"}:
        pipeline_filter = "all"

    recommendation_filter = normalize_recommendation_label(recommendation)
    if recommendation_filter not in {"買入", "持有", "避免"}:
        recommendation_filter = "all"
    data_trust_value = data_trust if isinstance(data_trust, str) else "all"
    data_trust_filter = data_trust_value.strip().lower()
    if data_trust_filter not in {"all", "fresh", "partial", "stale", "error", "unknown"}:
        data_trust_filter = "all"
    include_versions_filter = _normalize_include_versions(include_versions)

    if os.path.exists(output_dir):
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
            )
        )
    else:
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
) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        return {"success": False, "error": "Invalid filename"}

    html_path = os.path.join(output_dir, filename)
    md_filename = filename[:-5] + ".md"
    data_filename = data_snapshot_filename_for_report(filename)
    md_path = os.path.join(output_dir, md_filename)
    data_path = os.path.join(output_dir, data_filename)

    if not os.path.exists(html_path) and not os.path.exists(md_path) and not os.path.exists(data_path):
        return {"success": False, "error": "File not found"}

    deleted = []
    errors = []
    for path in [html_path, md_path, data_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted.append(os.path.basename(path))
            except Exception as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")

    if errors:
        return {"success": False, "error": "; ".join(errors), "deleted": deleted}

    for ticker, cached_filename in list(report_cache.items()):
        if cached_filename == filename:
            del report_cache[ticker]
    repository.delete(filename, output_dir)
    return {"success": True, "deleted": deleted}


def get_report_file(filename: str, output_dir: str):
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    filepath = os.path.join(output_dir, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/html")
    return HTMLResponse("<h1>找不到報告</h1>", status_code=404)


def download_report_file(filename: str, output_dir: str, kind: str):
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    if kind == "html":
        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            return FileResponse(
                filepath,
                filename=filename,
                media_type="text/html",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        return HTMLResponse("<h1>找不到報告</h1>", status_code=404)
    if kind == "md":
        md_filename = filename.replace(".html", ".md")
        filepath = os.path.join(output_dir, md_filename)
        if os.path.exists(filepath):
            return FileResponse(
                filepath,
                filename=md_filename,
                media_type="text/markdown",
                headers={"Content-Disposition": f"attachment; filename={md_filename}"},
            )
        return HTMLResponse("<h1>找不到報告 Markdown 版本</h1>", status_code=404)
    if kind == "data":
        data_filename = data_snapshot_filename_for_report(filename)
        filepath = os.path.join(output_dir, data_filename)
        if os.path.exists(filepath):
            return FileResponse(
                filepath,
                filename=data_filename,
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={data_filename}"},
            )
        return HTMLResponse("<h1>找不到報告資料快照</h1>", status_code=404)
    raise ValueError(f"Unknown report download kind: {kind}")
