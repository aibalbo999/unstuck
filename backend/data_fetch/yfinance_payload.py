"""Legacy-compatible yfinance payload dict assembly."""

from __future__ import annotations

from datetime import datetime, timezone

import time as time_module

from cache_store import set_cache_json
from config import FINANCIAL_DATA_CACHE_SECONDS
from data_trust import append_source_audit, finalize_data_trust

from .audit_helpers import _append_full_fetch_audit, _mark_market_data_fetched, _mark_sources_fetched

from .constants import DATA_SCHEMA_VERSION
from .formatting import format_number, format_pct


def build_legacy_payload(ctx: dict) -> dict:
    """Build the historical payload shape from collected local values."""
    return {
        "data_schema_version": DATA_SCHEMA_VERSION,
        "ticker": ctx["ticker"],
        "company_name": ctx["company_name"],
        "raw_company_name": ctx["raw_company_name"],
        "company_identity": ctx["company_identity"],
        "sector": ctx["sector"],
        "industry": ctx["industry"],
        "country": ctx["country"],
        "employees": ctx["employees"],
        "fetch_date": datetime.now().strftime("%Y年%m月%d日"),
        "current_price": ctx["current_price"],
        "market_cap_raw": ctx["market_cap"],
        "week_52_high": ctx["week_52_high"],
        "week_52_low": ctx["week_52_low"],
        "current_price_fmt": f"NT${ctx['current_price']:.2f}" if isinstance(ctx["current_price"], (int, float)) else "N/A",
        "market_cap_fmt": format_number(ctx["market_cap"], "億"),
        "week_52_high_fmt": f"NT${ctx['week_52_high']:.2f}" if isinstance(ctx["week_52_high"], (int, float)) else "N/A",
        "week_52_low_fmt": f"NT${ctx['week_52_low']:.2f}" if isinstance(ctx["week_52_low"], (int, float)) else "N/A",
        "pe_ratio": f"{ctx['pe_ratio']:.1f}x" if isinstance(ctx["pe_ratio"], (int, float)) else "N/A",
        "forward_pe": f"{ctx['forward_pe']:.1f}x" if isinstance(ctx["forward_pe"], (int, float)) else "N/A",
        "pb_ratio": f"{ctx['pb_ratio']:.2f}x" if isinstance(ctx["pb_ratio"], (int, float)) else "N/A",
        "ps_ratio": f"{ctx['ps_ratio']:.2f}x" if isinstance(ctx["ps_ratio"], (int, float)) else "N/A",
        "ev_ebitda": f"{ctx['ev_ebitda']:.1f}x" if isinstance(ctx["ev_ebitda"], (int, float)) else "N/A",
        "shares_outstanding": format_number(ctx["shares_outstanding"], "億"),
        "shares_raw": ctx["shares_outstanding"],
        "forward_eps": ctx["forward_eps"],
        "trailing_eps": ctx["trailing_eps"],
        "forward_pe_raw": ctx["forward_pe"],
        "pe_ratio_raw": ctx["pe_ratio"],
        "revenue_ttm": format_number(ctx["revenue_ttm"], "億"),
        "revenue_ttm_raw": ctx["revenue_ttm"],
        "gross_margin": format_pct(ctx["gross_margin"]),
        "gross_margin_raw": ctx["gross_margin"],
        "operating_margin": format_pct(ctx["operating_margin"]),
        "operating_margin_raw": ctx["operating_margin"],
        "profit_margin": format_pct(ctx["profit_margin"]),
        "profit_margin_raw": ctx["profit_margin"],
        "profit_margin_provider": format_pct(ctx["provider_profit_margin"]),
        "profit_margin_provider_raw": ctx["provider_profit_margin"],
        "net_income_ttm": format_number(ctx["net_income_ttm"], "億"),
        "net_income_ttm_raw": ctx["net_income_ttm"],
        "net_income_ttm_source": ctx["net_income_source"],
        "ebitda_fmt": format_number(ctx["ebitda"], "億"),
        "ebitda_raw": ctx["ebitda"],
        "free_cash_flow": format_number(ctx["free_cash_flow"], "億"),
        "free_cash_flow_raw": ctx["free_cash_flow"],
        "operating_cash_flow": format_number(ctx["operating_cash_flow"], "億"),
        "operating_cash_flow_raw": ctx["operating_cash_flow"],
        "total_debt": format_number(ctx["total_debt"], "億"),
        "total_debt_raw": ctx["total_debt"],
        "total_cash": format_number(ctx["total_cash"], "億"),
        "total_cash_raw": ctx["total_cash"],
        "debt_to_equity": f"{ctx['debt_to_equity']:.2f}%" if isinstance(ctx["debt_to_equity"], (int, float)) else "N/A",
        "current_ratio": f"{ctx['current_ratio']:.2f}" if isinstance(ctx["current_ratio"], (int, float)) else "N/A",
        "roe": format_pct(ctx["roe"]),
        "roa": format_pct(ctx["roa"]),
        "dividend_yield": f"{float(ctx['dividend_yield']):.2f}%" if isinstance(ctx["dividend_yield"], (int, float)) else "N/A",
        "dividend_yield_raw": ctx["dividend_yield"],
        "dividend_rate": f"NT${ctx['dividend_rate']:.2f}" if isinstance(ctx["dividend_rate"], (int, float)) else "N/A",
        "dividend_rate_raw": ctx["dividend_rate"],
        "payout_ratio": format_pct(ctx["payout_ratio"]),
        "payout_ratio_raw": ctx["payout_ratio"],
        "revenue_growth": f"{ctx['latest_annual_revenue_growth']:.1f}%（最新年度 YoY）" if ctx["latest_annual_revenue_growth"] is not None else "N/A",
        "earnings_growth": f"{ctx['latest_annual_net_income_growth']:.1f}%（最新年度 YoY）" if ctx["latest_annual_net_income_growth"] is not None else "N/A",
        "latest_annual_revenue_growth": f"{ctx['latest_annual_revenue_growth']:.1f}%" if ctx["latest_annual_revenue_growth"] is not None else "N/A",
        "ttm_vs_latest_annual_revenue_change": f"{ctx['ttm_vs_latest_annual_revenue_change']:.1f}%" if ctx["ttm_vs_latest_annual_revenue_change"] is not None else "N/A",
        "latest_annual_net_income_growth": f"{ctx['latest_annual_net_income_growth']:.1f}%" if ctx["latest_annual_net_income_growth"] is not None else "N/A",
        "yahoo_revenue_growth": format_pct(ctx["yahoo_revenue_growth_raw"]),
        "yahoo_earnings_growth": format_pct(ctx["yahoo_earnings_growth_raw"]),
        "revenue_cagr_5yr": ctx["revenue_cagr"],
        "beta": f"{ctx['beta']:.2f}" if isinstance(ctx["beta"], (int, float)) else "N/A",
        "analyst_target": f"NT${ctx['analyst_target']:.2f}" if isinstance(ctx["analyst_target"], (int, float)) else "N/A",
        "analyst_rec": ctx["analyst_rec"],
        "analyst_count": str(ctx["analyst_count"]),
        "years": ctx["years"],
        "revenue_history": ctx["revenue_history"],
        "net_income_history": ctx["net_income_history"],
        "gross_profit_history": ctx["gross_profit_history"],
        "operating_income_history": ctx["operating_income_history"],
        "fcf_history": ctx["fcf_history"],
        "gross_margin_history": ctx["gross_margin_history"],
        "op_margin_history": ctx["op_margin_history"],
        "net_margin_history": ctx["net_margin_history"],
        "roe_history": ctx["roe_history"],
        "total_equity_history": ctx["total_equity_history"],
        "total_assets_history": ctx["total_assets_history"],
        "price_history": ctx["price_history"],
        "recent_monthly_revenue": ctx["recent_monthly_revenue"],
        "recent_catalysts": ctx["recent_catalysts"],
        "institutional_trading": ctx["institutional_trading"],
        "dynamic_peer_metrics": ctx["dynamic_peer_metrics"],
        "peer_discovery_results": ctx["peer_discovery_results"],
        "pe_river_chart": ctx["pe_river_chart"],
        "data_source_notes": ctx["data_source_notes"],
        "equity_multiplier": ctx["equity_multiplier"],
        "equity_multiplier_note": ctx["equity_multiplier_note"],
        "dupont_identity_note": ctx["dupont_identity_note"],
        "wacc_capital_structure_note": ctx["wacc_capital_structure_note"],
    }


