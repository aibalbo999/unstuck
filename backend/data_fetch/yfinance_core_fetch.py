"""Canonical yfinance core fetch runtime.

This module owns the blocking yfinance/FinMind core payload assembly. Legacy
imports are kept in data_fetch.yfinance_legacy_fetch only.
"""

import asyncio
import time as time_module
import warnings
from cache_store import get_cache_json, set_cache_json
from .market_sources.common import (
    safe_get,
)
from .market_sources.http_enrichment import (
    fetch_fmp_quote_fallback,
    fetch_recent_catalysts,
)
from .market_sources.identity import build_company_identity
from .market_sources.taiwan import (
    DataLoader,
    fetch_finmind_financial_statement_fallback,
)
from .market_sources.ticker_resolver import get_market_data_provider
from .market_sources.valuation import build_pe_river_chart_data
from prompt_builder import format_data_for_prompt
from runtime_events import emit_log
from .audit_helpers import (
    _append_cache_audit_entries,
    _append_source_fetch_audit,
    _assess_cached_financial_data,
    _is_likely_market_session,
)
from .constants import DATA_SCHEMA_VERSION
from .optional_enrichment import enrich_optional_http_async
from .yfinance_cache_gate import build_fresh_cache_payload
from .yfinance_capital_notes import build_capital_structure_notes
from .yfinance_core_context import build_yfinance_payload_vars
from .yfinance_error_payload import build_fetch_error_payload
from .yfinance_payload import build_legacy_payload, finalize_and_cache_legacy_payload
from .yfinance_derived import (
    calculate_margin_histories,
    calculate_revenue_cagr,
)
from .yfinance_extractors import extract_dividend_history, extract_event_calendar, extract_financial_histories, extract_price_history, extract_price_history_ranges, fetch_monthly_revenue_records
from .yfinance_sync_enrichment import fetch_sync_enrichment_bundle

warnings.filterwarnings("ignore", module="yfinance")


