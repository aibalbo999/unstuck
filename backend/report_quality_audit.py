"""Summarize report quality metadata coverage without changing report artifacts."""

from __future__ import annotations

import json
import re
from typing import Any

from data_trust_snapshot import verify_data_snapshot_integrity
from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text, safe_text_list
from report_history_pagination import collect_all_report_pages
from report_history_storage import load_storage_item, storage_for_existing_output_dir
from report_index import query_report_metadata
from report_quality_repair_items import quality_metadata_repair_item


SCHEMA_VERSION = "report_quality_audit.v1"
QUALITY_METADATA_FIELDS = ("report_conformance", "evidence_exit_gate", "content_credibility")
QUALITY_METADATA_PROVENANCE = ("after_refresh", "no_refresh_provenance")
ARTIFACT_QUALITY_SUMMARY_STATUSES = ("present", "not_found", "unavailable")
ARTIFACT_QUALITY_MARKERS = {
    "report_conformance": (
        re.compile(r"(?im)^\s*-\s*\*\*Report conformance:\*\*\s*\S+"),
        re.compile(r"(?is)<[^>]*>\s*Report conformance[:：]\s*[^<\n]+"),
    ),
    "evidence_exit_gate": (
        re.compile(r"(?im)^\s*-\s*\*\*Evidence gate:\*\*\s*\S+"),
        re.compile(r"(?is)<[^>]*>\s*Evidence gate[:：]\s*[^<\n]+"),
    ),
    "content_credibility": (
        re.compile(r"(?im)^\s*-\s*\*\*Content credibility:\*\*\s*\S+"),
        re.compile(r"(?is)<[^>]*>\s*Content credibility[:：]\s*[^<\n]+"),
    ),
}


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
    reports = _indexed_quality_reports(rows.get("reports", []), storage)
    return build_report_quality_audit(reports, scope="all_indexed_reports", item_limit=item_limit, item_offset=item_offset)


