"""Offline, complete-session dataset validation."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

from .canonical import content_hash
from .calendar import validate_sessions


def _finite_price(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value)) and float(value) > 0


def validate_dataset(dataset: Mapping[str, Any]) -> str:
    required = {"schema_version", "provider", "timezone", "as_of", "price_policy", "corporate_action_policy", "calendar", "bars"}
    missing = required - set(dataset)
    if missing:
        raise ValueError(f"dataset missing fields: {', '.join(sorted(missing))}")
    if dataset["price_policy"] != "raw" or dataset["corporate_action_policy"] != "explicit_unprocessed_allowed":
        raise ValueError("dataset policy is not allowed for this study")
    sessions = validate_sessions(dataset["calendar"])
    try:
        datetime.fromisoformat(str(dataset["as_of"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("dataset as_of is invalid") from exc
    bars = dataset["bars"]
    if not isinstance(bars, Mapping):
        raise ValueError("bars must be ticker mapping")
    for ticker, rows in bars.items():
        if not isinstance(ticker, str) or not isinstance(rows, list):
            raise ValueError("malformed bars mapping")
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, Mapping) or row.get("date") in seen:
                raise ValueError("duplicate or malformed bar")
            day = str(row.get("date"))
            if day in seen or day not in {d.isoformat() for d in sessions}:
                raise ValueError("bar date is not in calendar")
            seen.add(day)
            if any(not _finite_price(row.get(key)) for key in ("open", "high", "low", "close")):
                raise ValueError("bar has invalid OHLC")
            if not (row["low"] <= min(row["open"], row["close"]) <= max(row["open"], row["close"]) <= row["high"]):
                raise ValueError("inconsistent OHLC")
            if row.get("complete") is not True:
                raise ValueError("only completed bars are accepted")
            if not row.get("completed_at"):
                raise ValueError("completed_at is required")
            try:
                completed_at = datetime.fromisoformat(str(row["completed_at"]).replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("completed_at is invalid") from exc
            if completed_at.tzinfo is None or completed_at.utcoffset() is None:
                raise ValueError("completed_at must include timezone")
    expected = dataset.get("dataset_sha256")
    actual = content_hash({k: v for k, v in dataset.items() if k != "dataset_sha256"})
    if expected is not None and expected != actual:
        raise ValueError("dataset hash mismatch")
    return actual
