"""Public fallback behavior using complete native official CSV originals."""
import base64
import gzip
from copy import deepcopy
from datetime import date
from hashlib import sha256
from pathlib import Path

import pandas as pd
import pytest

from data_fetch.types import FetchRequest
from data_fetch.taiwan_providers import MonthlyRevenueProvider

FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition/official_monthly_20261012'


@pytest.fixture(autouse=True)
def isolated_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


class EmptyLoader:
    def taiwan_stock_month_revenue(self, **kwargs):
        return pd.DataFrame()


def native_csv(monkeypatch, filename='listed.csv.gz'):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    # Import before patching the source clock; otherwise this module captures
    # a patched function at first import and leaks it into later test modules.
    from data_fetch.market_sources import official_monthly_transport
    raw = gzip.decompress((FIXTURES / filename).read_bytes())
    calls = []
    def download(self, url, diagnostic):
        calls.append(url)
        self.http_request_count += 1
        diagnostic['http_request_sent'] = True
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(),
                'sha256': sha256(raw).hexdigest()}
    monkeypatch.setattr(IssuerNewsHttp, '_download', download)
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader', EmptyLoader)
    monkeypatch.setattr('data_fetch.market_sources.official_monthly_revenue._today', lambda: date(2026, 10, 12))
    monkeypatch.setattr(official_monthly_transport, '_today', lambda: date(2026, 10, 12))
    return calls


def test_public_monthly_provider_recovers_finmind_empty_with_dated_official_amounts(monkeypatch):
    calls = native_csv(monkeypatch)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.status == 'success'
    assert result.value == ['2026年8月: NT$5148.05億', '2026年9月: NT$5118.57億']
    assert calls == ['https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv']
    assert result.audit['coverage_status'] == 'partial_two_adjacent_months'
    assert result.audit['window_complete'] is False
    assert result.audit['related_entries'][0]['provider'] == 'FinMind TaiwanStockMonthRevenue'
    assert result.audit['related_entries'][0]['status'] == 'unavailable'
    assert result.audit['original_receipt']['http_status'] == 200


def test_official_warm_original_keeps_epoch_and_is_excluded_from_acquisition(monkeypatch):
    from provider_acquisition import observation_kind
    calls = native_csv(monkeypatch)
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    second = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert len(calls) == 1
    assert second.value == first.value
    assert second.status == 'skipped_fresh_cache'
    assert second.audit['http_request_sent'] is False and second.audit['cache_hit'] is True
    assert second.audit['fetched_at_epoch'] == first.audit['fetched_at_epoch']
    row = {**second.audit, 'details': second.audit}
    assert observation_kind(row) == 'fresh_cache_count'


@pytest.mark.parametrize('ticker,context_ticker', [('2330.TW', '3023.TW'), ('6488.TWO', '6488.TW'),
                                                ('AAPL', '2330.TW'), ('3023', '2330.TW')])
def test_monthly_request_cannot_be_redirected_to_another_issuer_or_market(monkeypatch, ticker, context_ticker):
    calls = native_csv(monkeypatch)
    data = {'ticker': context_ticker}
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker(ticker), {'data': data})
    assert calls == [] and result.value == []
    assert result.status == 'not_applicable' and result.audit['http_request_sent'] is False
    assert data == {'ticker': context_ticker}


def test_successful_finmind_does_not_make_official_request(monkeypatch):
    calls = native_csv(monkeypatch)
    class GoodLoader:
        def taiwan_stock_month_revenue(self, **kwargs):
            return pd.DataFrame([{'revenue_year': 2026, 'revenue_month': 9, 'revenue': 200_000_000}])
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader', GoodLoader)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.value == ['2026年9月: NT$2.00億'] and result.status == 'success'
    assert calls == [] and result.provider == 'FinMind TaiwanStockMonthRevenue'


