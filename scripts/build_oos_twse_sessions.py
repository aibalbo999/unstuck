#!/usr/bin/env python3
"""Build an immutable TWSE session list from the repository calendar definition."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from market_calendar_store import BUILTIN_MARKET_CALENDARS, normalize_calendar
from oos_research.canonical import canonical_bytes, content_hash
from oos_research.calendar import validate_sessions


def build(*, start: date, end: date) -> dict:
    if start > end or start.year != end.year:
        raise ValueError("session range must be ordered within one calendar year")
    source = BUILTIN_MARKET_CALENDARS.get(("tw", start.year), {})
    calendar = normalize_calendar(source, market="tw", year=start.year)
    if (
        calendar.get("market") != "tw"
        or calendar.get("year") != start.year
        or calendar.get("timezone") != "Asia/Taipei"
        or calendar.get("open") != "09:00"
    ):
        raise ValueError("TWSE calendar definition is incomplete")
    holidays = set(calendar.get("holidays") or [])
    sessions = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor.isoformat() not in holidays:
            sessions.append(cursor.isoformat())
        cursor += timedelta(days=1)
    validate_sessions(sessions)
    if not sessions:
        raise ValueError("session range contains no exchange sessions")
    return {
        "schema_version": "oos.exchange-sessions.v1",
        "market": "tw",
        "timezone": "Asia/Taipei",
        "session_open_local_time": "09:00:00",
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "calendar_definition_sha256": content_hash(calendar),
        "sessions": sessions,
    }


def write_exclusive(output: Path, payload: dict) -> None:
    if not output.is_absolute() or output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("output must be a new absolute path in an existing directory")
    data = canonical_bytes(payload) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(output.parent.resolve() / output.name, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short session calendar write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = build(start=args.start, end=args.end)
    write_exclusive(args.output, payload)
    print(json.dumps({
        "calendar_definition_sha256": payload["calendar_definition_sha256"],
        "session_count": len(payload["sessions"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
