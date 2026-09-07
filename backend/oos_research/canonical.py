"""Canonical JSON and safe hashing primitives used by the OOS store."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any


class CanonicalizationError(ValueError):
    pass


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise CanonicalizationError("NaN and Infinity are not permitted")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError("JSON object keys must be strings")
            _reject_nonfinite(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_nonfinite(child)
    elif isinstance(value, (datetime, date)):
        raise CanonicalizationError("date values must be serialized explicitly")


def canonical_bytes(value: Any) -> bytes:
    _reject_nonfinite(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError(str(exc)) from exc


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))
