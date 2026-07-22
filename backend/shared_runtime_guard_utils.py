"""Shared utility helpers for runtime guards."""

from __future__ import annotations

import hashlib
from datetime import datetime, time as datetime_time, timedelta
from zoneinfo import ZoneInfo


def guard_hash(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def seconds_until_next_pacific_midnight(now: datetime | None = None) -> float:
    """Seconds until the next America/Los_Angeles midnight."""
    try:
        pacific = ZoneInfo("America/Los_Angeles")
        current = now or datetime.now(pacific)
        if current.tzinfo is None:
            current = current.replace(tzinfo=pacific)
        current = current.astimezone(pacific)
        next_day = current.date() + timedelta(days=1)
        reset_at = datetime.combine(next_day, datetime_time.min, tzinfo=pacific)
        return max((reset_at - current).total_seconds(), 1.0)
    except Exception:
        return 24 * 60 * 60.0
