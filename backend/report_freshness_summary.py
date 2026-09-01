"""Build explicit read-only freshness summaries for indexed report scopes."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text


SCHEMA_VERSION = "report_freshness_summary.v1"
ITEMS_SCHEMA_VERSION = "report_freshness_items.v1"
FRESHNESS_ITEM_LIMIT = 5
FRESHNESS_BUCKETS = ("current", "needs_rerun", "unknown")


def build_report_freshness_summary(
    reports: dict[str, Any] | list[dict[str, Any]],
    *,
    scope: str = "daily_report_sample",
    selection_basis: str | None = None,
) -> dict[str, Any]:
    rows = _report_rows(reports)
    scope_text = safe_text(scope).strip() or "daily_report_sample"
    selection_basis_text = safe_text(selection_basis).strip() or (
        "latest_per_ticker_pipeline" if scope_text == "all_indexed_reports" else "caller_supplied_rows"
    )
    counts = {"current_reports": 0, "needs_rerun_reports": 0, "unknown_reports": 0}
    for report in rows:
        counts[f"{report_freshness_bucket(report)}_reports"] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": scope_text,
        "selection_basis": selection_basis_text,
        "audited_reports": len(rows),
        **counts,
    }


def attach_full_report_freshness_summary(payload: dict[str, Any], reports: Any) -> dict[str, Any]:
    rows = _report_rows(reports)
    payload["decision_freshness_summary"] = build_report_freshness_summary(
        rows,
        scope="all_indexed_reports",
        selection_basis="latest_per_ticker_pipeline",
    )
    payload["decision_freshness_items"] = build_report_freshness_items(
        rows,
        scope="all_indexed_reports",
        selection_basis="latest_per_ticker_pipeline",
    )
    return payload


def build_report_freshness_items(
    reports: dict[str, Any] | list[dict[str, Any]],
    *,
    scope: str = "all_indexed_reports",
    selection_basis: str = "latest_per_ticker_pipeline",
    item_limit: int = FRESHNESS_ITEM_LIMIT,
) -> dict[str, Any]:
    rows = _report_rows(reports)
    stale_rows = []
    for report in rows:
        freshness = safe_mapping_dict(report.get("decision_freshness")) or {}
        if report_freshness_bucket(report) == "needs_rerun":
            stale_rows.append(_freshness_item(report, freshness))
    limit = max(0, safe_int(item_limit, default=FRESHNESS_ITEM_LIMIT))
    returned = stale_rows[:limit]
    return {
        "schema_version": ITEMS_SCHEMA_VERSION,
        "scope": safe_text(scope).strip() or "all_indexed_reports",
        "selection_basis": safe_text(selection_basis).strip() or "latest_per_ticker_pipeline",
        "audited_reports": len(rows),
        "needs_rerun_reports": len(stale_rows),
        "items_limit": limit,
        "items_total": len(stale_rows),
        "items_returned": len(returned),
        "items_truncated": len(returned) < len(stale_rows),
        "items": returned,
    }


def _report_rows(reports: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(reports, dict):
        return safe_dict_list(reports.get("reports"))
    return safe_dict_list(reports)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return safe_text(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def _requires_rerun(report: dict[str, Any], freshness: dict[str, Any]) -> bool:
    return any(
        _safe_bool(value)
        for value in (
            freshness.get("requires_rerun"),
            report.get("requires_rerun"),
            report.get("analysis_text_stale"),
            report.get("refreshed_without_analysis_rerun"),
        )
    ) or safe_text(freshness.get("status")).strip().lower() == "needs_rerun"


def report_freshness_bucket(report: dict[str, Any]) -> str:
    """Return the same freshness bucket used by all read-only summaries."""
    freshness = safe_mapping_dict(report.get("decision_freshness")) or {}
    status = safe_text(freshness.get("status") or report.get("decision_validity_status")).strip().lower()
    if _requires_rerun(report, freshness):
        return "needs_rerun"
    if status == "current":
        return "current"
    return "unknown"


def _freshness_item(report: dict[str, Any], freshness: dict[str, Any]) -> dict[str, Any]:
    data_trust = safe_mapping_dict(report.get("data_trust")) or {}
    return {
        "ticker": safe_text(report.get("ticker")).strip(),
        "pipeline_id": safe_text(report.get("pipeline_id")).strip() or "v1",
        "filename": safe_text(report.get("filename") or report.get("report_filename")).strip(),
        "report_date": safe_text(report.get("report_date") or report.get("date")).strip(),
        "snapshot_refreshed_at": safe_text(freshness.get("snapshot_refreshed_at") or report.get("snapshot_refreshed_at")).strip(),
        "data_trust_status": safe_text(data_trust.get("status") or report.get("data_trust_status")).strip().lower(),
        "reason": safe_text(freshness.get("requires_rerun_reason") or freshness.get("message")).strip(),
    }


__all__ = [
    "FRESHNESS_BUCKETS",
    "FRESHNESS_ITEM_LIMIT",
    "ITEMS_SCHEMA_VERSION",
    "attach_full_report_freshness_summary",
    "build_report_freshness_items",
    "build_report_freshness_summary",
    "report_freshness_bucket",
]
