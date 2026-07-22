"""Atomic claim helpers for scheduled watchlist runs."""

from __future__ import annotations

from datetime import datetime

import watchlist_store
from watchlist_schedule_helpers import slot_due


TAIPEI = watchlist_store.TAIPEI
DEFAULT_SCHEDULES = watchlist_store.DEFAULT_SCHEDULES


def claim_due_watchlist_items(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(TAIPEI)
    today = now.date().isoformat()
    claimed = []
    now_iso = watchlist_store._now_iso(now)
    with watchlist_store._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        watchlist_store._ensure_legacy_json_migrated(conn)
        store = watchlist_store._read_store_from_conn(conn)
        for item in store["items"]:
            if not item.get("enabled"):
                continue
            last_run_dates = dict(item.get("last_run_dates") or {})
            item_claimed = False
            for slot in item.get("schedule_slots", []):
                if not slot_due(slot, now, schedules=DEFAULT_SCHEDULES) or last_run_dates.get(slot) == today:
                    continue
                claimed.append({**item, "due_slot": slot, "due_label": DEFAULT_SCHEDULES[slot]["label"], "due_date": today})
                last_run_dates[slot] = today
                item_claimed = True
            if item_claimed:
                item["last_run_dates"] = last_run_dates
                item["updated_at"] = now_iso
                watchlist_store._replace_item_row(conn, item)
        if claimed:
            watchlist_store._touch_store(conn, now_iso)
    return claimed
