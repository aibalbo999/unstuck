"""Trigger configuration and event persistence for watchlist radar."""

from __future__ import annotations

import json
from datetime import datetime

from pipeline_modes import normalize_pipeline_run_id
import watchlist_store


def _ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist_item_triggers (
            ticker TEXT NOT NULL,
            pipeline TEXT NOT NULL,
            triggers_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (ticker, pipeline)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist_trigger_events (
            ticker TEXT NOT NULL,
            pipeline TEXT NOT NULL,
            trigger_key TEXT NOT NULL,
            evaluation_date TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            matched INTEGER NOT NULL,
            pipeline_selected TEXT NOT NULL,
            message TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            job_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            PRIMARY KEY (ticker, pipeline, trigger_key, evaluation_date)
        )
        """
    )


def _normalize_ticker(ticker: str) -> str:
    return str(ticker or "").strip().upper()


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def set_item_triggers(ticker: str, pipeline: str, triggers: list | None) -> None:
    ticker = _normalize_ticker(ticker)
    pipeline = normalize_pipeline_run_id(pipeline or "v1")
    trigger_list = triggers if isinstance(triggers, list) else []
    with watchlist_store._connect() as conn:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO watchlist_item_triggers (ticker, pipeline, triggers_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker, pipeline) DO UPDATE SET
                triggers_json = excluded.triggers_json,
                updated_at = excluded.updated_at
            """,
            (ticker, pipeline, _json(trigger_list), watchlist_store._now_iso()),
        )


def delete_item_triggers(ticker: str, pipeline: str = "all") -> None:
    ticker = _normalize_ticker(ticker)
    with watchlist_store._connect() as conn:
        _ensure_schema(conn)
        if str(pipeline or "all").lower() == "all":
            conn.execute("DELETE FROM watchlist_item_triggers WHERE ticker = ?", (ticker,))
        else:
            conn.execute(
                "DELETE FROM watchlist_item_triggers WHERE ticker = ? AND pipeline = ?",
                (ticker, normalize_pipeline_run_id(pipeline)),
            )


def triggers_for_items(items: list[dict]) -> dict[tuple[str, str], list]:
    if not items:
        return {}
    with watchlist_store._connect() as conn:
        _ensure_schema(conn)
        rows = conn.execute("SELECT ticker, pipeline, triggers_json FROM watchlist_item_triggers").fetchall()
    result = {}
    for row in rows:
        try:
            triggers = json.loads(row["triggers_json"] or "[]")
        except json.JSONDecodeError:
            triggers = []
        result[(row["ticker"], row["pipeline"])] = triggers if isinstance(triggers, list) else []
    return result


def record_trigger_event(event: dict) -> dict:
    ticker = _normalize_ticker(event.get("ticker"))
    pipeline = normalize_pipeline_run_id(event.get("pipeline") or "v1")
    trigger_key = str(event.get("trigger_key") or event.get("trigger_type") or "").strip()
    evaluation_date = str(event.get("evaluation_date") or datetime.now(watchlist_store.TAIPEI).date().isoformat())
    values = (
        ticker,
        pipeline,
        trigger_key,
        evaluation_date,
        str(event.get("trigger_type") or trigger_key),
        1 if event.get("matched") else 0,
        normalize_pipeline_run_id(event.get("pipeline_selected") or pipeline),
        str(event.get("message") or "")[:240],
        _json(event.get("metrics") if isinstance(event.get("metrics"), dict) else {}),
        str(event.get("job_id") or ""),
        watchlist_store._now_iso(),
    )
    with watchlist_store._connect() as conn:
        _ensure_schema(conn)
        existing = conn.execute(
            """
            SELECT matched FROM watchlist_trigger_events
            WHERE ticker = ? AND pipeline = ? AND trigger_key = ? AND evaluation_date = ?
            """,
            (ticker, pipeline, trigger_key, evaluation_date),
        ).fetchone()
        if existing:
            if not bool(existing["matched"]) and event.get("matched"):
                conn.execute(
                    """
                    UPDATE watchlist_trigger_events
                    SET matched = 1, pipeline_selected = ?, message = ?,
                        metrics_json = ?, job_id = ?, created_at = ?
                    WHERE ticker = ? AND pipeline = ? AND trigger_key = ? AND evaluation_date = ?
                    """,
                    (values[6], values[7], values[8], values[9], values[10], ticker, pipeline, trigger_key, evaluation_date),
                )
                return {"inserted": True, "event": event}
            return {"inserted": False, "event": event}
        conn.execute(
            """
            INSERT INTO watchlist_trigger_events (
                ticker, pipeline, trigger_key, evaluation_date, trigger_type,
                matched, pipeline_selected, message, metrics_json, job_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
    return {"inserted": True, "event": event}


def latest_event_for_item(ticker: str, pipeline: str) -> dict:
    with watchlist_store._connect() as conn:
        _ensure_schema(conn)
        row = conn.execute(
            """
            SELECT * FROM watchlist_trigger_events
            WHERE ticker = ? AND pipeline = ?
            ORDER BY evaluation_date DESC, created_at DESC LIMIT 1
            """,
            (_normalize_ticker(ticker), normalize_pipeline_run_id(pipeline or "v1")),
        ).fetchone()
    return _row_to_event(row) if row else {}


def latest_events_for_items(items: list[dict]) -> dict[tuple[str, str], dict]:
    return {
        (_normalize_ticker(item.get("ticker")), normalize_pipeline_run_id(item.get("pipeline") or "v1")):
        latest_event_for_item(item.get("ticker"), item.get("pipeline") or "v1")
        for item in items
    }


def _row_to_event(row) -> dict:
    try:
        metrics = json.loads(row["metrics_json"] or "{}")
    except json.JSONDecodeError:
        metrics = {}
    return {
        "ticker": row["ticker"],
        "pipeline": row["pipeline"],
        "trigger_key": row["trigger_key"],
        "evaluation_date": row["evaluation_date"],
        "trigger_type": row["trigger_type"],
        "matched": bool(row["matched"]),
        "pipeline_selected": row["pipeline_selected"],
        "message": row["message"],
        "metrics": metrics,
        "job_id": row["job_id"],
        "created_at": row["created_at"],
    }
