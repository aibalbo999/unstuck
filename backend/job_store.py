"""Persistent job/event store for analysis task progress."""

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from config import ANALYSIS_JOB_STALE_SECONDS, TASK_DB_PATH


_JOB_LOCK = threading.Lock()


def _connect():
    path = Path(TASK_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
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
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(analysis_jobs)").fetchall()
    }
    if "pipeline_id" not in columns:
        conn.execute("ALTER TABLE analysis_jobs ADD COLUMN pipeline_id TEXT NOT NULL DEFAULT 'v1'")
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_jobs_ticker_status ON analysis_jobs(ticker, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_jobs_ticker_pipeline_status ON analysis_jobs(ticker, pipeline_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_events_job_id_id ON analysis_events(job_id, id)")
    return conn


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


def append_event(job_id: str, payload: dict) -> None:
    now = time.time()
    with _JOB_LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO analysis_events (job_id, payload, created_at) VALUES (?, ?, ?)",
            (job_id, json.dumps(payload, ensure_ascii=False), now),
        )
        conn.execute(
            "UPDATE analysis_jobs SET updated_at = ? WHERE job_id = ? AND status IN ('queued', 'running')",
            (now, job_id),
        )
    _print_job_event(job_id, payload)


def _print_job_event(job_id: str, payload: dict) -> None:
    event_type = payload.get("type", "event")
    message = payload.get("message") or payload.get("name") or payload.get("filename") or ""
    if event_type == "progress":
        message = f"Agent {payload.get('current')}/{payload.get('total')} 完成：{payload.get('name', '')}"
    elif event_type == "done":
        message = f"報告生成完成：{payload.get('filename', '')}"
    elif event_type == "error":
        message = f"錯誤：{message}"

    detail = payload.get("detail")
    line = f"[job {job_id[:8]}] {event_type}: {message}"
    if detail:
        line += f" | {detail}"
    print(line[:500], flush=True)


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
