"""Safe value helpers shared by data trust audit and scoring."""

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal
from numbers import Real
from typing import Any

from mapping_fields import safe_int, safe_mapping_dict, safe_sequence_items, safe_text


def list_count(value: Any) -> int:
    return len([item for item in safe_sequence_items(value) if has_value(item)])


def has_value(value: Any) -> bool:
    if value is None or isinstance(value, (bool, bytes, bytearray, memoryview, complex)):
        return False
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, Real):
        try:
            numeric_value = float(value)
        except (OverflowError, TypeError, ValueError):
            return False
        return math.isfinite(numeric_value)
    if isinstance(value, str):
        text = value.strip()
        return bool(text) and text.upper() not in {
            "N/A", "NA", "NONE", "NULL", "NIL", "MISSING", "-", "--",
            "NAN", "INF", "+INF", "-INF", "INFINITY", "+INFINITY", "-INFINITY",
        }
    if isinstance(value, (set, frozenset)):
        return any(has_value(item) for item in set_items(value))
    if isinstance(value, (list, tuple)):
        return any(has_value(item) for item in safe_sequence_items(value))
    if isinstance(value, Mapping):
        value_map = safe_mapping_dict(value)
        if value_map is None:
            return False
        return any(has_value(child) for child in value_map.values())
    return True


def string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [
            text
            for item in safe_sequence_items(value)
            if (text := safe_list_text(item))
        ]
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (bool, int, float)) and not value:
        return []
    text = safe_list_text(value)
    return [text] if text else []


def safe_list_text(value: Any) -> str:
    if isinstance(value, Decimal) and not value.is_finite():
        return ""
    if isinstance(value, Real) and not isinstance(value, bool):
        try:
            numeric_value = float(value)
        except (OverflowError, TypeError, ValueError):
            return ""
        if not math.isfinite(numeric_value):
            return ""
    if isinstance(value, str) and not has_value(value):
        return ""
    return safe_text_value(value).strip()


def set_items(value: Any) -> list[Any]:
    if not isinstance(value, (set, frozenset)):
        return []
    try:
        iterator = iter(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        iterator = native_set_iterator(value)
        if iterator is None:
            return []
    items = []
    while True:
        try:
            items.append(next(iterator))
        except StopIteration:
            return items
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            native_iterator = native_set_iterator(value)
            if native_iterator is None or native_iterator is iterator:
                return items
            return _collect_set_items(native_iterator)


def _collect_set_items(iterator: Any) -> list[Any]:
    native_items = []
    while True:
        try:
            native_items.append(next(iterator))
        except StopIteration:
            return native_items
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            return native_items


def native_set_iterator(value: Any):
    try:
        if isinstance(value, frozenset):
            return frozenset.__iter__(value)
        if isinstance(value, set):
            return set.__iter__(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return None
    return None


def safe_text_value(value: Any) -> str:
    return safe_text(value)


def safe_int_value(value: Any) -> int:
    return safe_int(value)


def safe_bool_value(value: Any) -> bool:
    if isinstance(value, (bytes, bytearray, memoryview, complex)):
        return False
    if isinstance(value, Mapping) or isinstance(value, (list, tuple, set, frozenset)):
        return False
    if isinstance(value, Decimal):
        if not value.is_finite():
            return False
        if value == 0:
            return False
        if value == 1:
            return True
        return False
    if isinstance(value, Real) and not isinstance(value, bool):
        try:
            numeric_value = float(value)
        except (OverflowError, TypeError, ValueError):
            return False
        if not math.isfinite(numeric_value):
            return False
        if value == 0:
            return False
        if value == 1:
            return True
        return False
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"", "0", "false", "no", "off", "none", "null"}:
            return False
        if text in {"1", "true", "yes", "on"}:
            return True
        try:
            numeric_text = Decimal(text)
        except (ArithmeticError, ValueError):
            return False
        if not numeric_text.is_finite():
            return False
        if numeric_text == 0:
            return False
        if numeric_text == 1:
            return True
        return False
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return False
