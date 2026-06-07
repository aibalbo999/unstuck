"""Persistent job/event store for analysis task progress."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid

from config import ANALYSIS_JOB_STALE_SECONDS, TASK_DB_PATH
from runtime_events import emit_log, format_event_log_line
from storage.migrations import MigrationRunner, column_names
from storage.sqlite_resource import ThreadLocalSqliteResource


_JOB_LOCK = threading.Lock()
JOB_STORE_SCHEMA_VERSION = 4


def _init_schema(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_jobs (
            job_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            pipeline_id TEXT NOT NULL DEFAULT 'v1',
            status TEXT NOT NULL,
            filename TEXT,
            error TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )

    def migrate_v2(migration_conn):
        columns = column_names(migration_conn, "analysis_jobs")
        if "pipeline_id" not in columns:
            migration_conn.execute("ALTER TABLE analysis_jobs ADD COLUMN pipeline_id TEXT NOT NULL DEFAULT 'v1'")

    def migrate_v3(migration_conn):
        columns = column_names(migration_conn, "analysis_events")
        if "event_type" not in columns:
            migration_conn.execute("ALTER TABLE analysis_events ADD COLUMN event_type TEXT")
        if "phase" not in columns:
            migration_conn.execute("ALTER TABLE analysis_events ADD COLUMN phase TEXT")
        if "level" not in columns:
            migration_conn.execute("ALTER TABLE analysis_events ADD COLUMN level TEXT")

    def migrate_v4(migration_conn):
        columns = column_names(migration_conn, "analysis_jobs")
        if "cancel_requested" not in columns:
            migration_conn.execute("ALTER TABLE analysis_jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")
        if "cancelled_at" not in columns:
            migration_conn.execute("ALTER TABLE analysis_jobs ADD COLUMN cancelled_at REAL")

    MigrationRunner(conn, "job_store").run(
        JOB_STORE_SCHEMA_VERSION,
        {1: lambda _conn: None, 2: migrate_v2, 3: migrate_v3, 4: migrate_v4},
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_jobs_ticker_status ON analysis_jobs(ticker, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_jobs_ticker_pipeline_status ON analysis_jobs(ticker, pipeline_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_events_job_id_id ON analysis_events(job_id, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_events_type_phase_created ON analysis_events(event_type, phase, created_at)")


_resource = ThreadLocalSqliteResource(lambda: TASK_DB_PATH, init_schema=_init_schema, row_factory=sqlite3.Row)


def _connect():
    return _resource.connect()


def close_job_store() -> None:
    _resource.close_current_thread()


def reset_job_store_for_tests() -> None:
    _resource.reset()


def create_job(ticker: str, pipeline_id: str = "v1") -> str:
    job_id = uuid.uuid4().hex
    now = time.time()
    with _JOB_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_jobs (job_id, ticker, pipeline_id, status, created_at, updated_at)
            VALUES (?, ?, ?, 'queued', ?, ?)
            """,
            (job_id, ticker, pipeline_id, now, now),
        )
    append_event(job_id, {"type": "status", "message": f"已建立 {ticker} 分析任務", "pipeline_id": pipeline_id})
    return job_id


def update_job(job_id: str, status: str, filename: str = None, error: str = None) -> None:
    with _JOB_LOCK, _connect() as conn:
        conn.execute(
            """
            UPDATE analysis_jobs
            SET status = ?, filename = COALESCE(?, filename), error = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (status, filename, error, time.time(), job_id),
        )


def get_job(job_id: str) -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else {}


def find_active_job(ticker: str, pipeline_id: str = "v1") -> dict:
    cutoff = time.time() - ANALYSIS_JOB_STALE_SECONDS
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM analysis_jobs
            WHERE ticker = ? AND pipeline_id = ? AND status IN ('queued', 'running') AND updated_at >= ?
              AND COALESCE(cancel_requested, 0) = 0
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (ticker, pipeline_id, cutoff),
        ).fetchone()
    return dict(row) if row else {}


def mark_incomplete_jobs_abandoned(reason: str) -> int:
    """Mark queued/running local jobs as abandoned after a server restart."""
    now = time.time()
    with _JOB_LOCK, _connect() as conn:
        rows = conn.execute(
            """
            SELECT job_id
            FROM analysis_jobs
            WHERE status IN ('queued', 'running')
            """
        ).fetchall()
        job_ids = [row["job_id"] for row in rows]
        if job_ids:
            conn.executemany(
                """
                UPDATE analysis_jobs
                SET status = 'error', error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                [(reason, now, job_id) for job_id in job_ids],
            )

    for job_id in job_ids:
        append_event(job_id, {"type": "error", "message": reason})

    return len(job_ids)


def request_job_cancel(job_id: str, reason: str = "使用者要求取消分析任務。") -> bool:
    now = time.time()
    with _JOB_LOCK, _connect() as conn:
        row = conn.execute("SELECT status FROM analysis_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return False
        status = row["status"]
        conn.execute(
            """
            UPDATE analysis_jobs
            SET cancel_requested = 1,
                cancelled_at = COALESCE(cancelled_at, ?),
                error = COALESCE(error, ?),
                updated_at = ?
            WHERE job_id = ?
            """,
            (now, reason, now, job_id),
        )
    if status in {"queued", "running"}:
        append_event(job_id, {"type": "status", "phase": "cancelling", "level": "warning", "message": reason})
    return True


def is_job_cancel_requested(job_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT cancel_requested FROM analysis_jobs WHERE job_id = ?", (job_id,)).fetchone()
    return bool(row and row["cancel_requested"])


def append_event(job_id: str, payload: dict) -> None:
    now = time.time()
    event_type = str(payload.get("type") or "event")
    phase = str(payload.get("phase") or "")
    level = str(payload.get("level") or "")
    with _JOB_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_events (job_id, payload, created_at, event_type, phase, level)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, json.dumps(payload, ensure_ascii=False), now, event_type, phase, level),
        )
        conn.execute(
            "UPDATE analysis_jobs SET updated_at = ? WHERE job_id = ? AND status IN ('queued', 'running')",
            (now, job_id),
        )
    _print_job_event(job_id, payload)


def _print_job_event(job_id: str, payload: dict) -> None:
    emit_log(format_event_log_line(job_id, payload, prefix="job"))


def get_events_since(job_id: str, after_id: int = 0) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, payload, created_at
            FROM analysis_events
            WHERE job_id = ? AND id > ?
            ORDER BY id ASC
            """,
            (job_id, after_id),
        ).fetchall()

    events = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {"type": "error", "message": "任務事件解析失敗"}
        events.append({"id": row["id"], "payload": payload, "created_at": row["created_at"]})
    return events


def query_events(
    job_id: str | None = None,
    *,
    event_type: str | None = None,
    phase: str | None = None,
    level: str | None = None,
    limit: int = 100,
) -> list[dict]:
    clauses = []
    params = []
    if job_id:
        clauses.append("job_id = ?")
        params.append(job_id)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if phase:
        clauses.append("phase = ?")
        params.append(phase)
    if level:
        clauses.append("level = ?")
        params.append(level)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    safe_limit = max(1, min(int(limit or 100), 1000))
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, job_id, payload, created_at, event_type, phase, level
            FROM analysis_events
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            (*params, safe_limit),
        ).fetchall()
    results = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {"type": "error", "message": "任務事件解析失敗"}
        results.append({
            "id": row["id"],
            "job_id": row["job_id"],
            "payload": payload,
            "created_at": row["created_at"],
            "event_type": row["event_type"],
            "phase": row["phase"],
            "level": row["level"],
        })
    return results
