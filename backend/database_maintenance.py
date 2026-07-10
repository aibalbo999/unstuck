"""SQLite backup, checkpoint, and vacuum maintenance helpers."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from config import (
    CACHE_DB_PATH,
    LANGGRAPH_CHECKPOINT_BACKEND,
    LANGGRAPH_CHECKPOINT_PATH,
    SQLITE_BACKUP_DIR,
    SQLITE_BACKUP_INTERVAL_DAYS,
    SQLITE_BACKUP_RETENTION_DAYS,
    TASK_DB_PATH,
)
from security_sanitizer import sanitize_error_message


_MANAGED_BACKUP_PATTERN = re.compile(r"^(cache_db|task_db|checkpoint_db)-(\d{8})\.sqlite3$")


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
    retention_days: int | None = None,
    backup_interval_days: int | None = None,
    write: bool = False,
    now: datetime | None = None,
) -> dict:
    _validate_maintenance_config(retention_days, backup_interval_days)
    return maintain_sqlite_databases(
        runtime_sqlite_paths(
            cache_db_path=cache_db_path,
            task_db_path=task_db_path,
            checkpoint_backend=checkpoint_backend,
            checkpoint_path=checkpoint_path,
        ),
        backup_dir=backup_dir or SQLITE_BACKUP_DIR,
        retention_days=retention_days,
        backup_interval_days=backup_interval_days,
        write=write,
        now=now,
    )


def maintain_sqlite_databases(
    databases: Mapping[str, str],
    *,
    backup_dir: str | None,
    retention_days: int | None = None,
    backup_interval_days: int | None = None,
    write: bool = False,
    now: datetime | None = None,
) -> dict:
    _validate_maintenance_config(retention_days, backup_interval_days)
    timestamp = now or datetime.now(timezone.utc)
    effective_retention_days = (
        SQLITE_BACKUP_RETENTION_DAYS if retention_days is None else retention_days
    )
    effective_backup_interval_days = (
        SQLITE_BACKUP_INTERVAL_DAYS
        if backup_interval_days is None
        else backup_interval_days
    )
    _validate_maintenance_config(effective_retention_days, effective_backup_interval_days)
    stamp = _date_stamp(timestamp)
    backup_root = Path(backup_dir).expanduser().resolve(strict=False) if backup_dir else None
    results = [
        _maintain_one_database(
            label,
            Path(path),
            backup_root=backup_root,
            stamp=stamp,
            backup_interval_days=effective_backup_interval_days,
            write=write,
        )
        for label, path in databases.items()
    ]
    return {
        "dry_run": not write,
        "backup_dir": str(backup_root) if backup_root else None,
        "databases": results,
        "backup_pruning": _prune_backup_files(
            backup_root,
            retention_days=effective_retention_days,
            timestamp=timestamp,
            write=write,
        ),
    }


def _validate_maintenance_config(
    retention_days: int | None,
    backup_interval_days: int | None,
) -> None:
    """Reject unsafe maintenance settings before touching any database or backup."""

    if retention_days is not None and retention_days <= 0:
        raise ValueError("retention_days must be at least 1")
    if backup_interval_days is not None and backup_interval_days <= 0:
        raise ValueError("backup_interval_days must be at least 1")


def _prune_backup_files(
    backup_root: Path | None,
    *,
    retention_days: int,
    timestamp: datetime,
    write: bool,
) -> dict:
    if retention_days <= 0:
        raise ValueError("retention_days must be at least 1")
    cutoff = _utc_date(timestamp) - timedelta(days=retention_days - 1)
    candidates: list[str] = []
    if backup_root and backup_root.is_dir():
        for path in sorted(backup_root.iterdir()):
            if path.is_symlink() or not path.is_file():
                continue
            match = _MANAGED_BACKUP_PATTERN.fullmatch(path.name)
            if match is None:
                continue
            try:
                backup_date = datetime.strptime(match.group(2), "%Y%m%d").date()
            except ValueError:
                continue
            if backup_date < cutoff:
                candidates.append(str(path))

    deleted: list[str] = []
    if write:
        for candidate in candidates:
            Path(candidate).unlink()
            deleted.append(candidate)
    return {
        "retention_days": retention_days,
        "cutoff": cutoff.isoformat(),
        "candidates": candidates,
        "deleted": deleted,
        "dry_run": not write,
    }


def _maintain_one_database(
    label: str,
    path: Path,
    *,
    backup_root: Path | None,
    stamp: str,
    write: bool,
    backup_interval_days: int = SQLITE_BACKUP_INTERVAL_DAYS,
) -> dict:
    resolved = path.expanduser().resolve(strict=False)
    exists = resolved.exists() and resolved.is_file()
    backup = _backup_plan(
        label,
        backup_root,
        stamp,
        exists,
        write,
        backup_interval_days=backup_interval_days,
    )
    maintenance_status = "planned" if exists else "skipped_missing"
    if backup.get("status") == "skipped_interval":
        maintenance_status = "skipped_backup_interval"
    result = {
        "label": label,
        "path": str(resolved),
        "exists": exists,
        "backup": backup,
        "wal_checkpoint": {"status": maintenance_status},
        "vacuum": {"status": maintenance_status},
    }
    if not exists or not write or backup.get("status") == "skipped_interval":
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


def _backup_plan(
    label: str,
    backup_root: Path | None,
    stamp: str,
    exists: bool,
    write: bool,
    *,
    backup_interval_days: int = SQLITE_BACKUP_INTERVAL_DAYS,
) -> dict:
    if backup_root is None:
        return {"status": "disabled", "path": None}
    path = backup_root / f"{label}-{stamp}.sqlite3"
    stamp_date = datetime.strptime(stamp, "%Y%m%d").date()
    latest_path: Path | None = None
    latest_date: date | None = None
    if backup_root.is_dir():
        for candidate in backup_root.iterdir():
            if candidate.is_symlink() or not candidate.is_file():
                continue
            match = _MANAGED_BACKUP_PATTERN.fullmatch(candidate.name)
            if match is None or match.group(1) != label:
                continue
            try:
                candidate_date = datetime.strptime(match.group(2), "%Y%m%d").date()
            except ValueError:
                continue
            if candidate_date > stamp_date:
                continue
            if latest_date is None or candidate_date > latest_date:
                latest_date = candidate_date
                latest_path = candidate
    latest_backup = str(latest_path) if latest_path else None
    next_due_date = (
        latest_date + timedelta(days=backup_interval_days)
        if latest_date is not None
        else stamp_date
    )
    metadata = {
        "path": str(path),
        "latest": latest_backup,
        "latest_backup": latest_backup,
        "latest_backup_date": latest_date.isoformat() if latest_date else None,
        "next_due": next_due_date.isoformat(),
        "next_due_date": next_due_date.isoformat(),
        "interval_days": backup_interval_days,
    }
    if not exists:
        metadata["status"] = "skipped_missing"
        return metadata
    if latest_date is not None:
        elapsed_days = (stamp_date - latest_date).days
        if elapsed_days < backup_interval_days:
            metadata["status"] = "skipped_interval"
            return metadata
    metadata["status"] = "planned" if not write else "pending"
    return metadata


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
    return _utc_date(value).strftime("%Y%m%d")


def _utc_date(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()
