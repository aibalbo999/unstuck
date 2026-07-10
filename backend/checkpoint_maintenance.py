"""Maintenance helpers for pruning terminal LangGraph checkpoints."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from security_sanitizer import sanitize_error_message


TERMINAL_JOB_STATUSES = {"done", "error", "cancelled"}
CHECKPOINT_CLEANUP_BATCH_SIZE = 200


def cleanup_terminal_checkpoints(
    *,
    checkpoint_db_path: str,
    task_db_path: str,
    write: bool = False,
) -> dict:
    checkpoint_path = Path(checkpoint_db_path).expanduser()
    task_path = Path(task_db_path).expanduser()
    result = _empty_result(checkpoint_path, task_path, write=write)
    if not checkpoint_path.is_file() or not task_path.is_file():
        result["missing_paths"] = [
            str(path) for path in (checkpoint_path, task_path) if not path.is_file()
        ]
        return result

    try:
        with sqlite3.connect(task_path) as task_conn, sqlite3.connect(checkpoint_path) as checkpoint_conn:
            schema = _schema_status(task_conn, checkpoint_conn)
            result["missing_schema"] = schema["missing"]
            if not schema["ready"]:
                return result

            terminal_jobs, active_jobs = _load_job_sets(task_conn)
            thread_ids = _load_checkpoint_threads(checkpoint_conn)
            candidate_threads: list[str] = []
            active_threads: list[str] = []
            unmatched_threads: list[str] = []
            for thread_id in thread_ids:
                job_id = _job_id_from_thread_id(thread_id)
                if job_id in terminal_jobs:
                    candidate_threads.append(thread_id)
                elif job_id in active_jobs:
                    active_threads.append(thread_id)
                else:
                    unmatched_threads.append(thread_id)

            candidate_checkpoint_rows = _count_rows(
                checkpoint_conn,
                "checkpoints",
                candidate_threads,
            )
            candidate_write_rows = _count_rows(checkpoint_conn, "writes", candidate_threads)
            estimated_bytes = _estimated_candidate_bytes(checkpoint_conn, candidate_threads)
            result.update(
                {
                    "schema_ready": True,
                    "terminal_job_count": len(terminal_jobs),
                    "active_job_count": len(active_jobs),
                    "total_thread_count": len(thread_ids),
                    "candidate_thread_count": len(candidate_threads),
                    "active_thread_count": len(active_threads),
                    "unmatched_thread_count": len(unmatched_threads),
                    "candidate_checkpoint_rows": candidate_checkpoint_rows,
                    "candidate_write_rows": candidate_write_rows,
                    "estimated_bytes": estimated_bytes,
                    "candidate_threads": candidate_threads,
                }
            )
            if write and candidate_threads:
                deleted = _delete_candidate_threads(checkpoint_conn, candidate_threads)
                result.update(deleted)
            return result
    except sqlite3.Error as exc:
        result["schema_ready"] = False
        result["error"] = sanitize_error_message(exc)
        return result


def _empty_result(checkpoint_path: Path, task_path: Path, *, write: bool) -> dict:
    return {
        "dry_run": not write,
        "schema_ready": False,
        "checkpoint_db_path": str(checkpoint_path),
        "task_db_path": str(task_path),
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
        "batch_size": CHECKPOINT_CLEANUP_BATCH_SIZE,
        "batches": 0,
        "candidate_threads": [],
    }


def _schema_status(task_conn: sqlite3.Connection, checkpoint_conn: sqlite3.Connection) -> dict:
    missing: list[str] = []
    if not {"job_id", "status"}.issubset(_table_columns(task_conn, "analysis_jobs")):
        missing.append("task.analysis_jobs(job_id,status)")
    if "thread_id" not in _table_columns(checkpoint_conn, "checkpoints"):
        missing.append("checkpoint.checkpoints(thread_id)")
    if "thread_id" not in _table_columns(checkpoint_conn, "writes"):
        missing.append("checkpoint.writes(thread_id)")
    return {"ready": not missing, "missing": missing}


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _load_job_sets(task_conn: sqlite3.Connection) -> tuple[set[str], set[str]]:
    terminal_jobs: set[str] = set()
    active_jobs: set[str] = set()
    for job_id, status in task_conn.execute("SELECT job_id, status FROM analysis_jobs"):
        if job_id is None:
            continue
        normalized_status = str(status or "").strip().lower()
        if normalized_status in TERMINAL_JOB_STATUSES:
            terminal_jobs.add(str(job_id))
        else:
            active_jobs.add(str(job_id))
    return terminal_jobs, active_jobs


def _load_checkpoint_threads(checkpoint_conn: sqlite3.Connection) -> list[str]:
    rows = checkpoint_conn.execute(
        """
        SELECT thread_id FROM checkpoints
        UNION
        SELECT thread_id FROM writes
        ORDER BY thread_id
        """
    ).fetchall()
    return [str(row[0]) for row in rows if row[0] is not None]


def _job_id_from_thread_id(thread_id: str) -> str:
    return str(thread_id).split(":", 1)[0]


def _count_rows(conn: sqlite3.Connection, table_name: str, thread_ids: list[str]) -> int:
    return sum(
        int(
            conn.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE thread_id IN ({_placeholders(batch)})",
                batch,
            ).fetchone()[0]
            or 0
        )
        for batch in _batches(thread_ids, CHECKPOINT_CLEANUP_BATCH_SIZE)
    )


def _estimated_candidate_bytes(conn: sqlite3.Connection, thread_ids: list[str]) -> int:
    total = 0
    for batch in _batches(thread_ids, CHECKPOINT_CLEANUP_BATCH_SIZE):
        placeholders = _placeholders(batch)
        checkpoint_bytes = conn.execute(
            f"""
            SELECT COALESCE(SUM(
                COALESCE(LENGTH(checkpoint), 0) + COALESCE(LENGTH(metadata), 0)
            ), 0)
            FROM checkpoints
            WHERE thread_id IN ({placeholders})
            """,
            batch,
        ).fetchone()[0]
        write_bytes = conn.execute(
            f"""
            SELECT COALESCE(SUM(COALESCE(LENGTH(value), 0)), 0)
            FROM writes
            WHERE thread_id IN ({placeholders})
            """,
            batch,
        ).fetchone()[0]
        total += int(checkpoint_bytes or 0) + int(write_bytes or 0)
    return total


def _delete_candidate_threads(conn: sqlite3.Connection, thread_ids: list[str]) -> dict:
    deleted_writes = 0
    deleted_checkpoints = 0
    batches = list(_batches(thread_ids, CHECKPOINT_CLEANUP_BATCH_SIZE))
    for batch in batches:
        placeholders = _placeholders(batch)
        with conn:
            deleted_writes += conn.execute(
                f"DELETE FROM writes WHERE thread_id IN ({placeholders})",
                batch,
            ).rowcount
            deleted_checkpoints += conn.execute(
                f"DELETE FROM checkpoints WHERE thread_id IN ({placeholders})",
                batch,
            ).rowcount
    return {
        "deleted_write_rows": deleted_writes,
        "deleted_checkpoint_rows": deleted_checkpoints,
        "batches": len(batches),
    }


def _batches(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _placeholders(values: list[str]) -> str:
    return ",".join("?" for _ in values)
