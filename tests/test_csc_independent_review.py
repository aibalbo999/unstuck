"""Public boundary checks. Original private-data replay cases remain local."""
import pytest
from test_csc_conference import valid_data

@pytest.mark.parametrize('request_ticker,data_ticker', [('2330.TW', '2002.TW'), ('2002.TW', '2002.TWO')])
def test_cross_requested_and_resolved_subject_never_reaches_source(monkeypatch, request_ticker, data_ticker):
    from data_fetch import enrichment_providers as providers
    from data_fetch.types import FetchRequest
    data = valid_data()
    data['ticker'] = data_ticker
    monkeypatch.setattr(providers, 'fetch_free_earnings_call_context', lambda *a, **kw: pytest.fail('cross subject HTTP'))
    result = providers.EarningsCallProvider().fetch(FetchRequest.from_ticker(request_ticker), {'data': data})
    assert not result.value and result.audit['error_kind'] == 'context_unverified'
    assert result.audit['http_request_count'] == 0
