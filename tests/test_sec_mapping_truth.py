from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from data_fetch.sec_edgar_provider import SecEdgarProvider
from data_fetch.types import FetchRequest
import data_fetch.sec_edgar_provider as sec


def test_mapping_transport_failure_is_not_verified_no_cik_and_can_recover(monkeypatch):
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise httpx.ConnectTimeout('private upstream detail')
        if 'company_tickers' in url:
            return SimpleNamespace(json=lambda: {'0': {'ticker': 'AAPL', 'cik_str': 320193}})
        return SimpleNamespace(json=lambda: {'name': 'Apple', 'filings': {'recent': {'accessionNumber': ['a'], 'form': ['10-Q'], 'filingDate': ['2026-07-01']}}})
    monkeypatch.setattr(sec, 'sync_get', fetch)
    provider = SecEdgarProvider()
    failed = provider.fetch(FetchRequest.from_ticker('AAPL'))
    assert failed.status == 'unavailable'
    assert failed.audit['error_kind'] == 'mapping_timeout'
    assert failed.audit['mapping_verified'] is False
    assert 'no applicable filings' not in failed.audit['message']
    assert 'private upstream detail' not in str(failed.audit)
    recovered = provider.fetch(FetchRequest.from_ticker('AAPL'))
    assert recovered.status == 'success'
    assert len(calls) == 3


@pytest.mark.parametrize('payload', [{}, [], {'error': 'rejected'}, {'0': {'ticker': 'AAPL', 'cik_str': False}}, {'0': {'ticker': 'AAPL', 'cik_str': 'bad'}}])
def test_malformed_mapping_is_not_cached_or_valid_empty(payload, monkeypatch):
    calls = []
    def fetch(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(json=lambda: payload)
    monkeypatch.setattr(sec, 'sync_get', fetch)
    provider = SecEdgarProvider()
    for _ in range(2):
        result = provider.fetch(FetchRequest.from_ticker('AAPL'))
        assert result.status == 'unavailable'
        assert result.audit['error_kind'] == 'mapping_parse_error'
        assert result.audit['mapping_verified'] is False
    assert len(calls) == 2


def test_verified_mapping_without_symbol_does_not_claim_filings_inapplicable(monkeypatch):
    monkeypatch.setattr(sec, 'sync_get', lambda *a, **k: SimpleNamespace(json=lambda: {'0': {'ticker': 'AAPL', 'cik_str': 320193}}))
    result = SecEdgarProvider().fetch(FetchRequest.from_ticker('ZZZZ'))
    assert result.status == 'degraded_enrichment'
    assert result.audit['mapping_verified'] is True
    assert result.audit['error_kind'] == 'cik_not_found'
    assert 'no applicable filings' not in result.audit['message']


def test_mapping_403_keeps_http_status_without_sensitive_response(monkeypatch):
    def rejected(*a, **k):
        response = httpx.Response(403, request=httpx.Request('GET', 'https://www.sec.gov/files/company_tickers.json'))
        raise httpx.HTTPStatusError('private response', request=response.request, response=response)
    monkeypatch.setattr(sec, 'sync_get', rejected)
    result = SecEdgarProvider().fetch(FetchRequest.from_ticker('AAPL'))
    assert result.status == 'unavailable'
    assert result.audit['error_kind'] == 'mapping_access_denied'
    assert result.audit['http_status'] == 403


def test_mapping_cache_expires_and_invalid_json_keeps_http_status(monkeypatch):
    calls = []
    now = [1000.0]
    monkeypatch.setattr(sec.time, 'time', lambda: now[0])
    def fetch(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            return SimpleNamespace(json=lambda: {'0': {'ticker': 'AAPL', 'cik_str': 320193}}, status_code=200)
        def invalid(): raise ValueError('private non JSON body')
        return SimpleNamespace(json=invalid, status_code=200)
    monkeypatch.setattr(sec, 'sync_get', fetch)
    provider = SecEdgarProvider()
    assert provider.fetch(FetchRequest.from_ticker('ZZZZ')).audit['mapping_verified'] is True
    now[0] += 100
    assert provider.fetch(FetchRequest.from_ticker('ZZZZ')).audit['mapping_verified'] is True
    assert calls == [1]
    now[0] += 86400
    result = provider.fetch(FetchRequest.from_ticker('ZZZZ'))
    assert result.audit['mapping_verified'] is False
    assert result.audit['error_kind'] == 'mapping_parse_error'
    assert result.audit['http_status'] == 200
    assert calls == [1, 1]
