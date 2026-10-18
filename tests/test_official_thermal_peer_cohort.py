"""Exact thermal-segment originals recover numeric context, not valuation peers."""
from datetime import date
from pathlib import Path
from hashlib import sha256
import base64
import gzip
from copy import deepcopy
import json
import time

import pandas as pd
import pytest

TODAY = date(2026, 10, 13)
TICKER = '3324.TWO'
EXPECTED = ['3017.TW', '3338.TW', '6230.TW', '2421.TW', '3483.TWO']
BASE = Path(__file__).parent / 'fixtures/source_acquisition/thermal_metrics_20261013'
URLS = {
    'https://ic.tpex.org.tw/company_chain.php?stk_code=3324': 'issuer.html.gz',
    'https://ic.tpex.org.tw/introduce.php?ic=F000': 'segment.html.gz',
    'https://openapi.twse.com.tw/v1/opendata/t187ap03_L': 'listed.json.gz',
    'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O': 'otc.json.gz',
}


@pytest.fixture(autouse=True)
def isolated_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def originals():
    return {url: gzip.decompress((BASE / name).read_bytes()) for url, name in URLS.items()}


def native_boundary(monkeypatch, raw=None):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    raw = originals() if raw is None else raw
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
    def __init__(self, symbol):
        self.symbol = symbol
    @property
    def info(self):
        return {'symbol': self.symbol, 'quoteType': 'EQUITY', 'industry': 'Electronic Components',
                'grossMargins': .25, 'operatingMargins': .1, 'profitMargins': .08,
                'returnOnEquity': .12, 'trailingPE': 18., 'priceToBook': 2.,
                'priceToSalesTrailing12Months': 1.6, 'totalRevenue': 999., 'totalAssets': 10.}
    @property
    def financials(self):
        return pd.DataFrame({'2025-12-31': [80.]}, index=['Total Revenue'])
    @property
    def balance_sheet(self):
        return pd.DataFrame({'2025-12-31': [100.]}, index=['Total Assets'])


def test_public_peer_collector_recovers_official_thermal_candidates_without_valuation_upgrade(monkeypatch):
    from data_fetch.market_sources import peers
    from stock_snapshot.peers_valuation import _peer_comparison
    from prompt_peer_projection import comparable_peer_rows
    calls = native_boundary(monkeypatch)
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: [])
    monkeypatch.setattr(peers.yf, 'Ticker', Stock)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        TICKER, '雙鴻', 'Technology', 'Computer Hardware', {})
    assert [r['ticker'] for r in result['peers']] == EXPECTED
    assert len(calls) == 4
    assert result['audit']['usable_count'] == 5
    assert result['audit']['candidate_attempt_count'] <= 10
    for row in result['peers']:
        assert row['comparison_scope'] == 'thermal_management_segment'
        assert row['business_comparability_verified_current'] is False
        assert row['asset_turnover'] == .8  # Never the undated 999 / 10 quote aggregate.
        assert row['metric_sources']['asset_turnover']['observed_at'] == '2025-12-31'
        assert 'whole_company_business_mix_not_verified' in row['comparison_limitations']
    assert _peer_comparison({'ticker': TICKER, 'dynamic_peer_metrics': result['peers']})['summary']['peer_count'] == 0
    assert comparable_peer_rows(result['peers']) == []


def collect(monkeypatch, raw=None, ticker=TICKER):
    from data_fetch.market_sources.official_thermal_peer_cohort import get_official_thermal_candidates
    calls = native_boundary(monkeypatch, raw)
    return get_official_thermal_candidates(ticker, today=TODAY), calls


@pytest.mark.parametrize('change', ['issuer', 'group', 'target_absent', 'desktop_disagreement',
                                  'old_target', 'future_target', 'wrong_target_ubn', 'wrong_market',
                                  'small_master', 'oversize', 'non_utf8'])
def test_incorrect_originals_cannot_establish_thermal_candidate_identity(monkeypatch, change):
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    raw = originals()
    if change == 'issuer': raw[source.ISSUER_URL] = raw[source.ISSUER_URL].replace(b'3324', b'3325')
    elif change == 'group': raw[source.SEGMENT_URL] = raw[source.SEGMENT_URL].replace(b'companyList_FB00', b'companyList_FX00')
    elif change == 'target_absent': raw[source.SEGMENT_URL] = raw[source.SEGMENT_URL].replace(b'stk_code=3324', b'stk_code=3325')
    elif change == 'desktop_disagreement':
        raw[source.SEGMENT_URL] = raw[source.SEGMENT_URL].replace('奇鋐'.encode(), '其他'.encode(), 1)
    elif change == 'oversize': raw[source.SEGMENT_URL] += b' ' * 500_001
    elif change == 'non_utf8': raw[source.ISSUER_URL] = b'\xff' * 200
    else:
        url = source.MASTERS['.TWO']; rows = json.loads(raw[url])
        row = next(r for r in rows if r['SecuritiesCompanyCode'] == '3324')
        if change == 'old_target': row['Date'] = '1150901'
        elif change == 'future_target': row['Date'] = '1151014'
        elif change == 'wrong_target_ubn': row['UnifiedBusinessNo.'] = '11111111'
        elif change == 'wrong_market': row['SecuritiesCompanyCode'] = '9999'
        elif change == 'small_master': rows = [row]
        raw[url] = json.dumps(rows, ensure_ascii=False).encode()
    result, _ = collect(monkeypatch, raw)
    if change == 'desktop_disagreement':
        assert [r['ticker'] for r in result['candidates']] == EXPECTED[1:]
    else:
        assert result['candidates'] == []


def test_other_market_target_does_not_start_thermal_transport(monkeypatch):
    result, calls = collect(monkeypatch, ticker='3324.TW')
    assert result['status'] == 'not_applicable' and not calls


