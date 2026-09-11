"""Read-only completeness inspection for immutable OOS maturity checkpoints."""

from __future__ import annotations

import json
import os
import re
import stat
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .dataset import validate_dataset
from .store import StoreError, StudyStore
from .summary import summary_markdown


_DATASET_LIMIT = 64 * 1024 * 1024
_REPLAY_LIMIT = 16 * 1024 * 1024
_SUMMARY_LIMIT = 2 * 1024 * 1024
_MARKET_TIMEZONE = ZoneInfo("Asia/Taipei")
_CAPTURE_NOT_BEFORE = time(15, 5)


def _existing_root(value: str | os.PathLike[str], *, label: str) -> Path:
    if not value:
        raise ValueError(f"{label} must be explicit")
    raw = Path(value)
    if not raw.is_absolute() or ".." in raw.parts:
        raise ValueError(f"{label} must be an absolute, normalized path")
    for component in (raw, *raw.parents):
        if component.is_symlink():
            raise ValueError(f"{label} may not contain symlink components")
    if not raw.is_dir():
        raise ValueError(f"{label} must be an existing directory")
    return raw.resolve(strict=True)


def _run_pattern(cutoff_session: str) -> re.Pattern[str]:
    return re.compile(
        rf"{re.escape(cutoff_session)}T"
        r"(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})"
        r"(?P<sign>[+-])(?P<offset_hour>\d{2})(?P<offset_minute>\d{2})"
        r"-r(?P<revision>[1-9]\d*)"
    )


def _valid_run_id(match: re.Match[str]) -> bool:
    values = {name: int(value) for name, value in match.groupdict().items() if name != "sign"}
    try:
        datetime(
            2000,
            1,
            1,
            values["hour"],
            values["minute"],
            values["second"],
        )
    except ValueError:
        return False
    return values["offset_hour"] <= 23 and values["offset_minute"] <= 59


def _read_regular_at(directory_fd: int, name: str, *, limit: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, dir_fd=directory_fd)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > limit:
            raise OSError("checkpoint evidence size or type is invalid")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > limit:
            raise OSError("checkpoint evidence exceeds size limit")
        return payload
    finally:
        os.close(descriptor)


def _read_json_at(directory_fd: int, name: str, *, limit: int) -> dict[str, Any]:
    payload = json.loads(_read_regular_at(directory_fd, name, limit=limit))
    if not isinstance(payload, dict):
        raise ValueError("checkpoint JSON must be an object")
    return payload


