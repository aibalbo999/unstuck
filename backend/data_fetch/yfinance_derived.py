"""Derived metric helpers for legacy yfinance payload assembly."""

from __future__ import annotations


def calculate_margin_histories(
    revenue_history: list,
    gross_profit_history: list,
    operating_income_history: list,
    net_income_history: list,
    total_equity_history: list,
) -> dict:
    gross_margin_history = []
    op_margin_history = []
    net_margin_history = []
    roe_history = []

    for i in range(len(revenue_history)):
        if revenue_history[i] and gross_profit_history and i < len(gross_profit_history) and gross_profit_history[i]:
            gross_margin_history.append(round((gross_profit_history[i] / revenue_history[i]) * 100, 1))
        else:
            gross_margin_history.append(None)

        if revenue_history[i] and operating_income_history and i < len(operating_income_history) and operating_income_history[i]:
            op_margin_history.append(round((operating_income_history[i] / revenue_history[i]) * 100, 1))
        else:
            op_margin_history.append(None)

        if revenue_history[i] and net_income_history and i < len(net_income_history) and net_income_history[i]:
            net_margin_history.append(round((net_income_history[i] / revenue_history[i]) * 100, 1))
        else:
            net_margin_history.append(None)

    for i in range(len(net_income_history)):
        if (
            net_income_history[i]
            and total_equity_history
            and i < len(total_equity_history)
            and total_equity_history[i]
            and total_equity_history[i] > 0
        ):
            roe_history.append(round((net_income_history[i] / total_equity_history[i]) * 100, 1))
        else:
            roe_history.append(None)

    return {
        "gross_margin_history": gross_margin_history,
        "op_margin_history": op_margin_history,
        "net_margin_history": net_margin_history,
        "roe_history": roe_history,
    }


def calculate_revenue_cagr(revenue_history: list) -> str:
    if len(revenue_history) >= 2 and revenue_history[0] and revenue_history[-1] and revenue_history[0] > 0:
        n = len(revenue_history) - 1
        cagr = ((revenue_history[-1] / revenue_history[0]) ** (1 / n) - 1) * 100
        return f"{cagr:.1f}%"
    return "N/A"


