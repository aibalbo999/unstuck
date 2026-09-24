"""Official dated margin rows, with explicit fallback and independent source dates."""
from copy import deepcopy

import pytest

from chip_data_fetcher import fetch_twse_margin_short_sales
from test_chip_source_contract import Response


@pytest.fixture(autouse=True)
def endpoint_state(monkeypatch):
    import search_provider_runtime as runtime
    state = {}
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: None)
    return state


FIELDS = ['代號', '名稱', '買進', '賣出', '現金償還', '前日餘額', '今日餘額', '次一營業日限額',
          '買進', '賣出', '現券償還', '前日餘額', '今日餘額', '次一營業日限額', '資券互抵', '註記']
GROUPS = [{'title': '股票', 'span': 2}, {'title': '融資', 'span': 6}, {'title': '融券', 'span': 6},
          {'title': '', 'span': 1}, {'title': '', 'span': 1}]
ROW = ['2330', '台積電', '1,139', '215', '50', '28,833', '29,707', '6,483,092',
       '2', '0', '0', '18', '16', '6,483,092', '0', ' ']


def dated_payload():
    # Metadata and row observed at the official endpoint on 2026-09-25 (Taipei).
    return {'stat': 'OK', 'date': '20260924', 'tables': [
        {'fields': ['項目', '買進', '賣出', '現金(券)償還', '前日餘額', '今日餘額'], 'data': []},
        {'fields': list(FIELDS), 'groups': deepcopy(GROUPS), 'data': [list(ROW)]},
    ]}


class Session:
    def __init__(self, payload=None, *, error=False):
        self.payload = dated_payload() if payload is None else payload
        self.calls = []
        self.error = error

    def get(self, url, **kwargs):
        self.calls.append(url)
        if '/rwd/' in url and 'MI_MARGN' in url:
            if self.error:
                raise TimeoutError('dated endpoint timeout')
            return Response(self.payload)
        if 'openapi.twse' in url:
            return Response([{'股票代號': '2330', '融資今日餘額': '111', '融券今日餘額': '0'}])
        return Response({'date': '20260923', 'data': [['2330'] + [None] * 8 + ['0', None, None, '1000']]})


def test_dated_official_margin_is_used_without_openapi_or_borrowed_date():
    session = Session()
    result = fetch_twse_margin_short_sales('2330.TW', session=session)
    assert result['margin_as_of_date'] == '2026-09-24'
    assert result['as_of_date'] == '2026-09-24'
    assert result['margin_date_status'] == 'reported'
    assert result['margin_purchase'] == 1139
    assert result['margin_balance'] == 29707
    assert result['short_purchase'] == 2
    assert result['short_sale'] == 0
    assert result['short_balance'] == 16
    assert result['borrowed_short_as_of_date'] == '2026-09-23'
    assert result['source'] == 'TWSE MI_MARGN dated report'
    assert '/rwd/zh/marginTrading/MI_MARGN?' in result['source_url']
    assert result['margin_unit'] == 'lots'
    assert len(session.calls) == 2
    assert not any('openapi.twse' in url for url in session.calls)


@pytest.mark.parametrize('change', ['unknown_date', 'future_date', 'field_order', 'group_order',
                                  'no_stock', 'duplicate_stock', 'duplicate_table', 'short_row',
                                  'nan', 'inf', 'negative', 'fractional', 'boolean', 'all_missing'])
