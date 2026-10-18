import time
import pytest
from test_tcfhc_conference_transport import network, response
from test_shared_provider_cache import memory_cache
from test_auras_conference import PDF


def test_auras_has_isolated_routes_and_cache_namespace(network, monkeypatch):
    t, base = network
    from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp
    calls = []
    def native(argv, *a, **kw):
        calls.append(argv); return response(argv)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    a = AurasConferenceHttp(time.monotonic() + 20).get_receipt(PDF)[1]
    b = AurasConferenceHttp(time.monotonic() + 20).get_receipt(PDF)[1]
    assert len(calls) == 1 and not a['cache_hit'] and b['cache_hit']
    assert a['retrieved_at'] == b['retrieved_at']
    assert AurasConferenceHttp.raw_cache_prefix != t.ConferenceHttp.raw_cache_prefix
    assert AurasConferenceHttp._admission_key(PDF) != t.ConferenceHttp._admission_key(PDF)
    with pytest.raises(t.SourceResponseError): t.ConferenceHttp(time.monotonic() + 20).get_receipt(PDF)
    assert len(calls) == 1


@pytest.mark.parametrize('url', [PDF + '#fragment', PDF + '?download=1', PDF.replace('https:', 'http:'),
    PDF.replace('www.auras.com.tw', 'www.auras.com.tw.evil.example'),
    PDF.replace('AnnexChinese', 'AnnexEnglish')])
def test_auras_rejects_unpublished_routes_before_http(network, monkeypatch, url):
    t, base = network
    from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp
    monkeypatch.setattr(base, 'collect_capped_process', lambda *a, **kw: pytest.fail('unexpected HTTP'))
    with pytest.raises(t.SourceResponseError): AurasConferenceHttp(time.monotonic() + 20).get_receipt(url)


@pytest.mark.parametrize('status', [403, 429, 503])
def test_auras_force_options_keep_source_failure_guard(network, monkeypatch, status):
    t, base = network
    from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp
    calls = []
    monkeypatch.setattr(base, 'remember_failure', lambda *a: {})
    def native(argv, *a, **kw):
        calls.append(argv); return response(argv, status)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    for options in ({}, {'force_refresh': True}, {'use_cache': False}):
        with pytest.raises(t.SourceResponseError):
            AurasConferenceHttp(time.monotonic() + 20, **options).get_receipt(PDF)
    assert len(calls) == 1


def test_slow_official_presentation_gets_twelve_seconds_without_automatic_retry(network, monkeypatch):
    t, base = network
    from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp
    calls = []
    def slow_pdf(argv, *a, **kw):
        calls.append(argv)
        if float(argv[argv.index('--max-time') + 1]) < 12:
            return response(argv)[0], 28, 'timeout'
        result = response(argv)
        return result
    monkeypatch.setattr(base, 'collect_capped_process', slow_pdf)
    transport = AurasConferenceHttp(time.monotonic() + 20)
    raw, receipt = transport.get_receipt(PDF)
    assert raw == b'%PDF-example' and receipt['http_status'] == 200
    assert len(calls) == 1 and transport.http_request_count == 1
    args = calls[0]
    assert float(args[args.index('--max-time') + 1]) == 12
    assert args[args.index('--retry') + 1] == '0'
    assert args[args.index('--connect-timeout') + 1] == '2.0'


def test_larger_pdf_budget_never_exceeds_remaining_workflow_deadline(network, monkeypatch):
    _, base = network
    from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp
    calls = []
    def native(argv, deadline, **kw):
        calls.append((argv, deadline)); return response(argv)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    deadline = time.monotonic() + 1
    AurasConferenceHttp(deadline).get_receipt(PDF)
    assert float(calls[0][0][calls[0][0].index('--max-time') + 1]) <= 1
    assert calls[0][1] <= deadline


def test_other_public_sources_keep_existing_five_second_cap(network, monkeypatch):
    t, base = network
    from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp, INDEX, MASTER
    from test_tcfhc_conference_transport import QA
    calls = []
    def native(argv, *a, **kw):
        calls.append(argv); return response(argv)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    t.ConferenceHttp(time.monotonic() + 20).get_receipt(QA)
    assert float(calls[0][calls[0].index('--max-time') + 1]) == 5
    a = AurasConferenceHttp(time.monotonic() + 20)
    assert a.request_timeout_seconds(INDEX) == a.request_timeout_seconds(MASTER) == 5
    assert base.IssuerNewsHttp(time.monotonic() + 20).request_timeout_seconds(base.SINBON_INDEX) == 5
