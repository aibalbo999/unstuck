"""CAA membership orders a bounded search; usable metrics still require evidence."""
from copy import deepcopy
from datetime import date
from hashlib import sha256
from pathlib import Path
import base64
import gzip
import io
import json
import time
import threading
import zipfile

import pandas as pd
import pytest
from bs4 import BeautifulSoup

TODAY = date(2026, 10, 13)
INDEX = 'https://www.caa.gov.tw/Article.aspx?a=518&lang=1'
ODS = 'https://www.caa.gov.tw/FileAtt.ashx?lang=1&id=41657'
BASE = Path(__file__).parent / 'fixtures/source_acquisition/caa_airline_20261013'


@pytest.fixture(autouse=True)
def isolated_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def raw_pages():
    return {INDEX: gzip.decompress((BASE / 'index.html.gz').read_bytes()),
            ODS: (BASE / 'operations.ods').read_bytes()}


def master():
    return [{'stock_id': code, 'stock_name': name, 'type': 'twse',
             'industry_category': '航運業', 'date': TODAY.isoformat()}
            for code, name in [('2610', '華航'), ('2618', '長榮航'), ('2646', '星宇航空'),
                               ('6757', '台灣虎航'), *[(str(c), '海運') for c in (2609, 2611, 2608, 2612, 2607, 2613, 2606, 2605, 2615, 2603)]]]


def native_boundary(monkeypatch, raw=None):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    raw = raw_pages() if raw is None else raw
    calls = []
    def download(self, url, diagnostic):
        calls.append(url)
        self.http_request_count += 1
        diagnostic['http_request_sent'] = True
        body = raw[url]
        return {'url': url, 'body_b64': base64.b64encode(body).decode(),
                'sha256': sha256(body).hexdigest()}
    monkeypatch.setattr(IssuerNewsHttp, '_download', download)
    return calls


class Stock:
    def __init__(self, symbol): self.symbol = symbol
    @property
    def info(self):
        return {'symbol': self.symbol, 'quoteType': 'EQUITY',
                'industry': 'Airlines' if self.symbol in {'2618.TW', '2646.TW', '6757.TW'} else 'Marine Shipping',
                'grossMargins': .25, 'operatingMargins': .1, 'profitMargins': .08,
                'returnOnEquity': .12, 'trailingPE': 18., 'priceToBook': 2.,
                'priceToSalesTrailing12Months': 1.6, 'totalRevenue': 999., 'totalAssets': 10.}
    @property
    def financials(self): return pd.DataFrame({'2025-12-31': [80.]}, index=['Total Revenue'])
    @property
    def balance_sheet(self): return pd.DataFrame({'2025-12-31': [100.]}, index=['Total Assets'])


def public_fetch(monkeypatch, stock=Stock):
    from data_fetch.market_sources import peers
    calls = native_boundary(monkeypatch)
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    monkeypatch.setattr(peers, 'load_peer_stock_master', master)
    monkeypatch.setattr(peers.yf, 'Ticker', stock)
    return peers.fetch_dynamic_peer_metrics_with_diagnostics('2610.TW', '華航', 'Industrials', 'Airlines', {}), calls


def test_airlines_reached_before_nearby_shipping_without_relaxing_metric_gate(monkeypatch):
    result, calls = public_fetch(monkeypatch)
    assert [r['ticker'] for r in result['peers']] == ['2618.TW', '2646.TW']
    assert calls == [INDEX, ODS]
    assert result['audit']['candidate_attempt_count'] <= 10
    assert result['audit']['usable_count'] == 2
    for row in result['peers']:
        assert row['comparison_status'] == 'business_industry_matched'
        assert row['numeric_comparability_verified'] is False
        assert row['membership_period_end'] == '2026-06-30'
        assert row['asset_turnover'] == .8
        assert 'whole_company_business_mix_not_verified' in row['comparison_limitations']
        assert all('CAA' not in s['provider'] for s in row['metric_sources'].values())


@pytest.mark.parametrize('change', ['no_symbol', 'no_quote_type', 'wrong_industry', 'no_industry'])
def test_membership_never_substitutes_for_exact_live_identity_and_fine_industry(monkeypatch, change):
    class InvalidStock(Stock):
        @property
        def info(self):
            info = super().info
            if self.symbol == '2618.TW':
                if change == 'no_symbol': info.pop('symbol')
                elif change == 'no_quote_type': info.pop('quoteType')
                elif change == 'no_industry': info.pop('industry')
                else: info['industry'] = 'Marine Shipping'
            return info
    result, _ = public_fetch(monkeypatch, InvalidStock)
    assert '2618.TW' not in {r['ticker'] for r in result['peers']}
    assert [r['ticker'] for r in result['peers']] == ['2646.TW']