def test_invalid_dated_response_keeps_original_undated_fallback(change):
    value = dated_payload()
    table = value['tables'][1]
    if change == 'unknown_date': value.pop('date')
    elif change == 'future_date': value['date'] = '99991231'
    elif change == 'field_order': table['fields'][2], table['fields'][3] = table['fields'][3], table['fields'][2]
    elif change == 'group_order': table['groups'][1], table['groups'][2] = table['groups'][2], table['groups'][1]
    elif change == 'no_stock': table['data'][0][0] = '3702'
    elif change == 'duplicate_stock': table['data'].append(list(ROW))
    elif change == 'duplicate_table': value['tables'].append(deepcopy(table))
    elif change == 'short_row': table['data'][0].pop()
    elif change == 'all_missing': table['data'][0][2:15] = ['--'] * 13
    else: table['data'][0][6] = {'nan': 'NaN', 'inf': 'Infinity', 'negative': '-1',
                               'fractional': '1.2', 'boolean': True}[change]
    result = fetch_twse_margin_short_sales('2330.TW', session=Session(value))
    assert result['source'] == 'TWSE OpenAPI MI_MARGN'
    assert result['margin_as_of_date'] is None
    assert result['margin_date_status'] == 'unknown'
    assert result['margin_balance'] == 111
    assert result['short_balance'] == 0
    assert result['borrowed_short_as_of_date'] == '2026-09-23'
    assert result['dated_margin_fallback_reason']


def test_timeout_keeps_original_margin_data_available():
    result = fetch_twse_margin_short_sales('2330.TW', session=Session(error=True))
    assert result['status'] == 'success'
    assert result['margin_balance'] == 111
    assert result['margin_date_status'] == 'unknown'
    assert result['dated_margin_fallback_reason'] == 'dated_fetch_failed'


def test_dated_zero_and_missing_fields_remain_distinct():
    value = dated_payload()
    value['tables'][1]['data'][0][6] = '--'
    result = fetch_twse_margin_short_sales('2330.TW', session=Session(value))
    assert result['source'] == 'TWSE MI_MARGN dated report'
    assert result['margin_balance'] is None
    assert result['short_sale'] == 0


