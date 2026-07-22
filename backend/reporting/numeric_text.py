"""Numeric text parsing helpers for report presentation layers."""

from __future__ import annotations

import math
import re
from typing import Any

from mapping_fields import safe_text
from numeric_safety import is_non_finite_number


NUMERIC_TOKEN_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def first_finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or is_non_finite_number(value):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    match = NUMERIC_TOKEN_RE.search(safe_text(value).replace(",", ""))
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if math.isfinite(number) else None
