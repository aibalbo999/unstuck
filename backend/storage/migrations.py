"""Shared SQLite schema migration runner."""

from __future__ import annotations

import sqlite3
import time
from typing import Callable


Migration = Callable[[sqlite3.Connection], None]


class MigrationRunner:
    def __init__(self, conn: sqlite3.Connection, component: str):
        self.conn = conn
        self.component = component
        self.ensure_table()

    def ensure_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                component TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

    def current_version(self) -> int:
        row = self.conn.execute(
            "SELECT version FROM schema_migrations WHERE component = ?",
            (self.component,),
        ).fetchone()
        if row is None:
            return 0
        return int(row["version"] if hasattr(row, "keys") else row[0])

    def set_version(self, version: int) -> None:
        self.conn.execute(
            """
            INSERT INTO schema_migrations (component, version, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(component) DO UPDATE SET
                version = excluded.version,
                updated_at = excluded.updated_at
            """,
            (self.component, int(version), time.time()),
        )

    def run(self, target_version: int, migrations: dict[int, Migration]) -> int:
        version = self.current_version()
        for next_version in range(version + 1, target_version + 1):
            migration = migrations.get(next_version)
            if migration is not None:
                migration(self.conn)
            self.set_version(next_version)
        if version > target_version:
            self.set_version(target_version)
        return self.current_version()


def column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
