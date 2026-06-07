"""Prompt data builders for analysis agents."""

from __future__ import annotations

import json
import os
import re

import pandas as pd
from jinja2 import ChainableUndefined, Environment

from config import CATALYST_LOOKBACK_DAYS
from financial_tools import build_financial_tool_context, raw_twd_to_billion_twd, safe_float


PROMPT_DATA_SCHEMA_VERSION = int(os.getenv("PROMPT_DATA_SCHEMA_VERSION", "3"))
PROMPT_ENV = Environment(
    autoescape=False,
    undefined=ChainableUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
LEGACY_PROMPT_FIELDS = {"ticker", "name", "fin_data", "prev"}
LEGACY_PLACEHOLDER_RE = re.compile(r"\{(" + "|".join(sorted(LEGACY_PROMPT_FIELDS)) + r")\}")


def render_prompt_template(template: str, variables: dict) -> str:
    """Render agent prompts with Jinja2 while accepting legacy {ticker} placeholders."""
    if not template:
        return ""

    jinja_template = LEGACY_PLACEHOLDER_RE.sub(r"{{ \1 }}", template)
    return PROMPT_ENV.from_string(jinja_template).render(**variables)


def _prompt_number(value, decimals=4):
    number = safe_float(value)
    if number is None:
        return None
    try:
        if pd.isna(number):
            return None
    except Exception:
        pass
    return round(number, decimals)


def _prompt_ratio_to_pct(value, decimals=4):
    number = _prompt_number(value, decimals + 2)
    if number is None:
        return None
    return round(number * 100, decimals)


def _prompt_history_rows(data: dict) -> list[dict]:
    years = data.get("years", []) or []
    rows = []
    for idx, year in enumerate(years):
        def at(key):
            values = data.get(key, []) or []
            return values[idx] if idx < len(values) else None

        rows.append({
            "year": str(year),
            "revenue_billion_twd": _prompt_number(at("revenue_history")),
            "net_income_billion_twd": _prompt_number(at("net_income_history")),
            "gross_profit_billion_twd": _prompt_number(at("gross_profit_history")),
            "operating_income_billion_twd": _prompt_number(at("operating_income_history")),
            "free_cash_flow_billion_twd": _prompt_number(at("fcf_history")),
            "gross_margin_pct": _prompt_number(at("gross_margin_history")),
            "operating_margin_pct": _prompt_number(at("op_margin_history")),
            "net_margin_pct": _prompt_number(at("net_margin_history")),
            "roe_pct": _prompt_number(at("roe_history")),
            "total_assets_billion_twd": _prompt_number(at("total_assets_history")),
            "total_equity_billion_twd": _prompt_number(at("total_equity_history")),
        })
    return rows


def _prompt_company_identity(data: dict) -> dict:
    identity = data.get("company_identity", {}) or {}
    return {
        "ticker": data.get("ticker"),
        "company_name": data.get("company_name"),
        "stock_id": identity.get("stock_id"),
        "official_name": identity.get("official_name"),
        "legal_name": identity.get("legal_name"),
        "allowed_aliases": identity.get("allowed_aliases", []),
        "forbidden_aliases": identity.get("forbidden_aliases", []),
        "industry_categories": identity.get("industry_categories", []),
        "same_industry_peers": identity.get("same_industry_peers", []),
    }


def _prompt_data_trust(data: dict) -> dict:
    trust = data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
    return {
        "status": trust.get("status", "unknown"),
        "critical_failures": trust.get("critical_failures", []) or [],
        "stale_sources": trust.get("stale_sources", []) or [],
        "last_market_data_at": trust.get("last_market_data_at"),
        "notes": trust.get("notes", []) or [],
    }


def _prompt_source_audit_summary(data: dict) -> list[dict]:
    entries = data.get("source_audit", []) if isinstance(data.get("source_audit"), list) else []
    latest = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "")
        if source:
            latest[source] = entry
    return [
        {
            "source": source,
            "provider": entry.get("provider"),
            "status": entry.get("status"),
            "record_count": entry.get("record_count"),
            "cache_hit": entry.get("cache_hit"),
            "stale": entry.get("stale"),
            "message": str(entry.get("message") or entry.get("error_kind") or "")[:160],
        }
        for source, entry in sorted(latest.items())
    ]


