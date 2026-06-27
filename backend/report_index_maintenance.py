"""Maintenance helpers for report metadata index rows."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from config import CACHE_DB_PATH


def report_index_orphan_summary(cache_db_path: Optional[str] = None) -> dict:
    path = Path(cache_db_path or CACHE_DB_PATH)
    if not path.exists():
        return {"exists": False, "orphan_output_dirs": 0, "orphan_rows": 0, "output_dirs": []}
    output_dirs = _output_dir_counts(path)
    orphan_dirs = [item for item in output_dirs if not Path(item["output_dir"]).exists()]
    return {
        "exists": True,
        "orphan_output_dirs": len(orphan_dirs),
        "orphan_rows": sum(int(item["rows"]) for item in orphan_dirs),
        "output_dirs": orphan_dirs,
    }


def cleanup_report_index_orphans(*, cache_db_path: Optional[str] = None, write: bool = False) -> dict:
    path = Path(cache_db_path or CACHE_DB_PATH)
    summary = report_index_orphan_summary(str(path))
    if not summary["exists"] or not summary["orphan_output_dirs"] or not write:
        return {**summary, "deleted_rows": 0, "dry_run": not write}

    orphan_dirs = [item["output_dir"] for item in summary["output_dirs"]]
    with sqlite3.connect(path) as conn:
        deleted = 0
        for output_dir in orphan_dirs:
            cursor = conn.execute("DELETE FROM reports WHERE output_dir = ?", (output_dir,))
            deleted += int(cursor.rowcount or 0)
    return {**report_index_orphan_summary(str(path)), "deleted_rows": deleted, "dry_run": False}


def cleanup_empty_report_directories(output_dir: str) -> list[str]:
    root = Path(output_dir)
    if not root.exists() or not root.is_dir():
        return []
    removed: list[str] = []
    for path in sorted((item for item in root.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            path.rmdir()
        except OSError:
            continue
        removed.append(str(path))
    return removed


def _output_dir_counts(path: Path) -> list[dict]:
    try:
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                """
                SELECT output_dir, COUNT(*) AS rows
                FROM reports
                GROUP BY output_dir
                ORDER BY rows DESC, output_dir
                """
            ).fetchall()
    except sqlite3.Error:
        return []
    return [{"output_dir": str(row[0]), "rows": int(row[1] or 0)} for row in rows]
