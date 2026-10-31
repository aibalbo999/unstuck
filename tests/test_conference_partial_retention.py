"""Partial HTTP200 PDF delivery through real collector and public report refresh."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import pytest
from test_voltronic_conference import profile, harness, acquire, identity, NOW
from test_report_conference_retention import refresh
from test_report_refresh_acquisition_audit import init_db, events
from data_freshness import build_source_freshness_entry
from search_provider_runtime import SourceResponseError

F = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/voltronic_partial_pdf_20261015.json').read_text())
TICKER = '6409.TW'


def packets(monkeypatch, harness):
    from data_fetch.market_sources import voltronic_conference as source
    from data_fetch.market_sources.voltronic_conference_transport import ConferenceHttp
    successful = {}
    value = acquire('voltronic', diagnostics=successful)
    stamp = value['fetched_at_epoch']
    def audit(details, *, failed=False):
        return {**deepcopy(details), 'source': 'earnings_call', 'provider': source.PROVIDER,
                'ticker': TICKER, 'status': 'error' if failed else 'success',
                'record_count': 0 if failed else 1, 'cache_hit': False, 'stale': False,
                'message': details.get('message', 'Saved native partial transfer'),
                'fetched_at_epoch': time.time(), 'fetched_at': datetime.fromtimestamp(time.time(), timezone.utc).isoformat()}
    old_audit = audit(successful)
    data = {**identity('voltronic'), 'earnings_call': value, 'source_audit': [old_audit],
            'source_freshness': {'earnings_call': build_source_freshness_entry('earnings_call', TICKER, stamp, cache_hit=False)},
            'current_price': 100}
    old = {'ticker': TICKER, 'company_name': data['company_name'], 'pipeline': 'v4',
           'refreshed_from_report': '6409_TW_v4_report_partial_retention.html', 'data': deepcopy(data),
           'source_audit': [deepcopy(old_audit)], 'source_freshness': deepcopy(data['source_freshness']),
           'analysis_evidence': {'unchanged': 'original conclusion input'},
           'report_lint': {'unchanged': 'quality warning'}, 'evidence_exit_gate': {'unchanged': 'original gate'}}
    from report_analysis_evidence import capture_analysis_evidence
    old['analysis_evidence'] = capture_analysis_evidence({'data': data}, generated_at=datetime.fromtimestamp(stamp, timezone.utc).isoformat())
    original = ConferenceHttp.download_original
    def partial(http, url, diagnostic):
        if url != source.PDF_URL:
            return original(http, url, diagnostic)
        http.http_request_count += 1
        diagnostic.update(deepcopy(F['component']))
        raise SourceResponseError('timeout', status_code=200)
    monkeypatch.setattr(ConferenceHttp, 'download_original', partial)
    monkeypatch.setattr(time, 'time', lambda: NOW + 60)
    failed = {}
    with pytest.raises(SourceResponseError) as error:
        acquire('voltronic', diagnostics=failed)
    assert error.value.error_kind == 'timeout'
    incoming = deepcopy(data)
    incoming.update(earnings_call={}, current_price=101, source_audit=[audit(failed, failed=True)])
    incoming['source_freshness']['earnings_call'] = build_source_freshness_entry('earnings_call', TICKER, NOW + 60, cache_hit=False)
    return old, incoming


def test_partial_http200_retains_verified_body_without_new_success(harness, monkeypatch, tmp_path):
    from provider_acquisition import project_acquisition_events
    old, incoming = packets(monkeypatch, harness)
    before = deepcopy(incoming)
    init_db(); ledger = events()
    current, result, keys, storage = refresh(old, incoming, tmp_path)
    data = current['data']
    assert data['earnings_call'] == old['data']['earnings_call'], 'partial transfer erased verified original'
    assert len(data['earnings_call']['documents'][0]['pages']) == 32
    assert data['conference_retention']['new_acquisition'] is False
    assert data['source_freshness']['earnings_call']['fetched_at_epoch'] == NOW
    assert data['source_freshness']['earnings_call']['stale'] is True
    assert data['source_audit'][1:] == incoming['source_audit']
    assert data['current_price'] == 101 and incoming == before and result['refreshed_data'] == before
    assert storage.get_report(keys.html_key).content == b'original HTML'
    assert storage.get_report(keys.md_key).content == b'original Markdown'
    for k in ('analysis_evidence', 'report_lint', 'evidence_exit_gate'):
        assert current[k] == old[k]
    assert events() == ledger
    rows = [{**a, 'created_at': time.time(), 'details_json': json.dumps(a)} for a in data['source_audit']]
    projected = project_acquisition_events(rows, window='last_24h', now=time.time())['sources'][0]
    assert projected['fetched_count'] == 0 and projected['failed_count'] == 1
    assert projected['stale_cache_count'] == 1


def test_observed_server_error_still_retains_historical_body(harness, monkeypatch, tmp_path):
    old, incoming = packets(monkeypatch, harness)
    audit = incoming['source_audit'][0]
    audit['error_kind'] = 'server_error'
    part = audit['component_statuses'][-1]
    part.update(http_status=500, http_status_observed=True, error_kind='server_error',
                response_bytes=0, response_bytes_read=0)
    current, _, _, _ = refresh(old, incoming, tmp_path)
    assert current['data']['earnings_call'] == old['data']['earnings_call']
    assert current['data']['conference_retention']['new_acquisition'] is False
    assert current['data']['source_audit'][1:] == incoming['source_audit']


@pytest.mark.parametrize('change', ['complete', 'missing_complete', 'no_error', 'wrong_body', 'wrong_method',
    'wrong_request_hash', 'missing_index', 'missing_master', 'index_partial', 'cache_hit', 'not_sent',
    'missing_status', 'string_status', 'bool_status', 'zero_status', 'read_all_bytes', 'bool_bytes', 'different_url', 'terminal_status'])
def test_partial_marker_cannot_hide_conflict_or_unproved_failure(harness, monkeypatch, tmp_path, change):
    old, incoming = packets(monkeypatch, harness)
    parts = incoming['source_audit'][0]['component_statuses']; part = parts[-1]
    if change == 'complete': part['response_complete'] = True
    elif change == 'missing_complete': part.pop('response_complete')
    elif change == 'no_error': part.pop('error_kind')
    elif change == 'wrong_body': part['request_body'] = part['request_body'].replace('6409', '3023')
    elif change == 'wrong_method': part['request_method'] = 'GET'
    elif change == 'wrong_request_hash': part['request_sha256'] = 'f' * 64
    elif change == 'missing_index': parts.pop(1)
    elif change == 'missing_master': parts.pop(0)
    elif change == 'index_partial':
        parts[1].pop('original_receipt'); parts[1].update(response_complete=False, error_kind='timeout')
    elif change == 'cache_hit': part['cache_hit'] = True
    elif change == 'not_sent': part['http_request_sent'] = False
    elif change == 'missing_status': part.pop('http_status')
    elif change == 'string_status': part['http_status'] = '200'
    elif change == 'bool_status': part['http_status'] = True
    elif change == 'zero_status': part['http_status'] = 0
    elif change == 'read_all_bytes': part['response_bytes_read'] = part['response_bytes'] = old['data']['earnings_call']['voltronic_conference_receipt']['pdf']['raw_response_bytes']
    elif change == 'bool_bytes': part['response_bytes_read'] = part['response_bytes'] = True
    elif change == 'different_url': part['url'] += '?other=1'
    else: part['http_status'] = 403
    current, _, _, _ = refresh(old, incoming, tmp_path)
    assert current['data']['earnings_call'] == {}
    assert 'conference_retention' not in current['data']