def finalize_and_cache_legacy_payload(
    *,
    data: dict,
    ticker: str,
    original_cache_key: str,
    provider,
    fetch_started_epoch: float,
    skip_optional_http: bool,
    enrichment_audit: list,
    fmp_quote_audit: dict | None,
    monthly_revenue_audit: dict | None,
    finmind_financial_fallback_audit: dict | None,
) -> dict:
    fetched_at_epoch = time_module.time()
    _mark_market_data_fetched(data, ticker, fetched_at_epoch=fetched_at_epoch, cache_hit=False)
    fetched_sources = [
        "financial_statements",
        "monthly_revenue",
        "recent_catalysts",
        "institutional_trading",
        "dynamic_peer_metrics",
        "pe_river_chart",
    ]
    if not skip_optional_http:
        fetched_sources.append("peer_discovery")
    _mark_sources_fetched(data, ticker, fetched_sources, fetched_at_epoch=fetched_at_epoch, cache_hit=False)
    _append_full_fetch_audit(
        data,
        ticker,
        getattr(provider, "name", provider.__class__.__name__),
        started_at_epoch=fetch_started_epoch,
        fetched_at_epoch=fetched_at_epoch,
        skip_optional_http=skip_optional_http,
    )
    for audit_entry in enrichment_audit:
        append_source_audit(data, audit_entry)
    if fmp_quote_audit:
        append_source_audit(data, fmp_quote_audit)
    if monthly_revenue_audit:
        append_source_audit(data, monthly_revenue_audit)
    if finmind_financial_fallback_audit:
        append_source_audit(data, finmind_financial_fallback_audit)
    finalize_data_trust(data)
    data["cache_generated_at_epoch"] = fetched_at_epoch
    data["cache_generated_at"] = datetime.fromtimestamp(fetched_at_epoch, timezone.utc).isoformat()
    set_cache_json(original_cache_key, data, FINANCIAL_DATA_CACHE_SECONDS)
    resolved_cache_key = f"financial_data:{ticker}"
    if resolved_cache_key != original_cache_key:
        set_cache_json(resolved_cache_key, data, FINANCIAL_DATA_CACHE_SECONDS)
    return data
