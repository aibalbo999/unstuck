"""Summary helpers for runtime storage diagnostics."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def report_file_counts(output_path: Path) -> dict:
    if not output_path.exists():
        return {"exists": False, "html": 0, "markdown": 0, "data_snapshots": 0}
    return {
        "exists": True,
        "html": _count_report_files(output_path, "*.html"),
        "markdown": _count_report_files(output_path, "*.md"),
        "data_snapshots": _count_report_files(output_path, "*.data.json"),
    }


def sqlite_table_counts(path: Path, table_names: tuple[str, ...]) -> dict:
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


def _count_report_files(output_path: Path, pattern: str) -> int:
    return sum(
        1
        for path in output_path.rglob(pattern)
        if path.is_file() and not path.is_symlink()
    )


def _table_count(conn: sqlite3.Connection, table_name: str) -> int | None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if not exists:
        return None
    quoted_name = '"' + table_name.replace('"', '""') + '"'
    return int(conn.execute(f"SELECT COUNT(*) FROM {quoted_name}").fetchone()[0])
