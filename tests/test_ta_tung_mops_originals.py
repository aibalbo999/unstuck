"""Synthetic public contract and optional private originals; replay is not acquisition."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json

import httpx
import pytest

from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
from data_fetch.market_sources.mops_json_company_history import verified_json_record
from source_content_selection import select_company_records

FIXTURE = Path(__file__).parent / 'fixtures/mops_1623_announcements_synthetic.json'
PRIVATE_FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/mops_ordinary_originals_1623_20261103.json'
CONTEXT = {'ticker': '1623.TW', 'instrument_type': 'EQUITY',
           'company_identity': {'official_name': '大東電', 'ticker': '1623.TW'}}


def replay(change=None, *, native=False):
    path = PRIVATE_FIXTURE if native else FIXTURE
    if native and not path.exists():
        pytest.skip('Private native originals are unavailable; synthetic contract checks remain active')
    fixture = json.loads(path.read_text())
    originals = fixture['wire_originals']
    assert len(originals) == 4
    for item in originals:
        raw = item['raw_body_utf8'].encode()
        assert sha256(raw).hexdigest() == item['response_sha256']
        assert len(raw) == item['response_bytes']
    if change:
        change(originals)
    by_request = {(x['url'], json.dumps(x['parameters'], sort_keys=True)): x for x in originals}
    calls = []
    def get(*args, **kwargs):
        pytest.fail('Qualified JSON issuer must not fall back to an unbound legacy route')
    def post(url, **kwargs):
        key = (url, json.dumps(kwargs['json'], sort_keys=True))
        calls.append(key)
        return httpx.Response(200, content=by_request[key]['raw_body_utf8'].encode(),
                              request=httpx.Request('POST', url), headers={'Content-Type': 'application/json'})
    now = datetime.fromisoformat(fixture.get('fixture_time') or fixture['captured_at'])
    rows, audit = fetch_recent_company_announcements('1623.TW', now=now, get=get, post=post)
    return rows, audit, calls, now


@pytest.mark.parametrize('native', [False, True])
def test_complete_new_issuer_window_retains_both_bound_originals(native):
    rows, audit, calls, now = replay(native=native)
    assert len(rows) == 2 and audit['status'] == 'success'
    assert audit['coverage_status'] == 'window_complete' and len(calls) == len(set(calls)) == 4
    assert {row['published_at'] for row in rows} == {'2026-10-19T17:59:13+08:00', '2026-10-27T10:33:54+08:00'}
    assert all(row['content_truncated'] is False and verified_json_record(row, CONTEXT) == '大東電' for row in rows)
    selected, _ = select_company_records(rows, CONTEXT, cutoff=now)
    assert len(selected) == 2
    assert all(row['source_role'] == 'issuer_statement' and row['catalyst_assessment'] == 'not_assessed' for row in rows)
    assert 'request_observations' not in audit, 'Injected replay is not current native HTTP proof'


@pytest.mark.parametrize('damage', ['issuer', 'company', 'publication', 'title', 'empty_body'])
def test_wrong_issuer_publication_or_body_is_not_published_as_a_complete_success(damage):
    def change(originals):
        item = next(x for x in originals if x['url'].endswith('_detail'))
        payload = json.loads(item['raw_body_utf8'])
        result = payload['result']
        if damage == 'issuer': result['companyId'] = '1626'
        elif damage == 'company': result['companyAbbreviation'] = '其他公司'
        elif damage == 'publication': result['data'][0][1] = '115/10/20'
        elif damage == 'title': result['data'][0][6] = '另一則公告'
        else: result['data'][0][9] = ''
        item['raw_body_utf8'] = json.dumps(payload, ensure_ascii=False)
    rows, audit, _, _ = replay(change)
    assert len(rows) == 1 and audit['status'] != 'success'
    assert audit['coverage_status'] == 'partial'
    assert audit['rejected_reason_counts']['original_unverified'] == 1


def test_saved_context_cannot_rebind_originals_to_another_issuer():
    rows, _, _, _ = replay()
    wrong = deepcopy(CONTEXT)
    wrong['company_identity']['official_name'] = '其他公司'
    assert all(verified_json_record(row, wrong) is None for row in rows)


def test_new_json_component_preserves_original_report_and_never_counts_replay_as_http(monkeypatch, tmp_path):
    import asyncio
    import time
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from data_fetch.types import ProviderResult
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db, events
    from provider_acquisition import get_provider_acquisition_summary
    now = datetime.fromisoformat(json.loads(FIXTURE.read_text())['fixture_time'])
    monkeypatch.setattr(time, 'time', lambda: now.timestamp())
    init_db()
    rows, audit, _, _ = replay()
    storage = InMemoryStorage()
    name, keys, snapshot = saved_report(storage)
    snapshot['ticker'] = snapshot['data']['ticker'] = '1623.TW'
    snapshot['data'].update(deepcopy(CONTEXT), company_name='大東電')
    storage.save_report(keys.data_key, json.dumps(snapshot).encode(), content_type='application/json')
    calls = []
    def acquire(request, context):
        calls.append(request.ticker)
        cached = {**audit, 'source': 'recent_catalysts', 'provider': 'TWSE company announcement history',
                  'status': 'skipped_fresh_cache', 'event_kind': 'cache_hit', 'cache_hit': True, 'stale': False,
                  'http_request_sent': False, 'http_request_count': 0, 'fetched_at_epoch': now.timestamp()}
        return ProviderResult('recent_catalysts', cached['provider'], cached['status'], value=rows, audit=cached)
    service = StockDataService(registry=ProviderRegistry([
        CallableProvider('recent_catalysts', 'TWSE company announcement history', acquire)]))
    response = asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
                           refresh_service=service, source='official_announcements'))
    after = json.loads(storage.get_report(keys.data_key).content)
    assert calls == ['1623.TW'] and len(after['data']['recent_catalysts']) == 2
    for field in ('current_price', 'revenue_history', 'years', 'earnings_call', 'peer_discovery_results'):
        assert after['data'][field] == snapshot['data'][field]
    for field in ('analysis_evidence', 'report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance'):
        assert after[field] == snapshot[field]
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'
    assert response['analysis_text_stale'] is True and len(events()) == 1
    source = next(x for x in get_provider_acquisition_summary()['sources'] if x['source'] == 'recent_catalysts')
    assert source['fetch_attempts'] == source['fetched_count'] == 0