def build_historical_indexed_report_quality_audit(
    output_dir: str,
    *,
    page_size: int = 100,
    item_limit: int = 25,
    item_offset: int = 0,
    q: str = "",
    pipeline: str = "all",
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
    reports = _indexed_quality_reports(rows.get("reports", []), storage)
    return build_report_quality_audit(
        reports,
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
        item_limit=item_limit,
        item_offset=item_offset,
    )


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
    item_offset: int = 0,
    selection_basis: str | None = None,
) -> dict[str, Any]:
    rows = _report_rows(reports)
    scope_text = safe_text(scope).strip() or "daily_report_sample"
    selection_basis_text = safe_text(selection_basis).strip() or (
        "latest_per_ticker_pipeline" if scope_text == "all_indexed_reports" else "caller_supplied_rows"
    )
    verified_snapshot_reports = 0
    invalid_snapshot_reports = 0
    unverified_snapshot_reports = 0
    complete_reports = 0
    missing_items = []
    missing_quality_field_counts = {field: 0 for field in QUALITY_METADATA_FIELDS}
    missing_quality_by_provenance = {provenance: 0 for provenance in QUALITY_METADATA_PROVENANCE}
    artifact_quality_summary_by_status = {status: 0 for status in ARTIFACT_QUALITY_SUMMARY_STATUSES}
    artifact_quality_summary_by_field = {field: 0 for field in QUALITY_METADATA_FIELDS}
    pipeline_quality_stats: dict[str, dict[str, Any]] = {}
    for report in rows:
        pipeline_id = safe_text(report.get("pipeline_id")).strip() or "v1"
        pipeline_stats = pipeline_quality_stats.setdefault(pipeline_id, _new_quality_stats())
        pipeline_stats["audited_reports"] += 1
        snapshot = safe_mapping_dict(report.get("snapshot_integrity")) or {}
        snapshot_status = safe_text(snapshot.get("status")).strip().lower()
        if snapshot_status != "verified":
            if snapshot_status == "invalid":
                invalid_snapshot_reports += 1
                pipeline_stats["snapshot_invalid_reports"] += 1
            else:
                unverified_snapshot_reports += 1
                pipeline_stats["snapshot_unverified_reports"] += 1
            continue
        verified_snapshot_reports += 1
        pipeline_stats["verified_snapshot_reports"] += 1
        item = quality_metadata_repair_item(report)
        if item is None:
            complete_reports += 1
            pipeline_stats["quality_metadata_complete_reports"] += 1
            continue
        missing_count_for_pipeline = pipeline_stats["quality_metadata_missing_reports"] + 1
        pipeline_stats["quality_metadata_missing_reports"] = missing_count_for_pipeline
        for field in safe_text_list(item.get("missing_quality_fields")):
            if field in missing_quality_field_counts:
                missing_quality_field_counts[field] += 1
                pipeline_stats["missing_quality_field_counts"][field] += 1
        provenance = _quality_metadata_provenance(item)
        missing_quality_by_provenance[provenance] += 1
        pipeline_stats["quality_metadata_missing_by_provenance"][provenance] += 1
        artifact_summary = safe_mapping_dict(report.get("artifact_quality_summary")) or {}
        artifact_status = safe_text(artifact_summary.get("status")).strip().lower()
        if artifact_status in artifact_quality_summary_by_status:
            artifact_quality_summary_by_status[artifact_status] += 1
        artifact_fields = set(safe_text_list(artifact_summary.get("fields")))
        for field in QUALITY_METADATA_FIELDS:
            if field in artifact_fields:
                artifact_quality_summary_by_field[field] += 1
        missing_items.append(_audit_item(report, item))

    missing_count = len(missing_items)
    coverage = round(complete_reports / verified_snapshot_reports * 100, 2) if verified_snapshot_reports else None
    quality_metadata_by_pipeline = {
        pipeline_id: _finalize_quality_stats(pipeline_quality_stats[pipeline_id])
        for pipeline_id in sorted(pipeline_quality_stats)
    }
    item_limit_value = max(0, safe_int(item_limit, default=5))
    item_offset_value = max(0, safe_int(item_offset, default=0))
    returned_items = missing_items[item_offset_value:item_offset_value + item_limit_value] if item_limit_value else []
    items_has_prev = item_offset_value > 0 and item_limit_value > 0
    items_has_next = item_limit_value > 0 and item_offset_value + len(returned_items) < missing_count
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": scope_text,
        "selection_basis": selection_basis_text,
        "audited_reports": len(rows),
        "verified_snapshot_reports": verified_snapshot_reports,
        "snapshot_invalid_reports": invalid_snapshot_reports,
        "snapshot_unverified_reports": unverified_snapshot_reports,
        "quality_metadata_complete_reports": complete_reports,
        "quality_metadata_missing_reports": missing_count,
        "missing_quality_field_counts": missing_quality_field_counts,
        "quality_metadata_missing_by_provenance": missing_quality_by_provenance,
        "artifact_quality_summary_by_status": artifact_quality_summary_by_status,
        "artifact_quality_summary_by_field": artifact_quality_summary_by_field,
        "quality_metadata_by_pipeline": quality_metadata_by_pipeline,
        "quality_metadata_coverage_pct": coverage,
        "quality_metadata_coverage_basis": "verified_snapshot_reports",
        "items_offset": item_offset_value,
        "items_limit": item_limit_value,
        "items_total": missing_count,
        "items": returned_items,
        "items_returned": len(returned_items),
        "items_has_prev": items_has_prev,
        "items_has_next": items_has_next,
        "items_truncated": missing_count > len(returned_items),
    }


def build_unavailable_report_quality_audit(
    *,
    scope: str = "all_indexed_reports",
    selection_basis: str | None = None,
) -> dict[str, Any]:
    return {
        **build_report_quality_audit([], scope=scope, selection_basis=selection_basis),
        "status": "unavailable",
        "error_code": "quality_audit_unavailable",
    }


