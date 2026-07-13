"""Mapping helpers for data snapshot integrity checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mapping_fields import safe_mapping_items


_MISSING = object()
_FIELD_ACCESS_ERRORS = (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError)


def _mapping_item_get(snapshot: Mapping, key: str, default: Any) -> Any:
    try:
        return snapshot[key]
    except _FIELD_ACCESS_ERRORS:
        return default


def mapping_get(snapshot: Mapping, key: str, default: Any = None) -> Any:
    if isinstance(snapshot, dict):
        try:
            return dict.get(snapshot, key, default)
        except _FIELD_ACCESS_ERRORS:
            try:
                return dict.__getitem__(snapshot, key)
            except _FIELD_ACCESS_ERRORS:
                return default
    try:
        return snapshot.get(key, default)
    except _FIELD_ACCESS_ERRORS:
        return _mapping_item_get(snapshot, key, default)


def mapping_has_key(snapshot: Mapping, key: str) -> bool:
    try:
        return key in snapshot
    except _FIELD_ACCESS_ERRORS:
        return mapping_get(snapshot, key, _MISSING) is not _MISSING


def hashable_snapshot_value(key: str, value: Any) -> Any:
    if key == "reproducibility_packet" and isinstance(value, Mapping):
        packet = dict(safe_mapping_items(value))
        packet.pop("data_snapshot_hash", None)
        return packet
    return value
