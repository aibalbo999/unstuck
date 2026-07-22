"""Watchlist item normalization and SQLite row helpers."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline_modes import normalize_pipeline_run_id


TAIPEI = ZoneInfo("Asia/Taipei")
DEFAULT_SCHEDULES = {
    "pre_market": {"label": "盤前", "time": "08:30"},
    "post_market": {"label": "盤後", "time": "15:30"},
}


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_list(value: str | None) -> list:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def json_dict(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def normalize_slots(value) -> list[str]:
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


def normalize_tags(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    tags = []
    for item in value:
        tag = str(item or "").strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def normalize_item(item: dict, *, now_iso_factory=None) -> dict:
    now_iso_factory = now_iso_factory or (lambda: datetime.now(TAIPEI).isoformat(timespec="seconds"))
    ticker = str(item.get("ticker") or "").strip().upper()
    pipeline = normalize_pipeline_run_id(item.get("pipeline") or item.get("pipeline_id") or "v1")
    return {
        "ticker": ticker,
        "pipeline": pipeline,
        "enabled": bool(item.get("enabled", True)),
        "schedule_slots": normalize_slots(item.get("schedule_slots")),
        "last_run_dates": item.get("last_run_dates") if isinstance(item.get("last_run_dates"), dict) else {},
        "tags": normalize_tags(item.get("tags")),
        "trigger_source": str(item.get("trigger_source") or "").strip().lower(),
        "created_at": item.get("created_at") or now_iso_factory(),
        "updated_at": item.get("updated_at") or now_iso_factory(),
    }


def item_from_row(row: sqlite3.Row) -> dict:
    return {
        "ticker": row["ticker"],
        "pipeline": row["pipeline"],
        "enabled": bool(row["enabled"]),
        "schedule_slots": normalize_slots(json_list(row["schedule_slots_json"])),
        "last_run_dates": json_dict(row["last_run_dates_json"]),
        "tags": normalize_tags(json_list(row["tags_json"])),
        "trigger_source": str(row["trigger_source"] or ""),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def replace_item_row(conn: sqlite3.Connection, item: dict) -> None:
    conn.execute(
        """
        INSERT INTO watchlist_items (
            ticker, pipeline, enabled, schedule_slots_json,
            last_run_dates_json, tags_json, trigger_source, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, pipeline) DO UPDATE SET
            enabled = excluded.enabled,
            schedule_slots_json = excluded.schedule_slots_json,
            last_run_dates_json = excluded.last_run_dates_json,
            tags_json = excluded.tags_json,
            trigger_source = excluded.trigger_source,
            created_at = excluded.created_at,
            updated_at = excluded.updated_at
        """,
        (
            item["ticker"],
            item["pipeline"],
            1 if item.get("enabled") else 0,
            json_dumps(normalize_slots(item.get("schedule_slots"))),
            json_dumps(item.get("last_run_dates") if isinstance(item.get("last_run_dates"), dict) else {}),
            json_dumps(normalize_tags(item.get("tags"))),
            str(item.get("trigger_source") or ""),
            item["created_at"],
            item["updated_at"],
        ),
    )


def select_item(conn: sqlite3.Connection, ticker: str, pipeline: str) -> dict | None:
    row = conn.execute(
        """
        SELECT ticker, pipeline, enabled, schedule_slots_json, last_run_dates_json,
               tags_json, trigger_source, created_at, updated_at
        FROM watchlist_items
        WHERE ticker = ? AND pipeline = ?
        """,
        (ticker, pipeline),
    ).fetchone()
    return item_from_row(row) if row else None
