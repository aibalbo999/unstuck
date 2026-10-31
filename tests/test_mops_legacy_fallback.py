"""Staged published-body failures cannot silently become metadata successes."""
import pytest

@pytest.mark.parametrize('ticker',['2330.TW','1229.TW'])
@pytest.mark.parametrize('kind',['rate_limited','published_material_unavailable'])
def test_published_body_failure_is_preserved_without_index_success(monkeypatch,ticker,kind):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import mops_presentation as source
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from search_provider_runtime import SourceResponseError
    from test_mops_presentation import valid_data
    def fail(*a,**kw):
        exc=SourceResponseError(kind)
        exc.diagnostic.update(actual_provider=source.PROVIDER,mops_material_workflow=True,
            mops_material_originals_verified=False,http_request_sent=True,http_request_count=2)
        raise exc
    from data_fetch.market_sources import lienhwa_conference
    monkeypatch.setattr(lienhwa_conference,'supports_lienhwa',lambda _:False)
    monkeypatch.setattr(source,'fetch_presentation_context',fail)
    monkeypatch.setattr(fetcher,'_fetch_official_index_context',lambda *a,**kw:pytest.fail('metadata cannot certify the requested body'))
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker(ticker),{'data':valid_data(ticker)})
    assert result.value=={} and result.audit['error_kind']==kind
    assert result.audit['record_count']==0 and result.audit['http_request_count']==2
