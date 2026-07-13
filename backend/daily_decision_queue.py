"""Prioritized daily operator decision queue."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from daily_decision_queue_notifications import notification_delivery_items
from daily_decision_route_warnings import route_warning_items
from daily_decision_source_labels import source_labels, source_texts
from decision_backtest import BACKTEST_HORIZONS, add_calendar_months
from mapping_fields import mapping_field as _field
from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text, safe_text_list

SCHEMA_VERSION = "daily_decision_queue.v1"
SOURCE_ORDER = {source: index for index, source in enumerate((
    "free_mode", "report_repair", "provider_impact", "notification_delivery", "backtest_due",
    "rerun_report", "model_route_budget", "watchlist", "screener", "monitor",
))}


def build_daily_decision_queue(
    *,
    reports: list[dict[str, Any]],
    repair_items: list[dict[str, Any]],
    rerun_reports: list[dict[str, Any]],
    high_priority_watchlist: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    performance: dict[str, Any],
    free_mode: dict[str, Any],
    provider_impact_ledger: dict[str, Any] | None = None,
    ops: dict[str, Any] | None = None,
    limit: int = 5,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Return one sorted queue across report, tracking, provider, and ops signals."""
    repair_actions = [_repair_action_payload(item) for item in safe_dict_list(repair_items)]
    repair_keys = {_report_key(item) for item in repair_actions if _report_key(item)}
    blocking_repair_keys = {
        _report_key(item)
        for item in repair_actions
        if _report_key(item) and _field(item, "type") != "rerun_report"
    }
    ops_payload = ops if isinstance(ops, dict) else {}
    provider_ledger = safe_mapping_dict(provider_impact_ledger) or {}
    items = []
    items.extend(_free_mode_items(free_mode))
    items.extend(repair_actions)
    items.extend(_provider_items(provider_ledger, skip_keys=repair_keys))
    items.extend(notification_delivery_items(ops_payload))
    items.extend(_backtest_due_items(reports, performance, as_of=as_of or date.today(), skip_keys=blocking_repair_keys))
    items.extend(_rerun_items(rerun_reports, skip_keys=repair_keys))
    items.extend(route_warning_items(ops_payload))
    items.extend(_watchlist_items(high_priority_watchlist))
    items.extend(_candidate_items(candidates))
    actionable = [item for item in items if item]
    actionable.sort(key=_sort_key)
    render_items = actionable or [_monitor_item()]
    display_limit = _int(limit) or 5
    displayed = render_items[: max(1, display_limit)]
    source_counts = _source_counts(actionable)
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "total_actionable": len(actionable),
            "displayed_count": len(displayed),
            "top_priority_score": int(_field(displayed[0], "priority_score") or 0) if displayed else 0,
            "sources": source_counts,
            "source_labels": source_labels(source_counts),
            "source_texts": source_texts(source_counts),
        },
        "items": displayed,
        "secondary_count": max(0, len(actionable) - len(displayed)),
    }


def _free_mode_items(free_mode: dict[str, Any]) -> list[dict[str, Any]]:
    if _bool(_field(free_mode, "can_run_without_paid_keys", True)):
        return []
    violations = safe_text_list(_field(free_mode, "violations"))
    return [{
        "source": "free_mode",
        "type": "fix_free_mode",
        "priority_score": 980,
        "title": "免費模式有付費依賴缺口",
        "detail": "先查看 provider contract，避免報告流程依賴付費來源。",
        "violations": violations,
    }]


def _provider_items(ledger: dict[str, Any], *, skip_keys: set[str]) -> list[dict[str, Any]]:
    items = []
    for row in safe_dict_list(_field(ledger, "items")):
        if not isinstance(row, dict) or _report_key(row) in skip_keys:
            continue
        summary = safe_mapping_dict(_field(row, "summary")) or {}
        blocks = _bool(_field(summary, "blocks_auto_rerun"))
        if not blocks:
            continue
        action = safe_text(_field(summary, "recommended_action")).strip() or "wait_provider_recovery"
        filename = safe_text(_field(row, "filename")).strip() or safe_text(_field(row, "report_filename")).strip() or None
        ticker = safe_text(_field(row, "ticker")).strip()
        pipeline_id = safe_text(_field(row, "pipeline_id")).strip() or "v1"
        items.append({
            "source": "provider_impact",
            "type": "wait_provider_recovery" if blocks else "monitor_provider",
            "priority_score": 900 if blocks else 520,
            "title": f"{ticker or '報告'} provider 影響需處理",
            "detail": _provider_detail(row, blocks),
            "ticker": ticker,
            "filename": filename,
            "report_filename": filename,
            "pipeline_id": pipeline_id,
            "recommended_action": action,
            "blocks_auto_rerun": blocks,
        })
    return items


