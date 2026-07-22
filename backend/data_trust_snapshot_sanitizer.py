"""Sanitization helpers shared by data snapshot persistence and sizing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from data_trust_constants import SENSITIVE_KEY_RE, SNAPSHOT_RERUN_ANALYSIS_MAX_CHARS
from mapping_fields import (
    safe_mapping_items as _safe_mapping_items,
    safe_sequence_items as _safe_sequence_items,
    safe_text,
)
from report_reproducibility import validated_prompt_fingerprint


def sanitize_for_snapshot(value: Any) -> Any:
    if isinstance(value, Mapping):
        clean = {}
        for key, item in _safe_mapping_items(value):
            key_str = _safe_text(key)
            if not key_str:
                continue
            if key_str == "prompt_fingerprint":
                if fingerprint := validated_prompt_fingerprint(item):
                    clean[key_str] = fingerprint
                continue
            if key_str.startswith("_") or (key_str != "prompt_version" and SENSITIVE_KEY_RE.search(key_str)):
                continue
            clean[key_str] = sanitize_for_snapshot(item)
        return clean
    if isinstance(value, (list, tuple)):
        return [sanitize_for_snapshot(item) for item in _safe_sequence_items(value)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return _safe_text(value)


def snapshot_text(value: Any, *, max_chars: int = SNAPSHOT_RERUN_ANALYSIS_MAX_CHARS) -> str:
    text = _safe_text(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[Snapshot truncated for size]"


def _safe_text(value: Any) -> str:
    return safe_text(value)


__all__ = ["sanitize_for_snapshot", "snapshot_text"]
