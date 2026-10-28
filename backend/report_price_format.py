"""Numeric research-price display shared by prose, summaries and evidence rows."""
from decimal import Decimal
import math

POLICY = 'report-price-display:v1-preserve-fraction'


def format_report_price(value):
    if value is None or isinstance(value, bool):
        return 'N/A'
    try:
        number = float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return 'N/A'
    if not math.isfinite(number) or number <= 0:
        return 'N/A'
    whole, _, fraction = format(Decimal(str(number)), ',f').partition('.')
    fraction = fraction.rstrip('0')
    return 'NT$' + whole + ('.' + fraction.ljust(2, '0') if fraction else '')