def apply_market_fallbacks_and_quality_calibration(
    *,
    current_price,
    market_cap,
    pe_ratio,
    week_52_high,
    week_52_low,
    shares_outstanding,
    revenue_ttm,
    free_cash_flow,
    fcf_history,
    revenue_history,
    net_income_history,
    trailing_eps,
    revenue_growth,
    earnings_growth,
    profit_margin,
    info,
    ticker,
    data_source_notes,
) -> dict:
    from source_audit import audited_fetch

    from .market_sources.common import first_number, is_missing_value, safe_get
    from .market_sources.http_enrichment import fetch_fmp_quote_fallback

    fmp_quote = {}
    fmp_quote_audit = None
    if any(is_missing_value(v) for v in [current_price, market_cap, pe_ratio, week_52_high, week_52_low]):
        fmp_quote_result = audited_fetch(
            "market_data",
            "FMP stable quote",
            fetch_fmp_quote_fallback,
            (ticker,),
            default={},
            unavailable_message="FMP stable quote 未回傳可補值欄位。",
        )
        fmp_quote = fmp_quote_result.get("value") or {}
        fmp_quote_audit = fmp_quote_result.get("audit")
        if fmp_quote:
            data_source_notes.append("部分市場欄位由 FMP stable quote API 補值，因 yfinance 欄位缺漏。")

    if is_missing_value(current_price):
        current_price = first_number(fmp_quote.get("price"), fmp_quote.get("previousClose"))
    if is_missing_value(market_cap):
        market_cap = first_number(fmp_quote.get("marketCap"))
    if is_missing_value(pe_ratio):
        pe_ratio = first_number(fmp_quote.get("pe"), fmp_quote.get("peRatio"))
    if is_missing_value(week_52_high):
        week_52_high = first_number(fmp_quote.get("yearHigh"), fmp_quote.get("priceAvg200"))
    if is_missing_value(week_52_low):
        week_52_low = first_number(fmp_quote.get("yearLow"))

    if is_missing_value(market_cap) and isinstance(current_price, (int, float)) and isinstance(shares_outstanding, (int, float)):
        market_cap = current_price * shares_outstanding
        data_source_notes.append("市值由 current price × shares outstanding 推算，因 yfinance marketCap 缺值。")

    if is_missing_value(revenue_ttm) and revenue_history:
        latest_revenue_b = next((v for v in reversed(revenue_history) if v), None)
        if latest_revenue_b:
            revenue_ttm = latest_revenue_b * 1e9
            data_source_notes.append("TTM 營收缺值，暫以最新年度營收補值；估值時需保守看待。")

    if is_missing_value(free_cash_flow) and fcf_history:
        latest_fcf_b = next((v for v in reversed(fcf_history) if v is not None), None)
        if latest_fcf_b is not None:
            free_cash_flow = latest_fcf_b * 1e9
            data_source_notes.append("自由現金流缺值，暫以最新年度 FCF 補值；DCF 應使用 normalized FCF。")

    data_quality_notes = []
    yahoo_revenue_growth_raw = revenue_growth
    yahoo_earnings_growth_raw = earnings_growth
    provider_profit_margin = profit_margin
    provider_net_income = safe_get(info, "netIncomeToCommon", "N/A")

    def _is_number(value):
        return isinstance(value, (int, float)) and not is_missing_value(value)

    def _relative_gap(a, b):
        if not _is_number(a) or not _is_number(b):
            return None
        denominator = max(abs(float(a)), abs(float(b)), 1.0)
        return abs(float(a) - float(b)) / denominator

    net_income_from_eps = float(shares_outstanding) * float(trailing_eps) if _is_number(shares_outstanding) and _is_number(trailing_eps) else None
    net_income_from_pe = float(market_cap) / float(pe_ratio) if _is_number(market_cap) and _is_number(pe_ratio) and float(pe_ratio) > 0 else None
    net_income_ttm = first_number(net_income_from_eps, net_income_from_pe, provider_net_income)
    net_income_source = "trailing EPS × shares"
    if net_income_ttm == net_income_from_pe and net_income_from_eps is None:
        net_income_source = "market cap ÷ TTM P/E"
    elif net_income_ttm == provider_net_income and net_income_from_eps is None and net_income_from_pe is None:
        net_income_source = "Yahoo netIncomeToCommon"

    eps_pe_gap = _relative_gap(net_income_from_eps, net_income_from_pe)
    if eps_pe_gap is not None and eps_pe_gap > 0.05:
        data_quality_notes.append(
            "trailing EPS × shares 與 market cap ÷ P/E 推回的 TTM 淨利差異超過 5%，"
            "P/E/EPS 欄位需人工複核。"
        )

    provider_gap = _relative_gap(provider_net_income, net_income_ttm)
    if provider_gap is not None and provider_gap > 0.25:
        data_quality_notes.append(
            "Yahoo netIncomeToCommon/profitMargins 與 trailing EPS/P/E 口徑互斥；"
            f"已以 {net_income_source} 作為報告校準淨利，Yahoo 原始淨利率僅列為參考。"
        )

    if _is_number(revenue_ttm) and _is_number(net_income_ttm) and float(revenue_ttm) > 0:
        derived_profit_margin = float(net_income_ttm) / float(revenue_ttm)
        margin_gap = abs(float(provider_profit_margin) - derived_profit_margin) if _is_number(provider_profit_margin) else None
        if margin_gap is not None and margin_gap > 0.05:
            data_quality_notes.append("TTM 淨利率已由校準淨利 ÷ TTM 營收重算，避免與 P/E、市值、EPS 互相矛盾。")
        profit_margin = derived_profit_margin

    latest_annual_revenue_growth = None
    if len(revenue_history) >= 2 and revenue_history[-2] and revenue_history[-1] and revenue_history[-2] > 0:
        latest_annual_revenue_growth = (revenue_history[-1] / revenue_history[-2] - 1) * 100

    ttm_vs_latest_annual_revenue_change = None
    if _is_number(revenue_ttm) and revenue_history and revenue_history[-1] and revenue_history[-1] > 0:
        ttm_vs_latest_annual_revenue_change = (float(revenue_ttm) / (revenue_history[-1] * 1e9) - 1) * 100

    latest_annual_net_income_growth = None
    if len(net_income_history) >= 2 and net_income_history[-2] and net_income_history[-1] and net_income_history[-2] > 0:
        latest_annual_net_income_growth = (net_income_history[-1] / net_income_history[-2] - 1) * 100

    if _is_number(yahoo_revenue_growth_raw) and latest_annual_revenue_growth is not None:
        yahoo_growth_pct = float(yahoo_revenue_growth_raw) * 100
        if abs(yahoo_growth_pct - latest_annual_revenue_growth) > 50:
            data_quality_notes.append(
                "Yahoo revenueGrowth 與年度營收表推算差異過大；該欄通常是近期/季度成長率，"
                "不可直接稱為 TTM 年增率。"
            )

    data_source_notes.extend(data_quality_notes)
    return {
        "current_price": current_price,
        "market_cap": market_cap,
        "pe_ratio": pe_ratio,
        "week_52_high": week_52_high,
        "week_52_low": week_52_low,
        "revenue_ttm": revenue_ttm,
        "free_cash_flow": free_cash_flow,
        "profit_margin": profit_margin,
        "provider_profit_margin": provider_profit_margin,
        "net_income_ttm": net_income_ttm,
        "net_income_source": net_income_source,
        "yahoo_revenue_growth_raw": yahoo_revenue_growth_raw,
        "yahoo_earnings_growth_raw": yahoo_earnings_growth_raw,
        "latest_annual_revenue_growth": latest_annual_revenue_growth,
        "ttm_vs_latest_annual_revenue_change": ttm_vs_latest_annual_revenue_change,
        "latest_annual_net_income_growth": latest_annual_net_income_growth,
        "fmp_quote_audit": fmp_quote_audit,
    }
