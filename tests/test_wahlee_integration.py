"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import pytest
from data_fetch.market_sources.wahlee_conference_transport import PDF_URL
PROVIDER = 'Wahlee official conference presentation'

def test_public_routing_uses_wahlee_presentation_without_mops_retry(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    calls = []
    expected = {'source': PROVIDER, 'documents': [{'page_count': 20}]}

    def fetch(ticker, **options):
        calls.append((ticker, options))
        return expected
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.wahlee_conference', SimpleNamespace(supports_wahlee=lambda t: t == '3010.TW', fetch_wahlee_context=fetch))
    assert fetcher.fetch_free_earnings_call_context('3010.TW', force_refresh=True, use_cache=False) == expected
    assert calls == [('3010.TW', {'diagnostics': {}, 'force_refresh': True, 'use_cache': False})]

@pytest.mark.parametrize('kind', ['timeout', 'cooldown', 'single_flight_busy', 'guard_storage_unavailable', 'lease_lost'])
def test_selected_source_failure_does_not_retry_mops(monkeypatch, kind):
    from data_fetch import earnings_call_fetcher as fetcher
    from search_provider_runtime import SourceResponseError

    def fetch(*a, **kw):
        raise SourceResponseError(kind)
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.wahlee_conference', SimpleNamespace(supports_wahlee=lambda t: t == '3010.TW', fetch_wahlee_context=fetch))
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('3010.TW')
    assert caught.value.error_kind == kind

@pytest.mark.parametrize('marker', [{'wahlee_conference_receipt': None}, {'source': PROVIDER}, {'projection_policy': 'wahlee-presentation-role-v1'}, {'url': PDF_URL}])
def test_archived_presentation_cannot_become_reusable_financial_payload(monkeypatch, marker):
    from data_fetch import cache_helpers
    calls = []
    monkeypatch.setattr(cache_helpers, 'set_cache_json', lambda *a, **k: calls.append(a))
    v = {'ticker': '3010.TW', 'earnings_call': {'documents': [marker]}}
    before = deepcopy(v)
    cache_helpers._cache_financial_data(v, '3010.TW')
    assert calls == [] and v == before

def test_private_receipt_does_not_enter_prompts():
    from prompt_evidence import prompt_evidence_copy
    assert prompt_evidence_copy({'wahlee_conference_receipt': {'private': 'archive'}, 'text': '回答'}) == {'text': '回答'}

def test_invalid_context_is_local_block_for_the_selected_issuer(monkeypatch):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', lambda *a, **kw: pytest.fail('invalid identity reached HTTP'))
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('3010.TW'), {'data': {'ticker': '3010.TW', 'company_name': '華立', 'quote_type': 'ETF'}})
    assert result.provider == PROVIDER and result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0

def test_one_presentation_does_not_count_pages_as_successes():
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    result = {'value': {'source': PROVIDER, 'documents': [{'page_count': 20}]}, 'audit': {'status': 'success', 'record_count': 12}}
    apply_earnings_call_audit(result, {'wahlee_presentation_workflow': True, 'wahlee_originals_verified': True, 'actual_provider': PROVIDER, 'http_request_count': 3, 'http_request_sent': True, 'cache_hit': False})
    assert result['audit']['record_count'] == 1 and result['audit']['http_request_count'] == 3
