"""Scheduled watchlist batch analysis helpers."""

from __future__ import annotations

import time
import inspect
from datetime import datetime

from data_fetch import FetchRequest
from pipeline_modes import normalize_pipeline_run_id
import watchlist_claim_store
import watchlist_store
import watchlist_trigger_store
from watchlist_report_alerts import apply_report_alerts, report_history_service, sync_report_metadata_once
from watchlist_schedule_helpers import due_watchlist_items as _scheduled_due_watchlist_items, post_market_due
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


def list_watchlist_with_report_alerts(output_dir: str, *, sync_metadata: bool = True) -> dict:
    if sync_metadata:
        sync_report_metadata_once(output_dir)
    payload = list_watchlist()
    alert_payload = apply_report_alerts(payload.get("items", []), output_dir)
    payload["items"] = alert_payload["items"]
    payload["priority_counts"] = alert_payload["priority_counts"]
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


def due_watchlist_items(now: datetime | None = None) -> list[dict]:
    return _scheduled_due_watchlist_items(list_watchlist()["items"], now=now, schedules=DEFAULT_SCHEDULES)


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
    if not post_market_due(now, schedules=DEFAULT_SCHEDULES):
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
                result = await data_service.fetch_async(FetchRequest.from_ticker(ticker, force_refresh=True))
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
            _enqueue_watchlist_analysis(task_queue, run_stock_analysis_job, job_id, ticker, selected_pipeline)
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
        _enqueue_watchlist_analysis(task_queue, run_stock_analysis_job, job_id, ticker, pipeline)
        queued.append({"ticker": ticker, "pipeline": pipeline, "job_id": job_id, "slot": item.get("due_slot")})
        if item.get("due_slot"):
            mark_watchlist_run(ticker, pipeline, item["due_slot"], run_date=item.get("due_date"))

        # 避免瞬間塞滿 LiteLLM rate limit，每個任務派發後休眠 45 秒
        time.sleep(45)
    return {"success": True, "queued": queued, "skipped": skipped}


def _enqueue_watchlist_analysis(task_queue, run_stock_analysis_job, job_id: str, ticker: str, pipeline: str) -> None:
    task_id = f"analysis:{job_id}"
    enqueue = task_queue.enqueue
    try:
        signature = inspect.signature(enqueue)
    except (TypeError, ValueError):
        signature = None
    supports_queue_name = False
    if signature is not None:
        supports_queue_name = "queue_name" in signature.parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
    if supports_queue_name:
        enqueue(task_id, run_stock_analysis_job, job_id, ticker, pipeline, queue_name="watchlist")
        return
    enqueue(task_id, run_stock_analysis_job, job_id, ticker, pipeline)
