"""TPEx OpenAPI margin balances; field contract verified against its official schema."""
from datetime import date
import re
import time

URL = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance'
SOURCE = 'TPEx OpenAPI tpex_mainboard_margin_balance'
# Official OpenAPI field identities; volume unit corroborated by TPEx EDIS S23.
_FIELDS = {'margin_previous_balance':'MarginPurchaseBalancePreviousDay',
           'margin_purchase':'MarginPurchase','margin_sale':'MarginSales',
           'margin_cash_repayment':'CashRedemption','margin_balance':'MarginPurchaseBalance',
           'short_previous_balance':'ShortSaleBalancePreviousDay','short_sale':'ShortSale',
           'short_purchase':'ShortConvering','short_cash_repayment':'StockRedemption',
           'short_balance':'ShortSaleBalance','offset':'Offsetting'}


def _date(value):
    text = str(value or '')
    try:
        if re.fullmatch(r'\d{7}',text):
            return date(int(text[:3])+1911,int(text[3:5]),int(text[5:])).isoformat()
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _fetch_report(http_get, timeout):
    from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                         record_observation, remember_failure, scope_key, error_details)
    key = scope_key(SOURCE, endpoint='margin_balance')
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
            rows = response.json()
            if not isinstance(rows, list) or any(not isinstance(row, dict) or
                    not {'Date', 'SecuritiesCompanyCode'} <= row.keys() for row in rows):
                raise ValueError('Invalid TPEx margin response')
        except Exception as exc:
            record_observation(SOURCE, started, outcome='failure', source='chip_data',
                               details={**(remember_failure(key, exc) if owns() else {**error_details(exc), 'state_write_skipped': 'lease_lost'}), 'parser_version': 'tpex-margin-v1'})
            raise
        reset_failure_history_after_success(key, observed_failure_state, owns=owns)
        record_observation(SOURCE, started, outcome='results' if rows else 'valid_empty', count=len(rows),
                           source='chip_data', details={'http_status': getattr(response, 'status_code', None),
                                                       'parser_version': 'tpex-margin-v1'})
        return rows


def fetch_tpex_margin(code, *, http_get, parse_int, session=None, timeout=20, use_cache=True):
    base = {'ticker':code,'source':SOURCE,'source_url':URL,'market':'TPEX'}
    try:
        if session is None:
            from shared_provider_cache import shared_fetch
            rows, meta = shared_fetch('tpex-margin:v1', lambda: _fetch_report(http_get, timeout),
                                      freshness_seconds=300, retention_seconds=300, error_retry_seconds=60,
                                      use_cache=use_cache)
            if meta.get('error_kind') or rows is None:
                return {**base, 'status': 'unavailable', 'reason_code': 'fetch_failed'}
        else:
            rows, meta = http_get(URL,session=session,timeout=timeout,provider=SOURCE).json(), {}
        matches = [row for row in rows if isinstance(row,dict) and str(row.get('SecuritiesCompanyCode')).strip()==code] if isinstance(rows,list) else []
        if len(matches)!=1:
            return {**base,'status':'unavailable','reason_code':'record_not_found' if not matches else 'ambiguous_records',
                    'message':'上櫃來源未提供唯一可用的標的紀錄；不推定為零。'}
        row=matches[0];observed=_date(row.get('Date'))
        quantities={field:parse_int(row.get(raw_field)) for field,raw_field in _FIELDS.items()}
        if not any(value is not None for value in quantities.values()):
            return {**base,'status':'unavailable','reason_code':'quantities_unavailable',
                    'as_of_date':observed,'message':'上櫃來源有標的紀錄，但未提供可用融資券數值。'}
        return {**base,'status':'success','company_name':str(row.get('CompanyName') or ''),
                'as_of_date':observed,'margin_as_of_date':observed,'margin_date_status':'reported' if observed else 'unknown',
                'margin_unit':'thousand_shares','unit_basis':'TPEx EDIS S23 margin field units',
                'margin_cache_hit':bool(meta.get('cache_hit')),'margin_fetched_at_epoch':meta.get('fetched_at_epoch'),
                **quantities,
                'borrowed_short_status':'unavailable','borrowed_short_reason_code':'not_in_margin_endpoint'}
    except Exception:
        return {**base,'status':'unavailable','reason_code':'fetch_failed','message':'上櫃融資券來源連線或格式失敗。'}
