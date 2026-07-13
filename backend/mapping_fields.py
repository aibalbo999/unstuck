"""Shared dict-native field reads for upstream payload shaping."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from typing import Any


def mapping_field(row: dict[str, Any], key: str, default: Any = None) -> Any:
    return dict.get(row, key, default)


def safe_text(value: Any) -> str:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return ""
    try:
        return "" if value is None else str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return ""


def safe_int(value: Any, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, float) and not value.is_integer():
        return 0
    if isinstance(value, Decimal):
        try:
            if not value.is_finite() or value != value.to_integral_value():
                return 0
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            return default
    if isinstance(value, Fraction) and value.denominator != 1:
        return 0
    try:
        return int(default if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return default


def safe_text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    texts = []
    iterator = _sequence_iterator(value)
    if iterator is None:
        return texts
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            break
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            if not used_native:
                native_iterator = _native_sequence_iterator(value)
                if native_iterator is not None:
                    native_texts = []
                    while True:
                        try:
                            native_item = next(native_iterator)
                        except StopIteration:
                            break
                        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
                            break
                        native_text = safe_text(native_item).strip()
                        if native_text:
                            native_texts.append(native_text)
                    if native_texts:
                        texts = native_texts
            break
        text = safe_text(item).strip()
        if text:
            texts.append(text)
    return texts


def safe_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    rows = []
    iterator = _sequence_iterator(value)
    if iterator is None:
        return rows
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            break
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            if not used_native:
                native_iterator = _native_sequence_iterator(value)
                if native_iterator is not None:
                    native_rows = []
                    while True:
                        try:
                            native_item = next(native_iterator)
                        except StopIteration:
                            break
                        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
                            break
                        native_row = safe_mapping_dict(native_item)
                        if native_row is not None:
                            native_rows.append(native_row)
                    if native_rows:
                        rows = native_rows
            break
        row = safe_mapping_dict(item)
        if row is not None:
            rows.append(row)
    return rows


def safe_mapping_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        try:
            return {key: child for key, child in dict.items(value)}
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            return None
    if not isinstance(value, Mapping):
        return None
    items = safe_mapping_items(value)
    if not items:
        try:
            if len(value) == 0:
                return {}
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            pass
        return None
    return {key: child for key, child in items}


def safe_sequence_items(value: Any) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    items = []
    iterator = _sequence_iterator(value)
    if iterator is None:
        return items
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            break
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            if not used_native:
                native_iterator = _native_sequence_iterator(value)
                if native_iterator is not None:
                    native_items = []
                    while True:
                        try:
                            native_item = next(native_iterator)
                        except StopIteration:
                            break
                        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
                            break
                        native_items.append(native_item)
                    if native_items:
                        items = native_items
            break
        items.append(item)
    return items


def safe_mapping_items(value: Any) -> list[tuple[Any, Any]]:
    if not isinstance(value, Mapping):
        return []
    used_native = False
    try:
        raw_items = value.items()
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        if isinstance(value, dict):
            try:
                raw_items = dict.items(value)
            except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
                return []
            used_native = True
        else:
            key_items = _mapping_key_items(value)
            if key_items:
                return key_items
            try:
                raw_items = Mapping.items(value)
            except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
                return []
    try:
        iterator = iter(raw_items)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        if not isinstance(value, dict):
            key_items = _mapping_key_items(value)
            if key_items:
                return key_items
            return []
        try:
            iterator = iter(dict.items(value))
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return []
        used_native = True
    items = []
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            return items
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            if used_native:
                return items
            if not isinstance(value, dict):
                key_items = _mapping_key_items(value)
                if key_items:
                    return key_items
                return items
            try:
                native_iterator = iter(dict.items(value))
            except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
                return items
            native_items = []
            while True:
                try:
                    native_item = next(native_iterator)
                except StopIteration:
                    break
                except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
                    break
                try:
                    native_key, native_child = native_item
                except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
                    continue
                native_items.append((native_key, native_child))
            if native_items:
                return native_items
            return items
        if isinstance(item, (str, bytes, bytearray)):
            continue
        try:
            key, child = item
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            continue
        try:
            hash(key)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            continue
        items.append((key, child))


def _mapping_key_items(value: Mapping[Any, Any]) -> list[tuple[Any, Any]]:
    items = []
    try:
        iterator = iter(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return items
    while True:
        try:
            key = next(iterator)
        except StopIteration:
            break
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            break
        try:
            hash(key)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            continue
        try:
            child = value[key]
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            continue
        items.append((key, child))
    return items


def _sequence_iterator(value: list[Any] | tuple[Any, ...]):
    try:
        return iter(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return _native_sequence_iterator(value)
    return None


def _native_sequence_iterator(value: list[Any] | tuple[Any, ...]):
    try:
        if isinstance(value, list):
            return list.__iter__(value)
        if isinstance(value, tuple):
            return tuple.__iter__(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    return None


__all__ = [
    "mapping_field",
    "safe_dict_list",
    "safe_mapping_dict",
    "safe_int",
    "safe_mapping_items",
    "safe_sequence_items",
    "safe_text",
    "safe_text_list",
]