def test_same_fetch_failure_reuse_requires_same_ticker_and_uncached_audit(monkeypatch):
    from provider_correlation import correlation_scope
    import data_fetch.taiwan_providers as providers
    calls = native_csv(monkeypatch)
    loader_calls = []
    class Loader(EmptyLoader):
        def taiwan_stock_month_revenue(self, **kwargs):
            loader_calls.append(kwargs)
            return super().taiwan_stock_month_revenue(**kwargs)
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader', Loader)
    bogus = {'source': 'monthly_revenue', 'provider': providers.MonthlyRevenueProvider.name,
             'status': 'unavailable', 'record_count': 0, 'event_kind': 'aggregate',
             'operation_id': 'old-operation', 'fetch_id': 'current-fetch', 'ticker': '3023.TW',
             'cache_hit': True, 'stale': True}
    data = {'ticker': '2330.TW', 'source_audit': [bogus]}
    original = deepcopy(data)
    with correlation_scope(replace=True, fetch_id='current-fetch', ticker='2330.TW'):
        result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'), {'data': data})
    assert len(loader_calls) == 1
    assert result.audit['operation_id'] != 'old-operation'
    assert data == original and len(calls) == 1


def test_core_merge_preserves_official_original_epoch_for_warm_monthly_data(monkeypatch):
    import asyncio
    from data_fetch.workflow import _run_missing_core_provider_plan
    from data_fetch.provider_registry import ProviderRegistry
    calls = native_csv(monkeypatch)
    request = FetchRequest.from_ticker('2330.TW')
    first = MonthlyRevenueProvider().fetch(request)
    data = {'ticker': '2330.TW', 'recent_monthly_revenue': [], 'source_audit': []}
    result = asyncio.run(_run_missing_core_provider_plan(request, ProviderRegistry([MonthlyRevenueProvider()]), data))
    freshness = result['source_freshness']['monthly_revenue']
    assert freshness['fetched_at_epoch'] == first.audit['fetched_at_epoch']
    assert freshness['cache_hit'] is True
    assert result['recent_monthly_revenue'] == first.value and len(calls) == 1


def test_current_fetch_genuine_finmind_failure_is_not_repeated(monkeypatch):
    from provider_correlation import correlation_scope
    from source_audit import audited_fetch
    calls = native_csv(monkeypatch)
    loader_calls = []
    class Loader(EmptyLoader):
        def taiwan_stock_month_revenue(self, **kwargs):
            loader_calls.append(kwargs)
            return super().taiwan_stock_month_revenue(**kwargs)
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader', Loader)
    with correlation_scope(replace=True, fetch_id='current-fetch', ticker='2330.TW'):
        original = audited_fetch('monthly_revenue', MonthlyRevenueProvider.name, lambda: [], default=[])
        data = {'ticker': '2330.TW', 'source_audit': [original['audit']]}
        saved = deepcopy(data)
        result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'), {'data': data})
    assert loader_calls == [] and len(calls) == 1
    assert result.status == 'success' and result.audit['related_entries'] == []
    assert result.audit['primary_failure_operation_id'] == original['audit']['operation_id']
    assert result.audit['operation_id'] != original['audit']['operation_id'] and data == saved


def test_otc_monthly_uses_separate_official_market_and_exact_issuer(monkeypatch):
    calls = native_csv(monkeypatch, 'otc.csv.gz')
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('6488.TWO'))
    assert result.value == ['2026年8月: NT$47.64億', '2026年9月: NT$51.29億']
    assert result.audit['issuer_name'] == '環球晶'
    assert calls == ['https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv']


def test_missing_issuer_is_unknown_and_not_zero_or_success(monkeypatch):
    calls = native_csv(monkeypatch)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2886.TW'))
    assert result.value == [] and result.status == 'unavailable'
    assert result.audit['related_entries'][0]['coverage_status'] == 'issuer_missing_unknown'
    assert len(calls) == 1


def test_invalid_csv_is_not_cached_as_nonempty_success(monkeypatch):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    calls = native_csv(monkeypatch)
    count = []
    def bad(self, url, diagnostic):
        count.append(url); self.http_request_count += 1; diagnostic['http_request_sent'] = True
        raw = b'<html>FOR SECURITY REASONS</html>'
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest()}
    monkeypatch.setattr(IssuerNewsHttp, '_download', bad)
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    second = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert first.value == second.value == [] and len(count) == 1
    assert first.status != 'success' and second.status != 'skipped_fresh_cache'
    assert first.audit['related_entries'][0]['http_request_sent'] is True
    assert second.audit['related_entries'][0]['http_request_sent'] is False


