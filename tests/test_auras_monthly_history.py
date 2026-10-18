"""Actual public Auras JSON and exchange originals through the monthly provider."""
from pathlib import Path
from hashlib import sha256
from datetime import date
from copy import deepcopy
import base64, gzip, time, json
import pandas as pd
import pytest
from data_fetch.types import FetchRequest
from data_fetch.taiwan_providers import MonthlyRevenueProvider

FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition/auras_monthly_20261013'
CSV = 'https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv'
MASTER = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
UNIT = 'https://www.auras.com.tw/assets/FinancialInformtion-f05283f2.js'
API = 'https://www.auras.com.tw/CmsApi/api/FinancialReport/getFinancialReportAsync?Year=&IsPage=false&CurrentPage=1&PageSize=10&OrderBy=&IsDesc=true'
EXPECTED = ['2026年4月: NT$28.42億', '2026年5月: NT$31.39億', '2026年6月: NT$27.18億',
            '2026年7月: NT$37.65億', '2026年8月: NT$31.41億', '2026年9月: NT$28.84億']


@pytest.fixture
def original_http(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    cache_store.set_cache_backend(InMemoryCache())
    bodies = {url: gzip.decompress((FIXTURES / (name + '.gz')).read_bytes())
              for url, name in [(CSV, 'otc.csv'), (MASTER, 'otc_roster.json'),
                                (UNIT, 'financial_module.js'), (API, 'financial.json')]}
    calls = []

    def download(self, url, diagnostic):
        calls.append(url)
        self.http_request_count += 1
        diagnostic.update(http_request_sent=True, http_status=200)
        raw = bodies[url]
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest()}

    class EmptyLoader:
        def taiwan_stock_month_revenue(self, **kwargs):
            return pd.DataFrame()

    monkeypatch.setattr(IssuerNewsHttp, '_download', download)
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader', EmptyLoader)
    monkeypatch.setattr('data_fetch.market_sources.official_monthly_revenue._today', lambda: date(2026, 10, 13))
    monkeypatch.setenv('PROVIDER_RETRY_BACKOFF_SECONDS', '0')
    monkeypatch.setenv('PROVIDER_RETRY_JITTER_SECONDS', '0')
    yield calls, bodies
    cache_store.reset_cache_store_for_tests()


def test_public_failed_primary_recovers_six_months_from_issuer_api(original_http):
    calls, _ = original_http
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert result.value == EXPECTED
    assert result.audit['window_complete'] is True
    assert result.audit['filed_amounts_NTD'] == ['2842339000', '3138892000', '2718035000',
                                              '3765466000', '3141249000', '2884061000']
    assert calls == [CSV, MASTER, UNIT, API]
    assert result.audit['historical_point_in_time_verified'] is False
    assert result.audit['related_entries'][0]['provider'] == 'FinMind TaiwanStockMonthRevenue'


def test_warm_read_preserves_original_epoch_and_does_not_count_new_acquisition(original_http):
    from provider_acquisition import observation_kind
    calls, _ = original_http
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    second = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert first.value == second.value == EXPECTED and calls == [CSV, MASTER, UNIT, API]
    assert second.audit['fetched_at_epoch'] == first.audit['fetched_at_epoch']
    assert second.audit['http_request_sent'] is False
    assert observation_kind({**second.audit, 'details': second.audit}) == 'fresh_cache_count'


def test_core_merge_keeps_issuer_api_freshness(original_http):
    import asyncio
    from data_fetch.workflow import _run_missing_core_provider_plan
    from data_fetch.provider_registry import ProviderRegistry
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    data = {'ticker': '3324.TWO', 'recent_monthly_revenue': [], 'source_audit': []}
    result = asyncio.run(_run_missing_core_provider_plan(
        FetchRequest.from_ticker('3324.TWO'), ProviderRegistry([MonthlyRevenueProvider()]), data))
    assert result['recent_monthly_revenue'] == EXPECTED
    assert result['source_freshness']['monthly_revenue']['fetched_at_epoch'] == first.audit['fetched_at_epoch']
    assert result['source_freshness']['monthly_revenue']['cache_hit'] is True


def test_healthy_primary_does_not_fetch_new_endpoints(original_http, monkeypatch):
    class GoodLoader:
        def taiwan_stock_month_revenue(self, **kwargs):
            return pd.DataFrame([{'revenue_year': 2026, 'revenue_month': 9, 'revenue': 2884061000}])
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader', GoodLoader)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert result.provider == 'FinMind TaiwanStockMonthRevenue' and original_http[0] == []


@pytest.mark.parametrize('data', [{'ticker': '3324.TWO', 'quote_type': 'ETF'}, {'ticker': '2330.TW'}])
def test_conflicting_context_does_not_make_requests(original_http, data):
    saved = deepcopy(data)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'), {'data': data})
    assert result.status == 'not_applicable' and original_http[0] == [] and data == saved