def _backtest_due_items(
    reports: list[dict[str, Any]], performance: dict[str, Any], *, as_of: date, skip_keys: set[str]
) -> list[dict[str, Any]]:
    explicit = safe_dict_list(_field(performance, "due_backtests"))
    if not explicit:
        explicit = safe_dict_list(_field(performance, "backtest_due"))
    if explicit:
        return [_due_item(row, skip_keys=skip_keys) for row in explicit if isinstance(row, dict) and _report_key(row) not in skip_keys]
    evaluated = {
        (safe_text(_field(row, "report_filename")).strip() or safe_text(_field(row, "filename")).strip(), _int(_field(row, "horizon_months")))
        for row in safe_dict_list(_field(performance, "details"))
    }
    due = []
    for report in safe_dict_list(reports):
        if _report_key(report) in skip_keys:
            continue
        generated = _report_date(report)
        filename = safe_text(_field(report, "filename")).strip() or safe_text(_field(report, "report_filename")).strip()
        if generated is None or not filename:
            continue
        for horizon in BACKTEST_HORIZONS:
            if add_calendar_months(generated, horizon) <= as_of and (filename, int(horizon)) not in evaluated:
                due.append(_due_item({**report, "horizon_months": horizon}, skip_keys=set()))
                break
    return due


def _due_item(row: dict[str, Any], *, skip_keys: set[str]) -> dict[str, Any]:
    horizon = _int(_field(row, "horizon_months")) or 3
    ticker = safe_text(_field(row, "ticker")).strip() or "報告"
    filename = safe_text(_field(row, "report_filename")).strip() or safe_text(_field(row, "filename")).strip() or None
    pipeline_id = safe_text(_field(row, "pipeline_id")).strip() or "v1"
    return {
        "source": "backtest_due",
        "type": "backtest_due",
        "priority_score": 760 + min(horizon, 12),
        "title": f"{ticker} {horizon}M 回測到期",
        "detail": "先完成到期回測，再判斷是否需要重跑或調整 thesis。",
        "ticker": ticker,
        "filename": filename,
        "report_filename": filename,
        "pipeline_id": pipeline_id,
        "horizon_months": horizon,
    }


def _rerun_items(rerun_reports: list[dict[str, Any]], *, skip_keys: set[str]) -> list[dict[str, Any]]:
    return [_rerun_report_payload(report) for report in safe_dict_list(rerun_reports) if _report_key(report) not in skip_keys]


def _watchlist_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = safe_dict_list(items)
    if not rows:
        return []
    samples = "、".join(ticker for item in rows[:3] if (ticker := safe_text(_field(item, "ticker")).strip()))
    return [{
        "source": "watchlist",
        "type": "run_watchlist",
        "priority_score": 560,
        "title": f"{len(rows)} 檔 watchlist 待分析",
        "detail": samples,
    }]