def test_native_http_rate_limit_is_preserved_as_failed_official_observation(monkeypatch):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    from search_provider_runtime import SourceResponseError
    native_csv(monkeypatch)
    def fail(self, url, diagnostic):
        self.http_request_count += 1; diagnostic['http_request_sent'] = True
        raise SourceResponseError('rate_limited', status_code=429)
    monkeypatch.setattr(IssuerNewsHttp, '_download', fail)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    failure = result.audit['related_entries'][0]
    assert result.value == [] and failure['error_kind'] == 'rate_limited'
    assert failure['http_status'] == 429 and failure['http_request_sent'] is True


def rows():
    from data_fetch.market_sources.official_monthly_revenue import parse_monthly_snapshot, URLS
    raw = gzip.decompress((FIXTURES / 'listed.csv.gz').read_bytes())
    return parse_monthly_snapshot(raw, URLS['.TW'], date(2026, 10, 12))


def encoded(table, fields=None):
    import csv, io
    from data_fetch.market_sources.official_monthly_revenue import FIELDS
    out = io.StringIO(newline=''); writer = csv.DictWriter(out, fieldnames=fields or FIELDS)
    writer.writeheader(); writer.writerows(table)
    return out.getvalue().encode('utf-8-sig')


@pytest.mark.parametrize('mutation', ['duplicate_issuer', 'duplicate_header', 'missing_header', 'future_date',
                                   'expired_date', 'future_period', 'bad_month', 'truncated', 'non_utf8', 'security_page'])
def test_incomplete_or_unqualified_native_table_cannot_be_admitted(mutation):
    from data_fetch.market_sources.official_monthly_revenue import FIELDS, URLS, parse_monthly_snapshot
    table = rows(); fields = FIELDS[:]; raw = None
    if mutation == 'duplicate_issuer': table.append(deepcopy(table[0]))
    elif mutation == 'duplicate_header': fields[-1] = fields[0]
    elif mutation == 'missing_header': fields = fields[:-1]; table = [{k: v for k, v in r.items() if k in fields} for r in table]
    elif mutation == 'future_date': table[0]['出表日期'] = '1151013'
    elif mutation == 'expired_date': table[0]['出表日期'] = '1150801'
    elif mutation == 'future_period': table[0]['資料年月'] = '11510'
    elif mutation == 'bad_month': table[0]['資料年月'] = '11513'
    elif mutation == 'truncated': raw = encoded(table)[:-15]
    elif mutation == 'non_utf8': raw = b'\xff' + encoded(table)
    else: raw = b'<html>FOR SECURITY REASONS</html>'
    with pytest.raises((ValueError, UnicodeError, __import__('csv').Error)):
        parse_monthly_snapshot(raw if raw is not None else encoded(table, fields), URLS['.TW'], date(2026, 10, 12))


@pytest.mark.parametrize('amount', ['', 'NaN', 'Infinity', 'True', '1e20', '100,000', '99999999999999999'])
def test_malformed_amount_is_not_monthly_evidence(amount):
    from data_fetch.market_sources.official_monthly_revenue import select_monthly_records
    table = rows(); row = next(r for r in table if r['公司代號'] == '2330')
    row['營業收入-當月營收'] = amount
    with pytest.raises(ValueError): select_monthly_records(table, '2330.TW', date(2026, 10, 12))


def test_zero_negative_and_year_rollover_are_preserved_without_fabricated_history():
    from data_fetch.market_sources.official_monthly_revenue import select_monthly_records
    table = rows(); row = next(r for r in table if r['公司代號'] == '2330')
    row.update({'資料年月': '11412', '出表日期': '1150112',
                '營業收入-上月營收': '-100000', '營業收入-當月營收': '0'})
    values, audit = select_monthly_records(table, '2330.TW', date(2026, 1, 12))
    assert values == ['2025年11月: NT$-1.00億', '2025年12月: NT$0.00億']
    assert audit['covered_months'] == ['2025-11', '2025-12'] and audit['window_complete'] is False


def test_warm_monthly_radar_remains_usable_and_retains_primary_failure(monkeypatch):
    import asyncio
    from data_fetch.radar import fetch_radar_payload
    from data_fetch.provider_registry import ProviderRegistry
    calls = native_csv(monkeypatch); request = FetchRequest.from_ticker('2330.TW')
    first = MonthlyRevenueProvider().fetch(request)
    result = asyncio.run(fetch_radar_payload(request, ('monthly_revenue',), ProviderRegistry([MonthlyRevenueProvider()])))
    assert result['recent_monthly_revenue'] == first.value and len(calls) == 1
    assert result['source_freshness']['monthly_revenue']['fetched_at_epoch'] == first.audit['fetched_at_epoch']
    assert any(a['provider'] == MonthlyRevenueProvider.name and a['status'] == 'unavailable' for a in result['source_audit'])
    assert any(a['cache_hit'] is True and a['status'] == 'skipped_fresh_cache' for a in result['source_audit'])


