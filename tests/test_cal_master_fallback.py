"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
from hashlib import sha256
import gzip, json, time
import pytest
from test_cal_annual_bridge import Http, F
JSON_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L'

def master_bytes():
    body = gzip.decompress((F / 'master-json.gz').read_bytes())
    meta = json.loads((F / 'master-json.json').read_text())
    assert sha256(body).hexdigest() == meta['sha256'] and len(body) == meta['bytes']
    return body

class LegacyJson(Http):
    """Replay fixture for the pre-shared raw JSON receipt; transport is tested separately."""

    def request(self, url, **kwargs):
        from data_fetch.market_sources.cal_annual_transport import MASTER_URL
        from search_provider_runtime import SourceResponseError
        from official_response_evidence import archive_response
        if url == MASTER_URL:
            self.calls.extend(['CSV failed', 'JSON master'])
            body = master_bytes()
            proof = archive_response(body, source_url=JSON_URL, retrieved_at=time.time(), http_status=200)
            self.components.extend([{'url': url, 'http_request_sent': True, 'http_status': 200, 'error_kind': 'timeout'}, {'url': JSON_URL, 'http_request_sent': True, 'http_status': 200, 'status': 'complete'}])
            return (body, proof)
        return super().request(url, **kwargs)

def test_legacy_raw_json_receipt_keeps_five_years_and_original_failure_metadata():
    from data_fetch.market_sources.cal_annual_bridge import fetch_bridge_result, project_bridge_history
    h = LegacyJson()
    r = fetch_bridge_result('2610.TW', transport=h)
    assert r['audit']['status'] == 'success' and r['audit']['record_count'] == 5
    assert r['value']['years'] == ['2021', '2022', '2023', '2024', '2025']
    assert r['value']['issuer_master_receipt']['source_url'] == JSON_URL
    assert r['value']['issuer_anchor']['master_response_sha256'] == sha256(master_bytes()).hexdigest()
    assert r['audit']['http_request_count'] == len(h.calls) == 25
    assert r['audit']['component_statuses']['0']['error_kind'] == 'timeout'
    assert project_bridge_history(r['value'], '2610.TW') == r['value']

@pytest.mark.parametrize('change', [lambda rows: rows.append(deepcopy(next((x for x in rows if x['公司代號'] == '2610')))), lambda rows: next((x for x in rows if x['公司代號'] == '2610')).update({'營利事業統一編號': '00000000'}), lambda rows: next((x for x in rows if x['公司代號'] == '2610')).update({'網址': 'https://example.com'}), lambda rows: next((x for x in rows if x['公司代號'] == '2610')).update({'出表日期': '1150101'}), lambda rows: rows.append(None)])
def test_json_roster_rejects_identity_date_or_shape_conflicts(change):
    from data_fetch.market_sources.cal_annual_transport import parse_master
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    rows = json.loads(master_bytes())
    change(rows)
    with pytest.raises(FilingError):
        parse_master(json.dumps(rows, ensure_ascii=False).encode(), source_url=JSON_URL)

def test_json_duplicate_fields_and_wrong_source_fail_closed():
    from data_fetch.market_sources.cal_annual_transport import parse_master
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    with pytest.raises(FilingError):
        parse_master(b'[{"a":1,"a":2}]', source_url=JSON_URL)
    with pytest.raises(FilingError):
        parse_master(master_bytes(), source_url=JSON_URL + '?fresh=1')

@pytest.mark.parametrize('url,remaining,expected', [('IR', 45, 5.0), ('IR', 3, 3.0), ('PDF', 45, 5.0)])
def test_non_master_original_native_caps_and_shared_deadline_unchanged(monkeypatch, url, remaining, expected):
    from data_fetch.market_sources import issuer_news_transport as native
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp, MASTER_URL, IR_URL, PDF_URLS, contract
    from search_provider_runtime import SourceResponseError
    url = {'CSV': MASTER_URL, 'IR': IR_URL, 'PDF': next(iter(PDF_URLS))}.get(url, url)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    monkeypatch.setattr(native, 'cooldown_state', lambda key: None)
    monkeypatch.setattr(native.time, 'monotonic', lambda: 100.0)
    seen = []

    def curl(args, deadline, **kwargs):
        seen.append((args, deadline, kwargs))
        return ({'body': b'', 'headers': b'', 'metadata': b'', 'process_started': True}, 28, 'timeout')
    monkeypatch.setattr(native, 'collect_capped_process', curl)
    h = BridgeHttp(seconds=remaining)
    with pytest.raises(SourceResponseError):
        h.request(url)
    args, end, limits = seen[0]
    assert float(args[args.index('--max-time') + 1]) == expected and end == 100 + expected
    assert float(args[args.index('--connect-timeout') + 1]) == 2.0
    assert args[args.index('--retry') + 1] == '0' and args[args.index('--max-redirs') + 1] == '0'
    assert limits['body_limit'] == contract(url)[0]
    assert len(seen) == 1 and h.components[0]['error_kind'] == 'timeout'

@pytest.fixture(scope='module')
def alternate_packet():
    from data_fetch.market_sources.cal_annual_bridge import fetch_bridge_histories
    return fetch_bridge_histories('2610.TW', transport=LegacyJson())

@pytest.mark.parametrize('change', [lambda p: p['issuer_master_receipt'].update(source_url='https://example.com/master'), lambda p: p['issuer_master_receipt'].update(raw_response_sha256='0' * 64), lambda p: p['issuer_master_receipt'].update(cache_hit=True), lambda p: p['issuer_master_receipt'].update(retrieved_at=time.time() + 3600), lambda p: p['issuer_master_receipt'].update(historical_point_in_time_verified=True), lambda p: p['issuer_anchor'].update(master_response_sha256='0' * 64)])
def test_alternative_cannot_bypass_original_provenance_replay(alternate_packet, change):
    from data_fetch.market_sources.cal_annual_bridge import project_bridge_history
    p = deepcopy(alternate_packet)
    change(p)
    assert project_bridge_history(p, '2610.TW') is None
