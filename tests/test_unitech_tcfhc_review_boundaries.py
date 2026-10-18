"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

@pytest.mark.parametrize('kind', ['lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'])
def test_unitech_lifecycle_abort_does_not_launch_other_source(monkeypatch, kind):
    from data_fetch import earnings_call_fetcher as wrapper
    from data_fetch.market_sources import unitech_conference as source
    from search_provider_runtime import SourceResponseError
    seen = []

    def abort(*a, **kw):
        seen.append('unitech')
        raise SourceResponseError(kind)
    monkeypatch.setattr(source, 'fetch_unitech_context', abort)
    monkeypatch.setattr(wrapper, '_fetch_official_index_context', lambda *a, **kw: pytest.fail('typed abort launched fallback'))
    with pytest.raises(SourceResponseError) as caught:
        wrapper.fetch_free_earnings_call_context('2367.TW')
    assert caught.value.error_kind == kind and seen == ['unitech']

def test_unitech_remote_failure_stays_in_successful_official_fallback_components(monkeypatch):
    from data_fetch import earnings_call_fetcher as wrapper
    from data_fetch.market_sources import unitech_conference as source
    from search_provider_runtime import SourceResponseError

    def failed(*a, **kw):
        e = SourceResponseError('server_error', status_code=503)
        e.diagnostic.update(actual_provider=source.PROVIDER, unitech_presentation_workflow=True, http_request_sent=True, http_request_count=2)
        raise e

    def fallback(ticker, *, diagnostics, **kw):
        diagnostics.update(actual_provider='MOPS investor conference', http_request_sent=True, http_request_count=1, component_statuses={'index': {'http_status': 200}})
        return {'ticker': ticker, 'source': 'MOPS investor conference', 'date': '2026-10-10'}
    monkeypatch.setattr(source, 'fetch_unitech_context', failed)
    monkeypatch.setattr(wrapper, '_fetch_official_index_context', fallback)
    d = {}
    v = wrapper.fetch_free_earnings_call_context('2367.TW', diagnostics=d)
    assert v['source'] == d['actual_provider'] == 'MOPS investor conference'
    assert d['component_statuses']['Unitech_presentation']['error_kind'] == 'server_error'
    assert d['component_statuses']['Unitech_presentation']['http_request_count'] == 2
    assert 'unitech_originals_verified' not in d

@pytest.mark.parametrize('target', ['2367.TW', '5880.TW'])
def test_changed_request_cannot_reuse_other_exact_issuer_context(monkeypatch, target):
    from data_fetch import enrichment_providers
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.market_sources import issuer_news
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', lambda *a, **kw: pytest.fail('cross-issuer HTTP'))
    monkeypatch.setattr(issuer_news, 'fetch_recent_issuer_news', lambda *a, **kw: pytest.fail('cross-issuer HTTP'))
    provider = enrichment_providers.EarningsCallProvider() if target == '2367.TW' else IssuerNewsProvider()
    r = provider.fetch(FetchRequest.from_ticker(target), {'data': {'ticker': '3042.TW', 'quote_type': 'EQUITY', 'company_name': '晶技'}})
    assert r.status == 'unavailable' and r.audit['event_kind'] == 'local_block'
    assert r.audit['http_request_sent'] is False and r.audit['record_count'] == 0
