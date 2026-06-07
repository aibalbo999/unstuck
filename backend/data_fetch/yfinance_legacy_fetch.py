# ============================================================
# financial_data.py - 從 yfinance 獲取完整財務數據
# ============================================================

import asyncio
import pandas as pd
import time as time_module
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence
import warnings
from cache_store import get_cache_json, set_cache_json
from config import (
    FINANCIAL_DATA_CACHE_SECONDS,
    FINANCIAL_DATA_MARKET_CACHE_SECONDS,
    FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS,
    SOURCE_FRESHNESS_MAX_AGE_SECONDS,
)
from data_trust import (
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
    append_source_audit,
    build_data_trust,
    build_source_audit_entry,
    finalize_data_trust,
    source_record_count,
)
import data_freshness as freshness_helpers
from .market_sources.common import (
    _dedupe_records,
    _run_named_fetches,
    first_number,
    is_missing_value,
    safe_get,
)
from .market_sources.http_enrichment import (
    fetch_fmp_news_catalysts,
    fetch_fmp_news_catalysts_async,
    fetch_fmp_quote_fallback,
    fetch_google_peer_discovery_results,
    fetch_google_peer_discovery_results_async,
    fetch_google_search_catalysts,
    fetch_google_search_catalysts_async,
    fetch_recent_catalysts,
    fetch_yfinance_news_catalysts,
)
from .market_sources.identity import build_company_identity, is_taiwan_ticker
from .market_sources.peers import fetch_dynamic_peer_metrics
from .market_sources.taiwan import (
    DataLoader,
    _align_finmind_history,
    _history_has_values,
    fetch_finmind_financial_statement_fallback,
    fetch_finmind_news_catalysts,
    fetch_institutional_trading_trend,
)
from .market_sources.ticker_resolver import get_market_data_provider
from .market_sources.valuation import build_pe_river_chart_data
from prompt_builder import format_data_for_prompt
from source_audit import append_audit_entry, audited_fetch, audited_fetch_async
from .audit_helpers import (
    _append_cache_audit_entries,
    _append_full_fetch_audit,
    _append_skipped_fresh_cache_audit,
    _append_source_fetch_audit,
    _assess_cached_financial_data,
    _build_data_freshness,
    _build_source_freshness,
    _build_source_freshness_entry,
    _cache_timestamp_epoch,
    _freshness_policy,
    _is_likely_market_session,
    _market_now,
    _mark_market_data_fetched,
    _mark_sources_fetched,
    _source_is_stale,
    _source_max_age_seconds,
    _source_timestamp_epoch,
)
from .cache_helpers import _cache_financial_data
from .constants import CORE_CACHE_SOURCES, DATA_SCHEMA_VERSION, SOURCE_FRESHNESS_SOURCES
from .formatting import format_number, format_pct
from .optional_enrichment import enrich_optional_http_async
from .yfinance_payload import build_legacy_payload, finalize_and_cache_legacy_payload
from .yfinance_derived import (
    apply_market_fallbacks_and_quality_calibration,
    calculate_margin_histories,
    calculate_revenue_cagr,
)
from .yfinance_extractors import extract_financial_histories, extract_price_history, fetch_monthly_revenue_records
from .yfinance_sync_enrichment import fetch_sync_enrichment_bundle

warnings.filterwarnings("ignore")