@pytest.mark.parametrize('change,reason', [
    ('name', 'auras_master_identity_unverified'), ('ubn', 'auras_master_identity_unverified'),
    ('domain', 'auras_registered_domain_unverified'), ('partial', 'auras_master_identity_unverified'),
    ('old', 'auras_master_identity_unverified')])
def test_unverified_issuer_master_keeps_two_month_snapshot(original_http, change, reason):
    calls, bodies = original_http
    rows = json.loads(bodies[MASTER]); issuer = next(r for r in rows if r['SecuritiesCompanyCode'] == '3324')
    if change == 'name': issuer['CompanyName'] = '另一家股份有限公司'
    elif change == 'ubn': issuer['UnifiedBusinessNo.'] = '12345678'
    elif change == 'domain': issuer['WebAddress'] = 'https://www.auras.com.tw.attacker.example'
    elif change == 'old': issuer['Date'] = '1151001'
    else: rows = [issuer]
    bodies[MASTER] = json.dumps(rows, ensure_ascii=False).encode()
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert result.value == EXPECTED[-2:] and not result.audit['window_complete']
    assert calls == [CSV, MASTER]
    assert result.audit['related_entries'][-1]['error_kind'] == reason


@pytest.mark.parametrize('change,reason', [
    ('missing', 'auras_six_month_window_incomplete'), ('bool', 'auras_month_amount_unverified'),
    ('string', 'auras_month_amount_unverified'), ('future', 'auras_future_month_amount'),
    ('duplicate_year', 'auras_year_unverified'), ('mismatch', 'auras_snapshot_amount_or_unit_conflict'),
    ('count', 'auras_financial_list_incomplete'), ('duplicate_key', 'auras_duplicate_json_key')])
def test_incomplete_or_conflicting_api_keeps_original_partial_data(original_http, change, reason):
    calls, bodies = original_http
    data = json.loads(bodies[API]); current = next(r for r in data['infos'] if r['year'] == 2026)
    if change == 'missing': current['aprilRevenue'] = None
    elif change == 'bool': current['aprilRevenue'] = True
    elif change == 'string': current['aprilRevenue'] = '2842339'
    elif change == 'future': current['octoberRevenue'] = 100
    elif change == 'duplicate_year': data['infos'].append(deepcopy(current)); data['totalCount'] += 1
    elif change == 'mismatch': current['septemberRevenue'] += 1
    elif change == 'count': data['totalCount'] += 1
    raw = json.dumps(data, ensure_ascii=False).encode()
    if change == 'duplicate_key': raw = raw.replace(b'"year": 2026', b'"year": 2026, "year": 2025', 1)
    bodies[API] = raw
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert result.value == EXPECTED[-2:] and not result.audit['window_complete']
    assert calls == [CSV, MASTER, UNIT, API]
    assert result.audit['related_entries'][-1]['error_kind'] == reason


def test_changed_unit_contract_and_cached_failure_cannot_promote_history(original_http):
    from provider_acquisition import observation_kind
    calls, bodies = original_http; bodies[UNIT] = bodies[UNIT].replace('仟元'.encode(), '百萬'.encode())
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    second = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert calls == [CSV, MASTER, UNIT] and first.value == second.value == EXPECTED[-2:]
    failure = first.audit['related_entries'][-1]; blocked = second.audit['related_entries'][-1]
    assert failure['error_kind'] == 'auras_published_unit_contract_changed'
    assert observation_kind({**failure, 'details': failure}) == 'failed_count'
    assert observation_kind({**blocked, 'details': blocked}) == 'local_block_count'


def test_existing_csv_and_new_history_share_eight_second_budget(original_http, monkeypatch):
    from data_fetch.market_sources import official_monthly_revenue as snapshot
    fetch = snapshot.fetch_official_monthly_revenue; clock = [time.monotonic()]
    monkeypatch.setattr(time, 'monotonic', lambda: clock[0])
    def consume(ticker):
        value = fetch(ticker); clock[0] += 8; return value
    monkeypatch.setattr(snapshot, 'fetch_official_monthly_revenue', consume)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert result.value == EXPECTED[-2:] and original_http[0] == [CSV]


def test_same_fetch_primary_failure_is_not_duplicated(original_http):
    from provider_correlation import correlation_scope
    from source_audit import audited_fetch
    with correlation_scope(replace=True, fetch_id='current', ticker='3324.TWO'):
        first = audited_fetch('monthly_revenue', MonthlyRevenueProvider.name, lambda: [], default=[])
        data = {'ticker': '3324.TWO', 'source_audit': [first['audit']]}; saved = deepcopy(data)
        result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'), {'data': data})
    assert result.value == EXPECTED and data == saved
    assert result.audit['primary_failure_operation_id'] == first['audit']['operation_id']
    assert all(a['provider'] != MonthlyRevenueProvider.name for a in result.audit['related_entries'])


