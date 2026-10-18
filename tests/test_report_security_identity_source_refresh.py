"""Public boundary checks. Original private-data replay cases remain local."""
import json, time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def isolated_identity_circuit():
    import os
    from provider_resilience import clear_provider_circuits, clear_provider_throttles
    from data_fetch.market_sources.twse_security_identity import PROVIDER
    assert os.environ.get('STOCK_AGENT_TEST_NO_NETWORK') == '1'
    clear_provider_circuits(PROVIDER)
    clear_provider_throttles(PROVIDER)
    yield
    clear_provider_circuits(PROVIDER)
    clear_provider_throttles(PROVIDER)

def native(monkeypatch, ticker='6669.TW', change=None):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp as SecurityIdentityHttp
    from data_fetch.market_sources.issuer_news_transport import ROSTER_URL
    calls = []
    raw = (Path(__file__).parent / 'fixtures/source_acquisition' / ('twse_isin_' + ticker.split('.')[0] + '_captured_20261011.html')).read_bytes()
    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    stamp = str(int(today[:4]) - 1911) + today[4:]
    records = [{'公司代號': str(n), '公司簡稱': '測試' + str(n), '公司名稱': '測試' + str(n), '出表日期': stamp} for n in range(1000, 2000)]
    records.extend([{'公司代號': '6669', '公司簡稱': '緯穎', '公司名稱': '緯穎科技股份有限公司', '出表日期': stamp}, {'公司代號': '6924', '公司簡稱': '榮惠-KY創', '公司名稱': '榮惠集團(開曼)股份有限公司', '出表日期': stamp}, {'公司代號': '2353', '公司簡稱': '宏碁', '公司名稱': '宏碁股份有限公司', '出表日期': stamp}])
    roster = json.dumps(records, ensure_ascii=False).encode()

    def get(self, url):
        calls.append(url)
        body = roster if url == ROSTER_URL else raw
        if change and url != ROSTER_URL:
            body = change(body)
        self.components.append({'url': url, 'cache_hit': False, 'http_request_sent': True, 'http_request_count': 1, 'fetched_at_epoch': time.time()})
        self.http_request_count += 1
        return body
    monkeypatch.setattr(SecurityIdentityHttp, 'get', get)
    return calls

def test_equivalent_quote_and_official_type_representations_do_not_force_another_analysis():
    from report_refresh_diff import refresh_data_diff, refresh_requires_analysis_rerun
    before = {'data': {'quote_type': 'EQUITY', 'instrument_type': 'EQUITY'}, 'data_trust': {'status': 'fresh'}}
    after = {'data': {'quote_type': 'EQUITY'}, 'data_trust': {'status': 'fresh'}}
    assert not refresh_requires_analysis_rerun(before, after, refresh_data_diff(before, after))

def test_refresh_timestamp_overflow_is_unknown_not_an_exception():
    from report_source_refresh import _timestamp
    assert _timestamp({'fetched_at_epoch': 10 ** 400, 'fetched_at': datetime.now(timezone.utc).isoformat()}) is None

def test_corrupt_archived_original_rejects_verified_identity(monkeypatch, tmp_path):
    from data_fetch.market_sources.twse_security_identity import fetch_security_identity, verified_security_identity
    from official_response_evidence import read_response
    import gzip
    native(monkeypatch)
    diagnostics = {}
    value = fetch_security_identity('6669.TW', diagnostics=diagnostics)
    assert verified_security_identity(value, '6669.TW')
    proof = value['source_record_archive']['identity']
    p = Path(proof['raw_response_path'])
    before = p.read_bytes()
    try:
        p.write_bytes(gzip.compress(b'incomplete source'))
        assert not verified_security_identity(value, '6669.TW')
    finally:
        p.write_bytes(before)

@pytest.mark.parametrize('bad', ['duplicate_empty_owner', 'wrong_host', 'http_boolean', 'wrong_epoch'])
def test_contradictory_saved_identity_receipt_is_rejected(monkeypatch, bad):
    from data_fetch.market_sources.twse_security_identity import fetch_security_identity, verified_security_identity
    native(monkeypatch)
    value = fetch_security_identity('6669.TW', diagnostics={})
    copy = deepcopy(value)
    if bad == 'duplicate_empty_owner':
        copy['source_record_archive']['identity']['source_url'] += '&owncode='
    elif bad == 'wrong_host':
        copy['source_record_archive']['identity']['source_url'] = copy['source_url'].replace('isin.twse.com.tw', 'invalid.example')
    elif bad == 'http_boolean':
        copy['source_record_archive']['identity']['http_status'] = True
    else:
        copy['source_record_archive']['identity']['retrieved_at'] -= 60
    assert not verified_security_identity(copy, '6669.TW')
import data_fetch.market_sources.twse_security_identity as source

def test_non_raw_evidence_kind_cannot_substantiate_full_original_classification(monkeypatch):
    native(monkeypatch)
    value = source.fetch_security_identity('6669.TW', diagnostics={})
    value['source_record_archive']['identity']['evidence_kind'] = 'selected_decoded_fields'
    assert not source.verified_security_identity(value, '6669.TW')
