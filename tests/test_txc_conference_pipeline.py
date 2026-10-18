"""The existing public earnings workflow must select a verified issuer source."""
import sys
from types import SimpleNamespace

import pytest

from data_fetch import earnings_call_fetcher as earnings
from search_provider_runtime import SourceResponseError


PROVIDER = 'TXC official conference presentation'


def configure(monkeypatch, callback):
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.txc_conference',
                        SimpleNamespace(supports_txc=lambda t: t in {'3042', '3042.TW'},
                                        fetch_txc_context=callback))
    monkeypatch.setattr(earnings, '_fetch_official_index_context',
                        lambda ticker, **kwargs: {'ticker': ticker, 'source': 'MOPS index', 'summary': 'metadata'})


def test_verified_official_presentation_precedes_empty_current_year_index(monkeypatch):
    context = {'ticker': '3042.TW', 'source': PROVIDER, 'transcript_available': False,
               'documents': [{'document_kind': 'presentation', 'text_extraction_complete': True}]}
    configure(monkeypatch, lambda ticker, **kwargs: context)
    result = earnings.fetch_free_earnings_call_context('3042.TW')
    assert result == context


def test_failed_official_source_retains_provenance_with_existing_index_fallback(monkeypatch):
    def refused(ticker, **kwargs):
        raise SourceResponseError('access_denied', status_code=403)
    configure(monkeypatch, refused)
    diagnostic = {}
    result = earnings.fetch_free_earnings_call_context('3042.TW', diagnostics=diagnostic)
    assert result['source'] == 'MOPS index'
    assert diagnostic['component_statuses']['TXC']['error_kind'] == 'access_denied'


def test_lost_source_lease_cannot_start_a_second_workflow(monkeypatch):
    def lost(ticker, **kwargs):
        raise SourceResponseError('lease_lost')
    configure(monkeypatch, lost)
    with pytest.raises(SourceResponseError) as raised:
        earnings.fetch_free_earnings_call_context('3042.TW')
    assert raised.value.error_kind == 'lease_lost'
