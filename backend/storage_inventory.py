"""Storage inventory helpers for local maintenance diagnostics."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from config import CACHE_DB_PATH, CACHE_DIR, MARKET_CALENDAR_DIR, OUTPUT_DIR, TASK_DB_PATH


def build_storage_summary(
    *,
    output_dir: Optional[str] = None,
    cache_dir: Optional[str] = None,
    cache_db_path: Optional[str] = None,
    task_db_path: Optional[str] = None,
    market_calendar_dir: Optional[str] = None,
) -> dict:
    output_path = Path(output_dir or OUTPUT_DIR)
    cache_path = Path(cache_dir or CACHE_DIR)
    cache_db = Path(cache_db_path or CACHE_DB_PATH)
    task_db = Path(task_db_path or TASK_DB_PATH)
    calendar_path = Path(market_calendar_dir or MARKET_CALENDAR_DIR)

    return {
        "paths": {
            "output_dir": str(output_path),
            "cache_dir": str(cache_path),
            "cache_db_path": str(cache_db),
            "task_db_path": str(task_db),
            "market_calendar_dir": str(calendar_path),
        },
        "reports": _report_file_counts(output_path),
        "cache_db": {
            "exists": cache_db.exists(),
            "tables": _sqlite_table_counts(cache_db, ("cache_entries", "reports", "schema_migrations")),
        },
        "task_db": {
            "exists": task_db.exists(),
            "tables": _sqlite_table_counts(
                task_db,
                (
                    "analysis_jobs",
                    "analysis_events",
                    "provider_sla_stats",
                    "provider_sla_events",
                    "schema_migrations",
                ),
            ),
        },
        "market_calendars": {
            "exists": calendar_path.exists(),
            "json_files": len(list(calendar_path.glob("*.json"))) if calendar_path.exists() else 0,
        },
    }


def _report_file_counts(output_path: Path) -> dict:
    if not output_path.exists():
        return {"exists": False, "html": 0, "markdown": 0, "data_snapshots": 0}
    return {
        "exists": True,
        "html": len(list(output_path.glob("*.html"))),
        "markdown": len(list(output_path.glob("*.md"))),
        "data_snapshots": len(list(output_path.glob("*.data.json"))),
    }


def _sqlite_table_counts(path: Path, table_names: tuple[str, ...]) -> dict:
    if not path.exists():
        return {name: None for name in table_names}
    counts = {}
    try:
        with sqlite3.connect(path) as conn:
            for table_name in table_names:
                counts[table_name] = _table_count(conn, table_name)
    except sqlite3.Error:
        return {name: None for name in table_names}
    return counts


def _table_count(conn: sqlite3.Connection, table_name: str) -> int | None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if not exists:
        return None
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
