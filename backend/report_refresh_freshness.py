"""Freshness helpers for report data snapshot refresh."""

from __future__ import annotations

from datetime import datetime, timezone

from config import SOURCE_FRESHNESS_MAX_AGE_SECONDS
from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text


HIGH_FREQUENCY_REFRESH_SOURCES = ("market_data", "recent_catalysts")


def _stale_sources(previous_snapshot: dict, *, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    previous_snapshot_map = safe_mapping_dict(previous_snapshot) or {}
    entries = safe_sequence_items(dict.get(previous_snapshot_map, "source_audit", []))
    if not entries:
        return list(HIGH_FREQUENCY_REFRESH_SOURCES)

    stale: set[str] = set()
    latest_success: dict[str, datetime] = {}
    seen_sources: set[str] = set()
    for raw_entry in entries:
        entry = safe_mapping_dict(raw_entry)
        if entry is None:
            continue
        source = str(dict.get(entry, "source") or "").strip()
        if not source:
            continue
        seen_sources.add(source)
        if str(dict.get(entry, "status") or "").strip().lower() != "success":
            stale.add(source)
            continue
        timestamp = _source_audit_timestamp(entry)
        if timestamp is None:
            stale.add(source)
            continue
        if source not in latest_success or timestamp > latest_success[source]:
            latest_success[source] = timestamp

    seen_sources.update(HIGH_FREQUENCY_REFRESH_SOURCES)
    for source in seen_sources:
        timestamp = latest_success.get(source)
        if timestamp is None:
            stale.add(source)
            continue
        max_age = int(SOURCE_FRESHNESS_MAX_AGE_SECONDS.get(source, 24 * 60 * 60))
        if (now - timestamp).total_seconds() > max_age:
            stale.add(source)
    return sorted(stale)


def _source_audit_timestamp(entry: dict) -> datetime | None:
    entry_map = safe_mapping_dict(entry) or {}
    for key in ("created_at", "fetched_at", "timestamp"):
        value = dict.get(entry_map, key)
        if value is None:
            continue
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    text = safe_text(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
