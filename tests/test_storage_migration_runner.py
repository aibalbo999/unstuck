import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from storage.migrations import MigrationRunner, column_names  # noqa: E402


def test_migration_runner_is_idempotent_and_records_version(tmp_path):
    db_path = tmp_path / "migrations.db"
    calls = []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY)")

        def migrate_v1(migration_conn):
            calls.append("v1")
            migration_conn.execute("ALTER TABLE demo ADD COLUMN name TEXT NOT NULL DEFAULT ''")

        runner = MigrationRunner(conn, "demo")
        assert runner.run(1, {1: migrate_v1}) == 1
        assert runner.run(1, {1: migrate_v1}) == 1

        assert calls == ["v1"]
        assert "name" in column_names(conn, "demo")
        row = conn.execute("SELECT version FROM schema_migrations WHERE component = 'demo'").fetchone()
        assert row["version"] == 1
