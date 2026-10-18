"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import pytest

def test_chipmos_transcript_role_keeps_translation_limits_and_bounded_text():
    from conference_presentation_prompt import presentation_prompt_context
    context = {'coverage_notes': ['Official transcript may contain material errors or omissions.'], 'documents': [{'source': 'ChipMOS official translated conference transcript', 'projection_policy': 'chipmos-translated-transcript-role-v1', 'document_kind': 'transcript', 'ticker': '8150.TW', 'page_count': 8, 'event_date': '2026-08-11', 'content_period': '2026Q2', 'published_at': None, 'language': 'en', 'translated_from_language': 'zh', 'translation_accuracy_verified': False, 'transcript_accuracy_independently_verified': False, 'xref_validation_evidence': {'internal_original_path': '/private/cache/a.pdf'}, 'pages': [{'page_number': n, 'text': 'revenue customer outlook future risk ' * 100} for n in range(1, 9)]}]}
    before = deepcopy(context)
    for role in (3, 5, 12):
        projected = presentation_prompt_context(context, role)
        assert projected.get('transcript_available') is True
        doc = projected['documents'][0]
        assert doc['published_at'] is None and doc['translation_accuracy_verified'] is False
        assert doc['transcript_accuracy_independently_verified'] is False
        assert doc['content_period'] == '2026Q2'
        assert 'xref_validation_evidence' not in doc
        assert sum((len(p['text'].split()) for p in doc['pages'])) <= 200
        assert '翻譯' in projected['evidence_policy'] and '未驗證' in projected['evidence_policy']
        assert projected['coverage_notes'] == context['coverage_notes']
    assert presentation_prompt_context(context, 1) == {}
    assert context == before

def test_chipmos_internal_receipt_is_removed_recursively_without_mutation():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'chipmos_conference_receipt': {'internal_path': '/private/raw'}, 'documents': [{'text': 'revenue', 'xref_validation_evidence': {'object_offsets': [1]}}]}}
    before = deepcopy(value)
    clean = prompt_evidence_copy(value)
    assert clean == {'data': {'documents': [{'text': 'revenue'}]}}
    assert value == before

@pytest.mark.parametrize('data', [False, [], 'bad', {'ticker': '8150.TW', 'company_name': '南茂', 'quote_type': 'ETF'}])
def test_chipmos_provider_rejects_invalid_original_before_external_fetch(monkeypatch, data):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest

    def forbidden(*a, **kw):
        pytest.fail('invalid original context reached acquisition')
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', forbidden)
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('8150.TW'), {'data': data})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0
    assert result.audit['http_request_sent'] is False

def test_chipmos_failed_body_provenance_survives_index_fallback_error(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import chipmos_conference as source
    from search_provider_runtime import SourceResponseError

    def body(*a, **kw):
        error = SourceResponseError('invalid_response')
        error.diagnostic.update(http_request_count=2, http_request_sent=True, specific_original='bad PDF')
        raise error

    def index(*a, **kw):
        raise SourceResponseError('unavailable')
    monkeypatch.setattr(source, 'fetch_chipmos_context', body)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', index)
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('8150.TW')
    original = caught.value.diagnostic['component_statuses']['ChipMOS_transcript']
    assert original['specific_original'] == 'bad PDF' and original['http_request_count'] == 2
