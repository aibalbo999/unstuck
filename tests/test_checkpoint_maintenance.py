import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import checkpoint_maintenance  # noqa: E402
import maintenance  # noqa: E402


def _create_task_db(path: Path, jobs: list[tuple[str, str]]) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE analysis_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO analysis_jobs (job_id, status) VALUES (?, ?)",
            jobs,
        )


def _create_checkpoint_db(path: Path, thread_ids: list[str]) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                type TEXT,
                checkpoint BLOB,
                metadata BLOB,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                type TEXT,
                value BLOB,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            )
            """
        )
        for thread_id in thread_ids:
            conn.execute(
                """
                INSERT INTO checkpoints (
                    thread_id, checkpoint_ns, checkpoint_id, type, checkpoint, metadata
                )
                VALUES (?, '', 'checkpoint-1', 'json', ?, ?)
                """,
                (thread_id, b"checkpoint", b"metadata"),
            )
            conn.execute(
                """
                INSERT INTO writes (
                    thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value
                )
                VALUES (?, '', 'checkpoint-1', 'task-1', 0, 'state', 'json', ?)
                """,
                (thread_id, b"write"),
            )


def _remaining_threads(path: Path) -> tuple[list[str], list[str]]:
    with sqlite3.connect(path) as conn:
        checkpoints = [
            row[0]
            for row in conn.execute("SELECT thread_id FROM checkpoints ORDER BY thread_id")
        ]
        writes = [row[0] for row in conn.execute("SELECT thread_id FROM writes ORDER BY thread_id")]
    return checkpoints, writes


def test_cleanup_terminal_checkpoints_dry_run_preserves_rows(tmp_path):
    task_db = tmp_path / "task.sqlite3"
    checkpoint_db = tmp_path / "checkpoint.sqlite3"
    _create_task_db(
        task_db,
        [
            ("done-job", "done"),
            ("error-job", "error"),
            ("running-job", "running"),
        ],
    )
    _create_checkpoint_db(
        checkpoint_db,
        ["done-job:v4", "error-job", "running-job:v4", "missing-job:v4"],
    )

    result = checkpoint_maintenance.cleanup_terminal_checkpoints(
        checkpoint_db_path=str(checkpoint_db),
        task_db_path=str(task_db),
        write=False,
    )

    assert result["dry_run"] is True
    assert result["schema_ready"] is True
    assert result["candidate_thread_count"] == 2
    assert result["active_thread_count"] == 1
    assert result["unmatched_thread_count"] == 1
    assert result["candidate_checkpoint_rows"] == 2
    assert result["candidate_write_rows"] == 2
    assert result["estimated_bytes"] > 0
    assert result["deleted_checkpoint_rows"] == 0
    assert result["deleted_write_rows"] == 0
    assert _remaining_threads(checkpoint_db) == (
        ["done-job:v4", "error-job", "missing-job:v4", "running-job:v4"],
        ["done-job:v4", "error-job", "missing-job:v4", "running-job:v4"],
    )


def test_cleanup_terminal_checkpoints_write_deletes_terminal_threads_only(tmp_path):
    task_db = tmp_path / "task.sqlite3"
    checkpoint_db = tmp_path / "checkpoint.sqlite3"
    _create_task_db(
        task_db,
        [
            ("cancelled-job", "cancelled"),
            ("done-job", "done"),
            ("queued-job", "queued"),
        ],
    )
    _create_checkpoint_db(
        checkpoint_db,
        ["cancelled-job:v4", "done-job:v4", "queued-job:v4", "unknown-job:v4"],
    )

    result = checkpoint_maintenance.cleanup_terminal_checkpoints(
        checkpoint_db_path=str(checkpoint_db),
        task_db_path=str(task_db),
        write=True,
    )

    assert result["dry_run"] is False
    assert result["schema_ready"] is True
    assert result["candidate_thread_count"] == 2
    assert result["deleted_write_rows"] == 2
    assert result["deleted_checkpoint_rows"] == 2
    assert _remaining_threads(checkpoint_db) == (
        ["queued-job:v4", "unknown-job:v4"],
        ["queued-job:v4", "unknown-job:v4"],
    )


def test_cleanup_terminal_checkpoints_missing_schema_is_safe(tmp_path):
    task_db = tmp_path / "task.sqlite3"
    checkpoint_db = tmp_path / "checkpoint.sqlite3"
    task_db.touch()
    checkpoint_db.touch()

    result = checkpoint_maintenance.cleanup_terminal_checkpoints(
        checkpoint_db_path=str(checkpoint_db),
        task_db_path=str(task_db),
        write=True,
    )

    assert result["schema_ready"] is False
    assert result["candidate_thread_count"] == 0
    assert result["deleted_write_rows"] == 0
    assert result["deleted_checkpoint_rows"] == 0


def test_cleanup_terminal_checkpoints_writes_in_batches(tmp_path):
    task_db = tmp_path / "task.sqlite3"
    checkpoint_db = tmp_path / "checkpoint.sqlite3"
    jobs = [(f"job-{index}", "done") for index in range(205)]
    thread_ids = [f"job-{index}:v4" for index in range(205)]
    _create_task_db(task_db, jobs)
    _create_checkpoint_db(checkpoint_db, thread_ids)

    result = checkpoint_maintenance.cleanup_terminal_checkpoints(
        checkpoint_db_path=str(checkpoint_db),
        task_db_path=str(task_db),
        write=True,
    )

    assert result["candidate_thread_count"] == 205
    assert result["deleted_write_rows"] == 205
    assert result["deleted_checkpoint_rows"] == 205
    assert result["batch_size"] == 200
    assert result["batches"] == 2
    assert _remaining_threads(checkpoint_db) == ([], [])


def test_cleanup_terminal_checkpoints_cli_outputs_json(tmp_path, monkeypatch, capsys):
    task_db = tmp_path / "task.sqlite3"
    checkpoint_db = tmp_path / "checkpoint.sqlite3"
    _create_task_db(task_db, [("done-job", "done")])
    _create_checkpoint_db(checkpoint_db, ["done-job:v4"])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "maintenance.py",
            "cleanup-terminal-checkpoints",
            "--checkpoint-db-path",
            str(checkpoint_db),
            "--task-db-path",
            str(task_db),
            "--write",
        ],
    )

    assert maintenance.main() == 0
    result = json.loads(capsys.readouterr().out)

    assert result["deleted_write_rows"] == 1
    assert result["deleted_checkpoint_rows"] == 1
