"""Schema migrations for the report metadata index."""

from __future__ import annotations

from storage.migrations import MigrationRunner, column_names


REPORT_INDEX_MIGRATION_KEY = "report_index"
REPORT_INDEX_SCHEMA_VERSION = 6


def run_report_index_migrations(conn) -> None:
    def migrate_v2(migration_conn):
        columns = column_names(migration_conn, "reports")
        if "data_snapshot_filename" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN data_snapshot_filename TEXT NOT NULL DEFAULT ''")
        if "data_trust_json" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN data_trust_json TEXT NOT NULL DEFAULT '{}'")

    def migrate_v3(migration_conn):
        columns = column_names(migration_conn, "reports")
        if "data_trust_status" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN data_trust_status TEXT NOT NULL DEFAULT 'unknown'")

    def migrate_v4(migration_conn):
        columns = column_names(migration_conn, "reports")
        if "analysis_text_stale" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN analysis_text_stale INTEGER NOT NULL DEFAULT 0")
        if "analysis_text_stale_message" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN analysis_text_stale_message TEXT NOT NULL DEFAULT ''")

    def migrate_v5(migration_conn):
        columns = column_names(migration_conn, "reports")
        if "data_snapshot_hash" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN data_snapshot_hash TEXT NOT NULL DEFAULT ''")

    def migrate_v6(migration_conn):
        columns = column_names(migration_conn, "reports")
        for column in ("html_hash", "markdown_hash", "data_file_hash"):
            if column not in columns:
                migration_conn.execute(f"ALTER TABLE reports ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")

    MigrationRunner(conn, REPORT_INDEX_MIGRATION_KEY).run(
        REPORT_INDEX_SCHEMA_VERSION,
        {1: lambda _conn: None, 2: migrate_v2, 3: migrate_v3, 4: migrate_v4, 5: migrate_v5, 6: migrate_v6},
    )
