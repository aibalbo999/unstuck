"""Input availability identity kept separate from report presentation logic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text


def input_bundle_observed_at(data: dict[str, Any]) -> str:
    """Return the latest fetch observation without claiming publication time."""

    data = safe_mapping_dict(data) or {}
    candidates: list[tuple[datetime, str]] = []
    for entry in safe_dict_list(dict.get(data, "source_audit")):
        value = safe_text(dict.get(entry, "fetched_at")).strip()
        if (parsed := _aware_timestamp(value)) is not None:
            candidates.append((parsed, value))
    for key in ("market_data_fetched_at", "cache_generated_at"):
        value = safe_text(dict.get(data, key)).strip()
        if (parsed := _aware_timestamp(value)) is not None:
            candidates.append((parsed, value))
    return max(candidates, key=lambda item: item[0])[1] if candidates else ""


def _aware_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)
