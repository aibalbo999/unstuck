"""Strict scalar allowlist for generation telemetry, never request bodies."""

from collections.abc import Mapping
import math
from typing import Any
from mapping_fields import safe_mapping_items


def safe_generation_settings(value: Any) -> dict[str, int | float | str]:
    if not isinstance(value, Mapping):
        return {}
    value = dict(safe_mapping_items(value))
    result = {}
    for field, upper in (("temperature", 2), ("top_p", 1)):
        item = value.get(field)
        if type(item) in (int, float) and 0 <= item <= upper and math.isfinite(item):
            result[field] = item
    output = value.get("max_output_tokens")
    if type(output) is int and 0 < output <= 1_000_000:
        result["max_output_tokens"] = output
    thinking = value.get("thinking_level")
    if isinstance(thinking, str) and thinking in {"minimal", "low", "medium", "high"}:
        result["thinking_level"] = thinking
    return result
