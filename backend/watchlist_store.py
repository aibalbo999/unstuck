"""SQLite storage for watchlist items."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import CACHE_DB_PATH
from pipeline_modes import normalize_pipeline_run_id
from storage.sqlite_resource import ThreadLocalSqliteResource


TAIPEI = ZoneInfo("Asia/Taipei")
WATCHLIST_PATH = Path(os.getenv("WATCHLIST_PATH", str(Path(CACHE_DB_PATH).parent / "watchlist.json")))
WATCHLIST_DB_PATH = os.getenv("WATCHLIST_DB_PATH")
DEFAULT_SCHEDULES = {
    "pre_market": {"label": "盤前", "time": "08:30"},
    "post_market": {"label": "盤後", "time": "15:30"},
}


def _db_path() -> Path:
    return Path(WATCHLIST_DB_PATH) if WATCHLIST_DB_PATH else Path(WATCHLIST_PATH).with_suffix(".sqlite3")


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist_items (
            ticker TEXT NOT NULL,
            pipeline TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            schedule_slots_json TEXT NOT NULL,
            last_run_dates_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (ticker, pipeline)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


_resource = ThreadLocalSqliteResource(_db_path, init_schema=_init_schema, row_factory=sqlite3.Row)


def reset_watchlist_store_for_tests() -> None:
    _resource.reset()


def _connect() -> sqlite3.Connection:
    return _resource.connect()


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(TAIPEI)).isoformat(timespec="seconds")


def _json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_list(value: str | None) -> list:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _json_dict(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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
        "created_at": item.get("created_at") or _now_iso(),
        "updated_at": item.get("updated_at") or _now_iso(),
    }


def _read_legacy_json_store() -> dict:
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


def _meta_value(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM watchlist_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO watchlist_meta (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def _touch_store(conn: sqlite3.Connection, updated_at: str | None = None) -> str:
    value = updated_at or _now_iso()
    _set_meta(conn, "updated_at", value)
    return value


def _item_from_row(row: sqlite3.Row) -> dict:
    return {
        "ticker": row["ticker"],
        "pipeline": row["pipeline"],
        "enabled": bool(row["enabled"]),
        "schedule_slots": _normalize_slots(_json_list(row["schedule_slots_json"])),
        "last_run_dates": _json_dict(row["last_run_dates_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _replace_item_row(conn: sqlite3.Connection, item: dict) -> None:
    conn.execute(
        """
        INSERT INTO watchlist_items (
            ticker, pipeline, enabled, schedule_slots_json,
            last_run_dates_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, pipeline) DO UPDATE SET
            enabled = excluded.enabled,
            schedule_slots_json = excluded.schedule_slots_json,
            last_run_dates_json = excluded.last_run_dates_json,
            created_at = excluded.created_at,
            updated_at = excluded.updated_at
        """,
        (
            item["ticker"],
            item["pipeline"],
            1 if item.get("enabled") else 0,
            _json_dumps(_normalize_slots(item.get("schedule_slots"))),
            _json_dumps(item.get("last_run_dates") if isinstance(item.get("last_run_dates"), dict) else {}),
            item["created_at"],
            item["updated_at"],
        ),
    )


def _read_store_from_conn(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT ticker, pipeline, enabled, schedule_slots_json, last_run_dates_json, created_at, updated_at
        FROM watchlist_items
        ORDER BY ticker ASC, pipeline ASC
        """
    ).fetchall()
    items = [_item_from_row(row) for row in rows]
    updated_at = _meta_value(conn, "updated_at")
    if updated_at is None and items:
        updated_at = max(item.get("updated_at") or "" for item in items) or None
    return {"items": items, "updated_at": updated_at}


def _ensure_legacy_json_migrated(conn: sqlite3.Connection) -> None:
    migration_key = f"legacy_json_migrated:{WATCHLIST_PATH.resolve(strict=False)}"
    if _meta_value(conn, migration_key):
        return
    has_rows = conn.execute("SELECT 1 FROM watchlist_items LIMIT 1").fetchone()
    if not has_rows:
        legacy = _read_legacy_json_store()
        for item in legacy["items"]:
            if item.get("ticker"):
                _replace_item_row(conn, item)
        if legacy.get("items"):
            _touch_store(conn, legacy.get("updated_at") or _now_iso())
    _set_meta(conn, migration_key, _now_iso())


def _select_item(conn: sqlite3.Connection, ticker: str, pipeline: str) -> dict | None:
    row = conn.execute(
        """
        SELECT ticker, pipeline, enabled, schedule_slots_json, last_run_dates_json, created_at, updated_at
        FROM watchlist_items
        WHERE ticker = ? AND pipeline = ?
        """,
        (ticker, pipeline),
    ).fetchone()
    return _item_from_row(row) if row else None


def list_watchlist() -> dict:
    with _connect() as conn:
        _ensure_legacy_json_migrated(conn)
        store = _read_store_from_conn(conn)
    return {"items": [item for item in store["items"] if item.get("ticker")], "schedules": DEFAULT_SCHEDULES, "updated_at": store.get("updated_at")}


def upsert_watchlist_item(payload: dict) -> dict:
    item = _normalize_item(payload or {})
    if not item["ticker"]:
        raise ValueError("ticker is required")
    now = _now_iso()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_legacy_json_migrated(conn)
        existing = _select_item(conn, item["ticker"], item["pipeline"])
        item["created_at"] = (existing or {}).get("created_at") or now
        item["last_run_dates"] = (existing or {}).get("last_run_dates") or item.get("last_run_dates", {})
        item["updated_at"] = now
        _replace_item_row(conn, item)
        _touch_store(conn, now)
        store = _read_store_from_conn(conn)
    return {"items": store["items"], "schedules": DEFAULT_SCHEDULES, "updated_at": store.get("updated_at")}


def delete_watchlist_item(ticker: str, pipeline: str = "all") -> dict:
    ticker = str(ticker or "").strip().upper()
    pipeline = str(pipeline or "all").strip().lower()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_legacy_json_migrated(conn)
        if pipeline == "all":
            cursor = conn.execute("DELETE FROM watchlist_items WHERE ticker = ?", (ticker,))
        else:
            cursor = conn.execute("DELETE FROM watchlist_items WHERE ticker = ? AND pipeline = ?", (ticker, normalize_pipeline_run_id(pipeline)))
        _touch_store(conn)
        store = _read_store_from_conn(conn)
    return {"success": True, "deleted": cursor.rowcount, "items": store["items"], "schedules": DEFAULT_SCHEDULES, "updated_at": store.get("updated_at")}


def mark_watchlist_run(ticker: str, pipeline: str, slot: str, now: datetime | None = None, run_date: str | None = None) -> None:
    now = now or datetime.now(TAIPEI)
    today = run_date or now.date().isoformat()
    ticker = str(ticker or "").strip().upper()
    pipeline = normalize_pipeline_run_id(pipeline or "v1")
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_legacy_json_migrated(conn)
        item = _select_item(conn, ticker, pipeline)
        if not item:
            return
        item.setdefault("last_run_dates", {})[slot] = today
        item["updated_at"] = _now_iso(now)
        _replace_item_row(conn, item)
        _touch_store(conn, item["updated_at"])
