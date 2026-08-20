"""Pure report follow-up actions used by the daily decision queue."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from daily_decision_report_keys import report_key
from decision_backtest import BACKTEST_HORIZONS, add_calendar_months
from mapping_fields import mapping_field as _field
from mapping_fields import safe_dict_list, safe_int, safe_text


def backtest_due_items(
    reports: list[dict[str, Any]], performance: dict[str, Any], *, as_of: date, skip_keys: set[str]
) -> list[dict[str, Any]]:
    explicit = safe_dict_list(_field(performance, "due_backtests"))
    if not explicit:
        explicit = safe_dict_list(_field(performance, "backtest_due"))
    if explicit:
        return [_due_item(row) for row in explicit if isinstance(row, dict) and report_key(row) not in skip_keys]
    evaluated = {
        (safe_text(_field(row, "report_filename")).strip() or safe_text(_field(row, "filename")).strip(), _int(_field(row, "horizon_months")))
        for row in safe_dict_list(_field(performance, "details"))
    }
    due = []
    for report in safe_dict_list(reports):
        if report_key(report) in skip_keys:
            continue
        generated = _report_date(report)
        filename = safe_text(_field(report, "filename")).strip() or safe_text(_field(report, "report_filename")).strip()
        if generated is None or not filename:
            continue
        for horizon in BACKTEST_HORIZONS:
            if add_calendar_months(generated, horizon) <= as_of and (filename, int(horizon)) not in evaluated:
                due.append(_due_item({**report, "horizon_months": horizon}))
                break
    return due


def rerun_items(rerun_reports: list[dict[str, Any]], *, skip_keys: set[str]) -> list[dict[str, Any]]:
    return [_rerun_report_payload(report) for report in safe_dict_list(rerun_reports) if report_key(report) not in skip_keys]


def _due_item(row: dict[str, Any]) -> dict[str, Any]:
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


def _int(value: Any) -> int:
    return safe_int(value)


__all__ = ["backtest_due_items", "rerun_items"]
