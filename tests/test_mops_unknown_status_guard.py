"""A failed request cannot borrow an earlier request's HTTP status."""
from copy import deepcopy
from types import SimpleNamespace
import time

import pytest

import mops_material_transport as transport
import search_provider_runtime as runtime
from test_mops_material_transport import descriptor, offline, wire


@pytest.fixture
def guard_state(monkeypatch):
    cache = {}
    token = runtime._HTTP_STATUS.set(None)
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: deepcopy(cache.get(key)))
    monkeypatch.setattr(runtime, 'set_cache_json',
                        lambda key, value, ttl_seconds: cache.__setitem__(key, deepcopy(value)))
    try:
        yield cache
    finally:
        runtime._HTTP_STATUS.reset(token)


@pytest.mark.parametrize('previous_status', [200, 429, 503])
def test_timeout_before_headers_keeps_unknown_status_in_failure_guard(
        guard_state, offline, monkeypatch, previous_status):
    runtime.observe_http_response(SimpleNamespace(status_code=previous_status))
    parts, rc, error = wire(raw=b'', status=0, rc=28)
    parts['headers'] = b''
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: (parts, rc, error))
    diagnostic = {}
    with pytest.raises(runtime.SourceResponseError) as caught:
        transport.download_published_material(descriptor(), deadline=time.monotonic()+25,
                                              diagnostics=diagnostic)
    assert diagnostic['http_request_sent'] is True
    assert diagnostic['http_status_observed'] is False
    assert diagnostic['response_bytes'] == 0 and diagnostic['response_complete'] is False
    state = runtime.remember_failure('test:mops:unknown-status', caught.value)
    assert state['http_status'] is None
    assert state['error_kind'] == 'timeout' and state['response_bytes'] == 0
    assert state['consecutive_failures'] == 1


@pytest.mark.parametrize('status,kind', [(200, 'timeout'), (429, 'rate_limited'), (503, 'server_error')])
def test_current_observed_response_and_retry_after_remain_authoritative(guard_state, status, kind):
    runtime.observe_http_response(SimpleNamespace(status_code=403))
    exc = runtime.SourceResponseError(kind, status_code=status)
    exc.response = SimpleNamespace(status_code=status, headers={'Retry-After': '7200'})
    exc.diagnostic['http_status_observed'] = True
    started = time.time()
    state = runtime.remember_failure('test:mops:observed-status', exc)
    assert state['http_status'] == status and state['error_kind'] == kind
    assert state['retry_at'] >= started+7200


def test_legacy_parser_without_per_request_status_flag_retains_observed_response(guard_state):
    runtime.observe_http_response(SimpleNamespace(status_code=200))
    assert runtime.error_details(runtime.SourceResponseError('parse_error'))['http_status'] == 200


def test_explicit_unknown_boolean_does_not_erase_actual_response(guard_state):
    exc = runtime.SourceResponseError('rate_limited', status_code=429)
    exc.diagnostic['http_status_observed'] = False
    assert runtime.error_details(exc)['http_status'] == 429
