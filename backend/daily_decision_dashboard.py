"""Daily decision dashboard aggregation."""

from __future__ import annotations

from typing import Any

from daily_decision_queue import build_daily_decision_queue
from free_notification_plan import build_daily_notification_plan
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
    report_rows = list(reports.get("reports") or [])
    watch_items = list(watchlist.get("items") or [])
    screener_items = list(screener.get("items") or [])
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
        if item.get("enabled") is not False and str(item.get("decision_priority") or "") == "high"
    ]
    candidates = _top_candidates(screener_items)
    rerun_report_items = [_rerun_report_payload(report) for report in rerun_reports]
    outcome_calibration = build_outcome_calibration(
        backtests=list(performance.get("details") or []),
        reports=report_rows,
    )
    provider_impact_ledger = build_provider_impact_ledger(report_rows)
    decision_queue = build_daily_decision_queue(
        reports=report_rows,
        repair_items=repair_coverage_items,
        rerun_reports=rerun_reports,
        high_priority_watchlist=high_priority_watchlist,
        candidates=candidates,
        performance=performance,
        free_mode=free_mode,
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
            "enabled": bool(free_mode.get("enabled")),
            "can_run_without_paid_keys": bool(free_mode.get("can_run_without_paid_keys")),
            "violations": list(free_mode.get("violations") or []),
        },
        "performance": dict(performance.get("summary") or {}),
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
    freshness = report.get("decision_freshness") if isinstance(report.get("decision_freshness"), dict) else {}
    return bool(
        freshness.get("requires_rerun")
        or report.get("requires_rerun")
        or report.get("analysis_text_stale")
    )


def _report_key(report: dict[str, Any]) -> str:
    filename = str(report.get("filename") or report.get("report_filename") or "")
    if filename:
        return filename
    return f"{report.get('ticker') or ''}:{report.get('pipeline_id') or 'v1'}"


def _direct_rerun_blocked_keys(repair_items: list[dict[str, Any]]) -> set[str]:
    return {
        key
        for item in repair_items
        if (key := _report_key(item)) and item.get("recommended_action") != "rerun_analysis"
    }


def _rerun_reason(report: dict[str, Any]) -> str:
    freshness = report.get("decision_freshness") if isinstance(report.get("decision_freshness"), dict) else {}
    return str(
        freshness.get("requires_rerun_reason")
        or report.get("analysis_text_stale_message")
        or report.get("requires_rerun_reason")
        or "資料快照與結論不同步。"
    )


def _rerun_report_payload(report: dict[str, Any]) -> dict[str, Any]:
    ticker = report.get("ticker") or "報告"
    pipeline_id = report.get("pipeline_id") or "v1"
    return {
        "type": "rerun_report",
        "title": f"{ticker} {pipeline_id} 結論需重跑",
        "detail": _rerun_reason(report),
        "ticker": report.get("ticker"),
        "filename": report.get("filename"),
        "pipeline_id": pipeline_id,
    }


def _top_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accepted = []
    for item in items:
        quality = item.get("quality_funnel") if isinstance(item.get("quality_funnel"), dict) else {}
        if str(quality.get("outcome") or "").lower() == "reject":
            continue
        accepted.append({
            "ticker": item.get("ticker"),
            "company_name": item.get("company_name") or "",
            "score": item.get("score"),
            "quality_outcome": quality.get("outcome"),
            "reason": item.get("reason") or item.get("category") or "",
        })
    return sorted(accepted, key=lambda row: float(row.get("score") or 0), reverse=True)[:5]


__all__ = ["build_daily_decision_dashboard"]
