"""Summarize report quality metadata coverage without changing report artifacts."""

from __future__ import annotations

import json
from collections import OrderedDict
from hashlib import sha256
from threading import RLock
from time import monotonic
from typing import Any

from data_trust_snapshot import verify_data_snapshot_integrity
from mapping_fields import safe_text, safe_text_list
from report_history_pagination import collect_all_report_pages
from report_history_storage import load_storage_item, storage_for_existing_output_dir
from report_index import query_report_metadata
from report_quality_repair_items import quality_metadata_repair_item
from report_quality_evidence import read_artifact_quality_summary
from reporting.content_credibility_final_audit import align_content_credibility_with_final_audit
from report_quality_audit_payload import (
    ARTIFACT_QUALITY_SUMMARY_STATUSES,
    QUALITY_METADATA_FIELDS,
    QUALITY_METADATA_PROVENANCE,
    QUALITY_REVIEW_STATUSES,
    SCHEMA_VERSION,
    _audit_item,
    _quality_review_status,
    build_report_quality_audit,
    build_unavailable_report_quality_audit,
)


REPORT_QUALITY_ROWS_CACHE_TTL_SECONDS = 15.0
REPORT_QUALITY_ROWS_CACHE_MAX_ENTRIES = 8
_REPORT_QUALITY_ROWS_CACHE: OrderedDict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = OrderedDict()
_REPORT_QUALITY_ROWS_CACHE_LOCK = RLock()


def build_indexed_report_quality_audit(output_dir: str, *, page_size: int = 100, item_limit: int = 5, item_offset: int = 0) -> dict[str, Any]:
    rows = collect_all_report_pages(
        list_indexed_report_quality_rows,
        page_size=page_size,
        q="",
        pipeline="all",
        recommendation="all",
        data_trust="all",
        include_versions=False,
        output_dir=output_dir,
        sync_metadata=False,
    )
    storage = storage_for_existing_output_dir(output_dir, None)
    reports = _cached_indexed_quality_reports(
        rows.get("reports", []),
        storage,
        cache_namespace=f"latest_per_ticker_pipeline:{output_dir}",
    )
    from report_quality_review_workflow import attach_quality_reviews
    attach_quality_reviews(reports, output_dir)
    return build_report_quality_audit(reports, scope="all_indexed_reports", item_limit=item_limit, item_offset=item_offset)


def build_historical_indexed_report_quality_audit(
    output_dir: str,
    *,
    page_size: int = 100,
    item_limit: int = 25,
    item_offset: int = 0,
    q: str = "",
    pipeline: str = "all",
    review_status: str = "all",
    missing_field: str = "all",
) -> dict[str, Any]:
    rows = collect_all_report_pages(
        list_indexed_report_quality_rows,
        page_size=page_size,
        q=q,
        pipeline=pipeline,
        recommendation="all",
        data_trust="all",
        include_versions=True,
        output_dir=output_dir,
        sync_metadata=False,
    )
    storage = storage_for_existing_output_dir(output_dir, None)
    reports = _cached_indexed_quality_reports(
        rows.get("reports", []),
        storage,
        cache_namespace=(
            f"historical:{output_dir}:{safe_text(q).strip().lower()}:{safe_text(pipeline).strip().lower()}"
        ),
    )
    from report_quality_review_workflow import attach_quality_reviews
    attach_quality_reviews(reports, output_dir)
    review_status_filter = _normalize_review_status_filter(review_status)
    missing_quality_field_filter = _normalize_quality_field_filter(missing_field)
    if review_status_filter != "all" or missing_quality_field_filter != "all":
        filtered_reports = []
        for report in reports:
            item = quality_metadata_repair_item(report)
            if item is None:
                continue
            if review_status_filter != "all" and _quality_review_status(report) != review_status_filter:
                continue
            if missing_quality_field_filter != "all" and missing_quality_field_filter not in safe_text_list(item.get("missing_quality_fields")):
                continue
            filtered_reports.append(report)
        reports = filtered_reports
    payload = build_report_quality_audit(
        reports,
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
        item_limit=item_limit,
        item_offset=item_offset,
    )
    payload["review_status_filter"] = review_status_filter
    payload["missing_quality_field_filter"] = missing_quality_field_filter
    return payload


def list_indexed_report_quality_rows(
    *,
    page: int,
    limit: int,
    q: str,
    pipeline: str,
    recommendation: str,
    data_trust: str,
    include_versions: bool,
    output_dir: str,
    sync_metadata: bool,
) -> dict[str, Any]:
    rows, total = query_report_metadata(
        page=page,
        limit=limit,
        q=q,
        pipeline=pipeline,
        recommendation=recommendation,
        data_trust=data_trust,
        include_versions=include_versions,
        output_dir=output_dir,
        sync_metadata=sync_metadata,
        row_mapper=_raw_row,
    )
    return {
        "reports": rows,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": max((total + limit - 1) // limit, 1),
        },
    }