def test_warm_cache_reuses_original_acquisition_epochs(monkeypatch):
    from data_fetch.market_sources.official_thermal_peer_cohort import get_official_thermal_candidates, RECEIPT_KEY
    result, calls = collect(monkeypatch)
    assert len(calls) == 4
    warm = get_official_thermal_candidates(TICKER, today=TODAY)
    assert len(calls) == 4 and warm['http_request_count'] == 0 and warm['cache_hit'] is True
    assert warm['candidates'] == result['candidates']
    assert warm['candidates'][0][RECEIPT_KEY] == result['candidates'][0][RECEIPT_KEY]


@pytest.mark.parametrize('change', ['missing', 'digest', 'path', 'bytes', 'expired', 'future',
                                  'bool_epoch', 'false_bool', 'different_target', 'wrong_peer'])
def test_saved_candidate_must_revalidate_the_complete_originals(monkeypatch, change):
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    result, _ = collect(monkeypatch)
    row = deepcopy(result['candidates'][0]); ticker = TICKER
    receipt = row[source.RECEIPT_KEY][source.SEGMENT_URL]
    if change == 'missing': row.pop(source.RECEIPT_KEY)
    elif change == 'digest': receipt['raw_response_sha256'] = '0' * 64
    elif change == 'path': receipt['raw_response_path'] = '/tmp/unrelated-original.gz'
    elif change == 'bytes': receipt['raw_response_bytes'] += 1
    elif change == 'expired': receipt['retrieved_at'] = time.time() - 1801
    elif change == 'future': receipt['retrieved_at'] = time.time() + 1
    elif change == 'bool_epoch': receipt['retrieved_at'] = True
    elif change == 'false_bool': row['business_comparability_verified_current'] = 0
    elif change == 'different_target': ticker = '3017.TW'
    elif change == 'wrong_peer': row['ticker'] = '2330.TW'
    assert not source.verified_thermal_candidate(row, ticker, today=TODAY)


def test_receipt_expiry_during_quote_fetch_does_not_publish_candidate_metrics(monkeypatch):
    from data_fetch.market_sources import peers, official_thermal_peer_cohort as source
    result, _ = collect(monkeypatch)
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: [])
    monkeypatch.setattr(peers, 'get_official_thermal_candidates', lambda *a, **k: result)
    class SlowStock(Stock):
        @property
        def info(self):
            for row in result['candidates']:
                row[source.RECEIPT_KEY][source.SEGMENT_URL]['retrieved_at'] = time.time() - 1801
            return super().info
    monkeypatch.setattr(peers.yf, 'Ticker', SlowStock)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(TICKER, '雙鴻', 'Technology', 'Computer Hardware', {})
    assert result['peers'] == [] and result['audit']['usable_count'] == 0


def seed_shared_master(stamp, until):
    import cache_store
    from official_response_evidence import archive_response
    from data_fetch.market_sources.official_company_legal_name import parse_roster
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    url = source.MASTERS['.TW']; raw = originals()[url]
    archive_response(raw, source_url=url, retrieved_at=stamp)
    cache_store.set_cache_json('shared_provider:v1:' + sha256(b'official-company-roster:v2:.TW').hexdigest(),
        {'value': parse_roster(raw, '.TW'), 'fetched_at_epoch': stamp, 'fresh_until_epoch': until}, 86400)


def test_shared_master_keeps_unknown_http_and_original_shorter_expiry(monkeypatch):
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    clock = [time.time()]; monkeypatch.setattr(time, 'time', lambda: clock[0])
    seed_shared_master(clock[0] - 100, clock[0] + 3)
    result, calls = collect(monkeypatch)
    assert len(calls) == 3 and len(result['candidates']) == 5
    receipt = result['candidates'][0][source.RECEIPT_KEY][source.MASTERS['.TW']]
    assert receipt['http_status'] is None and receipt['http_status_observed'] is False
    assert receipt['evidence_kind'] == source.SHARED_KIND
    assert receipt['fresh_until_epoch'] == clock[0] + 3
    assert source.verified_thermal_candidates(result['candidates'], TICKER, today=TODAY)
    clock[0] += 4
    assert not source.verified_thermal_candidates(result['candidates'], TICKER, today=TODAY)


def test_expiry_during_last_archive_rejects_collector_result(monkeypatch):
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    clock = [time.time()]; monkeypatch.setattr(time, 'time', lambda: clock[0])
    seed_shared_master(clock[0] - 100, clock[0] + 3)
    archive = source.archive_response
    def slow_archive(*args, **kwargs):
        result = archive(*args, **kwargs)
        if kwargs['source_url'] == source.SEGMENT_URL:
            clock[0] += 4
        return result
    monkeypatch.setattr(source, 'archive_response', slow_archive)
    result, _ = collect(monkeypatch)
    assert not result['candidates']


def test_native_master_receipt_retains_thirty_minute_limit(monkeypatch):
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    result, _ = collect(monkeypatch)
    receipt = result['candidates'][0][source.RECEIPT_KEY][source.MASTERS['.TWO']]
    assert receipt['fresh_until_epoch'] - receipt['retrieved_at'] <= 1800
    receipt['fresh_until_epoch'] = receipt['retrieved_at'] + 86400
    assert not source.verified_thermal_candidates(result['candidates'], TICKER, today=TODAY)


import pytest
@pytest.fixture(autouse=True)
def replay_acquisition_day(monkeypatch):
    import time
    from datetime import datetime, timezone
    from data_fetch.market_sources import peers
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    monkeypatch.setattr(time, 'time', lambda: datetime(TODAY.year, TODAY.month, TODAY.day, 6, tzinfo=timezone.utc).timestamp())
