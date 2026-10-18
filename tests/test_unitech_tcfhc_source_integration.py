"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import pytest

def test_tcfhc_parent_news_has_a_free_provider_route():
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import FetchRequest
    registry = ProviderRegistry()
    for ticker in ('5880.TW', '5880'):
        assert 'Verified issuer news' in registry.provider_names(FetchRequest.from_ticker(ticker), 'recent_catalysts')
    assert 'Verified issuer news' not in registry.provider_names(FetchRequest.from_ticker('5880.TWO'), 'recent_catalysts')

def test_unitech_private_receipt_is_not_agent_prompt_content():
    from prompt_evidence import prompt_evidence_copy
    value = {'ticker': '2367.TW', 'unitech_conference_receipt': {'raw_response_path': '/internal/cache/original.gz'}}
    before = deepcopy(value)
    assert 'unitech_conference_receipt' not in prompt_evidence_copy(value)
    assert value == before

def test_unitech_role_view_preserves_missing_charts_and_ownership_notice():
    from conference_presentation_prompt import presentation_prompt_context
    document = {'document_kind': 'presentation', 'source': 'Unitech official conference presentation', 'page_count': 16, 'pages': [{'page_number': 9, 'text': '財務概況與未來展望'}], 'known_native_text_omissions': [{'page_number': 9, 'issue': 'chart_values_not_extracted'}], 'ownership_confidentiality_notice_present': True, 'commercial_reuse_permission_verified': False, 'content_period': None, 'event_date_basis': 'issuer_index_and_PDF_cover', 'event_status': 'announced_past_not_independently_verified', 'event_time': '14:00', 'event_timezone': None}
    before = deepcopy(document)
    for role in (3, 5, 12):
        projected = presentation_prompt_context({'documents': [document]}, role)['documents'][0]
        for field in ('known_native_text_omissions', 'ownership_confidentiality_notice_present', 'commercial_reuse_permission_verified', 'content_period', 'event_date_basis', 'event_status', 'event_time', 'event_timezone'):
            assert field in projected and projected[field] == document[field]
    assert document == before

@pytest.mark.parametrize('target', ['2367.TW', '5880.TW'])
@pytest.mark.parametrize('malformed', [False, [], 'not a data mapping', 3])
def test_new_provider_rejects_explicit_invalid_data_before_acquisition(monkeypatch, target, malformed):
    from data_fetch import enrichment_providers
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.market_sources import issuer_news
    from data_fetch.types import FetchRequest

    def forbidden(*a, **kw):
        pytest.fail('malformed original context reached an external source')
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', forbidden)
    monkeypatch.setattr(issuer_news, 'fetch_recent_issuer_news', forbidden)
    provider = enrichment_providers.EarningsCallProvider() if target == '2367.TW' else IssuerNewsProvider()
    result = provider.fetch(FetchRequest.from_ticker(target), {'data': malformed})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert result.audit['http_request_count'] == result.audit['record_count'] == 0
