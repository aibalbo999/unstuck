"""Operator-selected daily decision tracking service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException

import decision_tracking_store
import report_history_service
from report_refresh_service import refresh_report_data_snapshot


DAILY_REFRESH_SLOT = "post_market"
DAILY_REFRESH_AFTER = (15, 40)
PIPELINE_ORDER = {"v1": 0, "v2": 1}


def _ticker_matches(report: dict, ticker: str) -> bool:
    report_ticker = str(report.get("ticker") or "").upper()
    ticker_upper = str(ticker or "").upper()
    return report_ticker == ticker_upper or report_ticker.split(".", 1)[0] == ticker_upper.split(".", 1)[0]


def latest_report_for_ticker(ticker: str, output_dir: str) -> dict:
    reports = latest_reports_for_ticker(ticker, output_dir)
    if not reports:
        return {}
    return max(reports, key=lambda report: float(report.get("timestamp") or 0))


def latest_reports_for_ticker(ticker: str, output_dir: str) -> list[dict]:
    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return []
    reports = report_history_service.list_reports(
        page=1,
        limit=20,
        q=ticker.split(".", 1)[0],
        pipeline="all",
        recommendation="all",
        data_trust="all",
        include_versions=False,
        output_dir=output_dir,
        report_cache={},
    ).get("reports", [])
    matched = [report for report in reports if _ticker_matches(report, ticker)]
    return sorted(matched, key=lambda report: (PIPELINE_ORDER.get(report.get("pipeline_id"), 99), -float(report.get("timestamp") or 0)))


def _attach_report(item: dict, output_dir: str) -> dict:
    latest_reports = latest_reports_for_ticker(item.get("ticker", ""), output_dir)
    latest_report = max(latest_reports, key=lambda report: float(report.get("timestamp") or 0)) if latest_reports else {}
    company_name = item.get("company_name") or next((report.get("company_name") for report in latest_reports if report.get("company_name")), None)
    alert = {"status": "no_report", "message": "尚未找到可追蹤報告。"}
    if latest_report:
        tracking = latest_report.get("decision_tracking") if isinstance(latest_report.get("decision_tracking"), dict) else {}
        alert = {"status": "tracked", "message": tracking.get("tracking_summary_status") or tracking.get("summary") or "已建立每日決策追蹤。"}
    return {**item, "company_name": company_name, "latest_report": latest_report, "latest_reports": latest_reports, "tracking_alert": alert}


def list_decision_tracking(output_dir: str) -> dict:
    items = [_attach_report(item, output_dir) for item in decision_tracking_store.list_items()]
    enabled = sum(1 for item in items if item.get("enabled"))
    return {"items": items, "enabled_count": enabled, "daily_refresh_slot": DAILY_REFRESH_SLOT}


def upsert_tracking_item(payload: dict, output_dir: str) -> dict:
    decision_tracking_store.upsert_item(payload)
    return list_decision_tracking(output_dir)


def delete_tracking_item(ticker: str, output_dir: str) -> dict:
    result = decision_tracking_store.delete_item(ticker)
    return {**result, **list_decision_tracking(output_dir)}


def _is_due(item: dict, now: datetime) -> bool:
    if not item.get("enabled"):
        return False
    hour, minute = DAILY_REFRESH_AFTER
    if (now.hour, now.minute) < (hour, minute):
        return False
    return item.get("last_refresh_date") != now.date().isoformat()


async def refresh_tracking_items(
    *,
    output_dir: str,
    refresh_service: Any,
    tickers: list[str] | None = None,
    due_only: bool = False,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(decision_tracking_store.TAIPEI)
    requested = {str(ticker or "").strip().upper() for ticker in (tickers or []) if str(ticker or "").strip()}
    updated_count = 0
    updated_reports_count = 0
    skipped = []
    errors = []
    for item in decision_tracking_store.list_items():
        ticker = item.get("ticker", "")
        if requested and ticker not in requested:
            continue
        if not item.get("enabled"):
            skipped.append({"ticker": ticker, "reason": "disabled"})
            continue
        if due_only and not _is_due(item, now):
            skipped.append({"ticker": ticker, "reason": "already_refreshed_today"})
            continue
        reports = latest_reports_for_ticker(ticker, output_dir)
        if not reports:
            message = "尚未找到可追蹤報告。"
            decision_tracking_store.mark_refresh(ticker, status="missing_report", message=message, now=now)
            errors.append({"ticker": ticker, "error": message})
            continue
        try:
            refreshed_for_ticker = 0
            for report in reports:
                freshness = report.get("decision_freshness") if isinstance(report.get("decision_freshness"), dict) else {}
                if report.get("analysis_text_stale") or freshness.get("requires_rerun"):
                    skipped.append({
                        "ticker": ticker,
                        "filename": report.get("filename", ""),
                        "reason": "needs_full_rerun",
                    })
                    continue
                await refresh_report_data_snapshot(report["filename"], output_dir=output_dir, refresh_service=refresh_service)
                refreshed_for_ticker += 1
                updated_reports_count += 1
            if refreshed_for_ticker:
                decision_tracking_store.mark_refresh(ticker, status="success", message="最新股價已刷新。", now=now)
                updated_count += 1
            else:
                message = "最新報告已標示需完整重跑，略過資料快照刷新。"
                decision_tracking_store.mark_refresh(ticker, status="needs_full_rerun", message=message, now=now)
        except HTTPException as exc:
            message = str(exc.detail or exc)
            decision_tracking_store.mark_refresh(ticker, status="error", message=message, now=now)
            errors.append({"ticker": ticker, "error": message})
        except Exception as exc:
            message = str(exc)
            decision_tracking_store.mark_refresh(ticker, status="error", message=message, now=now)
            errors.append({"ticker": ticker, "error": message})
    payload = list_decision_tracking(output_dir)
    return {"success": not errors, "updated_count": updated_count, "updated_reports_count": updated_reports_count, "skipped": skipped, "errors": errors, **payload}


def compute_tracking_performance_stats(output_dir: str) -> dict:
    """
    Compute aggregate performance statistics for tracked reports.
    (Stub for future automated return calculations)
    """
    items = list_decision_tracking(output_dir).get("items", [])
    
    total_tracked = len(items)
    active_tracked = sum(1 for item in items if item.get("enabled"))
    
    # In the future, this will loop through tracking histories and compare current_price
    # with the initial report price to calculate hit rates, avg return, etc.
    
    return {
        "summary": {
            "total_tracked_stocks": total_tracked,
            "active_tracked_stocks": active_tracked,
            "average_return_pct": 0.0,
            "hit_rate_pct": 0.0,
        },
        "details": [],
        "message": "績效統計服務架構已建置，等待歷史決策紀錄累積後自動計算。",
    }
