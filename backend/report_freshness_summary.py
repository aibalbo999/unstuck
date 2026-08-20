"""Build explicit read-only freshness summaries for indexed report scopes."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text


SCHEMA_VERSION = "report_freshness_summary.v1"


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
        freshness = safe_mapping_dict(report.get("decision_freshness")) or {}
        status = safe_text(freshness.get("status") or report.get("decision_validity_status")).strip().lower()
        requires_rerun = any(
            _safe_bool(value)
            for value in (
                freshness.get("requires_rerun"),
                report.get("requires_rerun"),
                report.get("analysis_text_stale"),
                report.get("refreshed_without_analysis_rerun"),
            )
        )
        if requires_rerun or status == "needs_rerun":
            counts["needs_rerun_reports"] += 1
        elif status == "current":
            counts["current_reports"] += 1
        else:
            counts["unknown_reports"] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": scope_text,
        "selection_basis": selection_basis_text,
        "audited_reports": len(rows),
        **counts,
    }


def attach_full_report_freshness_summary(payload: dict[str, Any], reports: Any) -> dict[str, Any]:
    payload["decision_freshness_summary"] = build_report_freshness_summary(
        reports,
        scope="all_indexed_reports",
        selection_basis="latest_per_ticker_pipeline",
    )
    return payload


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


__all__ = ["attach_full_report_freshness_summary", "build_report_freshness_summary"]
