"""Legacy issuer/index behavior only when no qualified MOPS profile is enabled.

All original failure/identity/denominator assertions remain. The qualified MOPS
primary and its no-retry guards are covered separately by the new route tests.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def legacy_profile_not_enabled(monkeypatch):
    from data_fetch.market_sources import mops_presentation
    monkeypatch.setattr(mops_presentation, 'PROFILES', {
        key:value for key,value in mops_presentation.PROFILES.items() if key != '3653.TW'
    })


def test_jentech_parse_failure_uses_verified_official_index_fallback(monkeypatch):
    import data_fetch.earnings_call_fetcher as flow
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.market_sources import jentech_conference
    from data_fetch.types import FetchRequest
    from search_provider_runtime import SourceResponseError

    calls = []
    fallback_context = {
        'ticker': '3653.TW',
        'date': '2026-10-16',
        'title': '健策法人說明會',
        'summary': '',
        'transcript_available': False,
        'transcript_excerpt': '',
        'materials': [{'label': '官方簡報', 'url': 'https://mopsov.twse.com.tw/nas/STR/365320261016M001.pdf'}],
        'source': 'MOPS investor conference',
        'coverage_status': 'official_event_record',
    }

    def jentech_failure(_ticker, *, diagnostics=None, **_kwargs):
        calls.append('jentech')
        details = {
            'actual_provider': jentech_conference.PROVIDER,
            'status': 'error',
            'error_kind': 'parse_error',
            'http_request_sent': True,
            'http_request_count': 2,
        }
        if diagnostics is not None:
            diagnostics.update(details)
        exc = SourceResponseError('parse_error')
        exc.diagnostic.update(details)
        raise exc

    def official_fallback(ticker, *, diagnostics=None, **_kwargs):
        calls.append('official_index')
        assert ticker == '3653.TW'
        if diagnostics is not None:
            diagnostics.update(
                actual_provider='MOPS investor conference',
                status='success',
                coverage_status='official_event_record',
                component_statuses={'MOPS': {'status': 'success'}},
            )
        return fallback_context

    monkeypatch.setattr(jentech_conference, 'fetch_jentech_context', jentech_failure)
    monkeypatch.setattr(flow, '_fetch_official_index_context', official_fallback)

    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('3653.TW'))

    assert calls == ['jentech', 'official_index']
    assert result.value['source'] == 'MOPS investor conference'
    assert result.value['materials'] == fallback_context['materials']
    assert result.audit['actual_provider'] == 'MOPS investor conference'
    assert result.audit['http_request_count'] == 2
    assert result.audit['component_statuses'][jentech_conference.PROVIDER]['error_kind'] == 'parse_error'


@pytest.mark.parametrize('error_kind', ['timeout', 'single_flight_busy', 'context_unverified'])
def test_jentech_terminal_or_identity_error_does_not_fallback(monkeypatch, error_kind):
    import data_fetch.earnings_call_fetcher as flow
    from data_fetch.market_sources import jentech_conference
    from search_provider_runtime import SourceResponseError

    calls = []

    def jentech_failure(_ticker, *, diagnostics=None, **_kwargs):
        exc = SourceResponseError(error_kind)
        if diagnostics is not None:
            diagnostics.update(error_kind=error_kind, http_request_sent=False)
        raise exc

    def forbidden_fallback(*_args, **_kwargs):
        calls.append('official_index')
        return {'ticker': '3653.TW'}

    monkeypatch.setattr(jentech_conference, 'fetch_jentech_context', jentech_failure)
    monkeypatch.setattr(flow, '_fetch_official_index_context', forbidden_fallback)

    with pytest.raises(SourceResponseError) as raised:
        flow.fetch_free_earnings_call_context('3653.TW', diagnostics={})

    assert raised.value.error_kind == error_kind
    assert calls == []


def test_jentech_failure_with_empty_fallback_remains_a_failure(monkeypatch):
    import data_fetch.earnings_call_fetcher as flow
    from data_fetch.market_sources import jentech_conference
    from search_provider_runtime import SourceResponseError

    def jentech_failure(_ticker, *, diagnostics=None, **_kwargs):
        details = {
            'actual_provider': jentech_conference.PROVIDER,
            'status': 'error',
            'error_kind': 'parse_error',
            'http_request_sent': True,
            'http_request_count': 2,
        }
        if diagnostics is not None:
            diagnostics.update(details)
        exc = SourceResponseError('parse_error')
        exc.diagnostic.update(details)
        raise exc

    def empty_official_fallback(_ticker, *, diagnostics=None, **_kwargs):
        if diagnostics is not None:
            diagnostics.update(
                actual_provider='MOPS investor conference',
                status='valid_empty',
                outcome='valid_empty',
                http_request_sent=True,
                http_request_count=1,
            )
        return {}

    monkeypatch.setattr(jentech_conference, 'fetch_jentech_context', jentech_failure)
    monkeypatch.setattr(flow, '_fetch_official_index_context', empty_official_fallback)

    with pytest.raises(SourceResponseError) as raised:
        flow.fetch_free_earnings_call_context('3653.TW', diagnostics={})

    assert raised.value.error_kind == 'parse_error'
    assert raised.value.diagnostic['http_request_count'] == 3
    assert raised.value.diagnostic['component_statuses'][jentech_conference.PROVIDER]['error_kind'] == 'parse_error'
    assert raised.value.diagnostic['component_statuses']['official_index']['outcome'] == 'valid_empty'
