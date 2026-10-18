"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import importlib
import pytest

def source():
    return importlib.import_module('data_fetch.market_sources.macronix_conference')

@pytest.mark.parametrize('marker_kind', ['receipt', 'provider', 'policy', 'url'])
def test_private_original_is_never_reusable_financial_cache(monkeypatch, marker_kind):
    from data_fetch import cache_helpers
    from prompt_evidence import prompt_evidence_copy
    s = source()
    marker = {'receipt': {'macronix_conference_receipt': None}, 'provider': {'source': s.PROVIDER}, 'policy': {'projection_policy': s.PROJECTION_POLICY}, 'url': {'url': s.PDF_URL}}[marker_kind]
    calls = []
    monkeypatch.setattr(cache_helpers, 'set_cache_json', lambda *a, **kw: calls.append(a))
    value = {'ticker': s.TICKER, 'earnings_call': {'documents': [marker]}}
    before = deepcopy(value)
    cache_helpers._cache_financial_data(value, s.TICKER)
    assert not calls and value == before
    assert prompt_evidence_copy({'macronix_conference_receipt': {'private': 'archive'}, 'text': '正文'}) == {'text': '正文'}

@pytest.mark.parametrize('failure', [None, 'timeout', 'cooldown', 'single_flight_busy', 'guard_storage_unavailable'])
def test_public_dispatch_honors_source_policy(monkeypatch, failure):
    from data_fetch import earnings_call_fetcher as e
    from search_provider_runtime import SourceResponseError
    s = source()
    calls = []
    expected = {'source': s.PROVIDER, 'documents': [{'page_count': s.PAGE_COUNT}]}

    def fake(ticker, **kw):
        calls.append((ticker, kw))
        if failure:
            raise SourceResponseError(failure)
        return expected
    monkeypatch.setattr(s, 'fetch_macronix_context', fake)
    if failure:
        with pytest.raises(SourceResponseError) as caught:
            e.fetch_free_earnings_call_context(s.TICKER)
        assert caught.value.error_kind == failure
    else:
        assert e.fetch_free_earnings_call_context(s.TICKER) == expected
    assert len(calls) == 1

def test_context_conflict_local_block_and_single_success_count(monkeypatch):
    from data_fetch import enrichment_providers as e
    from data_fetch.types import FetchRequest
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    s = source()
    monkeypatch.setattr(e, 'fetch_free_earnings_call_context', lambda *a, **k: pytest.fail('invalid identity reached HTTP'))
    result = e.EarningsCallProvider().fetch(FetchRequest.from_ticker(s.TICKER), {'data': {'ticker': s.TICKER, 'quote_type': 'ETF'}})
    assert result.provider == s.PROVIDER and result.audit['event_kind'] == 'local_block' and (result.audit['http_request_count'] == 0)
    result = {'value': {'source': s.PROVIDER, 'documents': [{'page_count': s.PAGE_COUNT}]}, 'audit': {'status': 'success', 'record_count': 12}}
    apply_earnings_call_audit(result, {'macronix_presentation_workflow': True, 'macronix_originals_verified': True, 'actual_provider': s.PROVIDER, 'http_request_count': 3, 'http_request_sent': True, 'cache_hit': False})
    assert result['audit']['record_count'] == 1 and result['audit']['http_request_count'] == 3