def _seed_isolated_master(bodies, stamp):
    import cache_store
    from official_response_evidence import archive_response
    from data_fetch.market_sources.official_company_legal_name import parse_roster
    raw = bodies[MASTER]
    archive_response(raw, source_url=MASTER, retrieved_at=stamp, http_status=200)
    key = 'shared_provider:v1:' + sha256(b'official-company-roster:v2:.TWO').hexdigest()
    cache_store.set_cache_json(key, {'value': parse_roster(raw, '.TWO'),
                                   'fetched_at_epoch': stamp, 'fresh_until_epoch': stamp + 86400}, 86400)
    return key


def test_existing_full_master_cache_reuses_original_epoch_without_extra_http(original_http):
    calls, bodies = original_http; stamp = time.time() - 100
    _seed_isolated_master(bodies, stamp)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert result.value == EXPECTED and calls == [CSV, UNIT, API]
    assert result.audit['issuer_original_metadata']['fetched_at_epoch'] == stamp
    assert result.audit['issuer_original_metadata']['http_status_observed'] is False


@pytest.mark.parametrize('change', ['http_bool', 'size', 'future_epoch'])
def test_corrupt_saved_api_receipt_does_not_supply_warm_six_months(original_http, change):
    import cache_store
    calls, _ = original_http
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert first.value == EXPECTED
    key = 'shared_provider:v1:' + sha256(('auras-monthly-raw:v1:' + API).encode()).hexdigest()
    row = cache_store.get_cache_json(key); receipt = row['value']['original_receipt']
    if change == 'http_bool': receipt['http_status'] = True
    elif change == 'size': receipt['raw_response_bytes'] -= 1
    else: receipt['retrieved_at'] = time.time() + 60
    cache_store.set_cache_json(key, row, 1800)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert result.value == EXPECTED[-2:] and calls == [CSV, MASTER, UNIT, API]
    assert result.audit['related_entries'][-1]['http_request_sent'] is False


@pytest.mark.parametrize('constituent', ['api', 'csv', 'cached_master'])
def test_expiry_during_final_original_read_prevents_six_month_promotion(original_http, monkeypatch, constituent):
    from data_fetch.market_sources import twse_monthly_history as receipt_helpers
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    calls, bodies = original_http; clock = [time.time()]
    monkeypatch.setattr(time, 'time', lambda: clock[0])
    master_stamp = clock[0] - 86394
    if constituent == 'cached_master': _seed_isolated_master(bodies, master_stamp)
    download = IssuerNewsHttp._download
    def spaced(self, url, diagnostic):
        clock[0] += 1
        return download(self, url, diagnostic)
    monkeypatch.setattr(IssuerNewsHttp, '_download', spaced)
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert first.value == EXPECTED
    csv_stamp = first.audit['snapshot_original_receipt']['retrieved_at']
    api_stamp = first.audit['original_receipt']['retrieved_at']
    if constituent != 'cached_master': clock[0] = csv_stamp + 1798
    read = receipt_helpers.read_response; api_reads = []
    def expire(receipt):
        raw = read(receipt)
        if receipt.get('source_url') == API:
            api_reads.append(1)
            if len(api_reads) == 2:
                clock[0] = (master_stamp + 86400 if constituent == 'cached_master'
                            else api_stamp + 1800 if constituent == 'api' else csv_stamp + 1800) + .01
        return raw
    monkeypatch.setattr(receipt_helpers, 'read_response', expire)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert len(api_reads) == 2
    assert result.value == EXPECTED[-2:] and not result.audit['window_complete']
    assert calls == ([CSV, UNIT, API] if constituent == 'cached_master' else [CSV, MASTER, UNIT, API])
    assert result.audit['related_entries'][-1]['http_request_sent'] is False


def test_csv_name_conflict_stops_issuer_history_before_http(original_http):
    import csv, io
    calls, bodies = original_http
    reader = csv.DictReader(io.StringIO(bodies[CSV].decode('utf-8-sig'), newline=''))
    fields = reader.fieldnames; rows = list(reader)
    next(r for r in rows if r['公司代號'] == '3324')['公司名稱'] = '另一家公司'
    stream = io.StringIO(newline=''); writer = csv.DictWriter(stream, fields)
    writer.writeheader(); writer.writerows(rows); bodies[CSV] = stream.getvalue().encode()
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert result.value == EXPECTED[-2:] and calls == [CSV]
    assert result.audit['related_entries'][-1]['error_kind'] == 'auras_snapshot_issuer_or_amount_unverified'


def test_actual_zero_month_is_preserved_and_not_substituted(original_http):
    _, bodies = original_http; data = json.loads(bodies[API]); data['infos'][0]['aprilRevenue'] = 0
    bodies[API] = json.dumps(data, ensure_ascii=False).encode()
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('3324.TWO'))
    assert result.value == ['2026年4月: NT$0.00億', *EXPECTED[1:]]
    assert result.audit['filed_amounts_NTD'][0] == '0' and result.audit['window_complete'] is True
