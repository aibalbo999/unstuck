"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

@pytest.mark.parametrize('bad_ticker', [{}, [], None, 42])
def test_malformed_context_identity_cannot_crash_or_project_qualified_pages(bad_ticker):
    from conference_presentation_prompt import presentation_prompt_context
    context = {'ticker': bad_ticker, 'documents': [{'ticker': '6282.TW', 'source': 'MOPS published presentation', 'document_kind': 'presentation', 'pages': [{'page_number': 1, 'text': 'revenue market strategy'}]}]}
    assert not presentation_prompt_context(context, 3).get('documents')
