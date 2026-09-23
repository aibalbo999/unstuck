"""Resolve dividend yield using explicit units or a compatible legacy % label.

Never infer a raw unit from numeric magnitude or dividend/price periods.
Margins and payout ratios have separate contracts and do not use this adapter.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation

_DISPLAY = re.compile(r'^\s*([+]?[0-9]+(?:\.[0-9]+)?)\s*[%％]\s*$')


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value) if math.isfinite(value) and value >= 0 else None
    except OverflowError:
        return None


def dividend_yield_pct(data: dict) -> float | None:
    """Percentage points, or None when source unit/value evidence conflicts."""
    if not isinstance(data, dict):
        return None
    raw = _number(dict.get(data, 'dividend_yield_raw'))
    label = dict.get(data, 'dividend_yield')
    display = _DISPLAY.fullmatch(label) if isinstance(label, str) else None
    displayed = float(display[1]) if display else None
    if displayed is not None and not math.isfinite(displayed):
        return None

    def consistent(value):
        if display is None:
            return label is None or str(label).strip().upper() in {'', 'N/A', 'NA'}
        try:
            # Respect the legacy formatted label's actual displayed precision.
            quantum = Decimal(1).scaleb(-len(display[1].partition('.')[2]))
            return abs(Decimal(str(value)) - Decimal(display[1])) <= quantum / 2
        except InvalidOperation:
            return False

    if 'dividend_yield_raw_unit' in data:
        unit = dict.get(data, 'dividend_yield_raw_unit')
        if raw is None or not isinstance(unit, str) or unit not in {'ratio', 'percentage_points'}:
            return None
        value = raw * 100 if unit == 'ratio' else raw
        return round(value, 4) if math.isfinite(value) and consistent(value) else None
    if display is None:
        return None
    # A legacy percent label is the unit evidence. Raw must support that label
    # under a declared historical representation, not merely be "small enough".
    if 'dividend_yield_raw' in data and (raw is None or not any(consistent(v) for v in (raw, raw * 100))):
        return None
    return round(displayed, 4)
