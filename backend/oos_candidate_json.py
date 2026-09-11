"""Strict JSON decoding for report artifacts and persisted job events."""

from __future__ import annotations

import json


def load_unique_json(raw: bytes) -> dict:
    def unique(pairs):
        value = {}
        for key, child in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = child
        return value

    try:
        payload = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON number: {value}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("artifact JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("artifact JSON must be an object")
    return payload
