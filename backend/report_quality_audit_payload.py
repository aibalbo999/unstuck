"""Build report-quality audit envelopes from already loaded report rows."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text, safe_text_list
from report_quality_metadata_repair import (
    QUALITY_METADATA_PROVENANCE,
    quality_metadata_provenance_from_reason_codes,
)
from report_quality_repair_items import quality_metadata_repair_item


SCHEMA_VERSION = "report_quality_audit.v1"
QUALITY_METADATA_FIELDS = ("report_conformance", "evidence_exit_gate", "content_credibility")
QUALITY_REVIEW_STATUSES = ("pending", "approved_with_gap", "rejected", "deferred")
ARTIFACT_QUALITY_SUMMARY_STATUSES = ("present", "not_found", "unavailable")
REPORT_VERSION_STATUSES = ("current", "historical", "unknown")
QUALITY_METADATA_RERUN_EXECUTION_STATUSES = (
    "full_rerun_required",
    "partial_rerun_available",
    "partial_rerun_review_required",
    "partial_rerun_unavailable",
    "not_evaluated",
)
QUALITY_METADATA_RERUN_CONTEXT_STATUSES = (
    "present",
    "partial",
    "artifact_fallback_available",
    "missing",
    "not_evaluated",
)


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
    missing_quality_by_rerun_execution = {
        status: 0 for status in QUALITY_METADATA_RERUN_EXECUTION_STATUSES
    }
    missing_quality_by_rerun_context = {
        status: 0 for status in QUALITY_METADATA_RERUN_CONTEXT_STATUSES
    }
    missing_quality_by_version_status = {status: 0 for status in REPORT_VERSION_STATUSES}
    quality_review_by_status = {status: 0 for status in QUALITY_REVIEW_STATUSES}
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
        pipeline_stats["quality_metadata_missing_reports"] += 1
        rerun_execution_status = safe_text(item.get("rerun_execution_status")).strip().lower()
        rerun_execution_bucket = (
            rerun_execution_status
            if rerun_execution_status in missing_quality_by_rerun_execution
            else "not_evaluated"
        )
        missing_quality_by_rerun_execution[rerun_execution_bucket] += 1
        pipeline_stats["quality_metadata_missing_by_rerun_execution"][rerun_execution_bucket] += 1
        rerun_context_status = safe_text(item.get("rerun_context_status")).strip().lower()
        rerun_context_bucket = (
            rerun_context_status
            if rerun_context_status in missing_quality_by_rerun_context
            else "not_evaluated"
        )
        missing_quality_by_rerun_context[rerun_context_bucket] += 1
        pipeline_stats["quality_metadata_missing_by_rerun_context"][rerun_context_bucket] += 1
        review_status = _quality_review_status(report)
        quality_review_by_status[review_status] += 1
        pipeline_stats["quality_review_by_status"][review_status] += 1
        for field in safe_text_list(item.get("missing_quality_fields")):
            if field in missing_quality_field_counts:
                missing_quality_field_counts[field] += 1
                pipeline_stats["missing_quality_field_counts"][field] += 1
        provenance = _quality_metadata_provenance(item)
        missing_quality_by_provenance[provenance] += 1
        version_status = _report_version_status(report)
        missing_quality_by_version_status[version_status] += 1
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
        "quality_metadata_missing_by_rerun_execution": missing_quality_by_rerun_execution,
        "quality_metadata_missing_by_rerun_context": missing_quality_by_rerun_context,
        "quality_metadata_missing_by_version_status": missing_quality_by_version_status,
        "quality_review_by_status": quality_review_by_status,
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
        "report_version_status": _report_version_status(report),
        "refreshed_from_report": safe_text(report.get("refreshed_from_report")).strip(),
        "snapshot_refreshed_at": safe_text(report.get("snapshot_refreshed_at")).strip(),
        "recommended_action": safe_text(item.get("recommended_action")).strip(),
        "priority_score": safe_int(item.get("priority_score"), default=0),
        "blocks_auto_rerun": bool(item.get("blocks_auto_rerun")),
    }
    refresh_provenance = safe_mapping_dict(report.get("quality_metadata_refresh_provenance"))
    if refresh_provenance:
        payload["quality_metadata_refresh_provenance"] = refresh_provenance
    rerun_context_status = safe_text(item.get("rerun_context_status")).strip()
    if rerun_context_status:
        payload["rerun_context_status"] = rerun_context_status
    for field in ("rerun_execution_status", "snapshot_rerun_context_status", "artifact_rerun_context_status"):
        value = safe_text(item.get(field)).strip()
        if value:
            payload[field] = value
    revision = safe_text(report.get("report_quality_revision")).strip()
    if revision:
        payload["report_quality_revision"] = revision
    quality_review = safe_mapping_dict(report.get("quality_review"))
    if quality_review is not None:
        from report_quality_review_workflow import serialize_quality_review
        payload["quality_review"] = serialize_quality_review(quality_review, revision)
    quality_review_history = report.get("quality_review_history")
    if isinstance(quality_review_history, list):
        from report_quality_review_workflow import serialize_quality_review
        payload["quality_review_history"] = [
            serialize_quality_review(review, revision)
            for review in quality_review_history
            if safe_mapping_dict(review) is not None
        ]
    artifact_summary = safe_mapping_dict(report.get("artifact_quality_summary"))
    if artifact_summary is not None:
        payload["artifact_quality_summary"] = {
            "status": safe_text(artifact_summary.get("status")).strip() or "unavailable",
            "source": safe_text(artifact_summary.get("source")).strip(),
            "fields": [field for field in safe_text_list(artifact_summary.get("fields")) if field in QUALITY_METADATA_FIELDS],
        }
    return payload


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
        "quality_metadata_missing_by_rerun_execution": {
            status: 0 for status in QUALITY_METADATA_RERUN_EXECUTION_STATUSES
        },
        "quality_metadata_missing_by_rerun_context": {
            status: 0 for status in QUALITY_METADATA_RERUN_CONTEXT_STATUSES
        },
        "quality_review_by_status": {status: 0 for status in QUALITY_REVIEW_STATUSES},
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
    return quality_metadata_provenance_from_reason_codes(item.get("reason_codes"))


def _quality_review_status(report: dict[str, Any]) -> str:
    review = safe_mapping_dict(report.get("quality_review")) or {}
    status = safe_text(review.get("status")).strip().lower()
    return status if status in QUALITY_REVIEW_STATUSES else "pending"


def _report_version_status(report: dict[str, Any]) -> str:
    status = safe_text(report.get("report_version_status")).strip().lower()
    return status if status in REPORT_VERSION_STATUSES else "unknown"


__all__ = [
    "ARTIFACT_QUALITY_SUMMARY_STATUSES",
    "QUALITY_METADATA_FIELDS",
    "QUALITY_METADATA_PROVENANCE",
    "QUALITY_METADATA_RERUN_CONTEXT_STATUSES",
    "QUALITY_METADATA_RERUN_EXECUTION_STATUSES",
    "QUALITY_REVIEW_STATUSES",
    "REPORT_VERSION_STATUSES",
    "SCHEMA_VERSION",
    "_audit_item",
    "_quality_metadata_provenance",
    "_report_rows",
    "build_report_quality_audit",
    "build_unavailable_report_quality_audit",
]
