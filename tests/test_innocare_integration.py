"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import pytest
PROVIDER = 'InnoCare official conference presentation'

def test_public_6861_routing_prefers_issuer_without_touching_mops(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import mops_presentation
    expected = {'ticker': '6861.TW', 'source': PROVIDER, 'documents': [{'page_count': 11}]}
    calls = []

    def acquire(ticker, **options):
        calls.append((ticker, options))
        return expected
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.innocare_conference', SimpleNamespace(supports_innocare=lambda t: t == '6861.TW', fetch_innocare_context=acquire))
    monkeypatch.setattr(mops_presentation, 'fetch_presentation_context', lambda *a, **kw: {'source': 'MOPS'})
    assert fetcher.fetch_free_earnings_call_context('6861.TW', force_refresh=True, use_cache=False) == expected
    assert len(calls) == 1 and calls[0][1]['force_refresh'] is True
    assert calls[0][1]['use_cache'] is False

@pytest.mark.parametrize('kind', ['timeout', 'lease_lost', 'single_flight_busy', 'guard_storage_unavailable', 'cooldown'])
def test_innocare_failure_never_retries_mops(monkeypatch, kind):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import mops_presentation
    from search_provider_runtime import SourceResponseError

    def fail(*a, **kw):
        raise SourceResponseError(kind)
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.innocare_conference', SimpleNamespace(supports_innocare=lambda t: t == '6861.TW', fetch_innocare_context=fail))
    monkeypatch.setattr(mops_presentation, 'fetch_presentation_context', lambda *a, **kw: {'source': 'MOPS'})
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('6861.TW')
    assert caught.value.error_kind == kind

def test_private_originals_do_not_enter_prompt():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'innocare_conference_receipt': {'private': 'archive'}, 'text': '原件摘要'}}
    assert prompt_evidence_copy(value) == {'data': {'text': '原件摘要'}}

@pytest.mark.parametrize('marker', [{'innocare_conference_receipt': None}, {'source': PROVIDER}, {'projection_policy': 'innocare-presentation-role-v1'}, {'url': 'https://www.innocare-x.com/wp-content/uploads/2026/09/20260910142650_0_e8f3ed.pdf'}])
def test_no_store_originals_cannot_become_payload_cache(monkeypatch, marker):
    from data_fetch import cache_helpers
    calls = []
    monkeypatch.setattr(cache_helpers, 'set_cache_json', lambda *a, **kw: calls.append(a))
    value = {'ticker': '6861.TW', 'earnings_call': {'documents': [marker]}}
    original = deepcopy(value)
    cache_helpers._cache_financial_data(value, '6861.TW')
    assert not calls
    assert value == original

def test_invalid_caller_is_attributed_to_selected_issuer_provider(monkeypatch):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', lambda *a, **kw: pytest.fail('invalid context reached network boundary'))
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('6861.TW'), {'data': {'ticker': '6861.TW', 'company_name': '睿生光電', 'quote_type': 'ETF'}})
    assert result.provider == PROVIDER
    assert result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0
