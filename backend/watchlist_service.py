"""Scheduled watchlist batch analysis helpers."""

from __future__ import annotations

import time
from datetime import datetime

from data_fetch import FetchRequest
from pipeline_modes import normalize_pipeline_run_id
import report_history_service
import watchlist_claim_store
import watchlist_store
import watchlist_trigger_store
from watchlist_triggers import evaluate_watchlist_triggers


TAIPEI = watchlist_store.TAIPEI
WATCHLIST_PATH = watchlist_store.WATCHLIST_PATH
WATCHLIST_DB_PATH = watchlist_store.WATCHLIST_DB_PATH
DEFAULT_SCHEDULES = watchlist_store.DEFAULT_SCHEDULES


def _sync_store_config() -> None:
    watchlist_store.WATCHLIST_PATH = WATCHLIST_PATH
    watchlist_store.WATCHLIST_DB_PATH = WATCHLIST_DB_PATH


def reset_watchlist_store_for_tests() -> None:
    _sync_store_config()
    watchlist_store.reset_watchlist_store_for_tests()


def list_watchlist() -> dict:
    _sync_store_config()
    payload = watchlist_store.list_watchlist()
    trigger_map = watchlist_trigger_store.triggers_for_items(payload.get("items", []))
    event_map = watchlist_trigger_store.latest_events_for_items(payload.get("items", []))
    payload["items"] = [
        {
            **item,
            "triggers": trigger_map.get((item.get("ticker"), item.get("pipeline")), []),
            "latest_trigger_event": event_map.get((item.get("ticker"), item.get("pipeline")), {}),
        }
        for item in payload.get("items", [])
    ]
    return payload


def _ticker_matches(report: dict, ticker: str) -> bool:
    report_ticker = str(report.get("ticker") or "").upper()
    ticker_upper = str(ticker or "").upper()
    return report_ticker == ticker_upper or report_ticker.split(".", 1)[0] == ticker_upper.split(".", 1)[0]


def _latest_report_for_item(item: dict, output_dir: str) -> dict:
    ticker = str(item.get("ticker") or "").strip().upper()
    if not ticker or not output_dir:
        return {}
    result = report_history_service.list_reports(
        page=1,
        limit=5,
        q=ticker.split(".", 1)[0],
        pipeline=item.get("pipeline") or "all",
        recommendation="all",
        data_trust="all",
        output_dir=output_dir,
        report_cache={},
    )
    reports = result.get("reports", [])
    for report in reports:
        if _ticker_matches(report, ticker):
            return report
    return reports[0] if reports else {}


def _priority_for_item(item: dict, latest_report: dict) -> tuple[str, dict]:
    if not item.get("enabled"):
        return "low", {"reason": "disabled", "message": "watchlist 項目已停用。"}
    if not latest_report:
        return "medium", {"reason": "missing_report", "message": "尚未產生最新報告。"}
    freshness = latest_report.get("decision_freshness") if isinstance(latest_report.get("decision_freshness"), dict) else {}
    if freshness.get("requires_rerun"):
        return "high", {"reason": "needs_rerun", "message": freshness.get("message") or "資料已更新，投資結論需重跑。"}
    return "normal", {"reason": "current", "message": "最新報告結論有效。"}


def list_watchlist_with_report_alerts(output_dir: str) -> dict:
    payload = list_watchlist()
    priority_counts = {"high": 0, "medium": 0, "normal": 0, "low": 0}
    items = []
    for item in payload.get("items", []):
        latest_report = _latest_report_for_item(item, output_dir)
        priority, alert = _priority_for_item(item, latest_report)
        priority_counts[priority] += 1
        compact_report = {}
        if latest_report:
            compact_report = {
                "filename": latest_report.get("filename"),
                "date": latest_report.get("date"),
                "decision_freshness": latest_report.get("decision_freshness") or {},
                "data_trust": latest_report.get("data_trust") or {},
            }
        items.append({
            **item,
            "decision_priority": priority,
            "decision_alert": alert,
            "latest_report": compact_report,
        })
    priority_order = {"high": 0, "medium": 1, "normal": 2, "low": 3}
    payload["items"] = sorted(items, key=lambda item: (priority_order.get(item.get("decision_priority"), 9), item.get("ticker", "")))
    payload["priority_counts"] = priority_counts
    return payload


def upsert_watchlist_item(payload: dict) -> dict:
    _sync_store_config()
    result = watchlist_store.upsert_watchlist_item(payload)
    if "triggers" in (payload or {}):
        ticker = str(payload.get("ticker") or "").strip().upper()
        pipeline = normalize_pipeline_run_id(payload.get("pipeline") or payload.get("pipeline_id") or "v1")
        watchlist_trigger_store.set_item_triggers(ticker, pipeline, payload.get("triggers"))
    return list_watchlist()


def delete_watchlist_item(ticker: str, pipeline: str = "all") -> dict:
    _sync_store_config()
    result = watchlist_store.delete_watchlist_item(ticker, pipeline)
    watchlist_trigger_store.delete_item_triggers(ticker, pipeline)
    return {**result, **list_watchlist(), "deleted": result.get("deleted", 0)}


