import time
import pytest
from test_tcfhc_conference_transport import network, response
from test_shared_provider_cache import memory_cache
from test_kingslide_conference import PDF


@pytest.mark.parametrize('status', [403,429,503])
def test_failure_guard_applies_to_normal_force_and_uncached_requests(network, monkeypatch, status):
    _, base = network
    from data_fetch.market_sources.kingslide_conference_transport import KingSlideConferenceHttp
    from search_provider_runtime import SourceResponseError
    calls = []
    monkeypatch.setattr(base, 'remember_failure', lambda *a: {})
    def native(argv, *a, **kw):
        calls.append(argv); return response(argv, status)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    for opts in ({}, {'force_refresh':True}, {'use_cache':False}):
        with pytest.raises(SourceResponseError): KingSlideConferenceHttp(time.monotonic()+20, **opts).get_receipt(PDF)
    assert len(calls) == 1


@pytest.mark.parametrize('url', [PDF+'?download=1', PDF+'#a', PDF.replace('https:', 'http:'),
    PDF.replace('www.kingslide.com','www.kingslide.com.evil.example'),
    PDF.replace('document/', 'document/%2E%2E/'), PDF.replace('document/', 'document/%252E%252E/')])
def test_unqualified_url_never_reaches_http(network, monkeypatch, url):
    _, base = network
    from data_fetch.market_sources.kingslide_conference_transport import KingSlideConferenceHttp
    from search_provider_runtime import SourceResponseError
    monkeypatch.setattr(base, 'collect_capped_process', lambda *a, **kw: pytest.fail('unexpected HTTP'))
    with pytest.raises(SourceResponseError): KingSlideConferenceHttp(time.monotonic()+20).get_receipt(url)
