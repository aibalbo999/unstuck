"""Backup naming, interval, and retention policy for SQLite maintenance."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


MANAGED_BACKUP_PATTERN = re.compile(r"^(cache_db|task_db|checkpoint_db)-(\d{8})\.sqlite3$")


def prune_backup_files(
    backup_root: Path | None,
    *,
    retention_days: int,
    timestamp: datetime,
    write: bool,
    protected_labels: set[str] | None = None,
) -> dict:
    if retention_days <= 0:
        raise ValueError("retention_days must be at least 1")
    cutoff = utc_date(timestamp) - timedelta(days=retention_days - 1)
    candidates: list[str] = []
    latest_by_label: dict[str, Path] = {}
    managed_backups: list[tuple[Path, str, date]] = []
    if backup_root and backup_root.is_dir():
        for path in sorted(backup_root.iterdir()):
            if path.is_symlink() or not path.is_file():
                continue
            match = MANAGED_BACKUP_PATTERN.fullmatch(path.name)
            if match is None:
                continue
            try:
                backup_date = datetime.strptime(match.group(2), "%Y%m%d").date()
            except ValueError:
                continue
            label = match.group(1)
            managed_backups.append((path, label, backup_date))
            if protected_labels is None or label in protected_labels:
                latest = latest_by_label.get(label)
                if latest is None or backup_date > _backup_date(latest):
                    latest_by_label[label] = path

        protected_latest_paths = set(latest_by_label.values())
        for path, label, backup_date in managed_backups:
            if protected_labels is not None and label not in protected_labels:
                candidates.append(str(path))
            elif backup_date < cutoff and path not in protected_latest_paths:
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
        "protected_labels": sorted(protected_labels) if protected_labels is not None else None,
    }


def backup_plan(
    label: str,
    backup_root: Path | None,
    stamp: str,
    exists: bool,
    write: bool,
    *,
    backup_interval_days: int,
) -> dict:
    if backup_root is None:
        return {"status": "disabled", "path": None}
    path = backup_root / f"{label}-{stamp}.sqlite3"
    stamp_date = datetime.strptime(stamp, "%Y%m%d").date()
    latest_path, latest_date = _latest_backup_for_label(backup_root, label, stamp_date)
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
    if path.is_symlink() or (path.exists() and not path.is_file()):
        metadata["status"] = "skipped_unsafe"
        metadata["reason"] = "backup destination is not a regular file"
        return metadata
    if latest_date is not None and (stamp_date - latest_date).days < backup_interval_days:
        metadata["status"] = "skipped_interval"
        return metadata
    metadata["status"] = "planned" if not write else "pending"
    return metadata


def date_stamp(value: datetime) -> str:
    return utc_date(value).strftime("%Y%m%d")


def utc_date(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()


def _latest_backup_for_label(
    backup_root: Path,
    label: str,
    stamp_date: date,
) -> tuple[Path | None, date | None]:
    latest_path: Path | None = None
    latest_date: date | None = None
    if backup_root.is_dir():
        for candidate in backup_root.iterdir():
            if candidate.is_symlink() or not candidate.is_file():
                continue
            match = MANAGED_BACKUP_PATTERN.fullmatch(candidate.name)
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
    return latest_path, latest_date


def _backup_date(path: Path) -> date:
    match = MANAGED_BACKUP_PATTERN.fullmatch(path.name)
    if match is None:
        return date.min
    return datetime.strptime(match.group(2), "%Y%m%d").date()