def fetch_stock_data(ticker: str, skip_optional_http: bool = False, market_data_provider=None) -> dict:
    """
    從 yfinance 獲取股票完整財務數據
    返回格式化的數據字典
    """
    ticker = ticker.strip().upper()
    original_ticker = ticker
    cache_key = f"financial_data:{original_ticker}"
    fetch_started_epoch = time_module.time()
    cached = get_cache_json(cache_key)
    if cached and cached.get("data_schema_version") == DATA_SCHEMA_VERSION:
        cache_ticker = str(cached.get("ticker") or original_ticker).strip().upper()
        is_fresh, freshness = _assess_cached_financial_data(cached, cache_ticker)
        if is_fresh:
            cached = dict(cached)
            cached["_cache_hit"] = True
            cached["source_audit"] = []
            cached["data_freshness"] = freshness
            cached["source_freshness"] = freshness.get("source_freshness", {})
            _append_cache_audit_entries(cached, cache_ticker, now_epoch=time_module.time())
            age_minutes = (freshness.get("age_seconds") or 0) / 60
            print(f"  ✅ 使用快取的 {cached.get('ticker', original_ticker)} 財務數據（市場資料約 {age_minutes:.1f} 分鐘前更新）")
            return cached
        stale_sources = freshness.get("stale_sources", []) or ["market_data"]
        stale_labels = ", ".join(stale_sources)
        print(
            f"  ♻️  {cache_ticker} 快取來源已過期（{stale_labels}），重新抓取核心分析資料..."
        )
    if cached and cached.get("data_schema_version") != DATA_SCHEMA_VERSION:
        print(f"  ♻️  {original_ticker} 快取資料口徑已更新，重新抓取財務數據...")

    print(f"  📊 正在獲取 {ticker} 財務數據...")
    
    try:
        provider = market_data_provider or get_market_data_provider(ticker)
        stock, info, is_valid, resolved_ticker, attempts = provider.resolve_stock(ticker)
        for index, attempt in enumerate(attempts[1:], start=1):
            previous = attempts[index - 1]
            if not previous.get("valid"):
                print(f"    ⚠️ {previous.get('ticker')} 查無資料，嘗試 {attempt.get('ticker')}...")
        if is_valid:
            ticker = resolved_ticker

        
        # === 基本資訊 ===
        raw_company_name = safe_get(info, "longName", safe_get(info, "shortName", ticker))
        company_identity = build_company_identity(ticker, info, raw_company_name)
        company_name = company_identity.get("display_name") or raw_company_name
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
        equity_multiplier = "N/A"
        equity_multiplier_note = ""
        dupont_identity_note = ""
        wacc_capital_structure_note = ""
        try:
            balance_latest = stock.balance_sheet
            if balance_latest is not None and not balance_latest.empty:
                ta_0 = balance_latest.loc["Total Assets"].iloc[0] if "Total Assets" in balance_latest.index else None
                eq_0 = balance_latest.loc["Stockholders Equity"].iloc[0] if "Stockholders Equity" in balance_latest.index else (
                    balance_latest.loc["Total Equity Gross Minority Interest"].iloc[0] if "Total Equity Gross Minority Interest" in balance_latest.index else None)
                if ta_0 and eq_0 and float(eq_0) > 0 and not pd.isna(ta_0) and not pd.isna(eq_0):
                    em = float(ta_0) / float(eq_0)
                    equity_multiplier = f"{em:.3f}x"
                    # Yahoo 的 ROA/ROE 多為 TTM/平均資產口徑，不能和最新一期資產負債表硬湊恒等式。
                    roa_raw = safe_get(info, "returnOnAssets", None)
                    if roa_raw and roa_raw != "N/A":
                        dupont_roe = float(roa_raw) * em * 100
                        equity_multiplier_note = (
                            f"(僅供口徑差異提示：Yahoo ROA {float(roa_raw)*100:.1f}% × 最新期 EM "
                            f"{em:.3f}x = {dupont_roe:.1f}%，不可解讀為嚴格杜邦恒等式)"
                        )

                    if revenue_history and net_income_history and total_assets_history and total_equity_history:
                        latest_rev = revenue_history[-1]
                        latest_ni = net_income_history[-1]
                        latest_assets = total_assets_history[-1]
                        latest_equity = total_equity_history[-1]
                        if latest_rev and latest_ni and latest_assets and latest_equity:
                            same_period_margin = latest_ni / latest_rev
                            same_period_turnover = latest_rev / latest_assets
                            same_period_em = latest_assets / latest_equity
                            same_period_roe = same_period_margin * same_period_turnover * same_period_em * 100
                            dupont_identity_note = (
                                f"同期間年度杜邦恒等式：淨利率 {same_period_margin*100:.1f}% × "
                                f"資產周轉率 {same_period_turnover:.3f}x × 權益乘數 {same_period_em:.3f}x "
                                f"= ROE {same_period_roe:.1f}%（等同淨利/股東權益）"
                            )
        except Exception:
            pass

        try:
            if isinstance(market_cap, (int, float)) and isinstance(total_debt, (int, float)):
                invested_capital = market_cap + total_debt
                if invested_capital > 0:
                    equity_weight = market_cap / invested_capital * 100
                    debt_weight = total_debt / invested_capital * 100
                    wacc_capital_structure_note = (
                        f"WACC 市值權重：股權 {equity_weight:.2f}% / 有息負債 {debt_weight:.2f}% "
                        f"（以市值 {format_number(market_cap, '億')} 與有息負債 {format_number(total_debt, '億')} 計算）"
                    )
        except Exception:
            pass
        
        # 計算收入 CAGR（5年）
        revenue_cagr = calculate_revenue_cagr(revenue_history)
        
        # === 近期股價歷史 ===
        price_history = extract_price_history(stock)
            
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
        institutional_trading = enrichment_bundle.get("institutional_trading", {})
        dynamic_peer_metrics = enrichment_bundle.get("dynamic_peer_metrics", [])
        peer_discovery_results = enrichment_bundle.get("peer_discovery_results", [])
        pe_river_chart = enrichment_bundle.get(
            "pe_river_chart",
            {"years": years, "eps_twd": [], "multiples": [10, 12, 15, 18], "bands": {}, "source": "unavailable"},
        )

        # === 欄位缺漏備援補值與財務一致性校準 ===
        quality_updates = apply_market_fallbacks_and_quality_calibration(locals())
        current_price = quality_updates["current_price"]
        market_cap = quality_updates["market_cap"]
        pe_ratio = quality_updates["pe_ratio"]
        week_52_high = quality_updates["week_52_high"]
        week_52_low = quality_updates["week_52_low"]
        revenue_ttm = quality_updates["revenue_ttm"]
        free_cash_flow = quality_updates["free_cash_flow"]
        profit_margin = quality_updates["profit_margin"]
        provider_profit_margin = quality_updates["provider_profit_margin"]
        net_income_ttm = quality_updates["net_income_ttm"]
        net_income_source = quality_updates["net_income_source"]
        yahoo_revenue_growth_raw = quality_updates["yahoo_revenue_growth_raw"]
        yahoo_earnings_growth_raw = quality_updates["yahoo_earnings_growth_raw"]
        latest_annual_revenue_growth = quality_updates["latest_annual_revenue_growth"]
        ttm_vs_latest_annual_revenue_change = quality_updates["ttm_vs_latest_annual_revenue_change"]
        latest_annual_net_income_growth = quality_updates["latest_annual_net_income_growth"]
        fmp_quote_audit = quality_updates["fmp_quote_audit"]
        
        # === 整合所有數據 ===
        data = build_legacy_payload(locals())
        
        data = finalize_and_cache_legacy_payload(
            data=data,
            ticker=ticker,
            original_cache_key=cache_key,
            provider=provider,
            fetch_started_epoch=fetch_started_epoch,
            skip_optional_http=skip_optional_http,
            enrichment_audit=enrichment_audit,
            fmp_quote_audit=fmp_quote_audit,
            monthly_revenue_audit=monthly_revenue_audit,
            finmind_financial_fallback_audit=finmind_financial_fallback_audit,
        )

        print(f"  ✅ {company_name} 數據獲取完成")
        return data
        
    except Exception as e:
        print(f"  ❌ 數據獲取失敗：{e}")
        failed = {
            "ticker": ticker,
            "company_name": ticker,
            "sector": "N/A",
            "industry": "N/A",
            "error": str(e),
            "fetch_date": datetime.now().strftime("%Y年%m月%d日"),
        }
        _append_source_fetch_audit(
            failed,
            "market_data",
            "market_data_provider",
            AUDIT_STATUS_ERROR,
            started_at_epoch=fetch_started_epoch,
            finished_at_epoch=time_module.time(),
            record_count=0,
            cache_hit=False,
            stale=True,
            error_kind=e.__class__.__name__,
            message=str(e)[:240],
        )
        failed["data_trust"] = build_data_trust(failed)
        return failed


async def async_fetch_stock_data(ticker: str) -> dict:
    """Fetch stock data with blocking SDK work offloaded and HTTP enrichment concurrent."""
    ticker = ticker.strip().upper()
    data = await asyncio.to_thread(fetch_stock_data, ticker, True)
    return await enrich_optional_http_async(ticker, data)
