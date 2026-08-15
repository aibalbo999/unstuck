"""Summarize report quality metadata coverage without changing report artifacts."""

from __future__ import annotations

import json
from typing import Any

from data_trust_snapshot import verify_data_snapshot_integrity
from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text
from report_history_pagination import collect_all_report_pages
from report_history_storage import load_storage_item, storage_for_existing_output_dir
from report_index import query_report_metadata
from report_quality_repair_items import quality_metadata_repair_item


SCHEMA_VERSION = "report_quality_audit.v1"


def build_indexed_report_quality_audit(output_dir: str, *, page_size: int = 100, item_limit: int = 5) -> dict[str, Any]:
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
    reports = [_report_from_index_row(row, storage) for row in rows.get("reports", [])]
    return build_report_quality_audit(reports, scope="all_indexed_reports", item_limit=item_limit)


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


def build_report_quality_audit(
    reports: dict[str, Any] | list[dict[str, Any]],
    *,
    scope: str = "daily_report_sample",
    item_limit: int = 5,
) -> dict[str, Any]:
    rows = _report_rows(reports)
    verified_snapshot_reports = 0
    invalid_snapshot_reports = 0
    unverified_snapshot_reports = 0
    complete_reports = 0
    missing_items = []
    for report in rows:
        snapshot = safe_mapping_dict(report.get("snapshot_integrity")) or {}
        snapshot_status = safe_text(snapshot.get("status")).strip().lower()
        if snapshot_status != "verified":
            if snapshot_status == "invalid":
                invalid_snapshot_reports += 1
            else:
                unverified_snapshot_reports += 1
            continue
        verified_snapshot_reports += 1
        item = quality_metadata_repair_item(report)
        if item is None:
            complete_reports += 1
            continue
        missing_items.append(_audit_item(report, item))

    missing_count = len(missing_items)
    coverage = round(complete_reports / verified_snapshot_reports * 100, 2) if verified_snapshot_reports else None
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": safe_text(scope).strip() or "daily_report_sample",
        "audited_reports": len(rows),
        "verified_snapshot_reports": verified_snapshot_reports,
        "snapshot_invalid_reports": invalid_snapshot_reports,
        "snapshot_unverified_reports": unverified_snapshot_reports,
        "quality_metadata_complete_reports": complete_reports,
        "quality_metadata_missing_reports": missing_count,
        "quality_metadata_coverage_pct": coverage,
        "quality_metadata_coverage_basis": "verified_snapshot_reports",
        "items": missing_items[: max(0, safe_int(item_limit, default=5))],
    }


def build_unavailable_report_quality_audit(*, scope: str = "all_indexed_reports") -> dict[str, Any]:
    return {
        **build_report_quality_audit([], scope=scope),
        "status": "unavailable",
        "error_code": "quality_audit_unavailable",
    }


def _audit_item(report: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": safe_text(report.get("ticker")).strip(),
        "filename": safe_text(report.get("filename") or report.get("report_filename")).strip(),
        "pipeline_id": safe_text(report.get("pipeline_id")).strip() or "v1",
        "title": safe_text(item.get("title")).strip(),
        "recommended_action": safe_text(item.get("recommended_action")).strip(),
        "priority_score": safe_int(item.get("priority_score"), default=0),
        "blocks_auto_rerun": bool(item.get("blocks_auto_rerun")),
    }


def _report_rows(reports: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    envelope = safe_mapping_dict(reports)
    return safe_dict_list(envelope.get("reports") if envelope is not None else reports)


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
        "pipeline_id": safe_text(row.get("pipeline_id")).strip() or "v1",
        "snapshot_integrity": integrity,
        "refreshed_from_report": safe_text(snapshot.get("refreshed_from_report")).strip(),
        "snapshot_refreshed_at": safe_text(snapshot.get("snapshot_refreshed_at")).strip(),
        "report_conformance": snapshot.get("report_conformance", {}),
        "evidence_exit_gate": snapshot.get("evidence_exit_gate", {}),
        "content_credibility": snapshot.get("content_credibility", {}),
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
