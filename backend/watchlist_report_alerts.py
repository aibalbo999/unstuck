"""Report alert helpers for watchlist listings."""

from __future__ import annotations

import logging
import sqlite3
from typing import Callable

import report_history_service

LOGGER = logging.getLogger(__name__)
PRIORITY_ORDER = {"high": 0, "medium": 1, "normal": 2, "low": 3}


def ticker_matches(report: dict, ticker: str) -> bool:
    report_ticker = str(report.get("ticker") or "").upper()
    ticker_upper = str(ticker or "").upper()
    return report_ticker == ticker_upper or report_ticker.split(".", 1)[0] == ticker_upper.split(".", 1)[0]


def latest_report_for_item(item: dict, output_dir: str) -> dict:
    ticker = str(item.get("ticker") or "").strip().upper()
    if not ticker or not output_dir:
        return {}
    try:
        result = report_history_service.list_reports(
            page=1,
            limit=5,
            q=ticker.split(".", 1)[0],
            pipeline=item.get("pipeline") or "all",
            recommendation="all",
            data_trust="all",
            output_dir=output_dir,
            report_cache={},
            sync_metadata=False,
        )
    except sqlite3.Error as exc:
        LOGGER.warning("Watchlist report lookup skipped because report index is unavailable: %s", exc)
        return {}
    reports = result.get("reports", [])
    for report in reports:
        if ticker_matches(report, ticker):
            return report
    return reports[0] if reports else {}


def sync_report_metadata_once(output_dir: str) -> None:
    if not output_dir:
        return
    try:
        report_history_service.list_reports(
            page=1,
            limit=1,
            q="",
            pipeline="all",
            recommendation="all",
            data_trust="all",
            output_dir=output_dir,
            report_cache={},
            sync_metadata=True,
        )
    except sqlite3.Error as exc:
        LOGGER.warning("Watchlist report metadata sync skipped because report index is unavailable: %s", exc)


def apply_report_alerts(
    items: list[dict],
    output_dir: str,
    *,
    latest_report_lookup: Callable[[dict, str], dict] = latest_report_for_item,
) -> dict:
    priority_counts = {"high": 0, "medium": 0, "normal": 0, "low": 0}
    alert_items = []
    for item in items:
        latest_report = latest_report_lookup(item, output_dir)
        priority, alert = priority_for_item(item, latest_report)
        priority_counts[priority] += 1
        alert_items.append({
            **item,
            "decision_priority": priority,
            "decision_alert": alert,
            "latest_report": compact_report(latest_report),
        })
    return {
        "items": sorted(
            alert_items,
            key=lambda item: (PRIORITY_ORDER.get(item.get("decision_priority"), 9), item.get("ticker", "")),
        ),
        "priority_counts": priority_counts,
    }


def priority_for_item(item: dict, latest_report: dict) -> tuple[str, dict]:
    if not item.get("enabled"):
        return "low", {"reason": "disabled", "message": "watchlist 項目已停用。"}
    if not latest_report:
        return "medium", {"reason": "missing_report", "message": "尚未產生最新報告。"}
    freshness = latest_report.get("decision_freshness") if isinstance(latest_report.get("decision_freshness"), dict) else {}
    if freshness.get("requires_rerun"):
        return "high", {"reason": "needs_rerun", "message": freshness.get("message") or "資料已更新，投資結論需重跑。"}
    return "normal", {"reason": "current", "message": "最新報告結論有效。"}


def compact_report(latest_report: dict) -> dict:
    if not latest_report:
        return {}
    return {
        "filename": latest_report.get("filename"),
        "date": latest_report.get("date"),
        "decision_freshness": latest_report.get("decision_freshness") or {},
        "data_trust": latest_report.get("data_trust") or {},
    }


__all__ = [
    "apply_report_alerts",
    "compact_report",
    "latest_report_for_item",
    "priority_for_item",
    "sync_report_metadata_once",
    "ticker_matches",
]
