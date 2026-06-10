"""SQLite schema and migrations for analysis job storage."""

from __future__ import annotations

import sqlite3

from storage.migrations import MigrationRunner, column_names


JOB_STORE_SCHEMA_VERSION = 5


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

    MigrationRunner(conn, "job_store").run(
        JOB_STORE_SCHEMA_VERSION,
        {1: lambda _conn: None, 2: migrate_v2, 3: migrate_v3, 4: migrate_v4, 5: migrate_v5},
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_jobs_ticker_status ON analysis_jobs(ticker, status)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_jobs_ticker_pipeline_status "
        "ON analysis_jobs(ticker, pipeline_id, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_jobs_worker_status "
        "ON analysis_jobs(worker_instance_id, status)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_events_job_id_id ON analysis_events(job_id, id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_events_type_phase_created "
        "ON analysis_events(event_type, phase, created_at)"
    )