def mark_watchlist_run(
    ticker: str,
    pipeline: str,
    slot: str,
    now: datetime | None = None,
    run_date: str | None = None,
) -> None:
    _sync_store_config()
    watchlist_store.mark_watchlist_run(ticker, pipeline, slot, now=now, run_date=run_date)


def _slot_due(slot: str, now: datetime) -> bool:
    spec = DEFAULT_SCHEDULES.get(slot)
    if not spec:
        return False
    hour, minute = [int(part) for part in spec["time"].split(":", 1)]
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= scheduled


def due_watchlist_items(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(TAIPEI)
    today = now.date().isoformat()
    due = []
    for item in list_watchlist()["items"]:
        if not item.get("enabled"):
            continue
        for slot in item.get("schedule_slots", []):
            if not _slot_due(slot, now):
                continue
            if (item.get("last_run_dates") or {}).get(slot) == today:
                continue
            due.append({**item, "due_slot": slot, "due_label": DEFAULT_SCHEDULES[slot]["label"], "due_date": today})
    return due


def _post_market_due(now: datetime) -> bool:
    hour, minute = [int(part) for part in DEFAULT_SCHEDULES["post_market"]["time"].split(":", 1)]
    return now >= now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _triggers_need_market_data(triggers: list) -> bool:
    for trigger in triggers:
        if not isinstance(trigger, dict) or trigger.get("enabled") is False:
            continue
        if str(trigger.get("type") or "").strip() != "daily_screener":
            return True
    return False


async def monitor_watchlist_triggers(
    *,
    data_service,
    create_job,
    find_active_job,
    task_queue,
    run_stock_analysis_job,
    now: datetime | None = None,
) -> dict:
    _sync_store_config()
    now = now or datetime.now(TAIPEI)
    if not _post_market_due(now):
        return {"success": True, "queued": [], "skipped": [{"reason": "before_post_market"}], "errors": []}
    queued = []
    skipped = []
    errors = []
    evaluation_date = now.date().isoformat()
    for item in list_watchlist().get("items", []):
        triggers = item.get("triggers") or []
        if not item.get("enabled") or not triggers:
            continue
        ticker = str(item.get("ticker") or "").strip().upper()
        try:
            if _triggers_need_market_data(triggers):
                result = await data_service.fetch_async(FetchRequest.from_ticker(ticker))
                data = result.data if isinstance(getattr(result, "data", None), dict) else {}
            else:
                data = {"ticker": ticker}
            events = evaluate_watchlist_triggers(item, data, evaluation_date=evaluation_date)
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)[:240]})
            continue
        for event in events:
            recorded = watchlist_trigger_store.record_trigger_event(event)
            if not recorded.get("inserted"):
                skipped.append({"ticker": ticker, "trigger": event.get("trigger_type"), "reason": "already_evaluated"})
                continue
            if not event.get("matched"):
                skipped.append({"ticker": ticker, "trigger": event.get("trigger_type"), "reason": "not_matched"})
                continue
            selected_pipeline = normalize_pipeline_run_id(event.get("pipeline_selected") or item.get("pipeline") or "v1")
            active = find_active_job(ticker, selected_pipeline)
            if active:
                skipped.append({"ticker": ticker, "pipeline": selected_pipeline, "reason": "active_job", "job_id": active.get("job_id")})
                continue
            job_id = create_job(ticker, selected_pipeline)
            task_queue.enqueue(f"analysis:{job_id}", run_stock_analysis_job, job_id, ticker, selected_pipeline)
            queued.append({"ticker": ticker, "pipeline": selected_pipeline, "job_id": job_id, "trigger": event.get("trigger_type")})

            # 避免瞬間塞滿 LiteLLM rate limit，每個觸發任務派發後休眠 45 秒
            time.sleep(45)
    return {"success": not errors, "queued": queued, "skipped": skipped, "errors": errors}


def claim_due_watchlist_items(now: datetime | None = None) -> list[dict]:
    _sync_store_config()
    return watchlist_claim_store.claim_due_watchlist_items(now)


def enqueue_watchlist_items(items: list[dict], *, create_job, find_active_job, task_queue, run_stock_analysis_job) -> dict:
    queued = []
    skipped = []
    for item in items:
        ticker = str(item.get("ticker") or "").strip().upper()
        pipeline = normalize_pipeline_run_id(item.get("pipeline") or "v1")
        if not ticker:
            continue
        active = find_active_job(ticker, pipeline)
        if active:
            skipped.append({"ticker": ticker, "pipeline": pipeline, "reason": "active_job", "job_id": active.get("job_id")})
            continue
        job_id = create_job(ticker, pipeline)
        task_queue.enqueue(f"analysis:{job_id}", run_stock_analysis_job, job_id, ticker, pipeline)
        queued.append({"ticker": ticker, "pipeline": pipeline, "job_id": job_id, "slot": item.get("due_slot")})
        if item.get("due_slot"):
            mark_watchlist_run(ticker, pipeline, item["due_slot"], run_date=item.get("due_date"))

        # 避免瞬間塞滿 LiteLLM rate limit，每個任務派發後休眠 45 秒
        time.sleep(45)
    return {"success": True, "queued": queued, "skipped": skipped}
