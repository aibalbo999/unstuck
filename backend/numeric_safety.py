"""Shared numeric guards for text rendering and payload normalization."""

from __future__ import annotations

import math
from decimal import Decimal
from numbers import Real
from typing import Any


def is_non_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, Decimal):
        try:
            return not value.is_finite()
        except (ArithmeticError, AttributeError, RuntimeError, TypeError, ValueError):
            return True
    if isinstance(value, Real):
        try:
            return not math.isfinite(float(value))
        except (OverflowError, TypeError, ValueError):
            return True
    return False


__all__ = ["is_non_finite_number"]
