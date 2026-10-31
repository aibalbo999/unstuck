"""The exact official mirror must pass the same raw-evidence gate as primary."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import httpx
import pytest
from test_oct5_source_admission import archive, official_value
from report_source_admission import institutional_admission


def test_existing_transport_mirror_is_usable_by_original_evidence_gate(archive, monkeypatch):
    import official_institutional_source as source
    import external_http_client
    import search_provider_runtime as runtime
    import official_source_runtime
    from contextlib import contextmanager
    import search_admission
    @contextmanager
    def admission(*a, **kw): yield lambda: True
    monkeypatch.setattr(search_admission, 'endpoint_admission', admission)
    monkeypatch.setattr(runtime, 'cooldown_state', lambda *a: {})
    monkeypatch.setattr(runtime, 'record_observation', lambda *a, **kw: None)
    monkeypatch.setattr(official_source_runtime, 'failure_state_snapshot', lambda *a: {})
    monkeypatch.setattr(official_source_runtime, 'reset_failure_history_after_success', lambda *a, **kw: None)
    raw = (Path(__file__).parent / 'fixtures/oct5_t86_raw.json').read_bytes()
    urls = []
    def get(url, **kwargs):
        urls.append(url)
        if len(urls) == 1: raise httpx.ConnectTimeout('ordinary primary timeout')
        return httpx.Response(200, content=raw, request=httpx.Request('GET', url))
    monkeypatch.setattr(external_http_client, 'sync_get', get)
    report = source._fetch_report('TWSE', '2026-10-05', 8)
    value = official_value()
    value['latest_official_observation']['raw_evidence'] = report['raw_evidence']
    assert urls == [source._url('TWSE', '2026-10-05'), source._url('TWSE', '2026-10-05').replace('www.twse.com.tw', 'wwwc.twse.com.tw')]
    assert report['fallback_reason'] == 'timeout'
    result = institutional_admission(value, '2026-10-05')
    assert result['eligible'], result
    assert result['finality_guaranteed'] is False


@pytest.mark.parametrize('change', ['evil_host', 'http', 'extra_query', 'fragment', 'other_day', 'other_market', 'provisional', 'shares', 'tampered'])
def test_mirror_does_not_waive_endpoint_date_or_raw_body_rules(archive, change):
    import gzip
    value = official_value(); proof = value['latest_official_observation']['raw_evidence']
    proof['source_url'] = proof['source_url'].replace('www.twse.com.tw', 'wwwc.twse.com.tw')
    if change == 'evil_host': proof['source_url'] = proof['source_url'].replace('wwwc.twse.com.tw', 'wwwc.twse.com.tw.evil.example')
    elif change == 'http': proof['source_url'] = proof['source_url'].replace('https:', 'http:')
    elif change == 'extra_query': proof['source_url'] += '&date=20261006'
    elif change == 'fragment': proof['source_url'] += '#anything'
    elif change == 'other_day': proof['source_url'] = proof['source_url'].replace('20261005', '20261006')
    elif change == 'other_market': value['latest_official_observation']['market'] = 'TPEX'
    elif change == 'provisional': proof['retrieved_at'] = '2026-10-05T14:29:59+00:00'
    elif change == 'shares': value['daily_category_observations'][0]['net_buy_shares'] += 1
    else: Path(proof['raw_response_path']).write_bytes(gzip.compress(b'changed body'))
    assert institutional_admission(value, '2026-10-05')['eligible'] is False