def test_all_stock_cache_reuses_acquisition_time_without_borrowing_dates(monkeypatch):
    import cache_store
    import chip_data_fetcher
    import shared_provider_cache
    from contextlib import nullcontext
    state, calls = {}, []
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(cache_store, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(shared_provider_cache, '_process_lock', lambda key: nullcontext(True))
    value = dated_payload()
    row = list(ROW); row[0] = '3702'; row[6] = '13,472'
    value['tables'][1]['data'].append(row)

    def get(url, **kwargs):
        calls.append(url)
        return Response(value if 'MI_MARGN' in url else {})

    monkeypatch.setattr(chip_data_fetcher, 'sync_get', get)
    first = fetch_twse_margin_short_sales('2330.TW')
    second = fetch_twse_margin_short_sales('3702.TW')
    assert first['margin_cache_hit'] is False
    assert second['margin_cache_hit'] is True
    assert first['margin_fetched_at_epoch'] == second['margin_fetched_at_epoch']
    assert first['margin_balance'] == 29707
    assert second['margin_balance'] == 13472
    assert first['margin_as_of_date'] == second['margin_as_of_date'] == '2026-09-24'
    assert sum('MI_MARGN' in url for url in calls) == 1
    cached = next(iter(state.values()))
    assert 299 <= cached['fresh_until_epoch'] - cached['fetched_at_epoch'] <= 301


def test_failed_dated_fetch_is_temporarily_coalesced_but_original_fallback_still_runs(monkeypatch):
    import cache_store
    import chip_data_fetcher
    import shared_provider_cache
    from contextlib import nullcontext
    state, calls = {}, []
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(cache_store, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(shared_provider_cache, '_process_lock', lambda key: nullcontext(True))

    def get(url, **kwargs):
        calls.append(url)
        if '/rwd/' in url and 'MI_MARGN' in url:
            raise TimeoutError('timeout')
        if 'openapi' in url:
            return Response([{'股票代號': '2330', '融資今日餘額': '111'}])
        return Response({})

    monkeypatch.setattr(chip_data_fetcher, 'sync_get', get)
    first = fetch_twse_margin_short_sales('2330.TW')
    second = fetch_twse_margin_short_sales('2330.TW')
    assert first['margin_balance'] == second['margin_balance'] == 111
    assert first['margin_as_of_date'] is second['margin_as_of_date'] is None
    assert sum('/rwd/' in url and 'MI_MARGN' in url for url in calls) == 1
    assert sum('openapi' in url for url in calls) == 2


def test_dated_endpoint_respects_retry_after_beyond_short_error_cache(monkeypatch):
    import cache_store
    import chip_data_fetcher
    import shared_provider_cache
    import httpx
    import time
    from contextlib import nullcontext
    state, calls = {}, []
    now = [time.time()]
    monkeypatch.setattr(time, 'time', lambda: now[0])
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(cache_store, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(shared_provider_cache, '_process_lock', lambda key: nullcontext(True))

    def get(url, **kwargs):
        calls.append(url)
        if '/rwd/' in url and 'MI_MARGN' in url:
            response = httpx.Response(429, headers={'Retry-After': '600'}, request=httpx.Request('GET', url))
            response.raise_for_status()
        return Response([{'股票代號': '2330', '融資今日餘額': '111'}] if 'openapi' in url else {})

    monkeypatch.setattr(chip_data_fetcher, 'sync_get', get)
    assert fetch_twse_margin_short_sales('2330.TW', use_cache=False)['margin_balance'] == 111
    now[0] += 61
    assert fetch_twse_margin_short_sales('2330.TW', use_cache=False)['margin_balance'] == 111
    assert sum('/rwd/' in url and 'MI_MARGN' in url for url in calls) == 1


def test_provider_force_refresh_bypasses_only_dated_data_cache(monkeypatch):
    import cache_store
    import chip_data_fetcher
    import shared_provider_cache
    from contextlib import nullcontext
    from data_fetch.agent_context_providers import ChipDataProvider
    from data_fetch.types import FetchRequest
    state, calls = {}, []
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(cache_store, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(shared_provider_cache, '_process_lock', lambda key: nullcontext(True))
    monkeypatch.setattr(chip_data_fetcher, 'fetch_tdcc_shareholder_distribution', lambda *a: {'status': 'unavailable'})

    def get(url, **kwargs):
        if 'MI_MARGN' in url:
            calls.append(url)
            value = dated_payload()
            value['tables'][1]['data'][0][6] = str(len(calls))
            return Response(value)
        return Response({})

    monkeypatch.setattr(chip_data_fetcher, 'sync_get', get)
    provider = ChipDataProvider()
    values = [provider.fetch(FetchRequest.from_ticker('2330.TW', force_refresh=force)).value
              for force in [False, False, True]]
    assert [v['twse_margin_short_sales']['margin_balance'] for v in values] == [1, 1, 2]
    assert len(calls) == 2


def test_offset_only_data_remains_partial_and_is_not_lost_without_other_components(monkeypatch):
    import chip_data_fetcher
    from data_fetch.agent_context_providers import ChipDataProvider
    from data_fetch.types import FetchRequest
    value = dated_payload()
    value['tables'][1]['data'][0][2:14] = ['--'] * 12
    # Retain a reported zero offset, never fabricate the two missing balances.
    original_fetch = chip_data_fetcher.fetch_twse_margin_short_sales
    monkeypatch.setattr(chip_data_fetcher, 'fetch_tdcc_shareholder_distribution', lambda *a: {'status': 'unavailable'})

    class PartialSession(Session):
        def get(self, url, **kwargs):
            if 'TWT93U' in url:
                return Response({})
            return super().get(url, **kwargs)

    monkeypatch.setattr(chip_data_fetcher, 'fetch_twse_margin_short_sales',
                        lambda ticker, **kwargs: original_fetch(ticker, session=PartialSession(value), **kwargs))
    result = ChipDataProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.status == 'degraded_enrichment'
    assert result.value['status'] == 'partial'
    margin = result.value['twse_margin_short_sales']
    assert margin['source'] == 'TWSE MI_MARGN dated report'
    assert margin['margin_balance'] is None and margin['short_balance'] is None
    assert margin['offset'] == 0
    assert result.audit['component_statuses']['margin_short']['status'] == 'partial'
    assert result.audit['component_statuses']['margin_short']['reason_code'] == 'core_balances_missing'
