"""Format observed FinMind monthly amounts, including explicit zero values."""
from decimal import Decimal, InvalidOperation
import math


def format_monthly_revenue_rows(frame) -> list[str]:
    """Keep the existing last-six-row window; missing values are never zero."""
    if frame is None or frame.empty:
        return []
    records = []
    for _, row in frame.tail(6).iterrows():
        try:
            # String conversion also rejects Python/numpy booleans rather than
            # accepting their numeric 0/1 coercion. It preserves SDK decimals.
            year, month, amount = (Decimal(str(row.get(key))) for key in
                                   ('revenue_year', 'revenue_month', 'revenue'))
            if not all(value.is_finite() for value in (year, month, amount)):
                continue
            if (year != year.to_integral_value() or month != month.to_integral_value()
                    or not 1 <= year <= 9999 or not 1 <= month <= 12):
                continue
            value = float(amount)
            if not math.isfinite(value):
                continue
        except (InvalidOperation, ValueError, TypeError, OverflowError):
            continue
        records.append(f'{int(year)}年{int(month)}月: NT${value / 1e8:.2f}億')
    return records
