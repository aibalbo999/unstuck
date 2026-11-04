"""A complete HTTP 200 denial page is not a successful MOPS original."""
from hashlib import sha256

import httpx
import pytest

NOTICE = ("<html><head><script>var message='not a report';</script></head><body>"
          "因為安全性考量，您所執行的頁面無法呈現。<br>"
          "FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED.<br>"
          "YOU COULD GO BACK TO PREVIOUS PAGE OR CALL US FOR FURTHER HELP：<br>"
          "錯誤代碼：fixture-only</body></html>").encode()


@pytest.mark.parametrize('route', ['json', 'template', 'index'])
def test_denial_preserves_actual_200_and_cools_the_same_native_host(monkeypatch, route):
    import data_fetch.market_sources.mops_public_annual as public
    from search_provider_runtime import SourceResponseError, error_details

    calls, failures, guards, archives = [], [], {}, []
    monkeypatch.setattr(public, 'cooldown_state', lambda key: guards.get(key, {}))

    def remember(key, exc):
        failures.append((key, exc))
        guards[key] = {'error_kind': 'access_denied', 'retry_at': 10**12}
    monkeypatch.setattr(public, 'remember_failure', remember)
    archive = public.archive_response
    def record_archive(*args, **kwargs):
        archives.append((args, kwargs))
        return archive(*args, **kwargs)
    monkeypatch.setattr(public, 'archive_response', record_archive)

    def respond(request):
        calls.append(request)
        return httpx.Response(200, content=NOTICE, headers={'Content-Type': 'text/html; charset=UTF-8'})
    http = public.PublicMopsHttp(client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(respond), **kw))
    url = public.INDEX_URL if route == 'index' else public.api_url('IncomeStatement') if route == 'json' else public.template_url('IncomeStatement')
    kwargs = {'json_body': public.payload('6230', 2025)} if route == 'json' else {'request': {'co_id': '6230'}} if route == 'index' else {}

    with pytest.raises(SourceResponseError) as first:
        http.request(url, **kwargs)
    assert first.value.error_kind == 'access_denied'
    assert error_details(first.value)['http_status'] == 200
    assert first.value.response.status_code == 200
    assert len(failures) == 1 and not archives
    assert http.components[0]['response_bytes'] == len(NOTICE)
    assert http.components[0]['response_sha256'] == sha256(NOTICE).hexdigest()
    assert http.components[0]['response_complete'] is False

    with pytest.raises(SourceResponseError) as second:
        http.request(url, **kwargs)
    assert second.value.error_kind == 'cooldown'
    assert len(calls) == 1
    assert http.components[1]['http_request_sent'] is False


def test_ordinary_wrong_content_type_stays_format_error_without_access_cooldown(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    from search_provider_runtime import SourceResponseError
    failures = []
    monkeypatch.setattr(public, 'cooldown_state', lambda key: {})
    monkeypatch.setattr(public, 'remember_failure', lambda *a: failures.append(a))
    raw = b'<html><body>Temporarily unavailable report</body></html>'
    factory = lambda **kw: httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=raw, headers={'Content-Type': 'text/html'})), **kw)
    with pytest.raises(SourceResponseError) as caught:
        public.PublicMopsHttp(client_factory=factory).request(public.api_url('IncomeStatement'), json_body=public.payload('6230', 2025))
    assert caught.value.error_kind == 'unexpected_content_type'
    assert not failures


def test_javascript_literal_is_not_a_denial_page(monkeypatch):
    import data_fetch.market_sources.mops_public_annual as public
    from search_provider_runtime import SourceResponseError
    failures = []
    monkeypatch.setattr(public, 'cooldown_state', lambda key: {})
    monkeypatch.setattr(public, 'remember_failure', lambda *a: failures.append(a))
    raw = b'const example = "FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED.";'
    monkeypatch.setattr(public, 'archive_response', lambda body, **kw: {'fixture': True})
    monkeypatch.setattr(public, '_receipt', lambda *a: raw)
    factory = lambda **kw: httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=raw, headers={'Content-Type': 'application/javascript'})), **kw)
    body, _ = public.PublicMopsHttp(client_factory=factory).request(public.template_url('IncomeStatement'))
    assert body == raw and not failures


@pytest.mark.parametrize('retry_after', [None, '7200'])
def test_full_acquisition_stops_after_denied_template_and_retains_native_cooldown(retry_after):
    import time
    import cache_store
    from cache_backends import InMemoryCache
    from provider_resilience import clear_provider_circuits
    from provider_throttle import clear_provider_throttles
    from search_provider_runtime import cooldown_state, scope_key
    import data_fetch.market_sources.mops_public_annual as public

    cache_store.set_cache_backend(InMemoryCache())
    clear_provider_circuits(public.PROVIDER)
    clear_provider_throttles(public.PROVIDER)
    calls = []
    index = ('<html><body>' + ' '.join(
        '/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=3443&year='
        + str(y) + '&season=4&report_id=C' for y in range(2021, 2026)) + '</body></html>').encode()
    def respond(request):
        calls.append(request)
        headers = {'Content-Type': 'text/html'}
        if retry_after is not None:
            headers['Retry-After'] = retry_after
        return httpx.Response(200, content=index if str(request.url) == public.INDEX_URL else NOTICE, headers=headers)
    factory = lambda **kw: httpx.Client(transport=httpx.MockTransport(respond), **kw)
    try:
        start = time.time()
        first = public._fetch_public_financial_result_uncached('3443.TW', transport=public.PublicMopsHttp(client_factory=factory))
        assert first['value'] is None and first['audit']['record_count'] == 0
        assert first['audit']['error_kind'] == 'access_denied'
        assert first['audit']['http_status'] == 200
        assert first['audit']['http_request_count'] == len(calls) == 2
        assert 'xbrl_fallback' not in first['audit']['component_statuses']
        guard = cooldown_state(scope_key(public.PROVIDER, endpoint='mops.twse.com.tw'))
        assert guard['error_kind'] == 'access_denied' and guard['http_status'] == 200
        assert guard['retry_at'] >= start + (int(retry_after) if retry_after else 1800)
        second = public._fetch_public_financial_result_uncached('3443.TW', transport=public.PublicMopsHttp(client_factory=factory))
        assert second['value'] is None and second['audit']['http_request_sent'] is False
        assert len(calls) == 2
    finally:
        clear_provider_circuits(public.PROVIDER)
        clear_provider_throttles(public.PROVIDER)
        cache_store.reset_cache_store_for_tests()
