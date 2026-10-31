"""Source recovery requires parsed native content within its lease and deadline."""
import importlib
import time
from contextlib import contextmanager

import pytest
from test_mops_presentation import harness as material_harness, NOW
from test_sigurd_conference import native_harness as sigurd_native, I as SIGURD_INDEX


def seed(key):
    from cache_store import set_cache_json
    set_cache_json(key, {'consecutive_failures': 8, 'error_kind': 'parse_error', 'retry_at': time.time() - 1}, ttl_seconds=1000)


def streak(key):
    import search_provider_runtime as runtime
    return runtime.remember_failure(key, runtime.SourceResponseError('parse_error'))['consecutive_failures']


@pytest.mark.parametrize('mode', ['native', 'warm', 'raw_only', 'parse_failure', 'lease_lost', 'deadline'])
def test_material_parser_boundary(material_harness, monkeypatch, mode):
    from data_fetch.market_sources import mops_presentation as source
    import mops_material_originals as original
    from mops_material_transport import index_request
    from search_provider_runtime import SourceResponseError
    spec = index_request('2330.TW', year=2026)
    owned = [True]
    deadline = time.monotonic() + 25
    def download(d):
        return source.download_conference_index('2330.TW', year=2026, deadline=deadline, diagnostics=d)
    if mode == 'warm':
        original.get_original(spec, download, deadline=deadline, owns=lambda: owned[0], diagnostic={})
    seed(original.GUARD)
    def parse(raw, receipt):
        if mode == 'parse_failure':
            raise ValueError('unrecognized index')
        if mode == 'lease_lost':
            owned[0] = False
        if mode == 'deadline':
            monkeypatch.setattr(original.time, 'monotonic', lambda: deadline + 1)
        return {'validated': True}
    options = dict(deadline=deadline, owns=lambda: owned[0], diagnostic={}, parser=None if mode == 'raw_only' else parse)
    if mode in {'parse_failure', 'lease_lost', 'deadline'}:
        with pytest.raises((ValueError, SourceResponseError)):
            original.get_original(spec, download, **options)
    else:
        original.get_original(spec, download, **options)
    assert streak(original.GUARD) == (1 if mode == 'native' else 9)


@pytest.mark.parametrize('name', ['voltronic', 'sinbon', 'fubon'])
@pytest.mark.parametrize('mode', ['native', 'warm', 'raw_only', 'parse_failure', 'lease_lost', 'deadline'])
def test_dedicated_parser_boundary(material_harness, monkeypatch, name, mode):
    t = importlib.import_module('data_fetch.market_sources.' + name + '_conference_transport')
    from search_provider_runtime import SourceResponseError
    owned = [True]
    @contextmanager
    def admission(*a, **k):
        yield lambda: owned[0]
    monkeypatch.setattr(t, 'endpoint_admission', admission)
    http = t.ConferenceHttp(time.monotonic() + 25)
    monkeypatch.setattr(http, '_external_guards', lambda url: None)
    def receipt(url):
        http.components.append({'http_request_sent': mode != 'warm', 'request_started_at': NOW})
        return b'<html>validated fixture</html>', {'cache_hit': mode == 'warm'}
    monkeypatch.setattr(http, '_get_receipt', receipt)
    seed(t.GUARD)
    def parse(raw, receipt):
        if mode == 'parse_failure':
            raise ValueError('unrecognized index')
        if mode == 'lease_lost':
            owned[0] = False
        if mode == 'deadline':
            http.deadline = time.monotonic() - 1
        return {'validated': True}
    if mode in {'parse_failure', 'lease_lost', 'deadline'}:
        with pytest.raises((ValueError, SourceResponseError)):
            http.get_receipt(t.INDEX_URL, parser=parse)
    else:
        http.get_receipt(t.INDEX_URL, parser=None if mode == 'raw_only' else parse)
    assert streak(t.GUARD) == (1 if mode == 'native' else 9)


@pytest.mark.parametrize('mode', ['native', 'warm', 'raw_only', 'invalid_html', 'deadline'])
def test_sigurd_parser_boundary(sigurd_native, mode):
    t, calls, controls = sigurd_native
    from data_fetch.market_sources.sigurd_conference import select_presentation
    from search_provider_runtime import SourceResponseError
    controls['body'] = (SIGURD_INDEX / 'index.body').read_bytes()
    http = t.ConferenceHttp(time.monotonic() + 25)
    if mode == 'warm':
        http.get_receipt(t.INDEX_URL)
    if mode == 'invalid_html':
        controls['body'] = b'<html><body>Service maintenance</body></html>'
    seed(t.MOPS_GUARD)
    def parse(raw, receipt):
        value = select_presentation(raw, receipt['retrieved_at'])
        if mode == 'deadline':
            http.deadline = time.monotonic() - 1
        return value
    if mode in {'invalid_html', 'deadline'}:
        with pytest.raises((ValueError, SourceResponseError)):
            http.get_receipt(t.INDEX_URL, parser=parse)
    else:
        http.get_receipt(t.INDEX_URL, parser=None if mode == 'raw_only' else parse)
    assert streak(t.MOPS_GUARD) == (1 if mode == 'native' else 9)
