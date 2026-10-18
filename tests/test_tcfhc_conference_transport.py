import json
import time
import pytest
from test_shared_provider_cache import memory_cache

QA = 'https://www.tcfhc.com.tw/-/media/files/tcfhc/investors-relations/event/2026year/2026q2question.pdf?sc_lang=zh-tw&hash=59FFDEA57931BF37983CFC2556648D41'


@pytest.fixture
def network(monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources import tcfhc_conference_transport as t
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in base.PROXY_ENV: monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(base, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(base, 'cooldown_state', lambda *a: None)
    monkeypatch.setattr(base, 'observe_http_response', lambda *a: None)
    return t, base


def response(argv, status=200, body=b'%PDF-example'):
    return {'body': body, 'headers': f'HTTP/2 {status}\r\nContent-Type: application/pdf\r\n\r\n'.encode(),
            'metadata': json.dumps({'http_code': status, 'url_effective': argv[-1], 'num_redirects': 0}).encode(),
            'process_started': True}, 0, None


def test_native_timeout_kind_survives_shared_cache_boundary(network, monkeypatch):
    t, base = network
    def timeout(argv, *a, **kw):
        parts, _, _ = response(argv)
        return parts, 28, 'timeout'
    monkeypatch.setattr(base, 'collect_capped_process', timeout)
    with pytest.raises(t.SourceResponseError) as exc: t.ConferenceHttp(time.monotonic() + 20).get_receipt(QA)
    assert exc.value.error_kind == 'timeout'


def test_guard_storage_failure_does_not_start_public_download(network, monkeypatch):
    t, base = network
    import cache_store
    def unavailable(*a, **kw): raise OSError('unavailable guard storage')
    monkeypatch.setattr(cache_store, 'get_cache_json', unavailable)
    calls = []
    def native(argv, *a, **kw): calls.append(argv); return response(argv)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    with pytest.raises(t.SourceResponseError) as exc: t.ConferenceHttp(time.monotonic() + 20).get_receipt(QA)
    assert exc.value.error_kind == 'guard_storage_unavailable' and not calls


def test_native_original_is_reused_with_original_epoch_and_no_credentials(network, monkeypatch):
    t, base = network; calls = []
    def native(argv, *a, **kw): calls.append(argv); return response(argv)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    first = t.ConferenceHttp(time.monotonic() + 20); raw, a = first.get_receipt(QA)
    second = t.ConferenceHttp(time.monotonic() + 20); same, b = second.get_receipt(QA)
    assert raw == same and a['retrieved_at'] == b['retrieved_at']
    assert a['cache_hit'] is False and b['cache_hit'] is True
    assert len(calls) == first.http_request_count == 1 and second.http_request_count == 0
    args = calls[0]
    assert not any('cookie' in s.lower() or 'authorization' in s.lower() for s in args)
    assert args[args.index('--retry') + 1] == '0' and args[args.index('--max-redirs') + 1] == '0'


@pytest.mark.parametrize('url', [QA.replace('tcfhc.com.tw', 'tcfhc.com.tw.evil.example'),
                                QA.replace('2026q2question', '2025q2question'),
                                QA + '&hash=ABCDEF1234567890', QA + '#fragment', QA.replace('https:', 'http:')])
def test_unpublished_or_mismatched_route_does_not_start_transport(network, monkeypatch, url):
    t, base = network
    monkeypatch.setattr(base, 'collect_capped_process', lambda *a, **kw: pytest.fail('invalid route requested'))
    with pytest.raises(t.SourceResponseError): t.ConferenceHttp(time.monotonic() + 20).get_receipt(url)


@pytest.mark.parametrize('status', [403, 429, 503])
def test_error_cooldown_prevents_repeat_download(network, monkeypatch, status):
    t, base = network; calls = []
    monkeypatch.setattr(base, 'remember_failure', lambda *a: {})
    def native(argv, *a, **kw): calls.append(argv); return response(argv, status)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    for _ in range(2):
        with pytest.raises(t.SourceResponseError): t.ConferenceHttp(time.monotonic() + 20).get_receipt(QA)
    assert len(calls) == 1


@pytest.mark.parametrize('options', [{'force_refresh': True}, {'use_cache': False}])
def test_explicit_fresh_acquisition_keeps_active_error_retry(network, monkeypatch, options):
    from hashlib import sha256
    from copy import deepcopy
    import cache_store
    t, base = network; calls = []
    def timeout(argv, *a, **kw):
        calls.append(argv)
        parts, _, _ = response(argv)
        return parts, 28, 'timeout'
    monkeypatch.setattr(base, 'collect_capped_process', timeout)
    with pytest.raises(t.SourceResponseError): t.ConferenceHttp(time.monotonic() + 20).get_receipt(QA)
    key = 'shared_provider:v1:' + sha256(('tcfhc-qa-raw:v1:' + QA).encode()).hexdigest()
    before = deepcopy(cache_store.get_cache_json(key))
    with pytest.raises(t.SourceResponseError) as exc:
        t.ConferenceHttp(time.monotonic() + 20, **options).get_receipt(QA)
    assert exc.value.error_kind == 'cooldown' and len(calls) == 1
    assert cache_store.get_cache_json(key) == before


def test_reservation_blocks_repeat_if_storage_breaks_after_http(network, monkeypatch):
    import cache_store
    import search_provider_runtime
    t, base = network; calls = []
    def cannot_write(*a, **kw): raise OSError('lost guard storage after request')
    def native(argv, *a, **kw):
        calls.append(argv)
        monkeypatch.setattr(cache_store, 'set_cache_json', cannot_write)
        monkeypatch.setattr(search_provider_runtime, 'set_cache_json', cannot_write)
        return response(argv, 429)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    with pytest.raises(t.SourceResponseError): t.ConferenceHttp(time.monotonic() + 20).get_receipt(QA)
    for opts in ({}, {'force_refresh': True}, {'use_cache': False}):
        with pytest.raises(t.SourceResponseError) as exc:
            t.ConferenceHttp(time.monotonic() + 20, **opts).get_receipt(QA)
        assert exc.value.error_kind == 'cooldown'
    assert len(calls) == 1
