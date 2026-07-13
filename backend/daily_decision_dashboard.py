"""Daily decision dashboard aggregation."""

from __future__ import annotations

from math import isfinite
from typing import Any

from daily_decision_queue import build_daily_decision_queue
from free_notification_plan import build_daily_notification_plan
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text, safe_text_list
from outcome_calibration import build_outcome_calibration
from provider_impact import build_provider_impact_ledger
from report_quality_repair_queue import build_report_quality_repair_queue


def build_daily_decision_dashboard(
    *,
    reports: dict[str, Any],
    watchlist: dict[str, Any],
    screener: dict[str, Any],
    performance: dict[str, Any],
    free_mode: dict[str, Any],
    ops: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the operator's next-best-action dashboard."""
    reports_payload = safe_mapping_dict(reports) or {}
    watchlist_payload = safe_mapping_dict(watchlist) or {}
    screener_payload = safe_mapping_dict(screener) or {}
    performance_payload = safe_mapping_dict(performance) or {}
    free_mode_payload = safe_mapping_dict(free_mode) or {}
    free_mode_enabled = _safe_bool(free_mode_payload.get("enabled"))
    free_mode_can_run_without_paid_keys = _safe_bool(free_mode_payload.get("can_run_without_paid_keys"))
    free_mode_violations = safe_text_list(free_mode_payload.get("violations"))
    free_mode_queue_payload = {
        **free_mode_payload,
        "enabled": free_mode_enabled,
        "can_run_without_paid_keys": free_mode_can_run_without_paid_keys,
        "violations": free_mode_violations,
    }
    report_rows = safe_dict_list(reports_payload.get("reports"))
    watch_items = safe_dict_list(watchlist_payload.get("items"))
    screener_items = safe_dict_list(screener_payload.get("items"))
    repair_queue = build_report_quality_repair_queue(report_rows, limit=5)
    repair_items = list(repair_queue.get("items") or [])
    repair_coverage = build_report_quality_repair_queue(report_rows, limit=len(report_rows))
    repair_coverage_items = list(repair_coverage.get("items") or [])
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
        rerun_reports=rerun_reports,
        high_priority_watchlist=high_priority_watchlist,
        candidates=candidates,
        performance=performance_payload,
        free_mode=free_mode_queue_payload,
        provider_impact_ledger=provider_impact_ledger,
        ops=ops or {},
    )
    actions = list(decision_queue.get("items") or [])
    status = "action_required" if actions and actions[0]["type"] != "monitor" else "ok"
    dashboard = {
        "status": status,
        "summary": {
            "sampled_reports": len(report_rows),
            "reports_needing_rerun": len(rerun_reports),
            "report_repairs_required": int((repair_queue.get("summary") or {}).get("action_required") or 0),
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
        "top_candidates": candidates,
        "rerun_reports": rerun_report_items,
        "repair_queue": repair_queue,
        "decision_queue": decision_queue,
        "actions": actions,
    }
    dashboard["notification_plan"] = build_daily_notification_plan(dashboard)
    return dashboard


def _report_needs_rerun(report: dict[str, Any]) -> bool:
    freshness = _decision_freshness(report)
    return any(
        _safe_bool(value)
        for value in (
            freshness.get("requires_rerun"),
            report.get("requires_rerun"),
            report.get("analysis_text_stale"),
        )
    )


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


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False


__all__ = ["build_daily_decision_dashboard"]
