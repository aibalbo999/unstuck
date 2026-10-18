"""The Taiwan-specific news provider owns Taiwan Yahoo news collection."""

import asyncio
import pytest


@pytest.mark.parametrize(
    ("ticker", "expect_generic_yahoo"),
    [("2330.TW", False), ("5314.TWO", False), ("AAPL", True)],
)
def test_sync_enrichment_avoids_redundant_taiwan_yahoo_news(
    monkeypatch, ticker, expect_generic_yahoo
):
    from data_fetch import yfinance_sync_enrichment as sync
    import source_applicability
    from data_fetch.market_sources import finmind_news
    from data_fetch.types import ProviderResult

    scheduled = []
    typed_news = []

    def news(request):
        typed_news.append(request.ticker)
        return ProviderResult(source="recent_catalysts", provider="FinMind news", status="unavailable", value=[],
                              audit={"source": "recent_catalysts", "provider": "FinMind news", "status": "unavailable",
                                     "http_request_sent": False, "cache_hit": True, "record_count": 0})

    monkeypatch.setattr(finmind_news, "fetch_finmind_news_result", news)

    def capture(fetches, **_kwargs):
        scheduled.extend(fetches)
        return {"values": {}, "audit": []}

    monkeypatch.setattr(sync, "_run_named_fetches", capture)
    monkeypatch.setattr(source_applicability, "source_is_applicable", lambda source, _data: source != "institutional_trading")

    sync.fetch_sync_enrichment_bundle(
        ticker=ticker,
        stock=object(),
        company_name=ticker,
        sector="Technology",
        industry="Semiconductors",
        company_identity={"instrument_type": "EQUITY"},
        years=[],
        net_income_history=[],
        shares_outstanding=None,
        skip_optional_http=False,
        defer_taiwan_yahoo_news=True,
    )

    assert ("recent_catalysts_yahoo" in scheduled) is expect_generic_yahoo
    assert ("recent_catalysts_finmind" in scheduled) is expect_generic_yahoo
    assert typed_news == ([] if expect_generic_yahoo else [ticker])


def test_standalone_sync_fetch_keeps_generic_yahoo_news(monkeypatch):
    from data_fetch import yfinance_sync_enrichment as sync
    import source_applicability

    scheduled = []
    monkeypatch.setattr(sync, "_run_named_fetches", lambda fetches, **_kwargs: (scheduled.extend(fetches), {"values": {}, "audit": []})[1])
    monkeypatch.setattr(source_applicability, "source_is_applicable", lambda source, _data: source != "institutional_trading")

    sync.fetch_sync_enrichment_bundle(
        ticker="2330.TW", stock=object(), company_name="台積電", sector="Technology",
        industry="Semiconductors", company_identity={"instrument_type": "EQUITY"},
        years=[], net_income_history=[], shares_outstanding=None,
        skip_optional_http=True,
    )
    assert "recent_catalysts_yahoo" in scheduled


def test_missing_peer_plan_does_not_repeat_a_current_empty_core_attempt(monkeypatch):
    from data_fetch import workflow
    from data_fetch.types import FetchRequest
    from provider_correlation import correlation_scope

    class PeerProvider:
        source = "dynamic_peer_metrics"

    class Registry:
        def for_request(self, _request, source=None):
            return [PeerProvider()] if source == "dynamic_peer_metrics" else []

    attempts = []

    async def capture(_request, providers, _context):
        attempts.extend(providers)
        return []

    monkeypatch.setattr(workflow, "fetch_provider_results", capture)
    monkeypatch.setattr(workflow, "source_is_applicable", lambda source, *_: source == "dynamic_peer_metrics")
    monkeypatch.setattr(workflow, "source_record_count", lambda *_: 0)
    request = FetchRequest.from_ticker("5314.TWO")
    with correlation_scope(replace=True, ticker="5314.TWO", fetch_id="current-fetch"):
        data = {"ticker": "5314.TWO", "dynamic_peer_metrics": [], "source_audit": [{
            "source": "dynamic_peer_metrics", "provider": "FinMind/yfinance",
            "fetch_id": "current-fetch", "operation_id": "core-operation",
            "provider_attempts": [{"attempt_id": "attempt-1", "source": "dynamic_peer_metrics",
                                   "provider": "FinMind/yfinance", "attempt_number": 1, "status": "success"}],
            "status": "unavailable", "record_count": 0,
        }]}
        asyncio.run(workflow._run_missing_core_provider_plan(request, Registry(), data))
    assert attempts == []

    with correlation_scope(replace=True, ticker="5314.TWO", fetch_id="new-fetch"):
        asyncio.run(workflow._run_missing_core_provider_plan(request, Registry(), data))
    assert len(attempts) == 1
