"""Synchronous enrichment fetches used by legacy yfinance payload assembly."""

from __future__ import annotations

from .market_sources.common import _dedupe_records, _run_named_fetches
from .market_sources.http_enrichment import (
    fetch_fmp_news_catalysts,
    fetch_google_peer_discovery_results,
    fetch_google_search_catalysts,
    fetch_yfinance_news_catalysts,
)
from .market_sources.peers import fetch_dynamic_peer_metrics
from .earnings_call_fetcher import fetch_latest_earnings_call
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
) -> dict:
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
        "institutional_trading": (
            fetch_institutional_trading_trend,
            (ticker,),
            {},
            "法人籌碼資料彙整失敗",
            "institutional_trading",
            "FinMind",
        ),
        "dynamic_peer_metrics": (
            fetch_dynamic_peer_metrics,
            (ticker, company_name, sector, industry, company_identity),
            [],
            "動態同業資料彙整失敗",
            "dynamic_peer_metrics",
            "FinMind/yfinance",
        ),
        "peer_discovery_results": (
            (lambda *_args: []) if skip_optional_http else fetch_google_peer_discovery_results,
            (ticker, company_name, sector, industry),
            [],
            "同業 discovery 資料彙整失敗",
            "peer_discovery",
            "Google Search",
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
        enrichment_fetches.update({
            "earnings_call": (
                fetch_latest_earnings_call,
                (ticker,),
                {},
                "法說逐字稿資料獲取失敗",
                "earnings_call",
                "FMP earnings call transcript",
            ),
            "recent_catalysts_google": (
                fetch_google_search_catalysts,
                (ticker, company_name, company_identity),
                [],
                "Google Search 催化劑資料獲取失敗",
                "recent_catalysts",
                "Google Search",
            ),
            "recent_catalysts_fmp": (
                fetch_fmp_news_catalysts,
                (ticker,),
                [],
                "FMP 新聞資料獲取失敗",
                "recent_catalysts",
                "FMP news",
            ),
        })

    enrichment_result = _run_named_fetches(
        enrichment_fetches,
        max_workers=6,
        include_audit=True,
    )
    enrichment = enrichment_result.get("values", {})
    recent_catalyst_records = []
    for key in (
        "recent_catalysts_finmind",
        "recent_catalysts_yahoo",
        "recent_catalysts_google",
        "recent_catalysts_fmp",
    ):
        recent_catalyst_records.extend(enrichment.get(key, []) or [])

    return {
        "recent_catalysts": _dedupe_records(recent_catalyst_records, limit=5)[:5],
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
