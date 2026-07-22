"""Pure schedule helpers for watchlist batch runs."""

from __future__ import annotations

from datetime import datetime

import watchlist_store


TAIPEI = watchlist_store.TAIPEI
DEFAULT_SCHEDULES = watchlist_store.DEFAULT_SCHEDULES


def slot_due(slot: str, now: datetime, *, schedules: dict | None = None) -> bool:
    schedule_map = schedules or DEFAULT_SCHEDULES
    spec = schedule_map.get(slot)
    if not spec:
        return False
    hour, minute = [int(part) for part in spec["time"].split(":", 1)]
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= scheduled


def due_watchlist_items(items: list[dict], *, now: datetime | None = None, schedules: dict | None = None) -> list[dict]:
    schedule_map = schedules or DEFAULT_SCHEDULES
    current_time = now or datetime.now(TAIPEI)
    today = current_time.date().isoformat()
    due = []
    for item in items:
        if not item.get("enabled"):
            continue
        for slot in item.get("schedule_slots", []):
            if not slot_due(slot, current_time, schedules=schedule_map):
                continue
            if (item.get("last_run_dates") or {}).get(slot) == today:
                continue
            due.append({
                **item,
                "due_slot": slot,
                "due_label": schedule_map[slot]["label"],
                "due_date": today,
            })
    return due


def post_market_due(now: datetime, *, schedules: dict | None = None) -> bool:
    return slot_due("post_market", now, schedules=schedules)
