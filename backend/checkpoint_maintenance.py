"""Safe cleanup helpers for terminal LangGraph checkpoint threads."""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

from config import LANGGRAPH_CHECKPOINT_PATH, TASK_DB_PATH
from security_sanitizer import sanitize_error_message


TERMINAL_STATUSES = ("done", "error", "cancelled")
DEFAULT_BATCH_SIZE = 200


def cleanup_terminal_checkpoints(
    *,
    checkpoint_db_path: str | None = None,
    task_db_path: str | None = None,
    write: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    checkpoint_path = Path(checkpoint_db_path or LANGGRAPH_CHECKPOINT_PATH).expanduser()
    task_path = Path(task_db_path or TASK_DB_PATH).expanduser()
    effective_batch_size = min(DEFAULT_BATCH_SIZE, max(1, int(batch_size or DEFAULT_BATCH_SIZE)))
    base = _base_result(
        checkpoint_path=checkpoint_path,
        task_path=task_path,
        write=write,
        batch_size=effective_batch_size,
    )
    if not checkpoint_path.is_file() or not task_path.is_file():
        base["missing_paths"] = [
            str(path) for path in (checkpoint_path, task_path) if not path.is_file()
        ]
        return base

    try:
        with sqlite3.connect(checkpoint_path) as checkpoint_conn, sqlite3.connect(task_path) as task_conn:
            schema = _schema_status(checkpoint_conn, task_conn)
            base["missing_schema"] = schema["missing"]
            if not schema["ready"]:
                return base

            terminal_jobs, active_jobs = _load_job_sets(task_conn)
            thread_ids = _checkpoint_thread_ids(checkpoint_conn)
            candidate_threads, active_threads, unmatched_threads = _classify_threads(
                thread_ids,
                terminal_jobs=terminal_jobs,
                active_jobs=active_jobs,
            )
            candidate_checkpoint_rows = _row_count(checkpoint_conn, "checkpoints", candidate_threads)
            candidate_write_rows = _row_count(checkpoint_conn, "writes", candidate_threads)
            result = {
                **base,
                "schema_ready": True,
                "terminal_job_count": len(terminal_jobs),
                "active_job_count": len(active_jobs),
                "total_thread_count": len(thread_ids),
                "candidate_thread_count": len(candidate_threads),
                "active_thread_count": len(active_threads),
                "unmatched_thread_count": len(unmatched_threads),
                "candidate_checkpoint_rows": candidate_checkpoint_rows,
                "candidate_write_rows": candidate_write_rows,
                "estimated_bytes": _estimated_payload_bytes(checkpoint_conn, candidate_threads),
                "batches": _batch_count(candidate_threads, effective_batch_size),
                "candidate_threads": candidate_threads,
            }
            if not write or not candidate_threads:
                return result

            deleted_writes = 0
            deleted_checkpoints = 0
            for batch in _chunks(candidate_threads, effective_batch_size):
                with checkpoint_conn:
                    deleted_writes += _delete_rows(checkpoint_conn, "writes", batch)
                    deleted_checkpoints += _delete_rows(checkpoint_conn, "checkpoints", batch)
            return {
                **result,
                "deleted_write_rows": deleted_writes,
                "deleted_checkpoint_rows": deleted_checkpoints,
                "dry_run": False,
            }
    except sqlite3.Error as exc:
        return {**base, "error": sanitize_error_message(exc)}


def _base_result(
    *,
    checkpoint_path: Path,
    task_path: Path,
    write: bool,
    batch_size: int,
) -> dict:
    return {
        "dry_run": not write,
        "checkpoint_db_path": str(checkpoint_path),
        "task_db_path": str(task_path),
        "checkpoint_db_exists": checkpoint_path.exists(),
        "task_db_exists": task_path.exists(),
        "schema_ready": False,
        "missing_paths": [],
        "missing_schema": [],
        "terminal_job_count": 0,
        "active_job_count": 0,
        "total_thread_count": 0,
        "candidate_thread_count": 0,
        "active_thread_count": 0,
        "unmatched_thread_count": 0,
        "candidate_checkpoint_rows": 0,
        "candidate_write_rows": 0,
        "estimated_bytes": 0,
        "deleted_checkpoint_rows": 0,
        "deleted_write_rows": 0,
        "batch_size": batch_size,
        "batches": 0,
        "candidate_threads": [],
    }


def _schema_status(checkpoint_conn: sqlite3.Connection, task_conn: sqlite3.Connection) -> dict:
    missing: list[str] = []
    if not {"job_id", "status"}.issubset(_table_columns(task_conn, "analysis_jobs")):
        missing.append("task.analysis_jobs(job_id,status)")
    if "thread_id" not in _table_columns(checkpoint_conn, "checkpoints"):
        missing.append("checkpoint.checkpoints(thread_id)")
    if "thread_id" not in _table_columns(checkpoint_conn, "writes"):
        missing.append("checkpoint.writes(thread_id)")
    return {"ready": not missing, "missing": missing}


def _checkpoint_thread_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT thread_id FROM checkpoints
        UNION
        SELECT thread_id FROM writes
        ORDER BY thread_id
        """
    ).fetchall()
    return [str(row[0]) for row in rows if row[0] is not None]


def _load_job_sets(task_conn: sqlite3.Connection) -> tuple[set[str], set[str]]:
    terminal_jobs: set[str] = set()
    active_jobs: set[str] = set()
    for job_id, status in task_conn.execute("SELECT job_id, status FROM analysis_jobs"):
        if job_id is None:
            continue
        normalized_status = str(status or "").strip().lower()
        if normalized_status in TERMINAL_STATUSES:
            terminal_jobs.add(str(job_id))
        else:
            active_jobs.add(str(job_id))
    return terminal_jobs, active_jobs


def _classify_threads(
    thread_ids: list[str],
    *,
    terminal_jobs: set[str],
    active_jobs: set[str],
) -> tuple[list[str], list[str], list[str]]:
    candidate_threads: list[str] = []
    active_threads: list[str] = []
    unmatched_threads: list[str] = []
    for thread_id in thread_ids:
        job_id = _job_id_from_thread(thread_id)
        if job_id in terminal_jobs:
            candidate_threads.append(thread_id)
        elif job_id in active_jobs:
            active_threads.append(thread_id)
        else:
            unmatched_threads.append(thread_id)
    return candidate_threads, active_threads, unmatched_threads


def _job_id_from_thread(thread_id: str) -> str:
    return thread_id.split(":", 1)[0]


def _row_count(conn: sqlite3.Connection, table_name: str, thread_ids: list[str]) -> int:
    if not thread_ids:
        return 0
    return sum(
        int(
            conn.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE thread_id IN ({_placeholders(batch)})",
                batch,
            ).fetchone()[0]
            or 0
        )
        for batch in _chunks(thread_ids, DEFAULT_BATCH_SIZE)
    )


def _estimated_payload_bytes(conn: sqlite3.Connection, thread_ids: list[str]) -> int:
    if not thread_ids:
        return 0
    total = 0
    for batch in _chunks(thread_ids, DEFAULT_BATCH_SIZE):
        checkpoint_bytes = int(
            conn.execute(
                f"""
                SELECT COALESCE(SUM(
                    COALESCE(length(checkpoint), 0) + COALESCE(length(metadata), 0)
                ), 0)
                FROM checkpoints
                WHERE thread_id IN ({_placeholders(batch)})
                """,
                batch,
            ).fetchone()[0]
            or 0
        )
        write_bytes = int(
            conn.execute(
                f"""
                SELECT COALESCE(SUM(COALESCE(length(value), 0)), 0)
                FROM writes
                WHERE thread_id IN ({_placeholders(batch)})
                """,
                batch,
            ).fetchone()[0]
            or 0
        )
        total += checkpoint_bytes + write_bytes
    return total


def _delete_rows(conn: sqlite3.Connection, table_name: str, thread_ids: list[str]) -> int:
    if not thread_ids:
        return 0
    cursor = conn.execute(
        f"DELETE FROM {table_name} WHERE thread_id IN ({_placeholders(thread_ids)})",
        thread_ids,
    )
    return int(cursor.rowcount or 0)


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _batch_count(values: list[str], batch_size: int) -> int:
    if not values:
        return 0
    return int(math.ceil(len(values) / batch_size))


def _chunks(values: list[str], size: int):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _placeholders(values) -> str:
    return ", ".join("?" for _ in values)