def fetch_stock_data(ticker: str, skip_optional_http: bool = False, market_data_provider=None, force_refresh: bool = False) -> dict:
    """
    從 yfinance 獲取股票完整財務數據
    返回格式化的數據字典
    """
    ticker = ticker.strip().upper()
    original_ticker = ticker
    cache_key = f"financial_data:{original_ticker}"
    fetch_started_epoch = time_module.time()
    if force_refresh:
        emit_log(f"  ♻️  {original_ticker} 已要求強制刷新，略過既有財務資料快取...")
    else:
        cached = get_cache_json(cache_key)
        fresh_cached, stale_sources, schema_mismatch = build_fresh_cache_payload(
            original_ticker,
            cached,
            assess_cached=_assess_cached_financial_data,
            append_cache_audit=_append_cache_audit_entries,
            now_epoch=time_module.time(),
        )
        if fresh_cached:
            age_minutes = (fresh_cached.get("data_freshness", {}).get("age_seconds") or 0) / 60
            emit_log(f"  ✅ 使用快取的 {fresh_cached.get('ticker', original_ticker)} 財務數據（市場資料約 {age_minutes:.1f} 分鐘前更新）")
            return fresh_cached
        if stale_sources:
            stale_labels = ", ".join(stale_sources)
            emit_log(
                f"  ♻️  {original_ticker} 快取來源已過期（{stale_labels}），重新抓取核心分析資料..."
            )
        if schema_mismatch:
            emit_log(f"  ♻️  {original_ticker} 快取資料口徑已更新，重新抓取財務數據...")

    emit_log(f"  📊 正在獲取 {ticker} 財務數據...")
    
    try:
        provider = market_data_provider or get_market_data_provider(ticker)
        stock, info, is_valid, resolved_ticker, attempts = provider.resolve_stock(ticker)
        for index, attempt in enumerate(attempts[1:], start=1):
            previous = attempts[index - 1]
            if not previous.get("valid"):
                emit_log(f"    ⚠️ {previous.get('ticker')} 查無資料，嘗試 {attempt.get('ticker')}...")
        if is_valid:
            ticker = resolved_ticker

        
        # === 基本資訊 ===
        raw_company_name = safe_get(info, "longName", safe_get(info, "shortName", ticker))
        company_identity = build_company_identity(ticker, info, raw_company_name)
        company_name = company_identity.get("display_name") or raw_company_name
        company_summary = safe_get(info, "longBusinessSummary", "")
        website = safe_get(info, "website", "")
        exchange = safe_get(info, "exchange", safe_get(info, "fullExchangeName", ""))
        currency = safe_get(info, "currency", "")
        financial_currency = safe_get(info, "financialCurrency", currency)
        sector = safe_get(info, "sector", "科技業")
        industry = safe_get(info, "industry", "半導體")
        country = safe_get(info, "country", "Taiwan")
        employees = safe_get(info, "fullTimeEmployees", "N/A")
        
        # === 市場數據 ===
        current_price = safe_get(info, "currentPrice", safe_get(info, "regularMarketPrice", "N/A"))
        if current_price == "N/A":
            current_price = safe_get(info, "previousClose", "N/A")
        
        if current_price == "N/A":
            try:
                hist_1d = stock.history(period="5d")
                if not hist_1d.empty:
                    current_price = round(float(hist_1d["Close"].iloc[-1]), 2)
            except Exception:
                pass

        open_price = safe_get(info, "open", "N/A")
        previous_close = safe_get(info, "previousClose", "N/A")
        day_high = safe_get(info, "dayHigh", "N/A")
        day_low = safe_get(info, "dayLow", "N/A")
        volume = safe_get(info, "volume", "N/A")
        market_cap = safe_get(info, "marketCap", "N/A")
        week_52_high = safe_get(info, "fiftyTwoWeekHigh", "N/A")
        week_52_low = safe_get(info, "fiftyTwoWeekLow", "N/A")
        avg_volume = safe_get(info, "averageVolume", "N/A")
        
        # === 估值指標 ===
        pe_ratio = safe_get(info, "trailingPE", "N/A")
        forward_pe = safe_get(info, "forwardPE", "N/A")
        pb_ratio = safe_get(info, "priceToBook", "N/A")
        ps_ratio = safe_get(info, "priceToSalesTrailing12Months", "N/A")
        ev_ebitda = safe_get(info, "enterpriseToEbitda", "N/A")
        ev = safe_get(info, "enterpriseValue", "N/A")
        
        shares_outstanding = safe_get(info, "sharesOutstanding", "N/A")
        float_shares = safe_get(info, "floatShares", "N/A")
        held_percent_insiders = safe_get(info, "heldPercentInsiders", "N/A")
        held_percent_institutions = safe_get(info, "heldPercentInstitutions", "N/A")
        shares_short = safe_get(info, "sharesShort", "N/A")
        short_ratio = safe_get(info, "shortRatio", "N/A")
        short_percent_of_float = safe_get(info, "shortPercentOfFloat", "N/A")
        forward_eps = safe_get(info, "forwardEps", "N/A")
        trailing_eps = safe_get(info, "trailingEps", "N/A")
        
        # === 財務指標 ===
        revenue_ttm = safe_get(info, "totalRevenue", "N/A")
        gross_margin = safe_get(info, "grossMargins", "N/A")
        operating_margin = safe_get(info, "operatingMargins", "N/A")
        profit_margin = safe_get(info, "profitMargins", "N/A")
        ebitda = safe_get(info, "ebitda", "N/A")
        
        # === 現金流 ===
        free_cash_flow = safe_get(info, "freeCashflow", "N/A")
        operating_cash_flow = safe_get(info, "operatingCashflow", "N/A")
        
        # === 資產負債 ===
        total_debt = safe_get(info, "totalDebt", "N/A")
        total_cash = safe_get(info, "totalCash", "N/A")
        debt_to_equity = safe_get(info, "debtToEquity", "N/A")
        current_ratio = safe_get(info, "currentRatio", "N/A")
        
        # === 股東回報 ===
        roe = safe_get(info, "returnOnEquity", "N/A")
        roa = safe_get(info, "returnOnAssets", "N/A")
        dividend_yield = safe_get(info, "dividendYield", "N/A")
        dividend_rate = safe_get(info, "dividendRate", "N/A")
        payout_ratio = safe_get(info, "payoutRatio", "N/A")
        
        # === 成長率 ===
        revenue_growth = safe_get(info, "revenueGrowth", "N/A")
        earnings_growth = safe_get(info, "earningsGrowth", "N/A")
        earnings_quarterly_growth = safe_get(info, "earningsQuarterlyGrowth", "N/A")
        
        # === Beta & 分析師評級 ===
        beta = safe_get(info, "beta", "N/A")
        analyst_target = safe_get(info, "targetMeanPrice", "N/A")
        analyst_rec = safe_get(info, "recommendationKey", "N/A")
        analyst_count = safe_get(info, "numberOfAnalystOpinions", "N/A")
        data_source_notes = []
        
        # === 歷史財務報表（5年）/ 現金流 / 資產負債 / FinMind 備援 ===
        histories = extract_financial_histories(stock, ticker, data_source_notes, DataLoader)
        years = histories["years"]
        revenue_history = histories["revenue_history"]
        net_income_history = histories["net_income_history"]
        gross_profit_history = histories["gross_profit_history"]
        operating_income_history = histories["operating_income_history"]
        fcf_history = histories["fcf_history"]
        total_assets_history = histories["total_assets_history"]
        total_equity_history = histories["total_equity_history"]
        finmind_financial_fallback_audit = histories["finmind_financial_fallback_audit"]
        
        # === 計算衍生指標 ===
        margin_histories = calculate_margin_histories(
            revenue_history,
            gross_profit_history,
            operating_income_history,
            net_income_history,
            total_equity_history,
        )
        gross_margin_history = margin_histories["gross_margin_history"]
        op_margin_history = margin_histories["op_margin_history"]
        net_margin_history = margin_histories["net_margin_history"]
        roe_history = margin_histories["roe_history"]
        
        # 計算權益乘數（Equity Multiplier = Total Assets / Equity）
        capital_notes = build_capital_structure_notes(
            stock,
            info,
            revenue_history=revenue_history,
            net_income_history=net_income_history,
            total_assets_history=total_assets_history,
            total_equity_history=total_equity_history,
            market_cap=market_cap,
            total_debt=total_debt,
        )
        equity_multiplier = capital_notes["equity_multiplier"]
        equity_multiplier_note = capital_notes["equity_multiplier_note"]
        dupont_identity_note = capital_notes["dupont_identity_note"]
        wacc_capital_structure_note = capital_notes["wacc_capital_structure_note"]
        
        # 計算收入 CAGR（5年）
        revenue_cagr = calculate_revenue_cagr(revenue_history)
        
        # === 近期股價歷史 ===
        price_history = extract_price_history(stock)
        price_history_ranges = extract_price_history_ranges(stock)
        dividend_history = extract_dividend_history(stock)
        event_calendar = extract_event_calendar(stock, info)
            
        # === FinMind 補充台股每月營收 ===
        recent_monthly_revenue, monthly_revenue_audit = fetch_monthly_revenue_records(ticker, DataLoader)

        # === 即時/質性資料擴充 ===
        enrichment_bundle = fetch_sync_enrichment_bundle(
            ticker=ticker,
            stock=stock,
            company_name=company_name,
            sector=sector,
            industry=industry,
            company_identity=company_identity,
            years=years,
            net_income_history=net_income_history,
            shares_outstanding=shares_outstanding,
            skip_optional_http=skip_optional_http,
        )
        enrichment_audit = enrichment_bundle.get("audit", [])
        recent_catalysts = enrichment_bundle.get("recent_catalysts", [])
        earnings_call = enrichment_bundle.get("earnings_call", {})
        institutional_trading = enrichment_bundle.get("institutional_trading", {})
        dynamic_peer_metrics = enrichment_bundle.get("dynamic_peer_metrics", [])
        peer_discovery_results = enrichment_bundle.get("peer_discovery_results", [])
        pe_river_chart = enrichment_bundle.get(
            "pe_river_chart",
            {"years": years, "eps_twd": [], "multiples": [10, 12, 15, 18], "bands": {}, "source": "unavailable"},
        )

        # === 整合所有數據 ===
        payload_vars, payload_context = build_yfinance_payload_vars(locals())
        data = build_legacy_payload(payload_vars)
        
        data = finalize_and_cache_legacy_payload(
            data=data,
            ticker=ticker,
            original_cache_key=cache_key,
            provider=provider,
            fetch_started_epoch=fetch_started_epoch,
            skip_optional_http=skip_optional_http,
            enrichment_audit=enrichment_audit,
            fmp_quote_audit=payload_context["fmp_quote_audit"],
            monthly_revenue_audit=monthly_revenue_audit,
            finmind_financial_fallback_audit=finmind_financial_fallback_audit,
        )

        emit_log(f"  ✅ {company_name} 數據獲取完成")
        return data
        
    except Exception as e:
        emit_log(f"  ❌ 數據獲取失敗：{e}")
        return build_fetch_error_payload(
            ticker,
            e,
            fetch_started_epoch=fetch_started_epoch,
            finished_at_epoch=time_module.time(),
            append_source_fetch_audit=_append_source_fetch_audit,
        )


async def async_fetch_stock_data(ticker: str) -> dict:
    """Fetch stock data with blocking SDK work offloaded and HTTP enrichment concurrent."""
    ticker = ticker.strip().upper()
    data = await asyncio.to_thread(fetch_stock_data, ticker, True)
    return await enrich_optional_http_async(ticker, data)
