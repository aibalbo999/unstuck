"""Storage inventory helpers for local maintenance diagnostics."""

from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path
from typing import Optional

from config import (
    CACHE_DB_PATH,
    CACHE_DIR,
    LANGGRAPH_CHECKPOINT_PATH,
    MARKET_CALENDAR_DIR,
    OUTPUT_DIR,
    TASK_DB_PATH,
)
from job_store_maintenance import analysis_history_summary
from report_index_maintenance import report_index_orphan_summary


def ensure_runtime_storage(
    *,
    output_dir: Optional[str] = None,
    cache_dir: Optional[str] = None,
    cache_db_path: Optional[str] = None,
    task_db_path: Optional[str] = None,
    checkpoint_path: Optional[str] = None,
    decision_tracking_db_path: Optional[str] = None,
    watchlist_db_path: Optional[str] = None,
    yfinance_cache_dir: Optional[str] = None,
    market_calendar_dir: Optional[str] = None,
) -> dict:
    """Create and verify runtime storage paths before workers start."""
    created_dirs: list[str] = []
    output_path = _ensure_directory(Path(output_dir or OUTPUT_DIR), "output_dir", created_dirs)
    cache_path = _ensure_directory(Path(cache_dir or CACHE_DIR), "cache_dir", created_dirs)
    calendar_path = _ensure_directory(Path(market_calendar_dir or MARKET_CALENDAR_DIR), "market_calendar_dir", created_dirs)

    cache_db = Path(cache_db_path or CACHE_DB_PATH)
    task_db = Path(task_db_path or TASK_DB_PATH)
    checkpoint_db = Path(checkpoint_path or LANGGRAPH_CHECKPOINT_PATH)
    tracking_db = Path(decision_tracking_db_path or os.getenv("DECISION_TRACKING_DB_PATH", str(task_db)))
    watchlist_db = _default_watchlist_db_path(cache_db, task_db, watchlist_db_path)
    yfinance_cache_path = _ensure_directory(
        Path(yfinance_cache_dir or os.getenv("YFINANCE_CACHE_DIR", str(cache_db.expanduser().parent / "yfinance"))),
        "yfinance_cache_dir",
        created_dirs,
    )
    _configure_yfinance_cache(yfinance_cache_path)
    sqlite_paths = {
        "cache_db": _ensure_sqlite_openable(cache_db, "cache_db", created_dirs),
        "task_db": _ensure_sqlite_openable(task_db, "task_db", created_dirs),
        "checkpoint_db": _ensure_sqlite_openable(checkpoint_db, "checkpoint_db", created_dirs),
        "decision_tracking_db": _ensure_sqlite_openable(tracking_db, "decision_tracking_db", created_dirs),
        "watchlist_db": _ensure_sqlite_openable(watchlist_db, "watchlist_db", created_dirs),
    }

    return {
        "success": True,
        "directories": {
            "output_dir": str(output_path),
            "cache_dir": str(cache_path),
            "market_calendar_dir": str(calendar_path),
            "yfinance_cache_dir": str(yfinance_cache_path),
        },
        "sqlite_paths": {name: str(path) for name, path in sqlite_paths.items()},
        "created_dirs": sorted(set(created_dirs)),
    }


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
            "report_index_orphans": report_index_orphan_summary(str(cache_db)),
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
            "analysis_history": analysis_history_summary(task_db_path=str(task_db)),
        },
        "market_calendars": {
            "exists": calendar_path.exists(),
            "json_files": len(list(calendar_path.glob("*.json"))) if calendar_path.exists() else 0,
        },
    }


def clear_runtime_storage(
    *,
    output_dir: Optional[str] = None,
    cache_dir: Optional[str] = None,
    cache_db_path: Optional[str] = None,
    task_db_path: Optional[str] = None,
    market_calendar_dir: Optional[str] = None,
    confirm_delete: bool = False,
) -> dict:
    """Delete generated reports, cache files, and runtime SQLite databases."""
    if not confirm_delete:
        raise ValueError("clear_runtime_storage requires confirm_delete=True")

    output_path = Path(output_dir or OUTPUT_DIR)
    cache_path = Path(cache_dir or CACHE_DIR)
    cache_db = Path(cache_db_path or CACHE_DB_PATH)
    task_db = Path(task_db_path or TASK_DB_PATH)
    calendar_path = Path(market_calendar_dir or MARKET_CALENDAR_DIR)
    removed: list[str] = []
    seen: set[Path] = set()

    for base in (output_path, cache_path):
        if not base.exists():
            continue
        for child in base.iterdir():
            _remove_path(child, removed, seen)

    for db_path in (cache_db, task_db):
        _remove_sqlite_family(db_path, removed, seen)
    _remove_path(calendar_path, removed, seen)

    output_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)

    summary = build_storage_summary(
        output_dir=str(output_path),
        cache_dir=str(cache_path),
        cache_db_path=str(cache_db),
        task_db_path=str(task_db),
        market_calendar_dir=str(calendar_path),
    )
    return {
        "confirmed": True,
        "removed_count": len(removed),
        "removed_paths": removed,
        "summary": summary,
    }


def _ensure_directory(path: Path, label: str, created_dirs: list[str]) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if resolved.exists() and not resolved.is_dir():
        raise RuntimeError(f"{label} should be a directory: {resolved}")
    existed = resolved.exists()
    resolved.mkdir(parents=True, exist_ok=True)
    if not existed:
        created_dirs.append(label)
    return resolved


def _ensure_sqlite_openable(path: Path, label: str, created_dirs: list[str]) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if resolved.exists() and resolved.is_dir():
        raise RuntimeError(f"{label} SQLite database path is a directory: {resolved}")
    _ensure_directory(resolved.parent, f"{label}_parent", created_dirs)
    try:
        with sqlite3.connect(resolved, timeout=30) as conn:
            conn.execute("PRAGMA user_version").fetchone()
    except sqlite3.Error as exc:
        raise RuntimeError(f"{label} SQLite database cannot be opened at {resolved}: {exc}") from exc
    return resolved


def _default_watchlist_db_path(cache_db: Path, task_db: Path, explicit_path: Optional[str]) -> Path:
    if explicit_path:
        return Path(explicit_path)
    env_db_path = os.getenv("WATCHLIST_DB_PATH", "").strip()
    if env_db_path:
        return Path(env_db_path)
    default_watchlist_path = cache_db.expanduser().parent / "watchlist.json"
    watchlist_path = Path(os.getenv("WATCHLIST_PATH", str(default_watchlist_path)))
    if watchlist_path == default_watchlist_path:
        return task_db
    return watchlist_path.with_suffix(".sqlite3")


def _configure_yfinance_cache(cache_dir: Path) -> None:
    try:
        import yfinance.cache as yf_cache
    except Exception:
        return
    desired = str(cache_dir)
    managers = (
        getattr(yf_cache, "_TzDBManager", None),
        getattr(yf_cache, "_CookieDBManager", None),
        getattr(yf_cache, "_ISINDBManager", None),
    )
    if all(manager is not None and manager.get_location() == desired for manager in managers):
        return
    yf_cache.set_cache_location(desired)


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


def _remove_sqlite_family(path: Path, removed: list[str], seen: set[Path]) -> None:
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        _remove_path(candidate, removed, seen)


def _remove_path(path: Path, removed: list[str], seen: set[Path]) -> None:
    resolved = path.expanduser().resolve(strict=False)
    if resolved in seen or not path.exists():
        return
    seen.add(resolved)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    removed.append(str(path))
