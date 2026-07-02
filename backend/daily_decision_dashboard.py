"""Daily decision dashboard aggregation."""

from __future__ import annotations

from typing import Any

from free_notification_plan import build_daily_notification_plan


def build_daily_decision_dashboard(
    *,
    reports: dict[str, Any],
    watchlist: dict[str, Any],
    screener: dict[str, Any],
    performance: dict[str, Any],
    free_mode: dict[str, Any],
) -> dict[str, Any]:
    """Return the operator's next-best-action dashboard."""
    report_rows = list(reports.get("reports") or [])
    watch_items = list(watchlist.get("items") or [])
    screener_items = list(screener.get("items") or [])
    rerun_reports = [report for report in report_rows if _report_needs_rerun(report)]
    high_priority_watchlist = [
        item for item in watch_items
        if item.get("enabled") is not False and str(item.get("decision_priority") or "") == "high"
    ]
    candidates = _top_candidates(screener_items)
    actions = _actions(rerun_reports, high_priority_watchlist, candidates, free_mode)
    status = "action_required" if actions and actions[0]["type"] != "monitor" else "ok"
    dashboard = {
        "status": status,
        "summary": {
            "sampled_reports": len(report_rows),
            "reports_needing_rerun": len(rerun_reports),
            "watchlist_high_priority": len(high_priority_watchlist),
            "top_candidate_count": len(candidates),
        },
        "free_mode": {
            "enabled": bool(free_mode.get("enabled")),
            "can_run_without_paid_keys": bool(free_mode.get("can_run_without_paid_keys")),
            "violations": list(free_mode.get("violations") or []),
        },
        "performance": dict(performance.get("summary") or {}),
        "top_candidates": candidates,
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


def _top_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accepted = []
    for item in items:
        quality = item.get("quality_funnel") if isinstance(item.get("quality_funnel"), dict) else {}
        if str(quality.get("outcome") or "").lower() == "reject":
            continue
        accepted.append({
            "ticker": item.get("ticker"),
            "score": item.get("score"),
            "quality_outcome": quality.get("outcome"),
            "reason": item.get("reason") or item.get("category") or "",
        })
    return sorted(accepted, key=lambda row: float(row.get("score") or 0), reverse=True)[:5]


def _actions(
    rerun_reports: list[dict[str, Any]],
    high_priority_watchlist: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    free_mode: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = []
    if not free_mode.get("can_run_without_paid_keys", True):
        actions.append({
            "type": "fix_free_mode",
            "title": "免費模式有付費依賴缺口",
            "detail": "先查看 provider contract，避免報告流程依賴付費來源。",
        })
    if rerun_reports:
        report = rerun_reports[0]
        actions.append({
            "type": "rerun_report",
            "title": f"{report.get('ticker') or '報告'} 結論需重跑",
            "detail": "資料快照與結論不同步。",
            "ticker": report.get("ticker"),
            "filename": report.get("filename"),
            "pipeline_id": report.get("pipeline_id") or "v1",
        })
    if high_priority_watchlist:
        samples = "、".join(str(item.get("ticker") or "") for item in high_priority_watchlist[:3] if item.get("ticker"))
        actions.append({
            "type": "run_watchlist",
            "title": f"{len(high_priority_watchlist)} 檔 watchlist 待分析",
            "detail": samples,
        })
    if candidates:
        actions.append({
            "type": "review_candidate",
            "title": f"{candidates[0].get('ticker')} 進入候選清單",
            "detail": f"score {candidates[0].get('score')}",
            "ticker": candidates[0].get("ticker"),
        })
    if not actions:
        actions.append({"type": "monitor", "title": "目前沒有急件", "detail": "保持每日追蹤。"})
    return actions[:5]


__all__ = ["build_daily_decision_dashboard"]