def _indexed_quality_reports(rows: list[dict[str, Any]], storage: Any) -> list[dict[str, Any]]:
    from report_quality_review_workflow import report_quality_revision
    reports = []
    for row in rows:
        report = _report_from_index_row(row, storage)
        report["report_quality_revision"] = report_quality_revision(row)
        if quality_metadata_repair_item(report) is not None:
            report["artifact_quality_summary"] = _read_artifact_quality_summary(storage, report.get("filename"))
        reports.append(report)
    return reports


def _cached_indexed_quality_reports(
    rows: list[dict[str, Any]],
    storage: Any,
    *,
    cache_namespace: str,
) -> list[dict[str, Any]]:
    cache_key = (cache_namespace, _indexed_rows_fingerprint(rows))
    now = monotonic()
    with _REPORT_QUALITY_ROWS_CACHE_LOCK:
        cached = _REPORT_QUALITY_ROWS_CACHE.get(cache_key)
        if cached is not None and now - cached[0] < REPORT_QUALITY_ROWS_CACHE_TTL_SECONDS:
            _REPORT_QUALITY_ROWS_CACHE.move_to_end(cache_key)
            return cached[1]

    reports = _indexed_quality_reports(rows, storage)
    with _REPORT_QUALITY_ROWS_CACHE_LOCK:
        _REPORT_QUALITY_ROWS_CACHE[cache_key] = (monotonic(), reports)
        _REPORT_QUALITY_ROWS_CACHE.move_to_end(cache_key)
        while len(_REPORT_QUALITY_ROWS_CACHE) > REPORT_QUALITY_ROWS_CACHE_MAX_ENTRIES:
            _REPORT_QUALITY_ROWS_CACHE.popitem(last=False)
    return reports


def _indexed_rows_fingerprint(rows: list[dict[str, Any]]) -> str:
    digest = sha256()
    fields = (
        "output_dir",
        "filename",
        "pipeline_id",
        "updated_at",
        "file_mtime",
        "data_snapshot_hash",
        "html_hash",
        "markdown_hash",
        "data_file_hash",
    )
    for row in rows:
        digest.update("\x1f".join(safe_text(row.get(field)) for field in fields).encode("utf-8"))
        digest.update(b"\x1e")
    return digest.hexdigest()


def _read_artifact_quality_summary(storage: Any, filename: Any) -> dict[str, Any]:
    return read_artifact_quality_summary(storage, filename, load_item=load_storage_item)


def _raw_row(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _report_from_index_row(row: dict[str, Any], storage: Any) -> dict[str, Any]:
    filename = safe_text(row.get("filename")).strip()
    snapshot = {}
    try:
        item = load_storage_item(storage, filename, kind="data") if storage and filename else None
    except Exception:
        item = None
    if item is not None:
        try:
            snapshot = json.loads(item.content)
        except Exception:
            snapshot = {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    integrity = _snapshot_integrity(snapshot)
    return {
        "ticker": safe_text(row.get("ticker")).strip(),
        "filename": filename,
        "report_date": safe_text(row.get("report_date") or row.get("date")).strip(),
        "pipeline_id": safe_text(row.get("pipeline_id")).strip() or "v1",
        "snapshot_integrity": integrity,
        "refreshed_from_report": safe_text(snapshot.get("refreshed_from_report")).strip(),
        "snapshot_refreshed_at": safe_text(snapshot.get("snapshot_refreshed_at")).strip(),
        "report_conformance": snapshot.get("report_conformance", {}),
        "evidence_exit_gate": snapshot.get("evidence_exit_gate", {}),
        "content_credibility": align_content_credibility_with_final_audit(
            snapshot.get("content_credibility", {}),
            snapshot.get("final_audit") or snapshot.get("report_conformance", {}),
        ),
    }


def _snapshot_integrity(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not snapshot:
        return {"status": "unverified", "valid": None, "errors": ["snapshot unavailable"]}
    try:
        integrity = verify_data_snapshot_integrity(snapshot)
    except Exception:
        return {"status": "unverified", "valid": None, "errors": ["snapshot integrity check failed"]}
    expected_hash = safe_text(integrity.get("expected_hash")).strip()
    if not expected_hash:
        return {"status": "unverified", "valid": None, "errors": ["snapshot_hash missing"]}
    return {
        "status": "verified" if integrity.get("valid") else "invalid",
        "valid": bool(integrity.get("valid")),
        "errors": [safe_text(error) for error in integrity.get("errors", []) if safe_text(error)],
    }


def _normalize_review_status_filter(value: Any) -> str:
    normalized = safe_text(value).strip().lower()
    return normalized if normalized in QUALITY_REVIEW_STATUSES else "all"


def _normalize_quality_field_filter(value: Any) -> str:
    normalized = safe_text(value).strip().lower()
    return normalized if normalized in QUALITY_METADATA_FIELDS else "all"
