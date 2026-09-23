"""Absolute publication timestamp parsing shared by news adapters and selection."""
from __future__ import annotations

import calendar
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from typing import Any


def iso_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, (tuple, list)) and len(value) >= 6:
        timestamp = calendar.timegm(tuple(value[:9]))
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    text = re.sub(r"\s+", " ", str(value or "")).strip()[:200]
    if not text:
        return ""
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except ValueError:
        return ""


def parse_news_datetime(value: Any) -> datetime | None:
    """Parse absolute provider timestamps without discarding their time or timezone."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            parsed = datetime.fromtimestamp(value, timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        parsed = None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
        if parsed is None:
            try:
                parsed = parsedate_to_datetime(raw)
            except (TypeError, ValueError):
                pass
        if parsed is None:
            for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
