"""SQLite schema and migrations for analysis job storage."""

from __future__ import annotations

import sqlite3

from storage.migrations import MigrationRunner, column_names


JOB_STORE_SCHEMA_VERSION = 8
ACTIVE_JOB_STATUSES_FOR_INDEX = ("queued", "running", "waiting_retry")


def init_job_store_schema(conn: sqlite3.Connection):
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

    def migrate_v5(migration_conn):
        columns = column_names(migration_conn, "analysis_jobs")
        if "worker_instance_id" not in columns:
            migration_conn.execute("ALTER TABLE analysis_jobs ADD COLUMN worker_instance_id TEXT")
        if "claimed_at" not in columns:
            migration_conn.execute("ALTER TABLE analysis_jobs ADD COLUMN claimed_at REAL")

    def migrate_v6(migration_conn):
        columns = column_names(migration_conn, "analysis_jobs")
        if "data_snapshot" not in columns:
            migration_conn.execute("ALTER TABLE analysis_jobs ADD COLUMN data_snapshot TEXT")
        if "metrics_snapshot" not in columns:
            migration_conn.execute("ALTER TABLE analysis_jobs ADD COLUMN metrics_snapshot TEXT")

    def migrate_v7(migration_conn):
        columns = column_names(migration_conn, "analysis_jobs")
        if "started_at" not in columns:
            migration_conn.execute("ALTER TABLE analysis_jobs ADD COLUMN started_at REAL")
        if "finished_at" not in columns:
            migration_conn.execute("ALTER TABLE analysis_jobs ADD COLUMN finished_at REAL")
        _cancel_duplicate_active_jobs(migration_conn)

    def migrate_v8(migration_conn):
        migration_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_node_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                pipeline_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                model TEXT,
                started_at REAL NOT NULL,
                finished_at REAL,
                latency_ms INTEGER,
                status TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cache_hit INTEGER NOT NULL DEFAULT 0,
                quality_gate_pass INTEGER,
                error TEXT,
                created_at REAL NOT NULL
            )
            """
        )

    MigrationRunner(conn, "job_store").run(
        JOB_STORE_SCHEMA_VERSION,
        {
            1: lambda _conn: None,
            2: migrate_v2,
            3: migrate_v3,
            4: migrate_v4,
            5: migrate_v5,
            6: migrate_v6,
            7: migrate_v7,
            8: migrate_v8,
        },
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_jobs_ticker_status ON analysis_jobs(ticker, status)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_jobs_ticker_pipeline_status "
        "ON analysis_jobs(ticker, pipeline_id, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status_updated "
        "ON analysis_jobs(status, updated_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_jobs_worker_status "
        "ON analysis_jobs(worker_instance_id, status)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_events_job_id_id ON analysis_events(job_id, id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_events_job_id_created "
        "ON analysis_events(job_id, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_events_type_phase_created "
        "ON analysis_events(event_type, phase, created_at)"
    )
    _cancel_duplicate_active_jobs(conn)
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_jobs_one_active_per_ticker_pipeline
        ON analysis_jobs(ticker, pipeline_id)
        WHERE status IN ('queued', 'running', 'waiting_retry') AND COALESCE(cancel_requested, 0) = 0
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_node_telemetry_job_id "
        "ON analysis_node_telemetry(job_id, id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_node_telemetry_job_node "
        "ON analysis_node_telemetry(job_id, node_name)"
    )


def _cancel_duplicate_active_jobs(conn: sqlite3.Connection) -> None:
    placeholders = ", ".join("?" for _ in ACTIVE_JOB_STATUSES_FOR_INDEX)
    groups = conn.execute(
        f"""
        SELECT ticker, pipeline_id
        FROM analysis_jobs
        WHERE status IN ({placeholders}) AND COALESCE(cancel_requested, 0) = 0
        GROUP BY ticker, pipeline_id
        HAVING COUNT(*) > 1
        """,
        ACTIVE_JOB_STATUSES_FOR_INDEX,
    ).fetchall()
    for group in groups:
        ticker = group["ticker"] if hasattr(group, "keys") else group[0]
        pipeline_id = group["pipeline_id"] if hasattr(group, "keys") else group[1]
        rows = conn.execute(
            f"""
            SELECT job_id
            FROM analysis_jobs
            WHERE ticker = ? AND pipeline_id = ?
              AND status IN ({placeholders})
              AND COALESCE(cancel_requested, 0) = 0
            ORDER BY updated_at DESC, created_at DESC, job_id DESC
            """,
            (ticker, pipeline_id, *ACTIVE_JOB_STATUSES_FOR_INDEX),
        ).fetchall()
        duplicate_ids = [
            row["job_id"] if hasattr(row, "keys") else row[0]
            for row in rows[1:]
        ]
        if duplicate_ids:
            conn.executemany(
                """
                UPDATE analysis_jobs
                SET status = 'cancelled',
                    cancel_requested = 1,
                    cancelled_at = COALESCE(cancelled_at, updated_at),
                    finished_at = COALESCE(finished_at, updated_at),
                    error = COALESCE(error, 'Cancelled by active-job uniqueness migration.')
                WHERE job_id = ?
                """,
                [(job_id,) for job_id in duplicate_ids],
            )
