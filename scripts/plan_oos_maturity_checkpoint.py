#!/usr/bin/env python3
"""Select the next registered OOS maturity cutoff without changing evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "backend"))

from oos_research.canonical import require_sha256_pin
from oos_research.maturity_schedule import plan_next_checkpoint, validate_maturity_schedule
from oos_research.store import StoreError


_MAX_SCHEDULE_BYTES = 256 * 1024


def _load_schedule(value: str) -> dict:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("schedule must be an absolute, normalized path")
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError("schedule may not contain symlink components")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > _MAX_SCHEDULE_BYTES:
            raise ValueError("schedule must be a bounded regular file")
        chunks: list[bytes] = []
        remaining = _MAX_SCHEDULE_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if len(raw) > _MAX_SCHEDULE_BYTES:
        raise ValueError("schedule exceeds size limit")
    try:
        schedule = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("schedule JSON is invalid") from None
    if not isinstance(schedule, dict):
        raise ValueError("schedule JSON must be an object")
    return schedule


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--expected-schedule-sha256", required=True)
    parser.add_argument("--checkpoints-root", required=True)
    parser.add_argument("--study-root", required=True)
    parser.add_argument("--study-id", required=True)
    args = parser.parse_args(argv)
    try:
        schedule = _load_schedule(args.schedule)
        schedule_hash = validate_maturity_schedule(schedule)
        require_sha256_pin(schedule_hash, args.expected_schedule_sha256, label="maturity schedule")
        result = plan_next_checkpoint(
            schedule=schedule,
            checkpoints_root=args.checkpoints_root,
            study_root=args.study_root,
            study_id=args.study_id,
        )
    except (OSError, StoreError, TypeError, ValueError):
        error = {
            "schema_version": "oos.maturity-plan.v1",
            "status": "error",
            "should_capture": False,
            "error_code": "maturity_schedule_or_evidence_error",
        }
        print(json.dumps(error, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result["status"] == "conflict" else 0


if __name__ == "__main__":
    raise SystemExit(main())
