"""Provider SLA SQLite schema and migrations."""

from __future__ import annotations

import sqlite3

from storage.migrations import MigrationRunner


PROVIDER_SLA_SCHEMA_VERSION = 3


def init_provider_sla_schema(conn: sqlite3.Connection) -> None:
    MigrationRunner(conn, "provider_sla").run(
        PROVIDER_SLA_SCHEMA_VERSION,
        {1: _migrate_v1, 2: _migrate_v2, 3: _migrate_v3},
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_sla_source_provider ON provider_sla_stats(source, provider)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_sla_events_lookup ON provider_sla_events(source, provider, created_at)")


def _migrate_v1(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_sla_stats (
            source TEXT NOT NULL,
            provider TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            unavailable_count INTEGER NOT NULL DEFAULT 0,
            skipped_fresh_cache_count INTEGER NOT NULL DEFAULT 0,
            total_duration_ms INTEGER NOT NULL DEFAULT 0,
            total_records INTEGER NOT NULL DEFAULT 0,
            last_status TEXT,
            last_message TEXT,
            last_at REAL NOT NULL,
            PRIMARY KEY (source, provider)
        )
        """
    )


def _migrate_v2(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_sla_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            record_count INTEGER NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        )
        """
    )


def _migrate_v3(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(provider_sla_stats)").fetchall()}
    if "not_configured_count" not in columns:
        conn.execute("ALTER TABLE provider_sla_stats ADD COLUMN not_configured_count INTEGER NOT NULL DEFAULT 0")
    if "degraded_enrichment_count" not in columns:
        conn.execute("ALTER TABLE provider_sla_stats ADD COLUMN degraded_enrichment_count INTEGER NOT NULL DEFAULT 0")