def _candidate_items(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = safe_dict_list(candidates)
    if not rows:
        return []
    candidate = rows[0]
    ticker = safe_text(_field(candidate, "ticker")).strip()
    company_name = safe_text(_field(candidate, "company_name")).strip()
    reason = safe_text(_field(candidate, "reason")).strip()
    return [{
        "source": "screener",
        "type": "review_candidate",
        "priority_score": 420,
        "title": " ".join(part for part in (ticker, company_name) if part),
        "detail": reason or "市場掃描候選",
        "reason": reason,
        "company_name": company_name,
        "score": _field(candidate, "score"),
        "ticker": ticker,
    }]


def _repair_action_payload(item: dict[str, Any]) -> dict[str, Any]:
    recommended = safe_text(_field(item, "recommended_action")).strip() or "manual_review"
    action_type = {
        "rerun_analysis": "rerun_report",
        "refresh_data_snapshot": "refresh_data_snapshot",
        "wait_provider_recovery": "wait_provider_recovery",
        "manual_review": "manual_review",
    }.get(recommended, "manual_review")
    ticker = safe_text(_field(item, "ticker")).strip() or "報告"
    pipeline_id = safe_text(_field(item, "pipeline_id")).strip() or "v1"
    filename = safe_text(_field(item, "filename")).strip() or safe_text(_field(item, "report_filename")).strip() or None
    title = safe_text(_field(item, "title")).strip() or "報告需處理"
    return {
        "source": "report_repair",
        "type": action_type,
        "priority_score": _int(_field(item, "priority_score")) or 700,
        "title": f"{ticker} {pipeline_id} {title}",
        "detail": safe_text(_field(item, "detail")),
        "ticker": ticker,
        "filename": filename,
        "report_filename": filename,
        "pipeline_id": pipeline_id,
        "severity": safe_text(_field(item, "severity")).strip() or None,
        "recommended_action": recommended,
        "action_label": safe_text(_field(item, "action_label")).strip() or None,
        "blocks_auto_rerun": _bool(_field(item, "blocks_auto_rerun")),
        "reason_codes": safe_text_list(_field(item, "reason_codes")),
    }


def _rerun_report_payload(report: dict[str, Any]) -> dict[str, Any]:
    ticker = safe_text(_field(report, "ticker")).strip() or "報告"
    pipeline_id = safe_text(_field(report, "pipeline_id")).strip() or "v1"
    filename = safe_text(_field(report, "filename")).strip() or safe_text(_field(report, "report_filename")).strip() or None
    raw_freshness = _field(report, "decision_freshness")
    freshness = raw_freshness if isinstance(raw_freshness, dict) else {}
    detail = next((text for text in (
        safe_text(_field(freshness, "requires_rerun_reason")).strip(),
        safe_text(_field(report, "analysis_text_stale_message")).strip(),
        safe_text(_field(report, "requires_rerun_reason")).strip(),
    ) if text), "資料快照與結論不同步。")
    return {
        "source": "rerun_report",
        "type": "rerun_report",
        "priority_score": 700,
        "title": f"{ticker} {pipeline_id} 結論需重跑",
        "detail": detail,
        "ticker": ticker,
        "filename": filename,
        "report_filename": filename,
        "pipeline_id": pipeline_id,
    }


def _provider_detail(row: dict[str, Any], blocks: bool) -> str:
    message = next((text for item in safe_dict_list(_field(row, "impacts")) if (text := safe_text(_field(item, "message")).strip())), "")
    if message:
        return message
    if blocks:
        return "核心來源不穩，先等待 provider recovery，避免盲目重跑。"
    return "來源有警示但未阻擋核心資料，列為監控。"


def _monitor_item() -> dict[str, Any]:
    return {
        "source": "monitor",
        "type": "monitor",
        "priority_score": 0,
        "title": "目前沒有急件",
        "detail": "保持每日追蹤。",
    }


def _report_key(row: dict[str, Any]) -> str:
    filename = safe_text(_field(row, "filename")).strip() or safe_text(_field(row, "report_filename")).strip()
    if filename:
        return filename
    ticker = safe_text(_field(row, "ticker")).strip()
    if not ticker:
        return ""
    pipeline_id = safe_text(_field(row, "pipeline_id")).strip() or "v1"
    return f"{ticker}:{pipeline_id}"


def _report_date(report: dict[str, Any]) -> date | None:
    date_text = safe_text(_field(report, "date")).strip()
    try:
        return datetime.fromisoformat(date_text[:16]).date()
    except ValueError:
        pass
    timestamp_value = _field(report, "timestamp")
    try:
        timestamp = float(0 if timestamp_value is None else timestamp_value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    if timestamp <= 0:
        return None
    try:
        return datetime.fromtimestamp(timestamp).date()
    except (OSError, OverflowError, ValueError):
        return None


def _source_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        source = str(_field(item, "source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


def _sort_key(item: dict[str, Any]) -> tuple[int, int, str, str]:
    source = str(_field(item, "source") or "")
    return (
        -_int(_field(item, "priority_score")),
        SOURCE_ORDER.get(source, 8),
        str(_field(item, "ticker") or ""),
        str(_field(item, "filename") or _field(item, "route") or ""),
    )


def _int(value: Any) -> int:
    return safe_int(value)


def _bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False
__all__ = ["SCHEMA_VERSION", "build_daily_decision_queue"]
