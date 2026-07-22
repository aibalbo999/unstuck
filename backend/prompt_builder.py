"""Prompt data builders for analysis agents."""

from __future__ import annotations

import json
import os
import re
import warnings
from functools import lru_cache

from jinja2 import ChainableUndefined, Environment

from config import CATALYST_LOOKBACK_DAYS
from financial_tools import build_financial_tool_context, raw_twd_to_billion_twd, safe_float
from prompt_builder_helpers import (
    _agent_context,
    _compact_list,
    _compact_pe_river,
    _prompt_company_identity,
    _prompt_data_trust,
    _prompt_history_rows,
    _prompt_number,
    _prompt_ratio_to_pct,
    _prompt_source_audit_summary,
    _safe_iterable_prefix,
)
from prompt_context_sections import prompt_global_market_context, prompt_international_news_context

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

    jinja_template, has_legacy_placeholders = _get_compiled_prompt_template(template)
    if has_legacy_placeholders:
        warnings.warn("legacy prompt placeholder syntax is deprecated; use Jinja2 placeholders like {{ ticker }} instead", DeprecationWarning, stacklevel=2)
    return jinja_template.render(**variables)


@lru_cache(maxsize=256)
def _get_compiled_prompt_template(template: str):
    has_legacy_placeholders = bool(LEGACY_PLACEHOLDER_RE.search(template))
    normalized = LEGACY_PLACEHOLDER_RE.sub(r"{{ \1 }}", template)
    return PROMPT_ENV.from_string(normalized), has_legacy_placeholders


