"""TPEx credit-control report: borrowed shorts are distinct from margin shorts.

The official page reports shares and updates around 20:30 and 22:30 Taipei time.
Its observation date is never inferred from the independently fetched margin feed.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
import time
from zoneinfo import ZoneInfo

URL = 'https://www.tpex.org.tw/openapi/v1/tpex_margin_sbl'
SOURCE = 'TPEx OpenAPI tpex_margin_sbl'
PARSER_VERSION = 'tpex-borrowed-short-v1'
_FIELDS = {'borrowed_short_previous_balance': 'SecuritiesBorrowingBalancePreviousDay',
           'borrowed_short_sale_today': 'SecuritiesBorrowingSale',
           'borrowed_short_return_today': 'SecuritiesBorrowingReturn',
           'borrowed_short_adjustment_today': 'SecuritiesBorrowingAdjustment',
           'borrowed_short_sale_balance': 'SecuritiesBorrowingBalanceOfTheMarketDay',
           'borrowed_short_next_session_limit': 'AvailableVolumesForSBLShortSale'}


def _quantity(value, *, signed=False):
    if value is None or str(value).strip() in {'', '-', '--'}:
        return None
    if isinstance(value, bool):
        raise ValueError('Boolean quantity')
    try:
        number = Decimal(str(value).strip().replace(',', ''))
    except InvalidOperation as exc:
        raise ValueError('Invalid quantity') from exc
    if not number.is_finite() or number != number.to_integral_value() or (not signed and number < 0):
        raise ValueError('Invalid quantity')
    return int(number)


def _day(value):
    text = str(value or '').strip()
    try:
        result = (date(int(text[:3]) + 1911, int(text[3:5]), int(text[5:]))
                  if re.fullmatch(r'\d{7}', text) else date.fromisoformat(text))
    except ValueError:
        return None
    return result.isoformat() if result <= datetime.now(ZoneInfo('Asia/Taipei')).date() else None


def _report(payload):
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise ValueError('Invalid TPEx borrowed-short payload')
    if payload and not all({'Date', 'SecuritiesCompanyCode', *_FIELDS.values()} <= row.keys() for row in payload):
        raise ValueError('Unknown TPEx borrowed-short schema')
    return payload


def _fetch_report(http_get, timeout):
    from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                         record_observation, remember_failure, scope_key, error_details)
    key = scope_key(SOURCE, endpoint='borrowed_short')
    started = time.monotonic()
    from search_admission import endpoint_admission
    timeout = max(0.001, min(float(timeout), 5))
    with endpoint_admission(key, timeout_seconds=timeout) as owns:
        if owns is None:
            record_observation(SOURCE, started, outcome='busy', source='chip_data',
                               details={'error_kind': 'single_flight_busy'}, sent=False)
            raise SourceResponseError('single_flight_busy')
        blocked = cooldown_state(key)
        if blocked:
            record_observation(SOURCE, started, outcome='cooldown', source='chip_data', details=blocked, sent=False)
            raise SourceResponseError(blocked.get('error_kind', 'cooldown'), status_code=blocked.get('http_status'))
        from official_source_runtime import failure_state_snapshot, reset_failure_history_after_success
        observed_failure_state = failure_state_snapshot(key)
        if observed_failure_state is None:
            record_observation(SOURCE, started, outcome='unavailable', source='chip_data',
                               details={'error_kind': 'guard_storage_unavailable'}, sent=False)
            raise SourceResponseError('guard_storage_unavailable')
        observe_http_response(None)
        try:
            response = http_get(URL, session=None, timeout=timeout, provider=SOURCE)
            observe_http_response(response)
            rows = _report(response.json())
        except Exception as exc:
            details = {**(remember_failure(key, exc) if owns() else {**error_details(exc), 'state_write_skipped': 'lease_lost'}), 'parser_version': PARSER_VERSION}
            record_observation(SOURCE, started, outcome='failure', source='chip_data', details=details)
            raise
        reset_failure_history_after_success(key, observed_failure_state, owns=owns)
        record_observation(SOURCE, started, outcome='results' if rows else 'valid_empty', count=len(rows),
                           source='chip_data', details={'http_status': getattr(response, 'status_code', None),
                                                       'parser_version': PARSER_VERSION})
        return rows


def fetch_tpex_borrowed_short(code, *, http_get, session=None, timeout=15, use_cache=True):
    base = {'borrowed_short_source': SOURCE, 'borrowed_short_source_url': URL,
            'borrowed_short_unit': 'shares', 'borrowed_short_unit_basis': 'TPEx 信用額度總量管制餘額：單位股'}
    try:
        if session is None:
            from shared_provider_cache import shared_fetch
            rows, meta = shared_fetch('tpex-borrowed-short:v1', lambda: _fetch_report(http_get, timeout),
                                      freshness_seconds=300, retention_seconds=300, error_retry_seconds=60,
                                      use_cache=use_cache)
            if meta.get('error_kind') or rows is None:
                return {**base, 'borrowed_short_status': 'unavailable', 'borrowed_short_reason_code': 'fetch_failed'}
        else:
            rows, meta = _report(http_get(URL, session=session, timeout=timeout, provider=SOURCE).json()), {}
        matches = [row for row in rows if str(row.get('SecuritiesCompanyCode')).strip() == code]
        if len(matches) != 1:
            return {**base, 'borrowed_short_status': 'unavailable',
                    'borrowed_short_reason_code': 'record_not_found' if not matches else 'ambiguous_records'}
        row = matches[0]
        observed = _day(row.get('Date'))
        if observed is None:
            return {**base, 'borrowed_short_status': 'unavailable', 'borrowed_short_reason_code': 'invalid_observation_date'}
        quantities = {field: _quantity(row.get(raw), signed=field == 'borrowed_short_adjustment_today')
                      for field, raw in _FIELDS.items()}
        if quantities['borrowed_short_sale_balance'] is None:
            return {**base, 'borrowed_short_status': 'unavailable', 'borrowed_short_reason_code': 'balance_unavailable',
                    'borrowed_short_as_of_date': observed}
        components = [quantities[field] for field in ('borrowed_short_previous_balance',
                      'borrowed_short_sale_today', 'borrowed_short_return_today', 'borrowed_short_adjustment_today')]
        if all(value is not None for value in components):
            previous, sold, returned, adjustment = components
            if previous + sold - returned + adjustment != quantities['borrowed_short_sale_balance']:
                return {**base, 'borrowed_short_status': 'unavailable',
                        'borrowed_short_reason_code': 'balance_reconciliation_failed',
                        'borrowed_short_as_of_date': observed}
        # Retain the official trading-state note; absence of a row is not a zero balance.
        return {**base, **quantities, 'borrowed_short_status': 'success',
                'borrowed_short_reason_code': 'reported_balance',
                'borrowed_short_as_of_date': observed, 'borrowed_short_date_status': 'reported',
                'borrowed_short_trading_note': str(row.get('Note') or ''),
                'borrowed_short_cache_hit': bool(meta.get('cache_hit')),
                'borrowed_short_fetched_at_epoch': meta.get('fetched_at_epoch')}
    except Exception:
        return {**base, 'borrowed_short_status': 'unavailable', 'borrowed_short_reason_code': 'fetch_or_parse_failed'}
