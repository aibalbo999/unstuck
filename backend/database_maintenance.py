"""SQLite backup, checkpoint, and vacuum maintenance helpers."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from config import CACHE_DB_PATH, LANGGRAPH_CHECKPOINT_BACKEND, LANGGRAPH_CHECKPOINT_PATH, SQLITE_BACKUP_DIR, TASK_DB_PATH
from security_sanitizer import sanitize_error_message


def runtime_sqlite_paths(
    *,
    cache_db_path: str | None = None,
    task_db_path: str | None = None,
    checkpoint_backend: str | None = None,
    checkpoint_path: str | None = None,
) -> dict[str, str]:
    paths = {
        "cache_db": str(cache_db_path or CACHE_DB_PATH),
        "task_db": str(task_db_path or TASK_DB_PATH),
    }
    backend = str(checkpoint_backend or LANGGRAPH_CHECKPOINT_BACKEND or "sqlite").strip().lower()
    if backend != "postgres":
        paths["checkpoint_db"] = str(checkpoint_path or LANGGRAPH_CHECKPOINT_PATH)

    deduplicated: dict[str, str] = {}
    seen_paths: set[Path] = set()
    for label, path in paths.items():
        canonical_path = Path(path).expanduser().resolve(strict=False)
        if canonical_path in seen_paths:
            continue
        seen_paths.add(canonical_path)
        deduplicated[label] = path
    return deduplicated


def run_sqlite_maintenance(
    *,
    cache_db_path: str | None = None,
    task_db_path: str | None = None,
    checkpoint_backend: str | None = None,
    checkpoint_path: str | None = None,
    backup_dir: str | None = None,
    write: bool = False,
    now: datetime | None = None,
) -> dict:
    return maintain_sqlite_databases(
        runtime_sqlite_paths(
            cache_db_path=cache_db_path,
            task_db_path=task_db_path,
            checkpoint_backend=checkpoint_backend,
            checkpoint_path=checkpoint_path,
        ),
        backup_dir=backup_dir or SQLITE_BACKUP_DIR,
        write=write,
        now=now,
    )


def maintain_sqlite_databases(
    databases: Mapping[str, str],
    *,
    backup_dir: str | None,
    write: bool = False,
    now: datetime | None = None,
) -> dict:
    timestamp = now or datetime.now(timezone.utc)
    stamp = _date_stamp(timestamp)
    backup_root = Path(backup_dir).expanduser().resolve(strict=False) if backup_dir else None
    results = [
        _maintain_one_database(label, Path(path), backup_root=backup_root, stamp=stamp, write=write)
        for label, path in databases.items()
    ]
    return {
        "dry_run": not write,
        "backup_dir": str(backup_root) if backup_root else None,
        "databases": results,
    }


def _maintain_one_database(
    label: str,
    path: Path,
    *,
    backup_root: Path | None,
    stamp: str,
    write: bool,
) -> dict:
    resolved = path.expanduser().resolve(strict=False)
    exists = resolved.exists() and resolved.is_file()
    result = {
        "label": label,
        "path": str(resolved),
        "exists": exists,
        "backup": _backup_plan(label, backup_root, stamp, exists, write),
        "wal_checkpoint": {"status": "planned" if exists else "skipped_missing"},
        "vacuum": {"status": "planned" if exists else "skipped_missing"},
    }
    if not exists or not write:
        return result

    try:
        _create_backup_if_needed(resolved, result["backup"])
        checkpoint_rows = _checkpoint_and_vacuum(resolved)
        result["wal_checkpoint"] = {"status": "ran", "result": checkpoint_rows}
        result["vacuum"] = {"status": "ran"}
    except sqlite3.Error as exc:
        result["error"] = sanitize_error_message(exc)
        if result["wal_checkpoint"]["status"] == "planned":
            result["wal_checkpoint"]["status"] = "error"
        if result["vacuum"]["status"] == "planned":
            result["vacuum"]["status"] = "error"
    return result


def _backup_plan(label: str, backup_root: Path | None, stamp: str, exists: bool, write: bool) -> dict:
    if backup_root is None:
        return {"status": "disabled", "path": None}
    path = backup_root / f"{label}-{stamp}.sqlite3"
    if not exists:
        return {"status": "skipped_missing", "path": str(path)}
    if path.exists():
        return {"status": "exists", "path": str(path)}
    return {"status": "planned" if not write else "pending", "path": str(path)}


def _create_backup_if_needed(source_path: Path, backup: dict) -> None:
    if backup.get("status") != "pending":
        return
    backup_path = Path(str(backup["path"]))
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path, timeout=30) as source, sqlite3.connect(backup_path, timeout=30) as dest:
        source.backup(dest)
    backup["status"] = "created"


def _checkpoint_and_vacuum(path: Path) -> list[tuple]:
    with sqlite3.connect(path, timeout=30, isolation_level=None) as conn:
        conn.execute("PRAGMA busy_timeout=30000")
        checkpoint_rows = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        conn.execute("VACUUM")
    return [tuple(row) for row in checkpoint_rows]


def _date_stamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y%m%d")
