"""Synchronous enrichment fetches used by legacy yfinance payload assembly."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

from .market_sources.common import _run_named_fetches
from .market_sources.identity import is_taiwan_ticker
from .market_sources.http_enrichment import (
    fetch_fmp_news_catalysts,
    fetch_yfinance_news_catalysts,
)
from .market_sources.peers import fetch_dynamic_peer_metrics
from .market_sources.taiwan import (
    fetch_finmind_news_catalysts,
    fetch_institutional_trading_trend,
)
from .market_sources.valuation import build_pe_river_chart_data


def fetch_sync_enrichment_bundle(
    *,
    ticker: str,
    stock,
    company_name: str,
    sector: str,
    industry: str,
    company_identity: dict,
    years: list,
    net_income_history: list,
    shares_outstanding,
    skip_optional_http: bool,
    force_refresh: bool = False,
    defer_taiwan_yahoo_news: bool = False,
) -> dict:
    earnings_audit = {}
    # Preserve candidate coverage and original receipts in normal analysis too.
    typed_peer_target=ticker.upper() in {"5314.TWO","9103.TW","3324.TWO","2610.TW","2618.TW","2646.TW","6757.TW"}
    enrichment_fetches = {
        "recent_catalysts_finmind": (
            fetch_finmind_news_catalysts,
            (ticker,),
            [],
            "FinMind 新聞資料獲取失敗",
            "recent_catalysts",
            "FinMind news",
        ),
        "recent_catalysts_yahoo": (
            fetch_yfinance_news_catalysts,
            (stock,),
            [],
            "Yahoo Finance 新聞資料獲取失敗",
            "recent_catalysts",
            "Yahoo Finance news",
        ),
        "dynamic_peer_metrics": (
            fetch_dynamic_peer_metrics,
            (ticker, company_name, sector, industry, company_identity),
            [],
            "動態同業資料彙整失敗",
            "dynamic_peer_metrics",
            "FinMind/yfinance",
        ),
        "pe_river_chart": (
            build_pe_river_chart_data,
            (ticker, years, net_income_history, shares_outstanding),
            {"years": years, "eps_twd": [], "multiples": [10, 12, 15, 18], "bands": {}, "source": "unavailable"},
            "P/E 河流圖資料彙整失敗",
            "pe_river_chart",
            "FinMind/default multiples",
        ),
    }
    if typed_peer_target:
        def fetch_published_peer_metrics():
            from .enrichment_providers import DynamicPeerMetricsProvider
            from .types import FetchRequest
            result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker(ticker),{"data":{
                "ticker":ticker,"company_name":company_name,"sector":sector,"industry":industry,
                "company_identity":company_identity}})
            return result
    # The canonical workflow fetches Taiwan Yahoo news through its regional
    # provider after core assembly. Its generic SDK news call returned no
    # records while adding another failed observation for the same company.
    # Standalone core callers keep the generic call as their only Yahoo path.
    if defer_taiwan_yahoo_news and is_taiwan_ticker(ticker):
        enrichment_fetches.pop("recent_catalysts_yahoo", None)
    if not skip_optional_http:
        from config import FMP_API_KEY

        def fetch_conference():
            from .enrichment_providers import EarningsCallProvider
            from .types import FetchRequest
            result = EarningsCallProvider().fetch(FetchRequest.from_ticker(ticker))
            earnings_audit.update(result.audit)
            return result.value

        enrichment_fetches.update({
            "earnings_call": (
                fetch_conference,
                (),
                {},
                "法說會資料獲取失敗",
                "earnings_call",
                "Free conference enrichment",
            ),
        })

        if FMP_API_KEY and not ticker.upper().endswith((".TW", ".TWO")):
            enrichment_fetches["recent_catalysts_fmp"] = (
                fetch_fmp_news_catalysts,
                (ticker,),
                [],
                "FMP 新聞資料獲取失敗",
                "recent_catalysts",
                "FMP news",
            )

    from source_applicability import source_is_applicable
    identity_data = {"ticker": ticker, "company_identity": company_identity}
    enrichment_fetches = {name: spec for name, spec in enrichment_fetches.items()
                          if source_is_applicable(spec[4], identity_data)}
    typed_peer=typed_peer_target and "dynamic_peer_metrics" in enrichment_fetches
    if typed_peer:
        enrichment_fetches.pop("dynamic_peer_metrics")
    from .institutional_provider import fetch_institutional_result
    from .market_sources.finmind_news import fetch_finmind_news_result
    from .types import FetchRequest
    typed_news = is_taiwan_ticker(ticker) and "recent_catalysts_finmind" in enrichment_fetches
    if typed_news:
        enrichment_fetches.pop("recent_catalysts_finmind")
    # The typed source owns resilience/audit; an outer audited wrapper would
    # count a cache read as another provider callback or block it on circuit state.
    with ThreadPoolExecutor(max_workers=1 + int(typed_peer) + int(typed_news)) as executor:
        institutional_future = (executor.submit(
            copy_context().run, fetch_institutional_result,
            FetchRequest.from_ticker(ticker, force_refresh=force_refresh), fetch=fetch_institutional_trading_trend,
        ) if source_is_applicable("institutional_trading", identity_data) else None)
        peer_future=(executor.submit(copy_context().run,fetch_published_peer_metrics) if typed_peer else None)
        news_future = (executor.submit(copy_context().run, fetch_finmind_news_result, FetchRequest.from_ticker(ticker))
                       if typed_news else None)
        enrichment_result = _run_named_fetches(enrichment_fetches, max_workers=6, include_audit=True)
        if institutional_future is not None:
            institutional_result = institutional_future.result()
            enrichment_result["values"]["institutional_trading"] = institutional_result.value
            enrichment_result["audit"].append(institutional_result.audit)
        if peer_future is not None:
            peer_result=peer_future.result()
            enrichment_result["values"]["dynamic_peer_metrics"]=peer_result.value
            enrichment_result["audit"].append(peer_result.audit)
            enrichment_result["audit"].extend(entry for entry in peer_result.audit.get("related_entries",[]) if isinstance(entry,dict))
        if news_future is not None:
            news_result = news_future.result()
            enrichment_result["values"]["recent_catalysts_finmind"] = news_result.value
            enrichment_result["audit"].append(news_result.audit)
    enrichment = enrichment_result.get("values", {})
    if earnings_audit:
        # Replace the scheduling wrapper with the canonical provider's provenance.
        enrichment_result["audit"] = [earnings_audit if row.get("source") == "earnings_call" else row
                                      for row in enrichment_result.get("audit", [])]
    recent_catalyst_records = []
    for key in (
        "recent_catalysts_finmind",
        "recent_catalysts_yahoo",
        "recent_catalysts_fmp",
    ):
        recent_catalyst_records.extend(enrichment.get(key, []) or [])

    return {
        "recent_catalysts": recent_catalyst_records,
        "institutional_trading": enrichment.get("institutional_trading", {}),
        "dynamic_peer_metrics": enrichment.get("dynamic_peer_metrics", []),
        "peer_discovery_results": enrichment.get("peer_discovery_results", []),
        "pe_river_chart": enrichment.get(
            "pe_river_chart",
            {"years": years, "eps_twd": [], "multiples": [10, 12, 15, 18], "bands": {}, "source": "unavailable"},
        ),
        "earnings_call": enrichment.get("earnings_call", {}),
        "audit": enrichment_result.get("audit", []),
    }