def collect(monkeypatch, raw=None, rows=None, ticker='2610.TW'):
    from data_fetch.market_sources.official_airline_peer_cohort import get_official_airline_candidates
    calls = native_boundary(monkeypatch, raw)
    return get_official_airline_candidates(ticker, master() if rows is None else rows, today=TODAY), calls


def edit_ods(raw, before, after):
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as src, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            value = src.read(name)
            if name == 'content.xml': value = value.replace(before.encode(), after.encode())
            dst.writestr(name, value)
    return out.getvalue()


@pytest.mark.parametrize('change', ['foreign_url', 'ambiguous_latest', 'future_period', 'bad_scope',
                                  'missing_target', 'xml_doctype', 'zip_bomb', 'wrong_master_name',
                                  'stale_master', 'wrong_market'])
def test_source_identity_date_scope_and_full_originals_are_required(monkeypatch, change):
    raw, rows = raw_pages(), master()
    if change == 'foreign_url':
        assert b'../FileAtt.ashx?lang=1&id=41657' in raw[INDEX]
        raw[INDEX] = raw[INDEX].replace(b'../FileAtt.ashx?lang=1&id=41657', b'https://other.example/41657')
    elif change == 'ambiguous_latest':
        raw[INDEX] = raw[INDEX].replace('115年第2季.ods'.encode(), '114年第4季.ods'.encode())
    elif change == 'future_period':
        raw[INDEX] = raw[INDEX].replace('115年第2季'.encode(), '116年第2季'.encode())
    elif change in {'bad_scope', 'missing_target', 'xml_doctype'}:
        before, after = {'bad_scope': ('個體財務資料', '合併財務資料'),
                         'missing_target': ('中華航空', '別家航空'),
                         'xml_doctype': ('<office:document-content', '<!DOCTYPE x><office:document-content')}[change]
        raw[ODS] = edit_ods(raw[ODS], before, after)
    elif change == 'zip_bomb': raw[ODS] = edit_ods(raw[ODS], '中華航空', '中華航空' + ' ' * 2_000_000)
    elif change == 'wrong_master_name': rows[0]['stock_name'] = '其他'
    elif change == 'stale_master': rows[0]['date'] = '2026-09-01'
    elif change == 'wrong_market': rows[0]['type'] = 'tpex'
    result, _ = collect(monkeypatch, raw, rows)
    assert result['candidates'] == []


def test_warm_cache_retains_original_epoch_and_never_adds_native_requests(monkeypatch):
    from data_fetch.market_sources import official_airline_peer_cohort as source
    cold, calls = collect(monkeypatch)
    warm = source.get_official_airline_candidates('2610.TW', master(), today=TODAY)
    assert len(calls) == 2 and warm['http_request_count'] == 0
    assert warm['cache_hit'] is True and cold['candidates'] == warm['candidates']


def test_other_ticker_does_not_fetch_caa(monkeypatch):
    result, calls = collect(monkeypatch, ticker='2603.TW')
    assert not calls and result['status'] == 'not_applicable'


def test_expiry_after_metrics_rejects_caa_rows(monkeypatch):
    from data_fetch.market_sources import official_airline_peer_cohort as source
    now = time.time()
    monkeypatch.setattr(source.time, 'time', lambda: now)
    class SlowStock(Stock):
        @property
        def balance_sheet(self):
            nonlocal now
            now += 1801
            return super().balance_sheet
    result, _ = public_fetch(monkeypatch, SlowStock)
    assert not result['peers']


@pytest.mark.parametrize('ticker', ['2610.TW', '2618.TW', '2646.TW', '6757.TW'])
def test_normal_analysis_keeps_partial_metric_audit_and_candidate_receipts(monkeypatch, ticker):
    from data_fetch import yfinance_sync_enrichment as sync
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.types import ProviderResult
    import source_applicability
    monkeypatch.setattr(source_applicability, 'source_is_applicable', lambda source, data: source == 'dynamic_peer_metrics')
    specs = []
    monkeypatch.setattr(sync, '_run_named_fetches', lambda fetches, **kw: (specs.extend(fetches) or {'values': {}, 'audit': []}))
    row = {'ticker': '2618.TW', 'metrics_status': 'partial', 'business_comparability_verified_current': False}
    audit = {'source': 'dynamic_peer_metrics', 'status': 'degraded_enrichment', 'record_count': 1,
             'coverage_status': 'partial', 'candidate_attempt_count': 10, 'official_airline_candidate_status': 'success'}
    monkeypatch.setattr(DynamicPeerMetricsProvider, 'fetch', lambda *a, **kw: ProviderResult(
        source='dynamic_peer_metrics', provider='FinMind/yfinance', value=[row], status='degraded_enrichment', audit=audit))
    result = sync.fetch_sync_enrichment_bundle(ticker=ticker, stock=None, company_name='Airline', sector='Industrials',
        industry='Airlines', company_identity={}, years=[], net_income_history=[], shares_outstanding=None, skip_optional_http=True)
    assert 'dynamic_peer_metrics' not in specs
    assert result['audit'] == [audit]
    assert result['dynamic_peer_metrics'] == [row]


