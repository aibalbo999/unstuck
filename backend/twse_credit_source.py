"""Dated TWSE margin report; never infer its date from the borrowed-short feed."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import time
from zoneinfo import ZoneInfo

from source_observation_freshness import parse_observation_date

URL = 'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&selectType=ALL'
SOURCE = 'TWSE MI_MARGN dated report'
PARSER_VERSION = 'twse-margin-dated-v1'
_FIELDS = ['代號', '名稱', '買進', '賣出', '現金償還', '前日餘額', '今日餘額', '次一營業日限額',
           '買進', '賣出', '現券償還', '前日餘額', '今日餘額', '次一營業日限額', '資券互抵', '註記']
_GROUPS = [('股票', 2), ('融資', 6), ('融券', 6), ('', 1), ('', 1)]
_QUANTITIES = {'margin_purchase': 2, 'margin_sale': 3, 'margin_cash_repayment': 4,
               'margin_previous_balance': 5, 'margin_balance': 6, 'short_purchase': 8,
               'short_sale': 9, 'short_cash_repayment': 10, 'short_previous_balance': 11,
               'short_balance': 12, 'offset': 14}


def _report(payload):
    if not isinstance(payload, dict) or payload.get('stat') != 'OK':
        raise ValueError('Unsuccessful dated margin response')
    day = parse_observation_date(payload.get('date'))
    if day is None or day > datetime.now(ZoneInfo('Asia/Taipei')).date():
        raise ValueError('Missing or future margin observation date')
    tables = payload.get('tables')
    if not isinstance(tables, list):
        raise ValueError('Missing margin tables')
    matches = [table for table in tables if isinstance(table, dict) and table.get('fields') == _FIELDS]
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous margin field contract')
    table = matches[0]
    groups = table.get('groups')
    if (not isinstance(groups, list) or not all(isinstance(g, dict) and type(g.get('span')) is int for g in groups)
            or [(g.get('title'), g.get('span')) for g in groups] != _GROUPS):
        raise ValueError('Unknown margin column groups')
    rows = table.get('data')
    if not isinstance(rows, list):
        raise ValueError('Missing margin rows')
    return {'as_of_date': day.isoformat(), 'rows': rows}


def _quantity(value):
    if value is None or (isinstance(value, str) and value.strip() in {'', '-', '--'}):
        return None
    if isinstance(value, bool):
        raise ValueError('Boolean margin quantity')
    try:
        number = Decimal(str(value).strip().replace(',', ''))
    except InvalidOperation as exc:
        raise ValueError('Invalid margin quantity') from exc
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise ValueError('Non-finite, negative or fractional margin quantity')
    return int(number)


def _fetch_report(http_get, timeout):
    """A new dated endpoint respects persistent Retry-After before fallback."""
    from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                         record_observation, remember_failure, scope_key)
    key = scope_key(SOURCE, endpoint='margin_report')
    started = time.monotonic()
    blocked = cooldown_state(key)
    if blocked:
        record_observation(SOURCE, started, outcome='cooldown', source='chip_data', details=blocked, sent=False)
        raise SourceResponseError(blocked.get('error_kind', 'cooldown'), status_code=blocked.get('http_status'))
    observe_http_response(None)
    try:
        response = http_get(URL, session=None, timeout=timeout, provider=SOURCE)
        observe_http_response(response)
        report = _report(response.json())
    except Exception as exc:
        details = {**remember_failure(key, exc), 'parser_version': PARSER_VERSION}
        record_observation(SOURCE, started, outcome='failure', source='chip_data', details=details)
        raise
    record_observation(SOURCE, started, outcome='results' if report['rows'] else 'valid_empty',
                       count=len(report['rows']), source='chip_data',
                       details={'http_status': getattr(response, 'status_code', None), 'parser_version': PARSER_VERSION})
    return report


def fetch_twse_dated_margin(code, *, http_get, session=None, timeout=15, use_cache=True):
    """Use one validated all-stock response for five minutes, then retry failures.

    Explicit test/client sessions are uncached. The shared cache preserves the
    acquisition timestamp and does not retain stale data past its fresh window.
    """
    base = {'ticker': code, 'source': SOURCE, 'source_url': URL}
    try:
        def fetch():
            return _report(http_get(URL, session=session, timeout=timeout, provider=SOURCE).json())

        if session is None:
            from shared_provider_cache import shared_fetch
            report, meta = shared_fetch('twse-margin-dated:v1', lambda: _fetch_report(http_get, timeout), freshness_seconds=300,
                                        retention_seconds=300, error_retry_seconds=60, use_cache=use_cache)
            if meta.get('error_kind') or not report:
                return {**base, 'status': 'unavailable', 'reason_code': 'dated_fetch_failed'}
        else:
            report, meta = fetch(), {}
        rows = [row for row in report['rows'] if isinstance(row, list) and row and str(row[0]).strip() == code]
        if len(rows) != 1:
            return {**base, 'status': 'unavailable',
                    'reason_code': 'record_not_found' if not rows else 'ambiguous_records'}
        row = rows[0]
        if len(row) != len(_FIELDS):
            raise ValueError('Incomplete margin row')
        quantities = {key: _quantity(row[index]) for key, index in _QUANTITIES.items()}
        if not any(value is not None for value in quantities.values()):
            return {**base, 'status': 'unavailable', 'reason_code': 'quantities_unavailable'}
        complete = all(quantities[key] is not None for key in ('margin_balance', 'short_balance'))
        return {**base, 'status': 'success' if complete else 'partial', 'company_name': str(row[1]), **quantities,
                'reason_code': 'complete_balances' if complete else 'core_balances_missing',
                'as_of_date': report['as_of_date'], 'margin_as_of_date': report['as_of_date'],
                'margin_date_status': 'reported', 'margin_unit': 'lots',
                'margin_unit_basis': 'TWSE MI_MARGN 融資／融券交易單位（張），未進行股數換算',
                'margin_cache_hit': bool(meta.get('cache_hit')),
                'margin_fetched_at_epoch': meta.get('fetched_at_epoch')}
    except Exception:
        return {**base, 'status': 'unavailable', 'reason_code': 'dated_fetch_failed'}
