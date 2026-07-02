"""Temporal report memory used to force final agents to review prior calls."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import decision_tracking_store
import report_history_service


LOGGER = logging.getLogger(__name__)


def build_temporal_memory(ticker: str, *, output_dir: str, current_price: float | None = None) -> dict[str, Any]:
    """Return the latest prior report memory for the same ticker, or an empty dict."""
    ticker_upper = str(ticker or "").strip().upper()
    if not ticker_upper:
        return {}
    reports = _list_reports_for_temporal_memory(ticker_upper, output_dir=output_dir)
    matched = [report for report in reports if _ticker_matches(report, ticker_upper)]
    if not matched:
        return {}
    previous = max(matched, key=_sort_key)
    recommendation = previous.get("recommendation") if isinstance(previous.get("recommendation"), dict) else {}
    backtests = _list_backtests_for_temporal_memory(str(previous.get("filename") or ""))
    prev_date = _parse_report_date(previous)
    elapsed_months = _elapsed_months(prev_date, date.today()) if prev_date else None
    memory = {
        "previous_report": {
            "filename": previous.get("filename", ""),
            "date": previous.get("date", ""),
            "ticker": previous.get("ticker", ""),
            "pipeline_id": previous.get("pipeline_id", ""),
            "summary": previous.get("summary", ""),
            "recommendation": recommendation.get("recommendation", ""),
            "target_3m": recommendation.get("target_3m", ""),
            "target_6m": recommendation.get("target_6m", ""),
            "target_12m": recommendation.get("target_12m", ""),
        },
        "current_price": current_price,
        "elapsed_months": elapsed_months,
        "backtests": backtests[:6],
    }
    memory["reflection_prompt"] = _reflection_prompt(memory)
    return memory


def _list_reports_for_temporal_memory(ticker: str, *, output_dir: str) -> list[dict[str, Any]]:
    try:
        response = report_history_service.list_reports(
            page=1,
            limit=50,
            q=ticker.split(".", 1)[0],
            pipeline="all",
            recommendation="all",
            data_trust="all",
            include_versions=True,
            output_dir=output_dir,
            report_cache={},
        )
    except Exception as exc:
        LOGGER.warning("Temporal memory skipped for %s: report history unavailable: %s", ticker, exc)
        return []
    if not isinstance(response, dict):
        return []
    reports = response.get("reports", [])
    return reports if isinstance(reports, list) else []


def _list_backtests_for_temporal_memory(report_filename: str) -> list[dict[str, Any]]:
    if not report_filename:
        return []
    try:
        backtests = decision_tracking_store.list_backtests_for_report(report_filename)
    except Exception as exc:
        LOGGER.warning("Temporal memory backtests skipped for %s: %s", report_filename, exc)
        return []
    return backtests if isinstance(backtests, list) else []


def build_valuation_memory_slice(temporal_memory: dict) -> dict:
    """
    回傳僅含估值相關欄位的精簡 temporal memory，
    供估值 Agent 使用，避免注入過多前期報告文字。
    """
    if not temporal_memory:
        return {}
    prev = temporal_memory.get("previous_report", {})
    backtests = temporal_memory.get("backtests", [])
    latest_backtest = backtests[0] if backtests else {}
    return {
        "prior_target_3m": prev.get("target_3m"),
        "prior_target_6m": prev.get("target_6m"),
        "prior_target_12m": prev.get("target_12m"),
        "prior_recommendation": prev.get("recommendation"),
        "prior_report_date": prev.get("date"),
        "latest_backtest_roi": latest_backtest.get("roi_pct"),
        "latest_backtest_hit": latest_backtest.get("hit"),
        "note": "請參考上期目標價與實際回測結果，審慎設定本期估值假設。",
    }


def _ticker_matches(report: dict, ticker: str) -> bool:
    report_ticker = str(report.get("ticker") or "").upper()
    return report_ticker == ticker or report_ticker.split(".", 1)[0] == ticker.split(".", 1)[0]


def _parse_report_date(report: dict) -> date | None:
    try:
        return datetime.fromisoformat(str(report.get("date") or "")[:16]).date()
    except ValueError:
        return None


def _sort_key(report: dict) -> tuple[float, str]:
    timestamp = report.get("timestamp")
    try:
        return float(timestamp or 0), str(report.get("date") or "")
    except (TypeError, ValueError):
        parsed = _parse_report_date(report)
        return (parsed.toordinal() if parsed else 0), str(report.get("date") or "")


def _elapsed_months(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + end.month - start.month
    return max(0, months - (1 if end.day < start.day else 0))


def _reflection_prompt(memory: dict) -> str:
    previous = memory.get("previous_report", {}) or {}
    backtests = memory.get("backtests", []) or []
    missed = [row for row in backtests if row.get("outcome") == "miss"]
    outcome_line = "目前已有到期回測，且預測落空。" if missed else "目前回測尚未顯示重大落空，仍需重新檢查假設。"
    return (
        "【Agent 歷史反思】\n"
        f"你或你的團隊在 {memory.get('elapsed_months') or '前次'} 個月前對 "
        f"{previous.get('ticker') or '此公司'} 給出 {previous.get('recommendation') or 'N/A'}，"
        f"3/6/12 月目標價分別為 {previous.get('target_3m') or 'N/A'}、"
        f"{previous.get('target_6m') or 'N/A'}、{previous.get('target_12m') or 'N/A'}。\n"
        f"{outcome_line}請對比當時預測與目前真實股價/財務發展；如果預測落空，"
        "請在此次分析中明確檢討先前假設哪裡出錯，例如高估擴產速度、低估成本、"
        "錯估估值均值回歸或忽略籌碼派發，並在本次最終建議中調整模型。"
    )