@pytest.mark.parametrize('change', ['future', 'expired', 'wrong_url', 'wrong_http', 'body_hash', 'missing_original',
                                  'unobserved_http', 'shared_only'])
def test_warm_invalid_original_cannot_produce_success_or_fresh_cache(monkeypatch, change):
    import cache_store, time
    calls = native_csv(monkeypatch)
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    key = 'shared_provider:v1:' + sha256(('official-monthly-raw:v1:' + calls[0]).encode()).hexdigest()
    cache = cache_store.get_cache_json(key); receipt = cache['value']['original_receipt']
    if change == 'future': receipt['retrieved_at'] = time.time() + 100
    elif change == 'expired': receipt['retrieved_at'] = time.time() - 1801
    elif change == 'wrong_url': receipt['source_url'] = 'https://evil.test/data.csv'
    elif change == 'wrong_http': receipt['http_status'] = 403
    elif change == 'body_hash': cache['value']['sha256'] = '0' * 64
    elif change == 'unobserved_http': receipt['http_status_observed'] = False
    elif change == 'shared_only': receipt.update(cache_source='twse_listed_company_legal_roster:v1',
                                                cache_verified_at=receipt['retrieved_at'],
                                                fresh_until_epoch=receipt['retrieved_at'] + 1800)
    else: cache['value'].pop('original_receipt')
    cache_store.set_cache_json(key, cache, ttl_seconds=1800)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert first.value and result.value == [] and len(calls) == 1
    assert result.status not in {'success', 'skipped_fresh_cache'}


@pytest.mark.parametrize('expiry', ['deadline', 'original_TTL'])
def test_final_original_revalidation_cannot_outlive_deadline_or_original_TTL(monkeypatch, expiry):
    import data_fetch.market_sources.official_monthly_revenue as module
    native_csv(monkeypatch)
    real_read = module.read_response; real_now = module.time.time()
    monotonic = [0.]
    monkeypatch.setattr(module.time, 'monotonic', lambda: monotonic[0])
    def late(receipt):
        raw = real_read(receipt)
        if expiry == 'deadline': monotonic[0] = 9.
        else: monkeypatch.setattr(module.time, 'time', lambda: real_now + 2000)
        return raw
    monkeypatch.setattr(module, 'read_response', late)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.value == [] and result.status not in {'success', 'skipped_fresh_cache'}
    assert result.audit['related_entries'][0]['error_kind'] == 'ValueError'


def test_same_fetch_primary_failure_is_preserved_once_when_official_also_missing(monkeypatch):
    import asyncio
    from provider_correlation import correlation_scope
    from data_fetch.market_sources.taiwan import fetch_monthly_revenue_records
    from data_fetch.workflow import _run_missing_core_provider_plan
    from data_fetch.provider_registry import ProviderRegistry
    calls = native_csv(monkeypatch); loader_calls = []
    class Loader(EmptyLoader):
        def taiwan_stock_month_revenue(self, **kwargs):
            loader_calls.append(kwargs); return super().taiwan_stock_month_revenue(**kwargs)
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader', Loader)
    with correlation_scope(replace=True, fetch_id='same-fetch', ticker='2886.TW'):
        original, audit = fetch_monthly_revenue_records('2886.TW', data_loader_cls=Loader)
        data = {'ticker': '2886.TW', 'recent_monthly_revenue': original, 'source_audit': [audit]}
        result = asyncio.run(_run_missing_core_provider_plan(
            FetchRequest.from_ticker('2886.TW'), ProviderRegistry([MonthlyRevenueProvider()]), data))
    primary = [a for a in result['source_audit'] if a.get('operation_id') == audit['operation_id']]
    assert len(primary) == 1 and len(loader_calls) == 1 and len(calls) == 1
    official = result['source_audit'][-1]
    assert official['status'] == 'unavailable' and official['record_count'] == 0
    assert official['primary_failure_operation_id'] == audit['operation_id']
    assert result['recent_monthly_revenue'] == []