@pytest.mark.parametrize('change', ['403', '429', 'timeout', 'truncated', 'redirect', 'url', 'content_type', 'encoding'])
def test_native_refusals_and_incomplete_responses_do_not_become_membership(monkeypatch, change):
    from data_fetch.market_sources import issuer_news_transport as transport
    from data_fetch.market_sources import official_airline_peer_cohort as source
    from search_provider_runtime import SourceResponseError
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    for key in transport.PROXY_ENV: monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(transport, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(transport, 'cooldown_state', lambda *a: None)
    monkeypatch.setattr(transport, 'observe_http_response', lambda *a: None)
    failures = []
    monkeypatch.setattr(transport, 'remember_failure', lambda key, exc: failures.append(exc.error_kind))
    status, rc, error = 200, 0, None
    meta = {'http_code': 200, 'url_effective': INDEX, 'num_redirects': 0}
    headers = 'Content-Type: text/html\r\n'
    if change in {'403', '429'}: status = int(change); meta['http_code'] = status
    elif change == 'timeout': rc = 28
    elif change == 'truncated': error = 'response_too_large'
    elif change == 'redirect': meta['num_redirects'] = 1
    elif change == 'url': meta['url_effective'] = 'https://other.example/'
    elif change == 'content_type': headers = 'Content-Type: application/json\r\n'
    else: headers += 'Content-Encoding: gzip\r\n'
    def process(argv, deadline, **kwargs):
        assert '--disable' in argv and '--location' not in argv
        assert argv[argv.index('--max-time') + 1] and float(argv[argv.index('--max-time') + 1]) <= 5
        assert argv[argv.index('--connect-timeout') + 1] == '2.0'
        assert argv[argv.index('--max-redirs') + 1] == '0'
        assert argv[argv.index('--retry') + 1] == '0'
        return {'body': raw_pages()[INDEX], 'headers': (f'HTTP/1.1 {status} Status\r\n' + headers + '\r\n').encode(),
                'metadata': json.dumps(meta).encode(), 'process_started': True}, rc, error
    monkeypatch.setattr(transport, 'collect_capped_process', process)
    http = source.AirlineHttp(time.monotonic() + 12)
    with pytest.raises(SourceResponseError): http.get(INDEX)
    assert http.http_request_count == 1
    assert bool(failures) == (change in {'403', '429'})


@pytest.mark.parametrize('change', ['body', 'http_status', 'epoch', 'pit_flag', 'shared_only', 'bytes', 'path'])
def test_warm_cache_cannot_renew_or_fabricate_native_original(monkeypatch, change):
    import cache_store
    from data_fetch.market_sources import official_airline_peer_cohort as source
    cold, calls = collect(monkeypatch)
    assert cold['status'] == 'success'
    key = 'shared_provider:v1:' + sha256(('caa-airline-raw:v1:' + ODS).encode()).hexdigest()
    cached = cache_store.get_cache_json(key)
    receipt = cached['value']['original_receipt']
    if change == 'body': cached['value']['body_b64'] = base64.b64encode(b'bad').decode()
    elif change == 'http_status': receipt['http_status'] = 403
    elif change == 'epoch': receipt['retrieved_at'] -= 1801
    elif change == 'pit_flag': receipt['historical_point_in_time_verified'] = True
    elif change == 'shared_only': receipt['evidence_kind'] = 'cached_complete_source_payload_verified_by_digest'
    elif change == 'bytes': receipt['raw_response_bytes'] = True
    elif change == 'path': receipt['raw_response_path'] = '/tmp/unrelated.gz'
    cache_store.set_cache_json(key, cached, ttl_seconds=1800)
    result = source.get_official_airline_candidates('2610.TW', master(), today=TODAY)
    assert not result['candidates'] and len(calls) == 2 and result['http_request_count'] == 0


@pytest.mark.parametrize('ticker,expected', [('2618.TW', ['2610.TW', '2646.TW', '6757.TW']),
    ('2646.TW', ['2610.TW', '2618.TW', '6757.TW']), ('6757.TW', ['2618.TW', '2646.TW'])])
def test_current_operator_candidates_exclude_self_and_known_related_issuer(monkeypatch, ticker, expected):
    result, _ = collect(monkeypatch, ticker=ticker)
    assert [r['ticker'] for r in result['candidates']] == expected


def test_single_flight_wait_respects_remaining_total_deadline(monkeypatch):
    import shared_provider_cache as cache
    from data_fetch.market_sources import official_airline_peer_cohort as source
    from search_provider_runtime import SourceResponseError
    digest=sha256(('caa-airline-raw:v1:'+INDEX).encode()).hexdigest()
    lock=cache._local_lock(digest)
    held=threading.Event();release=threading.Event()
    def holder():
        with lock:held.set();release.wait(3)
    thread=threading.Thread(target=holder);thread.start();assert held.wait(1)
    monkeypatch.setattr(source.AirlineHttp,'_download',lambda *a:pytest.fail('deadline must not download'))
    start=time.monotonic()
    try:
        with pytest.raises(SourceResponseError):source.AirlineHttp(start+.03).get(INDEX)
        elapsed=time.monotonic()-start
    finally:release.set();thread.join()
    assert elapsed<.15, f'30ms total budget spent {elapsed:.3f}s waiting for shared lock'

@pytest.mark.parametrize('empty', [False, True])
def test_provider_only_counts_actual_metrics_and_preserves_partial(monkeypatch,empty):
    from data_fetch.market_sources import peers
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.types import FetchRequest
    native_boundary(monkeypatch)
    monkeypatch.setattr(peers,'_today',lambda:TODAY)
    monkeypatch.setattr(peers,'load_peer_stock_master',master)
    monkeypatch.setattr(peers,'fetch_peer_valuation_fallback',lambda *a,**k:{'metrics':{},'status':'valid_empty'})
    class S(Stock):
        @property
        def info(self):
            value=super().info
            if empty:return {k:value[k] for k in ('symbol','quoteType','industry')}
            value.pop('returnOnEquity');return value
        @property
        def financials(self):return pd.DataFrame()
        @property
        def balance_sheet(self):return pd.DataFrame()
    monkeypatch.setattr(peers.yf,'Ticker',S)
    result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('2610.TW'),{
        'data':{'ticker':'2610.TW','company_name':'華航','sector':'Industrials','industry':'Airlines','company_identity':{}}})
    assert len(result.value)==2
    assert result.audit['usable_count']==(0 if empty else 2)
    assert result.audit['coverage_status']==('unavailable' if empty else 'partial')
    assert result.status!='success'
    assert all(r['metrics_status']==('unavailable' if empty else 'partial') for r in result.value)


