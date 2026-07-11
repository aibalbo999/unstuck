"""Shared dict-native field reads for upstream payload shaping."""

from __future__ import annotations

from typing import Any


def mapping_field(row: dict[str, Any], key: str, default: Any = None) -> Any:
    return dict.get(row, key, default)


def safe_text(value: Any) -> str:
    try:
        return "" if value is None else str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ""


def safe_int(value: Any) -> int:
    try:
        return int(0 if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0


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
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            if not texts and not used_native:
                native_iterator = _native_sequence_iterator(value)
                if native_iterator is not None:
                    iterator = native_iterator
                    used_native = True
                    continue
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
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            if not rows and not used_native:
                native_iterator = _native_sequence_iterator(value)
                if native_iterator is not None:
                    iterator = native_iterator
                    used_native = True
                    continue
            break
        if isinstance(item, dict):
            rows.append(item)
    return rows


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
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            if not items and not used_native:
                native_iterator = _native_sequence_iterator(value)
                if native_iterator is not None:
                    iterator = native_iterator
                    used_native = True
                    continue
            break
        items.append(item)
    return items


def safe_mapping_items(value: Any) -> list[tuple[Any, Any]]:
    if not isinstance(value, dict):
        return []
    used_native = False
    try:
        raw_items = value.items()
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        try:
            raw_items = dict.items(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return []
        used_native = True
    try:
        iterator = iter(raw_items)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
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
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            if items or used_native:
                return items
            try:
                iterator = iter(dict.items(value))
            except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
                return items
            used_native = True
            continue
        try:
            key, child = item
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            continue
        items.append((key, child))


def _sequence_iterator(value: list[Any] | tuple[Any, ...]):
    try:
        return iter(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
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
    "safe_int",
    "safe_mapping_items",
    "safe_sequence_items",
    "safe_text",
    "safe_text_list",
]
