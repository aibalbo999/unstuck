"""Scalar coercion helpers for analysis job public payloads."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from typing import Any


def _safe_bool_flag(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return default
    if isinstance(value, Mapping) or isinstance(value, (list, tuple, set, frozenset)):
        return default
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"", "0", "false", "no", "off", "none", "null"}:
            return False
        return default
    if isinstance(value, complex):
        return default
    if isinstance(value, Decimal):
        try:
            if not value.is_finite():
                return default
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
        if value == 1:
            return True
        if value == 0:
            return False
        return default
    if isinstance(value, Fraction):
        if value == 1:
            return True
        if value == 0:
            return False
        return default
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
        if not math.isfinite(number):
            return default
        if number == 1:
            return True
        if number == 0:
            return False
        return default
    return default


def _safe_int(value: Any, *, default: int = 0) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return default
    if isinstance(value, int):
        return value if value >= 0 else default
    if isinstance(value, Fraction):
        if value.denominator != 1 or value < 0:
            return default
        try:
            return int(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
    if isinstance(value, Decimal):
        try:
            if not value.is_finite():
                return default
            integral = value.to_integral_value()
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
        if value != integral or integral < 0:
            return default
        try:
            return int(integral)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer() or value < 0:
            return default
        try:
            return int(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
    if isinstance(value, str):
        try:
            integer = int(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
        return integer if integer >= 0 else default
    return default


def _safe_optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, (bool, bytes, bytearray, memoryview)):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, Fraction):
        if value.denominator != 1 or value < 0:
            return None
        try:
            return int(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return None
    if isinstance(value, Decimal):
        try:
            if not value.is_finite():
                return None
            integral = value.to_integral_value()
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return None
        if value != integral or integral < 0:
            return None
        try:
            return int(integral)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return None
    if not isinstance(value, (float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    if not math.isfinite(number) or not number.is_integer() or number < 0:
        return None
    try:
        return int(number)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None


def _safe_bool_field(value: Any) -> bool:
    return _safe_bool_flag(value, default=False)


def _iso_timestamp(value: Any) -> str | None:
    if value is None or isinstance(value, (bool, bytes, bytearray, memoryview)):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    if not isinstance(value, (int, float, str, Decimal, Fraction)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    if not math.isfinite(number):
        return None
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None