def _audit_item(report: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "ticker": safe_text(report.get("ticker")).strip(),
        "filename": safe_text(report.get("filename") or report.get("report_filename")).strip(),
        "report_date": safe_text(report.get("report_date")).strip(),
        "pipeline_id": safe_text(report.get("pipeline_id")).strip() or "v1",
        "title": safe_text(item.get("title")).strip(),
        "detail": safe_text(item.get("detail")).strip(),
        "missing_quality_fields": safe_text_list(item.get("missing_quality_fields")),
        "reason_codes": safe_text_list(item.get("reason_codes")),
        "quality_metadata_provenance": _quality_metadata_provenance(item),
        "refreshed_from_report": safe_text(report.get("refreshed_from_report")).strip(),
        "snapshot_refreshed_at": safe_text(report.get("snapshot_refreshed_at")).strip(),
        "recommended_action": safe_text(item.get("recommended_action")).strip(),
        "priority_score": safe_int(item.get("priority_score"), default=0),
        "blocks_auto_rerun": bool(item.get("blocks_auto_rerun")),
    }
    artifact_summary = safe_mapping_dict(report.get("artifact_quality_summary"))
    if artifact_summary is not None:
        payload["artifact_quality_summary"] = {
            "status": safe_text(artifact_summary.get("status")).strip() or "unavailable",
            "source": safe_text(artifact_summary.get("source")).strip(),
            "fields": [field for field in safe_text_list(artifact_summary.get("fields")) if field in QUALITY_METADATA_FIELDS],
        }
    return payload


def _indexed_quality_reports(rows: list[dict[str, Any]], storage: Any) -> list[dict[str, Any]]:
    reports = []
    for row in rows:
        report = _report_from_index_row(row, storage)
        if quality_metadata_repair_item(report) is not None:
            report["artifact_quality_summary"] = _read_artifact_quality_summary(storage, report.get("filename"))
        reports.append(report)
    return reports


def _read_artifact_quality_summary(storage: Any, filename: Any) -> dict[str, Any]:
    source = ""
    for kind in ("md", "html"):
        try:
            item = load_storage_item(storage, safe_text(filename).strip(), kind=kind)
        except Exception:
            continue
        if item is None:
            continue
        source = "markdown" if kind == "md" else kind
        try:
            content = item.content
            text = content.decode("utf-8") if isinstance(content, bytes) else safe_text(content)
        except Exception:
            continue
        fields = [
            field
            for field in QUALITY_METADATA_FIELDS
            if any(pattern.search(text) for pattern in ARTIFACT_QUALITY_MARKERS[field])
        ]
        if fields:
            return {"status": "present", "source": source, "fields": fields}
    return {"status": "not_found" if source else "unavailable", "source": source, "fields": []}


def _new_quality_stats() -> dict[str, Any]:
    return {
        "audited_reports": 0,
        "verified_snapshot_reports": 0,
        "snapshot_invalid_reports": 0,
        "snapshot_unverified_reports": 0,
        "quality_metadata_complete_reports": 0,
        "quality_metadata_missing_reports": 0,
        "missing_quality_field_counts": {field: 0 for field in QUALITY_METADATA_FIELDS},
        "quality_metadata_missing_by_provenance": {provenance: 0 for provenance in QUALITY_METADATA_PROVENANCE},
    }


def _finalize_quality_stats(stats: dict[str, Any]) -> dict[str, Any]:
    verified_snapshot_reports = safe_int(stats.get("verified_snapshot_reports"), default=0)
    complete_reports = safe_int(stats.get("quality_metadata_complete_reports"), default=0)
    return {
        **stats,
        "quality_metadata_coverage_pct": round(complete_reports / verified_snapshot_reports * 100, 2) if verified_snapshot_reports else None,
        "quality_metadata_coverage_basis": "verified_snapshot_reports",
    }


def _report_rows(reports: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    envelope = safe_mapping_dict(reports)
    return safe_dict_list(envelope.get("reports") if envelope is not None else reports)


def _quality_metadata_provenance(item: dict[str, Any]) -> str:
    return "after_refresh" if "quality_metadata_after_refresh" in safe_text_list(item.get("reason_codes")) else "no_refresh_provenance"


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
