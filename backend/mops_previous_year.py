"""Strictly bounded prior-year selection, never a generic empty-HTML detector."""
from datetime import date, datetime
from hashlib import sha256
import math
from zoneinfo import ZoneInfo

POLICY = 'mops-published-presentation-previous-year-v1'
# Two independent issuer requests returned this identical official no-results
# template. Its malformed closing tags are NOT accepted as a populated table.
EMPTY_SHA256 = '87e52938f7b40c03e624eb4838fec6b506f1b61eb0fdd03fb54fdf0dabdb84c9'


def exact_no_results(raw):
    return (isinstance(raw, bytes) and len(raw) == 2593
            and sha256(raw).hexdigest() == EMPTY_SHA256)


def eligible_previous(selected, current_year, observed_at):
    try:
        if (not isinstance(selected, dict) or type(current_year) is not int
                or type(observed_at) not in (int, float)
                or not math.isfinite(observed_at) or observed_at <= 0):
            return False
        today = datetime.fromtimestamp(observed_at, ZoneInfo('Asia/Taipei')).date()
        start = date.fromisoformat(selected['event_date'])
        end = date.fromisoformat(selected['event_end_date'])
        return (today.year == current_year and start.year == end.year == current_year - 1
                and start <= end <= today and 0 <= (today - start).days <= 370)
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return False
