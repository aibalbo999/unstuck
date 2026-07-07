"""Operator-selected daily decision tracking service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException

import decision_tracking_store
import report_history_service
from decision_backtest_service import compute_performance_stats, run_due_backtests
from report_refresh_service import refresh_report_data_snapshot


DAILY_REFRESH_SLOT = "post_market"
DAILY_REFRESH_AFTER = (15, 40)
PIPELINE_ORDER = {"v1": 0, "v2": 1, "v3": 2, "v4": 3}


def _ticker_matches(report: dict, ticker: str) -> bool:
    report_ticker = str(report.get("ticker") or "").upper()
    ticker_upper = str(ticker or "").upper()
    return report_ticker == ticker_upper or report_ticker.split(".", 1)[0] == ticker_upper.split(".", 1)[0]


def latest_report_for_ticker(ticker: str, output_dir: str, *, sync_metadata: bool = True) -> dict:
    reports = latest_reports_for_ticker(ticker, output_dir, sync_metadata=sync_metadata)
    if not reports:
        return {}
    return max(reports, key=lambda report: float(report.get("timestamp") or 0))


def latest_reports_for_ticker(ticker: str, output_dir: str, *, sync_metadata: bool = True) -> list[dict]:
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
        sync_metadata=sync_metadata,
    ).get("reports", [])
    matched = [report for report in reports if _ticker_matches(report, ticker)]
    return sorted(matched, key=lambda report: (PIPELINE_ORDER.get(report.get("pipeline_id"), 99), -float(report.get("timestamp") or 0)))


def _sync_report_metadata_once(output_dir: str) -> None:
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


def _attach_report(item: dict, output_dir: str, *, sync_metadata: bool = False) -> dict:
    latest_reports = latest_reports_for_ticker(item.get("ticker", ""), output_dir, sync_metadata=sync_metadata)
    latest_report = max(latest_reports, key=lambda report: float(report.get("timestamp") or 0)) if latest_reports else {}
    company_name = item.get("company_name") or next((report.get("company_name") for report in latest_reports if report.get("company_name")), None)
    alert = {"status": "no_report", "message": "尚未找到可追蹤報告。"}
    if latest_report:
        tracking = latest_report.get("decision_tracking") if isinstance(latest_report.get("decision_tracking"), dict) else {}
        alert = {"status": "tracked", "message": tracking.get("tracking_summary_status") or tracking.get("summary") or "已建立每日決策追蹤。"}
    return {**item, "company_name": company_name, "latest_report": latest_report, "latest_reports": latest_reports, "tracking_alert": alert}


def list_decision_tracking(output_dir: str, *, sync_metadata: bool = True) -> dict:
    if sync_metadata:
        _sync_report_metadata_once(output_dir)
    items = [_attach_report(item, output_dir, sync_metadata=False) for item in decision_tracking_store.list_items()]
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
    _sync_report_metadata_once(output_dir)
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
        reports = latest_reports_for_ticker(ticker, output_dir, sync_metadata=False)
        if not reports:
            message = "尚未找到可追蹤報告。"
            decision_tracking_store.mark_refresh(ticker, status="missing_report", message=message, now=now)
            errors.append({"ticker": ticker, "error": message})
            continue
        try:
            refreshed_for_ticker = 0
            refreshed_data = None
            for report in reports:
                refresh_result = await refresh_report_data_snapshot(
                    report["filename"],
                    output_dir=output_dir,
                    refresh_service=refresh_service,
                    refreshed_data=refreshed_data,
                    return_refreshed_data=refreshed_data is None,
                )
                if refreshed_data is None:
                    refreshed_data = refresh_result.get("refreshed_data")
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
    del output_dir
    return compute_performance_stats()