def format_data_for_prompt(data: dict, *, compact: bool = False) -> str:
    """Format financial data as clean JSON to avoid unit drift and prompt overload."""
    shares = safe_float(dict.get(data, "shares_raw"))
    forward_eps = safe_float(dict.get(data, "forward_eps"))
    profit_margin_raw = safe_float(dict.get(data, "profit_margin_raw"))
    revenue_ttm_raw = safe_float(dict.get(data, "revenue_ttm_raw"))

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

    total_debt_b = raw_twd_to_billion_twd(dict.get(data, "total_debt_raw"))
    total_cash_b = raw_twd_to_billion_twd(dict.get(data, "total_cash_raw"))
    net_debt_b = None
    if total_debt_b is not None or total_cash_b is not None:
        net_debt_b = round((total_debt_b or 0) - (total_cash_b or 0), 4)

    payload = {
        "schema_version": dict.get(data, "data_schema_version", PROMPT_DATA_SCHEMA_VERSION),
        "unit_contract": {
            "money": "billion_twd",
            "price": "twd_per_share",
            "percent": "percentage_points",
            "ratios": "plain_multiple_unless_key_ends_with_pct",
        },
        "company": {
            "identity": _prompt_company_identity(data),
            "sector": dict.get(data, "sector"),
            "industry": dict.get(data, "industry"),
            "country": dict.get(data, "country"),
            "employees": dict.get(data, "employees"),
            "fetch_date": dict.get(data, "fetch_date"),
        },
        "data_freshness": raw_data_freshness if isinstance(raw_data_freshness := dict.get(data, "data_freshness"), dict) else {},
        "source_freshness": raw_source_freshness if isinstance(raw_source_freshness := dict.get(data, "source_freshness"), dict) else {},
        "data_trust": _prompt_data_trust(data),
        "source_audit_summary": _prompt_source_audit_summary(data),
        "agent_context": _agent_context(data),
        "market_data": {
            "current_price_twd": _prompt_number(dict.get(data, "current_price")),
            "market_cap_billion_twd": raw_twd_to_billion_twd(dict.get(data, "market_cap_raw")),
            "week_52_high_twd": _prompt_number(dict.get(data, "week_52_high")),
            "week_52_low_twd": _prompt_number(dict.get(data, "week_52_low")),
        },
        "valuation_metrics": {
            "pe_ttm": _prompt_number(dict.get(data, "pe_ratio_raw")),
            "forward_pe": _prompt_number(dict.get(data, "forward_pe_raw")),
            "pb": _prompt_number(dict.get(data, "pb_ratio")),
            "ps": _prompt_number(dict.get(data, "ps_ratio")),
            "ev_ebitda": _prompt_number(dict.get(data, "ev_ebitda")),
            "shares_outstanding": _prompt_number(dict.get(data, "shares_raw"), 0),
            "trailing_eps_twd": _prompt_number(dict.get(data, "trailing_eps")),
            "forward_eps_twd": _prompt_number(dict.get(data, "forward_eps")),
            "dividend_yield_pct": _prompt_ratio_to_pct(dict.get(data, "dividend_yield_raw")),
            "dividend_per_share_twd": _prompt_number(dict.get(data, "dividend_rate_raw")),
            "payout_ratio_pct": _prompt_ratio_to_pct(dict.get(data, "payout_ratio_raw")),
        },
        "ttm_financials": {
            "revenue_billion_twd": raw_twd_to_billion_twd(dict.get(data, "revenue_ttm_raw")),
            "net_income_billion_twd": raw_twd_to_billion_twd(dict.get(data, "net_income_ttm_raw")),
            "net_income_source": dict.get(data, "net_income_ttm_source"),
            "ebitda_billion_twd": raw_twd_to_billion_twd(dict.get(data, "ebitda_raw")),
            "gross_margin_pct": _prompt_ratio_to_pct(dict.get(data, "gross_margin_raw")),
            "operating_margin_pct": _prompt_ratio_to_pct(dict.get(data, "operating_margin_raw")),
            "profit_margin_pct_calibrated": _prompt_ratio_to_pct(dict.get(data, "profit_margin_raw")),
            "profit_margin_pct_provider": _prompt_ratio_to_pct(dict.get(data, "profit_margin_provider_raw")),
        },
        "cash_flow": {
            "free_cash_flow_billion_twd": raw_twd_to_billion_twd(dict.get(data, "free_cash_flow_raw")),
            "operating_cash_flow_billion_twd": raw_twd_to_billion_twd(dict.get(data, "operating_cash_flow_raw")),
        },
        "balance_sheet": {
            "total_debt_billion_twd": total_debt_b,
            "total_cash_billion_twd": total_cash_b,
            "net_debt_billion_twd": net_debt_b,
            "debt_to_equity_pct": _prompt_number(dict.get(data, "debt_to_equity")),
            "current_ratio": _prompt_number(dict.get(data, "current_ratio")),
            "equity_multiplier": dict.get(data, "equity_multiplier"),
        },
        "growth": {
            "latest_annual_revenue_growth_pct": _prompt_number(dict.get(data, "latest_annual_revenue_growth")),
            "latest_annual_net_income_growth_pct": _prompt_number(dict.get(data, "latest_annual_net_income_growth")),
            "ttm_vs_latest_annual_revenue_change_pct": _prompt_number(dict.get(data, "ttm_vs_latest_annual_revenue_change")),
            "yahoo_recent_revenue_growth_pct": _prompt_number(dict.get(data, "yahoo_revenue_growth")),
            "yahoo_recent_earnings_growth_pct": _prompt_number(dict.get(data, "yahoo_earnings_growth")),
            "revenue_cagr_5yr_pct": _prompt_number(dict.get(data, "revenue_cagr_5yr")),
        },
        "history": {
            "unit": "billion_twd",
            "rows": _prompt_history_rows(data),
        },
        "market_catalysts": {
            "lookback_days": CATALYST_LOOKBACK_DAYS,
            "items": _compact_list(dict.get(data, "recent_catalysts", []), 3) if compact else _safe_iterable_prefix(dict.get(data, "recent_catalysts", [])),
        },
        "global_market_context": prompt_global_market_context(data, compact=compact),
        "international_news_context": prompt_international_news_context(data, compact=compact),
        "institutional_trading": raw_institutional_trading if isinstance(raw_institutional_trading := dict.get(data, "institutional_trading"), dict) else {},
        "peer_context": {
            "dynamic_peer_metrics": _compact_list(dict.get(data, "dynamic_peer_metrics", []), 5) if compact else _safe_iterable_prefix(dict.get(data, "dynamic_peer_metrics", [])),
            "search_discovery_results": [] if compact else _safe_iterable_prefix(dict.get(data, "peer_discovery_results", [])),
        },
        "local_valuation_context": {
            "pe_river_chart": _compact_pe_river(raw_pe_river_chart := dict.get(data, "pe_river_chart")) if compact else (raw_pe_river_chart if isinstance(raw_pe_river_chart := dict.get(data, "pe_river_chart"), dict) else {}),
        },
        "cross_checks": {
            "forward_eps_implied_net_income_billion_twd": implied_forward_net_income_b,
            "forward_eps_implied_revenue_billion_twd": implied_forward_revenue_b,
            "forward_eps_implied_revenue_growth_pct": implied_forward_revenue_growth_pct,
            "dupont_identity_note": dict.get(data, "dupont_identity_note") or dict.get(data, "equity_multiplier_note"),
            "wacc_capital_structure_note": dict.get(data, "wacc_capital_structure_note"),
        },
        "data_quality_notes": _compact_list(dict.get(data, "data_source_notes", []), 5) if compact else _safe_iterable_prefix(dict.get(data, "data_source_notes", [])),
        "recent_monthly_revenue_text": _compact_list(dict.get(data, "recent_monthly_revenue", []), 4) if compact else _safe_iterable_prefix(dict.get(data, "recent_monthly_revenue", [])),
        "deterministic_financial_tool_results": build_financial_tool_context(data),
    }

    usage_rules = [
        "所有金額欄位均已統一為 billion_twd；不要把「億台幣」或 Billion 互相換算後再混用。",
        "引用 current_price_twd、市場估值、新聞、法人或同業資料時，必須參考 source_freshness/data_freshness；若來源為快取或盤後資料，不可宣稱是即時資料。",
        "總經、產業循環、美股帶動或國際局勢敘述必須引用 global_market_context / international_news_context；若缺資料，必須明確標示未驗證。",
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
