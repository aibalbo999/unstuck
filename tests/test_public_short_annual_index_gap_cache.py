"""A fully verified short public index stays a failure, without repeat HTTP.

Only the existing captured index is real. Mock HTTP and damaged bodies below
are isolated test inputs; none establish a live acquisition or missing zero.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import time

import pytest

from test_public_annual_gap_cache import isolated_cache_and_provider

RAW = Path(__file__).parent.joinpath(
    'fixtures/source_acquisition/seetel_short_annual_index_complete_20261010.html').read_bytes()


class ShortIndexTransport:
    def __init__(self, raw=RAW):
        self.raw = raw
        self.calls = []
        self.non_index_calls = []
        self.components = []
        self.deadline = time.monotonic() + 45
        self.batch_count = 0

    @contextmanager
    def batch(self):
        self.batch_count += 1
        yield self

    def request(self, url, **kwargs):
        from data_fetch.market_sources.mops_public_annual import INDEX_URL
        from data_fetch.market_sources.official_xbrl_financial import FilingError
        from official_response_evidence import archive_response
        if url != INDEX_URL:
            self.non_index_calls.append(url)
            raise FilingError('test transport has no statement fixture')
        assert kwargs == {'request': {'step': '1', 'firstin': 'ture', 'off': '1',
            'queryName': 'co_id', 'inpuType': 'co_id', 'TYPEK': 'all', 'co_id': '7740'}}
        self.calls.append((url, kwargs))
        self.components.append({'url': url, 'http_request_sent': True, 'http_status': 200,
            'response_bytes': len(self.raw), 'response_sha256': sha256(self.raw).hexdigest(), 'status': 'complete'})
        return self.raw, archive_response(self.raw, source_url=url, retrieved_at=time.time(), http_status=200)


def run(transport):
    from data_fetch.market_sources.mops_public_annual import fetch_public_financial_result
    return fetch_public_financial_result('7740.TW', transport=transport)


def test_complete_short_public_index_warm_read_does_not_repeat_HTTP_or_claim_success():
    from data_fetch.market_sources import mops_public_gap_cache as cache
    from provider_acquisition import observation_kind
    from provider_correlation import correlation_scope
    from provider_observation_details import observation_details
    cold_http = ShortIndexTransport(); warm_http = ShortIndexTransport()
    with correlation_scope(replace=True, fetch_id='short-cold', ticker='7740.TW'):
        cold = run(cold_http)
    with correlation_scope(replace=True, fetch_id='short-warm', ticker='7740.TW'):
        warm = run(warm_http)
    assert len(cold_http.calls) == 1
    assert warm_http.calls == [] and warm_http.non_index_calls == [] and warm_http.batch_count == 0
    assert cold['value'] is warm['value'] is None
    a = warm['audit']
    assert a['status'] == 'error' and a['record_count'] == 0 and a['error_kind'] == 'FilingError'
    assert a['cache_hit'] is True and a['event_kind'] == 'cache_hit' and a['stale'] is False
    assert a['http_request_sent'] is False and a['http_request_count'] == 0
    assert a['original_http_request_count'] == 1 and a['component_statuses'] == {}
    assert a['provider_attempts'] == [] and a['provider_attempt_count'] == 0
    assert a['fetch_id'] == 'short-warm' and a['fetched_at'] == cold['audit']['fetched_at']
    assert a['retry_at'] == datetime.fromisoformat(a['fetched_at']).timestamp() + cache.GAP_RETRY_SECONDS
    assert cache.GAP_RETRY_SECONDS == 24 * 60 * 60
    assert observation_kind({**a, 'details': observation_details(a)}) == 'empty_cache_count'
    assert observation_kind({**cold['audit'], 'details': observation_details(cold['audit'])}) == 'failed_count'


@pytest.mark.parametrize('mutation', ['wrong_preview_issuer', 'wrong_scope_label', 'truncated',
    'missing_header', 'security_page', 'empty_index', 'noncontiguous', 'blank_query'])
def test_unverified_or_noncontiguous_index_never_suppresses_another_attempt(mutation):
    text = RAW.decode()
    if mutation == 'wrong_preview_issuer': text = text.replace('ci-cr-7740-2025Q4', 'ci-cr-2330-2025Q4', 1)
    elif mutation == 'wrong_scope_label': text = text.replace('<td>合併</td>', '<td>個體</td>', 1)
    elif mutation == 'truncated': text = text[:5000]
    elif mutation == 'missing_header': text = text.replace('<th>財報類別</th>', '<th>其他</th>')
    elif mutation == 'security_page': text = '<html><title>Security check</title><body>Verify</body></html>'
    elif mutation == 'empty_index': text = '<html><title>公開資訊觀測站</title><body>無資料</body></html>'
    elif mutation == 'noncontiguous': text = text.replace('112Q4', '110Q4').replace('2023', '2021')
    else: text = text.replace('&report_id=C', '&report_id=C&unexpected=', 1)
    first = ShortIndexTransport(text.encode()); again = ShortIndexTransport(text.encode())
    run(first); result = run(again)
    assert len(first.calls) == len(again.calls) == 1
    assert result['audit']['cache_hit'] is False and result['value'] is None


def four_filing_index():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(RAW, 'html.parser')
    row = next(r for r in soup.find_all('tr') if r.find('td') and r.find('td').get_text(strip=True) == '112Q4')
    extra = BeautifulSoup(str(row), 'html.parser').find('tr')
    extra.find('td').string = '111Q4'
    for button in extra.find_all('input'):
        button['onclick'] = button['onclick'].replace('2023', '2022')
    row.insert_before(extra)
    return str(soup).encode()


def test_four_published_filings_continue_to_statements_and_are_not_short_index_cache():
    from data_fetch.market_sources.annual_filing_index_gap import confirmed_short_annual_index
    raw = four_filing_index()
    assert confirmed_short_annual_index(raw, '7740')['available_consolidated_annual_years'] == [2022, 2023, 2024, 2025]
    first = ShortIndexTransport(raw); again = ShortIndexTransport(raw)
    run(first); result = run(again)
    assert len(first.calls) == len(again.calls) == 1
    assert first.non_index_calls and again.non_index_calls
    assert result['audit']['cache_hit'] is False


@pytest.mark.parametrize('damage', ['issuer_request', 'body_hash', 'component_bytes', 'four_filings', 'expired'])
def test_unverified_or_expired_saved_short_index_cannot_hide_real_recheck(monkeypatch, damage):
    from data_fetch.market_sources import mops_public_gap_cache as cache
    from official_response_evidence import archive_response
    run(ShortIndexTransport()); getter = cache.get_cache_json
    def altered(key):
        p = deepcopy(getter(key)); assert p is not None
        original = p['originals'][0]
        if damage == 'issuer_request': original['request']['request']['co_id'] = '2330'
        elif damage == 'body_hash': original['raw_receipt']['raw_response_sha256'] = '0' * 64
        elif damage == 'component_bytes': p['audit']['component_statuses']['0']['response_bytes'] += 1
        elif damage == 'four_filings':
            raw = four_filing_index(); receipt = original['raw_receipt']
            original['raw_receipt'] = archive_response(raw, source_url=receipt['source_url'], retrieved_at=receipt['retrieved_at'])
            p['audit']['component_statuses']['0'].update(response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
        else:
            stamp = time.time() - cache.GAP_RETRY_SECONDS - 1
            p['audit'].update(fetched_at_epoch=stamp, fetched_at=datetime.fromtimestamp(stamp, timezone.utc).isoformat())
            original['raw_receipt']['retrieved_at'] = stamp - 1
        return p
    monkeypatch.setattr(cache, 'get_cache_json', altered)
    http = ShortIndexTransport(); result = run(http)
    assert len(http.calls) == 1 and result['audit']['cache_hit'] is False


def test_short_warm_cache_preserves_retry_epoch_and_does_not_rewrite_cache(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as cache
    from provider_correlation import correlation_scope
    setter = cache.set_cache_json; writes = []
    def recorded(*args):
        writes.append(args); return setter(*args)
    monkeypatch.setattr(cache, 'set_cache_json', recorded)
    with correlation_scope(replace=True, fetch_id='first', data_fingerprint='a' * 64):
        cold = run(ShortIndexTransport())
    assert len(writes) == 1 and writes[0][-1] == cache.GAP_RETRY_SECONDS
    for fetch_id in ('second', 'third'):
        with correlation_scope(replace=True, fetch_id=fetch_id): warm = run(ShortIndexTransport())
        assert warm['audit']['fetch_id'] == fetch_id and 'data_fingerprint' not in warm['audit']
        assert warm['audit']['fetched_at'] == cold['audit']['fetched_at']
        assert warm['audit']['retry_at'] == datetime.fromisoformat(cold['audit']['fetched_at']).timestamp() + cache.GAP_RETRY_SECONDS
        assert len(writes) == 1


def test_short_index_original_prevalidation_cannot_restart_replay_deadline(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as cache
    run(ShortIndexTransport())
    base = cache.time.monotonic()
    now = [base]
    reader = cache._receipt
    reads = [0]
    monkeypatch.setattr(cache.time, 'monotonic', lambda: now[0])
    def slow_original(*args, **kwargs):
        reads[0] += 1
        if reads[0] == 1:
            now[0] = base + 46
        return reader(*args, **kwargs)
    monkeypatch.setattr(cache, '_receipt', slow_original)
    result = run(ShortIndexTransport())
    assert result['audit']['cache_hit'] is False


def test_source_only_short_index_cold_and_warm_errors_preserve_report_and_failed_observation(monkeypatch, tmp_path):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    import data_fetch.market_sources.ordinary_individual_annual
    from data_fetch.market_sources import mops_public_annual as native
    from report_refresh_service import refresh_report_data_snapshot
    from test_report_annual_financial_source_refresh import report, init_db
    init_db(); storage, name, keys, old = report('7740.TW')
    originals = {k: storage.get_report(k).content for k in [keys.html_key, keys.md_key, keys.data_key]}
    transports = []
    class PublicMopsHttpFactory(native.PublicMopsHttp):
        def __new__(cls, *args, **kwargs):
            transport = ShortIndexTransport(); transports.append(transport); return transport
    monkeypatch.setattr(native, 'PublicMopsHttp', PublicMopsHttpFactory)
    for _ in range(2):
        with pytest.raises(HTTPException) as failure:
            asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
                refresh_service=StockDataService(), source='financial_statements'))
        assert failure.value.status_code == 502
        assert {k: storage.get_report(k).content for k in originals} == originals
    assert len(transports) == 1 and len(transports[0].calls) == 1
