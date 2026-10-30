"""Bounded exact-day subgroup records from saved provider observations.

No totals, missing categories, sessions or acquisitions are inferred here.
Appending these records keeps existing source-reference indexes unchanged.
"""
from collections import defaultdict
from datetime import date
import math

DAILY_CATEGORY_PATH_PREFIX = 'institutional_trading.daily_category_observations['
_SOURCES = {'FinMind TaiwanStockInstitutionalInvestorsBuySell', 'TWSE T86', 'TPEx dailyTrade', 'TPEx institutional OpenAPI'}
_CATEGORIES = {'foreign', 'investment_trust', 'dealer'}


def _day(value):
    if not isinstance(value, str):
        return None
    try:
        return value if date.fromisoformat(value).isoformat() == value else None
    except ValueError:
        return None


def daily_category_records(raw, *, ticker=None):
    rows = raw.get('daily_category_observations')
    dates = raw.get('observation_dates')
    latest = _day(raw.get('latest_date'))
    source = raw.get('source')
    if (not isinstance(rows, list) or not 1 <= len(rows) <= 300
            or not isinstance(dates, list) or not 1 <= len(dates) <= 100
            or any(_day(day) is None for day in dates) or len(set(dates)) != len(dates)
            or latest != max(dates) or not isinstance(source, str)):
        return []
    providers = set(source.split(' + '))
    if not providers or not providers.issubset(_SOURCES):
        return []
    if 'TPEx institutional OpenAPI' in providers:
        from institutional_openapi_evidence import openapi_rows_bound
        if not openapi_rows_bound(raw,ticker):
            return []
    if 'observed_date_count' in raw and (type(raw['observed_date_count']) is not int
                                        or raw['observed_date_count'] != len(dates)):
        return []
    selected_dates = set(sorted(dates)[-10:])
    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        if (isinstance(row, dict) and isinstance(row.get('date'), str)
                and row['date'] in selected_dates and isinstance(row.get('category'), str)
                and row['category'] in _CATEGORIES):
            # An invalid duplicate still makes this date/population ambiguous.
            grouped[(row['date'], row['category'])].append((index, row))
    records = []
    for (observed, population), candidates in grouped.items():
        if len(candidates) != 1:
            continue
        index, row = candidates[0]
        value, provider = row.get('net_buy_shares'), row.get('source')
        if (type(value) not in (int, float) or row.get('unit') != 'shares'
                or not isinstance(provider, str) or provider not in providers):
            continue
        try:
            if not math.isfinite(value) or int(value) != value:
                continue
        except OverflowError:
            continue
        records.append({'path': f'{DAILY_CATEGORY_PATH_PREFIX}{index}].net_buy_shares',
                        'value': value, 'unit': 'shares', 'population': population,
                        'window': {'kind': 'day', 'date': observed},
                        'observed_at': observed, 'provider': provider})
    return records