def test_same_document_concurrency_is_shared(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from data_fetch.market_sources import official_airline_peer_cohort as source
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    raw=raw_pages();calls=[];calls_lock=threading.Lock()
    def download(self,url,diagnostic):
        with calls_lock:calls.append(url)
        time.sleep(.03);self.http_request_count+=1;diagnostic['http_request_sent']=True
        return {'url':url,'body_b64':base64.b64encode(raw[url]).decode(),'sha256':sha256(raw[url]).hexdigest()}
    monkeypatch.setattr(IssuerNewsHttp,'_download',download)
    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes=list(executor.map(lambda _:source.get_official_airline_candidates('2610.TW',master(),today=TODAY),range(8)))
    assert calls==[INDEX,ODS]
    assert all(len(o['candidates'])==2 for o in outcomes)
    assert sum(o['http_request_count'] for o in outcomes)==2

@pytest.mark.parametrize('extension', ['xlsx', 'ODS'])
def test_new_quarter_changed_attachment_format_cannot_silently_fall_back(monkeypatch,extension):
    raw=raw_pages();soup=BeautifulSoup(raw[INDEX],'html.parser')
    first=soup.find('a',title='115年第2季.ods')
    row=BeautifulSoup(str(first.find_parent('tr')).replace('115年第2季','115年第3季'),'html.parser').find('tr')
    anchors=row.select('a[title]')
    for a in anchors[1:]:a.decompose()
    anchors[0]['title']='115年第3季.'+extension
    anchors[0].string='115年第3季.'+extension
    first.find_parent('tr').insert_before(row)
    raw[INDEX]=str(soup).encode()
    result,calls=collect(monkeypatch,raw=raw)
    assert result['candidates']==[], 'Changed latest-quarter format must be unsupported, not Q2 membership'
    assert calls==[INDEX]
