"""Synchronous enrichment fetches used by legacy yfinance payload assembly."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

from .market_sources.common import _run_named_fetches
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
) -> dict:
    earnings_audit = {}
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
    from .institutional_provider import fetch_institutional_result
    from .types import FetchRequest
    # The typed source owns resilience/audit; an outer audited wrapper would
    # count a cache read as another provider callback or block it on circuit state.
    with ThreadPoolExecutor(max_workers=1) as executor:
        institutional_future = (executor.submit(
            copy_context().run, fetch_institutional_result,
            FetchRequest.from_ticker(ticker, force_refresh=force_refresh), fetch=fetch_institutional_trading_trend,
        ) if source_is_applicable("institutional_trading", identity_data) else None)
        enrichment_result = _run_named_fetches(enrichment_fetches, max_workers=6, include_audit=True)
        if institutional_future is not None:
            institutional_result = institutional_future.result()
            enrichment_result["values"]["institutional_trading"] = institutional_result.value
            enrichment_result["audit"].append(institutional_result.audit)
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
