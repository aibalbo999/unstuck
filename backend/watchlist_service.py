"""Local watchlist storage and scheduled batch analysis helpers."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import CACHE_DB_PATH
from pipeline_modes import normalize_pipeline_run_id


TAIPEI = ZoneInfo("Asia/Taipei")
WATCHLIST_PATH = Path(os.getenv("WATCHLIST_PATH", str(Path(CACHE_DB_PATH).parent / "watchlist.json")))
DEFAULT_SCHEDULES = {
    "pre_market": {"label": "盤前", "time": "08:30"},
    "post_market": {"label": "盤後", "time": "15:30"},
}


def _read_store() -> dict:
    if not WATCHLIST_PATH.exists():
        return {"items": [], "updated_at": None}
    try:
        value = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": [], "updated_at": None}
    if not isinstance(value, dict):
        return {"items": [], "updated_at": None}
    items = value.get("items") if isinstance(value.get("items"), list) else []
    return {"items": [_normalize_item(item) for item in items if isinstance(item, dict)], "updated_at": value.get("updated_at")}


def _write_store(store: dict) -> dict:
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    store = {"items": list(store.get("items") or []), "updated_at": datetime.now(TAIPEI).isoformat(timespec="seconds")}
    WATCHLIST_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return store


def _normalize_slots(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        value = ["post_market"]
    slots = []
    for item in value:
        slot = str(item or "").strip().lower()
        if slot in DEFAULT_SCHEDULES and slot not in slots:
            slots.append(slot)
    return slots or ["post_market"]


def _normalize_item(item: dict) -> dict:
    ticker = str(item.get("ticker") or "").strip().upper()
    pipeline = normalize_pipeline_run_id(item.get("pipeline") or item.get("pipeline_id") or "v1")
    return {
        "ticker": ticker,
        "pipeline": pipeline,
        "enabled": bool(item.get("enabled", True)),
        "schedule_slots": _normalize_slots(item.get("schedule_slots")),
        "last_run_dates": item.get("last_run_dates") if isinstance(item.get("last_run_dates"), dict) else {},
        "created_at": item.get("created_at") or datetime.now(TAIPEI).isoformat(timespec="seconds"),
        "updated_at": item.get("updated_at") or datetime.now(TAIPEI).isoformat(timespec="seconds"),
    }


def list_watchlist() -> dict:
    store = _read_store()
    return {
        "items": [item for item in store["items"] if item.get("ticker")],
        "schedules": DEFAULT_SCHEDULES,
        "updated_at": store.get("updated_at"),
    }


def upsert_watchlist_item(payload: dict) -> dict:
    item = _normalize_item(payload or {})
    if not item["ticker"]:
        raise ValueError("ticker is required")
    store = _read_store()
    items = store["items"]
    replaced = False
    now = datetime.now(TAIPEI).isoformat(timespec="seconds")
    for index, existing in enumerate(items):
        if existing.get("ticker") == item["ticker"] and existing.get("pipeline") == item["pipeline"]:
            item["created_at"] = existing.get("created_at") or item["created_at"]
            item["last_run_dates"] = existing.get("last_run_dates", {})
            item["updated_at"] = now
            items[index] = item
            replaced = True
            break
    if not replaced:
        item["created_at"] = now
        item["updated_at"] = now
        items.append(item)
    return _write_store({"items": sorted(items, key=lambda row: (row.get("ticker", ""), row.get("pipeline", "")))})


def delete_watchlist_item(ticker: str, pipeline: str = "all") -> dict:
    ticker = str(ticker or "").strip().upper()
    pipeline = str(pipeline or "all").strip().lower()
    store = _read_store()
    before = len(store["items"])
    items = [
        item for item in store["items"]
        if not (
            item.get("ticker") == ticker
            and (pipeline == "all" or item.get("pipeline") == normalize_pipeline_run_id(pipeline))
        )
    ]
    written = _write_store({"items": items})
    return {"success": True, "deleted": before - len(items), **written}


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


def mark_watchlist_run(ticker: str, pipeline: str, slot: str, now: datetime | None = None, run_date: str | None = None) -> None:
    now = now or datetime.now(TAIPEI)
    today = run_date or now.date().isoformat()
    store = _read_store()
    for item in store["items"]:
        if item.get("ticker") == ticker and item.get("pipeline") == pipeline:
            dates = item.setdefault("last_run_dates", {})
            dates[slot] = today
            item["updated_at"] = now.isoformat(timespec="seconds")
    _write_store(store)


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
        time.sleep(0.01)
    return {"success": True, "queued": queued, "skipped": skipped}
