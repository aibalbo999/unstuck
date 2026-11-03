"""Honprec's official segment does not establish whole-company comparability."""
from copy import deepcopy
from pathlib import Path
import gzip
import json

import pytest

from test_official_thermal_peer_cohort import (
    EXPECTED, TODAY, Stock, isolated_cache, native_boundary, originals,
    replay_acquisition_day,
)

TICKER = '2354.TW'
ISSUER_URL = 'https://ic.tpex.org.tw/company_chain.php?stk_code=2354'
BASE = Path(__file__).parent / 'fixtures/source_acquisition/honprec_thermal_20261103'


def bodies():
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    raw = originals()
    raw.pop(source.ISSUER_URL)
    raw[ISSUER_URL] = gzip.decompress((BASE / 'issuer.html.gz').read_bytes())
    raw[source.SEGMENT_URL] = gzip.decompress((BASE / 'segment.html.gz').read_bytes())
    return raw


def test_published_honprec_membership_recovers_candidates_from_complete_originals(monkeypatch):
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    calls = native_boundary(monkeypatch, bodies())
    result = source.get_official_thermal_candidates(TICKER, today=TODAY)
    assert result['status'] == 'success'
    assert [r['ticker'] for r in result['candidates']] == EXPECTED
    assert set(calls) == {*source.MASTERS.values(), ISSUER_URL, source.SEGMENT_URL}
    assert source.verified_thermal_candidates(result['candidates'], TICKER, today=TODAY)
    assert not source.verified_thermal_candidates(result['candidates'], '3324.TWO', today=TODAY)
    for row in result['candidates']:
        assert row['issuer_source_url'] == ISSUER_URL
        assert row['issuer_master_anchor']['legal_name'] == '鴻準精密工業股份有限公司'
        assert row['business_comparability_verified_current'] is False
        assert row['numeric_comparability_verified'] is False
        assert row['membership_effective_date_verified'] is False
    warm = source.get_official_thermal_candidates(TICKER, today=TODAY)
    assert warm['http_request_count'] == 0 and warm['cache_hit'] is True
    assert warm['candidates'] == result['candidates'] and len(calls) == 4


def test_normal_collector_uses_verified_segment_despite_vendor_industry_mismatch(monkeypatch):
    from data_fetch.market_sources import peers
    from prompt_peer_projection import comparable_peer_rows
    from stock_snapshot.peers_valuation import _peer_comparison
    calls = native_boundary(monkeypatch, bodies())
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: [])
    monkeypatch.setattr(peers.yf, 'Ticker', Stock)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        TICKER, '鴻準', 'Technology', 'Electronics & Computer Distribution', {})
    assert [r['ticker'] for r in result['peers']] == EXPECTED
    assert result['audit']['usable_count'] == 5 and len(calls) == 4
    assert result['audit']['candidate_attempt_count'] <= 10
    assert comparable_peer_rows(result['peers']) == []
    assert _peer_comparison({'ticker': TICKER, 'dynamic_peer_metrics': result['peers']})['summary']['peer_count'] == 0


@pytest.mark.parametrize('change', ['wrong_page_code', 'wrong_page_name', 'missing_target',
                                  'desktop_disagreement', 'wrong_segment', 'wrong_ubn'])
def test_honprec_requires_exact_target_page_both_segment_panels_and_current_identity(monkeypatch, change):
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    raw = bodies()
    if change == 'wrong_page_code':
        raw[ISSUER_URL] = raw[ISSUER_URL].replace(b'2354', b'2355')
    elif change == 'wrong_page_name':
        raw[ISSUER_URL] = raw[ISSUER_URL].replace('鴻準'.encode(), '其他'.encode())
    elif change == 'missing_target':
        raw[source.SEGMENT_URL] = raw[source.SEGMENT_URL].replace(b'stk_code=2354', b'stk_code=2355')
    elif change == 'desktop_disagreement':
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw[source.SEGMENT_URL].decode(), 'html.parser')
        first = soup.select('div#companyList_FB00')[0]
        first.find('a', href='company_basic.php?stk_code=2354').string = '其他'
        raw[source.SEGMENT_URL] = str(soup).encode()
    elif change == 'wrong_segment':
        raw[source.SEGMENT_URL] = raw[source.SEGMENT_URL].replace(b'companyList_FB00', b'companyList_FX00')
    else:
        rows = json.loads(raw[source.MASTERS['.TW']])
        next(r for r in rows if r['公司代號'] == '2354')['營利事業統一編號'] = '00000000'
        raw[source.MASTERS['.TW']] = json.dumps(rows, ensure_ascii=False).encode()
    native_boundary(monkeypatch, raw)
    assert source.get_official_thermal_candidates(TICKER, today=TODAY)['candidates'] == []


def test_honprec_proof_does_not_depend_on_another_targets_membership(monkeypatch):
    from data_fetch.market_sources import official_thermal_peer_cohort as source
    raw = bodies()
    raw[source.SEGMENT_URL] = raw[source.SEGMENT_URL].replace(b'stk_code=3324', b'stk_code=3325')
    native_boundary(monkeypatch, raw)
    result = source.get_official_thermal_candidates(TICKER, today=TODAY)
    assert [row['ticker'] for row in result['candidates']] == EXPECTED


def test_honprec_refresh_accepts_only_exact_equity_context_and_originals(monkeypatch):
    from data_fetch.market_sources import peers
    from fastapi import HTTPException
    from peer_source_refresh import validate_peer_refresh_context
    from thermal_peer_source_refresh import merge_thermal_peer_source
    import thermal_peer_source_refresh as refresh
    from datetime import datetime
    import time
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(time.time(), tz)
    monkeypatch.setattr(refresh, 'datetime', Clock)
    native_boundary(monkeypatch, bodies())
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: [])
    monkeypatch.setattr(peers.yf, 'Ticker', Stock)
    old = {'ticker': TICKER, 'company_name': '鴻準 / Foxconn Technology Co., Ltd.',
           'instrument_type': 'EQUITY', 'dynamic_peer_metrics': [], 'current_price': 100,
           'source_audit': []}
    before = deepcopy(old)
    assert validate_peer_refresh_context(old, TICKER) == 'thermal'
    value = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        TICKER, '鴻準', 'Technology', 'Electronics & Computer Distribution', {})['peers']
    audits = [{'source': 'dynamic_peer_metrics', 'provider': 'FinMind/yfinance',
               'status': 'success', 'fetch_id': 'isolated-honprec', 'record_count': 5,
               'usable_count': 5, 'stale': False, 'fetched_at_epoch': time.time()}]
    merged = merge_thermal_peer_source(old, [], value, audits, TICKER)
    assert merged['dynamic_peer_metrics'] == value and old == before
    assert merged['current_price'] == old['current_price']
    for field, invalid in [('company_name', '另一家公司'), ('ticker', '2354.TWO'),
                           ('instrument_type', 'ETF')]:
        wrong = {**old, field: invalid}
        with pytest.raises(HTTPException) as raised:
            validate_peer_refresh_context(wrong, TICKER)
        assert raised.value.status_code == 400
    for row in value:
        row['business_comparability_verified_current'] = True
    with pytest.raises(HTTPException) as raised:
        merge_thermal_peer_source(old, [], value, audits, TICKER)
    assert raised.value.status_code == 502 and old == before
