"""Iterator-safe sequence helpers for mapping payload sanitation."""

from __future__ import annotations

from typing import Any


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
