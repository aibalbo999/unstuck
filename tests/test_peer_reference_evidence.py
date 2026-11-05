"""Derivation proof mutations are offline tests, not provider acquisitions."""
from copy import deepcopy
from datetime import date
import json
import time

import pytest

from test_peer_reference_income import reference_body, index_body, income_body
from data_fetch.market_sources import peer_reference_transport as transport

DAY = date(2026, 11, 4)


@pytest.fixture
def evidence_environment(monkeypatch):
    from data_fetch.market_sources import peer_reference_evidence as e
    from test_peer_reference_transport import parts
    import cache_store
    store = {}; calls = []
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store, 'peek_cache_json', lambda key: deepcopy(store.get(key)))
    monkeypatch.setattr(e, 'peek_cache_json', lambda key: deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store, 'set_cache_json', lambda key, value, ttl_seconds=None: store.__setitem__(key, deepcopy(value)))
    rows = [{'公司代號': str(1000+i)} for i in range(800)] + [{
        '公司代號': '6230', '公司名稱': '尼得科超眾科技股份有限公司', '公司簡稱': '尼得科超眾',
        '營利事業統一編號': '34005476', '出表日期': '1151103', '產業別': '25',
        '編制財務報表類型': '1', '特別股': '0', '已發行普通股數或TDR原股發行股數': '86343396'}]
    raw = json.dumps(rows, ensure_ascii=False).encode()
    from hashlib import sha256
    master = {'cache_hit': True, 'stale': False, 'fetched_at_epoch': time.time()-10,
        'cache_source': 'official-company-roster:v2:.TW',
        'source_url': 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L',
        'source_payload_sha256': sha256(raw).hexdigest(), 'source_payload_bytes': len(raw),
        'evidence_kind': 'cached_complete_source_payload_verified_by_digest', 'http_status_observed': False}
    monkeypatch.setattr(e, 'read_cached_listed_roster_bytes', lambda: (raw, deepcopy(master)))
    def download(self, request, diagnostic):
        calls.append(deepcopy(request)); p = request['params']; kind = request['kind']
        if kind == 'home': body = '<html><body><a name="IncomeStatement">綜合損益表(累計)</a></body></html>'.encode()
        elif kind == 'methodology':
            body = ('<html><head><meta charset="utf-8"></head><body><li>本益比 = 收盤價／每股參考稅後純益，'
                '其中每股參考稅後純益 = 該公司稅後參考純益／發行參考股數，'
                '當每股參考稅後純益為0或負數時，則不計算本益比。'
                '以上純益資料採用各上市公司於公開資訊觀測站過去已申報格式化之近滿4季財務報告為計算基礎。'
                '</li></body></html>').encode()
        elif kind == 'reference': body = reference_body()
        elif kind == 'index': body = index_body(p['year'], [2] if p['year'] == 2026 else [2, 4])
        else: body = income_body(p['year'], p['quarter'], {(2026,2):-156827, (2025,2):69020, (2025,4):-210560}[(p['year'],p['quarter'])])
        value = parts(request, body=body)
        return self._consume(request, request['url'], value, 0, None, diagnostic)
    monkeypatch.setattr(transport.PeerIncomeHttp, '_download', download)
    return store, calls, master


def test_normal_proof_keeps_pe_undefined_and_recomputes_exact_reference_income(evidence_environment):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income, verified_reference_income
    value = collect_reference_income('6230.TW', '2026-11-04', today=DAY)
    proof = value['source_record_archive']
    verified = verified_reference_income(proof, ticker='6230.TW', observed_at='2026-11-04', today=DAY)
    assert verified['net_income_twd'] == -436407000
    assert verified['period_start'] == '2025-07-01' and verified['period_end'] == '2026-06-30'
    assert 'pe_ttm' not in value and value['reason'] == 'not_applicable_nonpositive_reference_income'
    assert len(evidence_environment[1]) == 8


@pytest.mark.parametrize('damage', ['amount', 'period', 'issuer', 'component_missing',
    'request', 'source_owner', 'master_owner', 'master_digest', 'wrong_day'])
def test_derivation_never_substitutes_unbound_fields_for_complete_live_originals(evidence_environment, damage):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income, verified_reference_income
    store, calls, master = evidence_environment
    value = collect_reference_income('6230.TW', '2026-11-04', today=DAY)
    proof = deepcopy(value['source_record_archive'])
    if damage == 'amount': proof['derived']['net_income_twd'] = -1
    elif damage == 'period': proof['derived']['period_end'] = '2026-09-30'
    elif damage == 'issuer': proof['ticker'] = '2330.TW'
    elif damage == 'component_missing': proof['components'].pop('income:2025Q2')
    elif damage == 'request': proof['components']['income:2025Q2']['spec']['data']['ys'] = '20262'
    elif damage == 'source_owner': store.clear()
    elif damage == 'master_owner': master['fetched_at_epoch'] += 1
    elif damage == 'master_digest': master['source_payload_sha256'] = '0'*64
    else: proof['observed_at'] = '2026-11-03'
    assert verified_reference_income(proof, ticker='6230.TW', observed_at='2026-11-04', today=DAY) is None


def test_existing_valid_core_annual_original_is_not_refetched_under_a_new_namespace(evidence_environment):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    store, calls, _ = evidence_environment
    # Unsupported existing annual schemas are held for original reuse qualification.
    store['financial_data:6230.TW'] = {'ticker': '6230.TW', 'source_audit': [{
        'source': 'financial_statements', 'status': 'success',
        'documents': [{'year': 2025, 'url': 'https://example.invalid/old-original'}]}]}
    with pytest.raises(ValueError, match='existing annual'):
        collect_reference_income('6230.TW', '2026-11-04', today=DAY)
    assert not calls


def test_unsupported_issuer_or_stale_valuation_starts_no_new_transport(evidence_environment):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    for ticker, observed in [('2330.TW', '2026-11-04'), ('6230.TW', '2026-10-01')]:
        with pytest.raises(ValueError): collect_reference_income(ticker, observed, today=DAY)
    assert not evidence_environment[1]