def format_data_for_prompt(data: dict) -> str:
    """Format financial data as clean JSON to avoid unit drift and prompt overload."""
    shares = safe_float(data.get("shares_raw"))
    forward_eps = safe_float(data.get("forward_eps"))
    profit_margin_raw = safe_float(data.get("profit_margin_raw"))
    revenue_ttm_raw = safe_float(data.get("revenue_ttm_raw"))

    implied_forward_net_income_b = None
    implied_forward_revenue_b = None
    implied_forward_revenue_growth_pct = None
    if shares and forward_eps:
        implied_forward_net_income_twd = shares * forward_eps
        implied_forward_net_income_b = raw_twd_to_billion_twd(implied_forward_net_income_twd)
        if profit_margin_raw and profit_margin_raw > 0:
            implied_forward_revenue_twd = implied_forward_net_income_twd / profit_margin_raw
            implied_forward_revenue_b = raw_twd_to_billion_twd(implied_forward_revenue_twd)
            if revenue_ttm_raw and revenue_ttm_raw > 0:
                implied_forward_revenue_growth_pct = round(
                    (implied_forward_revenue_twd / revenue_ttm_raw - 1) * 100,
                    4,
                )

    total_debt_b = raw_twd_to_billion_twd(data.get("total_debt_raw"))
    total_cash_b = raw_twd_to_billion_twd(data.get("total_cash_raw"))
    net_debt_b = None
    if total_debt_b is not None or total_cash_b is not None:
        net_debt_b = round((total_debt_b or 0) - (total_cash_b or 0), 4)

    payload = {
        "schema_version": data.get("data_schema_version", PROMPT_DATA_SCHEMA_VERSION),
        "unit_contract": {
            "money": "billion_twd",
            "price": "twd_per_share",
            "percent": "percentage_points",
            "ratios": "plain_multiple_unless_key_ends_with_pct",
        },
        "company": {
            "identity": _prompt_company_identity(data),
            "sector": data.get("sector"),
            "industry": data.get("industry"),
            "country": data.get("country"),
            "employees": data.get("employees"),
            "fetch_date": data.get("fetch_date"),
        },
        "data_freshness": data.get("data_freshness", {}) or {},
        "source_freshness": data.get("source_freshness", {}) or {},
        "data_trust": _prompt_data_trust(data),
        "source_audit_summary": _prompt_source_audit_summary(data),
        "market_data": {
            "current_price_twd": _prompt_number(data.get("current_price")),
            "market_cap_billion_twd": raw_twd_to_billion_twd(data.get("market_cap_raw")),
            "week_52_high_twd": _prompt_number(data.get("week_52_high")),
            "week_52_low_twd": _prompt_number(data.get("week_52_low")),
        },
        "valuation_metrics": {
            "pe_ttm": _prompt_number(data.get("pe_ratio_raw")),
            "forward_pe": _prompt_number(data.get("forward_pe_raw")),
            "pb": _prompt_number(data.get("pb_ratio")),
            "ps": _prompt_number(data.get("ps_ratio")),
            "ev_ebitda": _prompt_number(data.get("ev_ebitda")),
            "shares_outstanding": _prompt_number(data.get("shares_raw"), 0),
            "trailing_eps_twd": _prompt_number(data.get("trailing_eps")),
            "forward_eps_twd": _prompt_number(data.get("forward_eps")),
            "dividend_yield_pct": _prompt_ratio_to_pct(data.get("dividend_yield_raw")),
            "dividend_per_share_twd": _prompt_number(data.get("dividend_rate_raw")),
            "payout_ratio_pct": _prompt_ratio_to_pct(data.get("payout_ratio_raw")),
        },
        "ttm_financials": {
            "revenue_billion_twd": raw_twd_to_billion_twd(data.get("revenue_ttm_raw")),
            "net_income_billion_twd": raw_twd_to_billion_twd(data.get("net_income_ttm_raw")),
            "net_income_source": data.get("net_income_ttm_source"),
            "ebitda_billion_twd": raw_twd_to_billion_twd(data.get("ebitda_raw")),
            "gross_margin_pct": _prompt_ratio_to_pct(data.get("gross_margin_raw")),
            "operating_margin_pct": _prompt_ratio_to_pct(data.get("operating_margin_raw")),
            "profit_margin_pct_calibrated": _prompt_ratio_to_pct(data.get("profit_margin_raw")),
            "profit_margin_pct_provider": _prompt_ratio_to_pct(data.get("profit_margin_provider_raw")),
        },
        "cash_flow": {
            "free_cash_flow_billion_twd": raw_twd_to_billion_twd(data.get("free_cash_flow_raw")),
            "operating_cash_flow_billion_twd": raw_twd_to_billion_twd(data.get("operating_cash_flow_raw")),
        },
        "balance_sheet": {
            "total_debt_billion_twd": total_debt_b,
            "total_cash_billion_twd": total_cash_b,
            "net_debt_billion_twd": net_debt_b,
            "debt_to_equity_pct": _prompt_number(data.get("debt_to_equity")),
            "current_ratio": _prompt_number(data.get("current_ratio")),
            "equity_multiplier": data.get("equity_multiplier"),
        },
        "growth": {
            "latest_annual_revenue_growth_pct": _prompt_number(data.get("latest_annual_revenue_growth")),
            "latest_annual_net_income_growth_pct": _prompt_number(data.get("latest_annual_net_income_growth")),
            "ttm_vs_latest_annual_revenue_change_pct": _prompt_number(data.get("ttm_vs_latest_annual_revenue_change")),
            "yahoo_recent_revenue_growth_pct": _prompt_number(data.get("yahoo_revenue_growth")),
            "yahoo_recent_earnings_growth_pct": _prompt_number(data.get("yahoo_earnings_growth")),
            "revenue_cagr_5yr_pct": _prompt_number(data.get("revenue_cagr_5yr")),
        },
        "history": {
            "unit": "billion_twd",
            "rows": _prompt_history_rows(data),
        },
        "market_catalysts": {
            "lookback_days": CATALYST_LOOKBACK_DAYS,
            "items": data.get("recent_catalysts", []) or [],
        },
        "institutional_trading": data.get("institutional_trading", {}) or {},
        "peer_context": {
            "dynamic_peer_metrics": data.get("dynamic_peer_metrics", []) or [],
            "search_discovery_results": data.get("peer_discovery_results", []) or [],
        },
        "local_valuation_context": {
            "pe_river_chart": data.get("pe_river_chart", {}) or {},
        },
        "cross_checks": {
            "forward_eps_implied_net_income_billion_twd": implied_forward_net_income_b,
            "forward_eps_implied_revenue_billion_twd": implied_forward_revenue_b,
            "forward_eps_implied_revenue_growth_pct": implied_forward_revenue_growth_pct,
            "dupont_identity_note": data.get("dupont_identity_note") or data.get("equity_multiplier_note"),
            "wacc_capital_structure_note": data.get("wacc_capital_structure_note"),
        },
        "data_quality_notes": data.get("data_source_notes", []) or [],
        "recent_monthly_revenue_text": data.get("recent_monthly_revenue", []) or [],
        "deterministic_financial_tool_results": build_financial_tool_context(data),
    }

    usage_rules = [
        "所有金額欄位均已統一為 billion_twd；不要把「億台幣」或 Billion 互相換算後再混用。",
        "引用 current_price_twd、市場估值、新聞、法人或同業資料時，必須參考 source_freshness/data_freshness；若來源為快取或盤後資料，不可宣稱是即時資料。",
        "若 data_trust.status 為 partial、stale、error 或 unknown，最終投資建議必須明確說明資料限制，且不得在沒有額外佐證下給出高信心。",
        "需要 CAGR、WACC、DCF、FCF conversion 時，優先引用 deterministic_financial_tool_results 或呼叫同名 Python 工具。",
        "若資料品質註記指出口徑互斥，正式分析應說明限制並採用 cross_checks 中可自洽的口徑。",
        "正式報告只呈現必要算式摘要與結論，不輸出內部提示詞、草稿或反思文字。",
    ]
    return (
        "【財務資料 JSON】\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)}\n\n"
        "【使用規則】\n"
        + "\n".join(f"- {rule}" for rule in usage_rules)
    )