def _inspect_run(
    root_fd: int,
    *,
    run_id: str,
    cutoff_session: str,
    store: StudyStore,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "run_id": run_id,
        "status": "incomplete",
        "dataset_hash": None,
        "reason_codes": [],
    }
    reasons: set[str] = set()
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        run_fd = os.open(run_id, directory_flags, dir_fd=root_fd)
    except OSError:
        result["reason_codes"] = ["unsafe_checkpoint_entry"]
        return result

    dataset: dict[str, Any] | None = None
    replay: dict[str, Any] | None = None
    dataset_hash: str | None = None
    summary_bytes: bytes | None = None
    try:
        try:
            dataset = _read_json_at(run_fd, "dataset.json", limit=_DATASET_LIMIT)
        except OSError:
            reasons.add("dataset_missing_or_unsafe")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            reasons.add("dataset_malformed")
        if dataset is not None:
            try:
                dataset_hash = validate_dataset(dataset)
                result["dataset_hash"] = dataset_hash
            except ValueError:
                reasons.add("dataset_invalid")
            else:
                if dataset.get("dataset_sha256") != dataset_hash:
                    reasons.add("dataset_hash_missing")
                if dataset.get("cutoff_session") != cutoff_session:
                    reasons.add("dataset_cutoff_mismatch")

        try:
            replay = _read_json_at(run_fd, "replay-result.json", limit=_REPLAY_LIMIT)
        except OSError:
            reasons.add("replay_missing_or_unsafe")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            reasons.add("replay_malformed")

        try:
            summary_bytes = _read_regular_at(run_fd, "summary.md", limit=_SUMMARY_LIMIT)
        except OSError:
            reasons.add("summary_missing_or_unsafe")

        if replay is not None:
            summary = replay.get("summary")
            if replay.get("study_id") != store.study_id or replay.get("dataset_hash") != dataset_hash:
                reasons.add("replay_identity_mismatch")
            if not isinstance(summary, dict):
                reasons.add("replay_summary_malformed")
            elif summary_bytes is not None:
                try:
                    expected_summary = summary_markdown(summary).encode("utf-8")
                except (AttributeError, TypeError, ValueError):
                    reasons.add("replay_summary_malformed")
                else:
                    if summary_bytes != expected_summary:
                        reasons.add("summary_mismatch")

        if dataset_hash is not None:
            record_id = f"checkpoint-{dataset_hash}"
            try:
                record = store.read_record(record_id)
            except (StoreError, TypeError, ValueError):
                reasons.add("checkpoint_record_missing_or_invalid")
            else:
                payload = record.get("payload")
                if (
                    record.get("record_type") != "checkpoint"
                    or record.get("record_id") != record_id
                    or not isinstance(payload, dict)
                    or payload.get("schema_version") != "oos.checkpoint.v1"
                    or payload.get("dataset_hash") != dataset_hash
                ):
                    reasons.add("checkpoint_record_mismatch")
    finally:
        os.close(run_fd)

    result["reason_codes"] = sorted(reasons)
    if not reasons:
        result["status"] = "complete"
    return result


def inspect_checkpoint_cutoff(
    *,
    checkpoints_root: str | os.PathLike[str],
    study_root: str | os.PathLike[str],
    study_id: str,
    cutoff_session: str,
    current_time: datetime | None = None,
) -> dict[str, Any]:
    """Return whether an official capture is needed for one exact cutoff."""
    try:
        cutoff = date.fromisoformat(cutoff_session)
    except (TypeError, ValueError) as exc:
        raise ValueError("cutoff_session must be an ISO date") from exc
    if cutoff.isoformat() != cutoff_session:
        raise ValueError("cutoff_session must be an ISO date")
    observed_at = current_time or datetime.now(_MARKET_TIMEZONE)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("current_time must include a timezone")
    capture_not_before = datetime.combine(cutoff, _CAPTURE_NOT_BEFORE, _MARKET_TIMEZONE)

    root = _existing_root(checkpoints_root, label="checkpoints_root")
    store = StudyStore(study_root, study_id=study_id, create=False)
    pattern = _run_pattern(cutoff_session)
    root_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    root_fd = os.open(root, root_flags)
    try:
        run_ids = []
        for name in os.listdir(root_fd):
            match = pattern.fullmatch(name)
            if match and _valid_run_id(match):
                run_ids.append(name)
        checkpoints = [
            _inspect_run(
                root_fd,
                run_id=run_id,
                cutoff_session=cutoff_session,
                store=store,
            )
            for run_id in sorted(run_ids)
        ]
    finally:
        os.close(root_fd)

    complete_count = sum(item["status"] == "complete" for item in checkpoints)
    incomplete_count = len(checkpoints) - complete_count
    if complete_count > 1:
        status, should_capture = "conflict", False
    elif complete_count == 1:
        status, should_capture = "complete", False
    elif incomplete_count:
        status, should_capture = "incomplete", True
    else:
        status, should_capture = "not_found", True
    result = {
        "schema_version": "oos.checkpoint-preflight.v1",
        "cutoff_session": cutoff_session,
        "status": status,
        "should_capture": should_capture,
        "complete_count": complete_count,
        "incomplete_count": incomplete_count,
        "checkpoints": checkpoints,
    }
    if should_capture and observed_at.astimezone(_MARKET_TIMEZONE) < capture_not_before:
        result.update({
            "status": "not_due",
            "should_capture": False,
            "capture_not_before": capture_not_before.isoformat(),
        })
    return result
