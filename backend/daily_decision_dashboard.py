"""Daily decision dashboard aggregation."""

from __future__ import annotations

from math import isfinite
from typing import Any

from daily_decision_queue import build_daily_decision_queue
from free_notification_plan import build_daily_notification_plan
from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text, safe_text_list
from outcome_calibration import build_outcome_calibration
from provider_impact import build_provider_impact_ledger
from report_quality_audit import build_report_quality_audit
from report_quality_repair_queue import build_report_quality_repair_queue
from report_freshness_summary import safe_bool


def build_daily_decision_dashboard(
    *,
    reports: dict[str, Any],
    watchlist: dict[str, Any],
    screener: dict[str, Any],
    performance: dict[str, Any],
    free_mode: dict[str, Any],
    ops: dict[str, Any] | None = None,
    quality_audit: dict[str, Any] | None = None,
    current_quality_summary: dict[str, Any] | None = None,
    quality_audit_reports: dict[str, Any] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the operator's next-best-action dashboard."""
    reports_payload = safe_mapping_dict(reports) or {}
    watchlist_payload = safe_mapping_dict(watchlist) or {}
    screener_payload = safe_mapping_dict(screener) or {}
    performance_payload = safe_mapping_dict(performance) or {}
    free_mode_payload = safe_mapping_dict(free_mode) or {}
    free_mode_enabled = safe_bool(free_mode_payload.get("enabled"))
    free_mode_can_run_without_paid_keys = safe_bool(free_mode_payload.get("can_run_without_paid_keys"))
    free_mode_violations = safe_text_list(free_mode_payload.get("violations"))
    free_mode_queue_payload = {
        **free_mode_payload,
        "enabled": free_mode_enabled,
        "can_run_without_paid_keys": free_mode_can_run_without_paid_keys,
        "violations": free_mode_violations,
    }
    report_rows = safe_dict_list(reports_payload.get("reports"))
    if quality_audit is not None:
        report_quality_audit = safe_mapping_dict(quality_audit) or {}
    else:
        audit_scope = "all_indexed_reports" if quality_audit_reports is not None else "daily_report_sample"
        report_quality_audit = build_report_quality_audit(
            quality_audit_reports if quality_audit_reports is not None else report_rows,
            scope=audit_scope,
        )
    if current_quality_summary is not None:
        report_quality_audit["current_quality_summary"] = safe_mapping_dict(current_quality_summary) or {}
    watch_items = safe_dict_list(watchlist_payload.get("items"))
    screener_items = safe_dict_list(screener_payload.get("items"))
    repair_queue = build_report_quality_repair_queue(report_rows, limit=5)
    repair_items = list(repair_queue.get("items") or [])
    repair_coverage = build_report_quality_repair_queue(report_rows, limit=len(report_rows))
    repair_coverage_items = list(repair_coverage.get("items") or [])
    repair_action_counts = _repair_action_counts(repair_coverage_items)
    direct_rerun_blocked_keys = _direct_rerun_blocked_keys(repair_coverage_items)
    rerun_reports = [
        report for report in report_rows
        if _report_needs_rerun(report) and _report_key(report) not in direct_rerun_blocked_keys
    ]
    high_priority_watchlist = [
        item for item in watch_items
        if _is_high_priority_watchlist_item(item)
    ]
    candidates = _top_candidates(screener_items)
    rerun_report_items = [_rerun_report_payload(report) for report in rerun_reports]
    outcome_calibration = build_outcome_calibration(
        backtests=safe_dict_list(performance_payload.get("details")),
        reports=report_rows,
    )
    provider_impact_ledger = build_provider_impact_ledger(report_rows)
    decision_queue = build_daily_decision_queue(
        reports=report_rows,
        repair_items=repair_coverage_items,
        quality_audit_items=_quality_audit_queue_items(report_quality_audit),
        rerun_reports=rerun_reports,
        high_priority_watchlist=high_priority_watchlist,
        candidates=candidates,
        performance=performance_payload,
        free_mode=free_mode_queue_payload,
        provider_impact_ledger=provider_impact_ledger,
        ops=ops or {},
    )
    report_quality_audit["repair_sample_overlap"] = _repair_sample_overlap(
        report_quality_audit,
        report_rows,
    )
    actions = list(decision_queue.get("items") or [])
    status = "action_required" if actions and actions[0]["type"] != "monitor" else "ok"
    dashboard = {
        "status": status,
        "summary": {
            "sampled_reports": len(report_rows),
            "report_scope": {
                "scope": "daily_report_sample",
                "label": "近期報告取樣",
                "sampled_reports": len(report_rows),
            },
            "reports_needing_rerun": len(rerun_reports),
            "reports_needing_freshness_rerun": len(rerun_reports),
            "report_repairs_required": int((repair_queue.get("summary") or {}).get("action_required") or 0),
            "report_repair_action_counts": repair_action_counts,
            "report_repair_rerun_required": repair_action_counts.get("rerun_analysis", 0),
            "watchlist_high_priority": len(high_priority_watchlist),
            "top_candidate_count": len(candidates),
        },
        "free_mode": {
            "enabled": free_mode_enabled,
            "can_run_without_paid_keys": free_mode_can_run_without_paid_keys,
            "violations": free_mode_violations,
        },
        "performance": safe_mapping_dict(performance_payload.get("summary")) or {},
        "outcome_calibration": outcome_calibration,
        "provider_impact_ledger": provider_impact_ledger,
        "report_quality_audit": report_quality_audit,
        "top_candidates": candidates,
        "rerun_reports": rerun_report_items,
        "repair_queue": repair_queue,
        "decision_queue": decision_queue,
        "actions": actions,
    }
    dashboard["notification_plan"] = build_daily_notification_plan(dashboard)
    return dashboard


def _quality_audit_queue_items(quality_audit: dict[str, Any]) -> list[dict[str, Any]]:
    if safe_text(quality_audit.get("status")).strip().lower() == "unavailable":
        return []
    if safe_text(quality_audit.get("scope")).strip() != "all_indexed_reports":
        return []
    if safe_text(quality_audit.get("selection_basis")).strip() != "latest_per_ticker_pipeline":
        return []
    missing_count = max(0, safe_int(quality_audit.get("quality_metadata_missing_reports"), default=0))
    items = safe_dict_list(quality_audit.get("items"))
    if missing_count <= 0 or quality_audit.get("items_truncated") is True or len(items) != missing_count:
        return []
    returned_count = safe_int(quality_audit.get("items_returned"), default=len(items))
    if returned_count != missing_count:
        return []
    if sum(1 for item in items if _report_identity_key(item) is not None) != missing_count:
        return []
    return items


def _report_needs_rerun(report: dict[str, Any]) -> bool:
    freshness = _decision_freshness(report)
    return any(
        safe_bool(value)
        for value in (
            freshness.get("requires_rerun"),
            report.get("requires_rerun"),
            report.get("analysis_text_stale"),
        )
    )


def _repair_sample_overlap(
    quality_audit: dict[str, Any],
    report_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if safe_text(quality_audit.get("status")).strip().lower() == "unavailable":
        return {"status": "unavailable"}
    scope = safe_text(quality_audit.get("scope")).strip()
    if scope != "all_indexed_reports":
        return {"status": "not_comparable"}
    audit_items = safe_dict_list(quality_audit.get("items"))
    audit_gap_reports = max(0, safe_int(quality_audit.get("quality_metadata_missing_reports"), default=0))
    audit_gap_items_returned = len(audit_items)
    sample_keys = {
        key for report in report_rows
        if (key := _report_identity_key(report)) is not None
    }
    audit_gap_keys = {
        key for item in audit_items
        if (key := _report_identity_key(item)) is not None
    }
    overlap = len(sample_keys & audit_gap_keys)
    truncated = quality_audit.get("items_truncated") is True or audit_gap_items_returned < audit_gap_reports
    result: dict[str, Any] = {
        "status": "partial" if truncated else "complete",
        "audit_gap_reports": audit_gap_reports,
        "audit_gap_items_returned": audit_gap_items_returned,
        "repair_sampled_reports": len(report_rows),
        "audit_gap_reports_in_repair_sample": overlap,
    }
    if not truncated:
        result["audit_gap_reports_outside_repair_sample"] = max(0, audit_gap_reports - overlap)
    return result


def _report_identity_key(report: dict[str, Any]) -> tuple[str, str] | None:
    filename = safe_text(report.get("filename") or report.get("report_filename")).strip()
    pipeline_id = safe_text(report.get("pipeline_id")).strip() or "v1"
    return (filename, pipeline_id) if filename else None


def _report_key(report: dict[str, Any]) -> str:
    filename = _report_filename(report)
    if filename:
        return filename
    ticker = safe_text(report.get("ticker")).strip()
    pipeline_id = safe_text(report.get("pipeline_id")).strip() or "v1"
    return f"{ticker}:{pipeline_id}"


def _report_filename(report: dict[str, Any]) -> str:
    return safe_text(report.get("filename")).strip() or safe_text(report.get("report_filename")).strip()


def _direct_rerun_blocked_keys(repair_items: list[dict[str, Any]]) -> set[str]:
    return {
        key
        for item in repair_items
        if (key := _report_key(item)) and item.get("recommended_action") != "rerun_analysis"
    }


def _repair_action_counts(repair_items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in repair_items:
        action = safe_text(item.get("recommended_action")).strip()
        if action:
            counts[action] = counts.get(action, 0) + 1
    return dict(sorted(counts.items()))


def _rerun_reason(report: dict[str, Any]) -> str:
    freshness = _decision_freshness(report)
    return next(
        (
            text
            for text in (
                safe_text(freshness.get("requires_rerun_reason")).strip(),
                safe_text(report.get("analysis_text_stale_message")).strip(),
                safe_text(report.get("requires_rerun_reason")).strip(),
            )
            if text
        ),
        "資料快照與結論不同步。",
    )


def _decision_freshness(report: dict[str, Any]) -> dict[str, Any]:
    return safe_mapping_dict(report.get("decision_freshness")) or {}


def _rerun_report_payload(report: dict[str, Any]) -> dict[str, Any]:
    ticker = safe_text(report.get("ticker")).strip() or "報告"
    pipeline_id = safe_text(report.get("pipeline_id")).strip() or "v1"
    filename = _report_filename(report) or None
    return {
        "type": "rerun_report",
        "title": f"{ticker} {pipeline_id} 結論需重跑",
        "detail": _rerun_reason(report),
        "ticker": ticker,
        "filename": filename,
        "pipeline_id": pipeline_id,
    }


def _is_high_priority_watchlist_item(item: dict[str, Any]) -> bool:
    if item.get("enabled") is False:
        return False
    return safe_text(item.get("decision_priority")).strip().lower() == "high"


def _top_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accepted = []
    for item in items:
        quality = safe_mapping_dict(item.get("quality_funnel")) or {}
        quality_outcome = safe_text(quality.get("outcome")).strip()
        if quality_outcome.lower() == "reject":
            continue
        accepted.append({
            "ticker": safe_text(item.get("ticker")).strip() or None,
            "company_name": safe_text(item.get("company_name")).strip(),
            "score": _score_value(item.get("score")),
            "quality_outcome": quality_outcome or None,
            "reason": _candidate_reason(item),
        })
    return sorted(accepted, key=lambda row: _score_value(row.get("score")), reverse=True)[:5]


def _candidate_reason(item: dict[str, Any]) -> str:
    return next(
        (
            text
            for text in (
                safe_text(item.get("reason")).strip(),
                safe_text(item.get("category")).strip(),
            )
            if text
        ),
        "",
    )


def _score_value(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        number = float(0 if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0.0
    return number if isfinite(number) else 0.0


__all__ = ["build_daily_decision_dashboard"]
