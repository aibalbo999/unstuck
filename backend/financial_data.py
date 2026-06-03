# ============================================================
# financial_data.py - 從 yfinance 獲取完整財務數據
# ============================================================

import asyncio
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import warnings
from cache_store import get_cache_json, set_cache_json
from config import FINANCIAL_DATA_CACHE_SECONDS
from market_data_fetchers import (
    DataLoader,
    _align_finmind_history,
    _dedupe_records,
    _history_has_values,
    _run_named_fetches,
    build_company_identity,
    build_pe_river_chart_data,
    fetch_dynamic_peer_metrics,
    fetch_finmind_financial_statement_fallback,
    fetch_fmp_news_catalysts_async,
    fetch_fmp_quote_fallback,
    fetch_google_peer_discovery_results,
    fetch_google_peer_discovery_results_async,
    fetch_google_search_catalysts_async,
    fetch_institutional_trading_trend,
    fetch_recent_catalysts,
    first_number,
    is_missing_value,
    is_taiwan_ticker,
    safe_get,
)
from prompt_builder import format_data_for_prompt
warnings.filterwarnings("ignore")

DATA_SCHEMA_VERSION = 4


def format_number(num, unit="億", decimals=2):
    """格式化數字顯示"""
    try:
        if num == "N/A" or num is None:
            return "N/A"
        num = float(num)
        if unit == "億":
            val_yi = num / 1e8
            val_b = num / 1e9
            return f"NT${val_yi:.{decimals}f}億 ({val_b:.{decimals}f}B)"
        elif unit == "兆":
            val_zhao = num / 1e12
            val_b = num / 1e9
            return f"NT${val_zhao:.{decimals}f}兆 ({val_b:.{decimals}f}B)"
        elif unit == "%":
            return f"{num:.{decimals}f}%"
        else:
            return f"{num:.{decimals}f}"
    except Exception:
        return "N/A"


def format_pct(val):
    """格式化百分比"""
    try:
        if val == "N/A" or val is None:
            return "N/A"
        return f"{float(val)*100:.1f}%"
    except Exception:
        return "N/A"


def fetch_stock_data(ticker: str, skip_optional_http: bool = False) -> dict:
    """
    從 yfinance 獲取股票完整財務數據
    返回格式化的數據字典
    """
    ticker = ticker.strip().upper()
    original_ticker = ticker
    cache_key = f"financial_data:{original_ticker}"
    cached = get_cache_json(cache_key)
    if cached and cached.get("data_schema_version") == DATA_SCHEMA_VERSION:
        cached["_cache_hit"] = True
        print(f"  ✅ 使用快取的 {cached.get('ticker', original_ticker)} 財務數據")
        return cached
    if cached:
        print(f"  ♻️  {original_ticker} 快取資料口徑已更新，重新抓取財務數據...")

    print(f"  📊 正在獲取 {ticker} 財務數據...")
    
    try:
        def get_valid_info(t):
            st = yf.Ticker(t)
            inf = st.info
            valid = "currentPrice" in inf or "regularMarketPrice" in inf or "previousClose" in inf
            return st, inf, valid
            
        stock, info, is_valid = get_valid_info(ticker)
        
        # 台灣股票自動切換 TW/TWO 邏輯
        if not is_valid:
            alt_ticker = None
            if ticker.endswith(".TW"):
                alt_ticker = ticker.replace(".TW", ".TWO")
            elif ticker.endswith(".TWO"):
                alt_ticker = ticker.replace(".TWO", ".TW")
            elif ticker.isdigit() and len(ticker) == 4:
                alt_ticker = f"{ticker}.TW"
                
            if alt_ticker:
                print(f"    ⚠️ {ticker} 查無資料，嘗試 {alt_ticker}...")
                alt_stock, alt_info, alt_valid = get_valid_info(alt_ticker)
                if alt_valid:
                    ticker = alt_ticker
                    stock = alt_stock
                    info = alt_info
                elif ticker.isdigit() and len(ticker) == 4:
                    alt_ticker2 = f"{ticker}.TWO"
                    print(f"    ⚠️ {alt_ticker} 查無資料，嘗試 {alt_ticker2}...")
                    alt_stock2, alt_info2, alt_valid2 = get_valid_info(alt_ticker2)
                    if alt_valid2:
                        ticker = alt_ticker2
                        stock = alt_stock2
                        info = alt_info2

        
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
        
        # === 歷史財務報表（5年）===
        revenue_history = []
        net_income_history = []
        gross_profit_history = []
        operating_income_history = []
        fcf_history = []
        total_assets_history = []
        total_equity_history = []
        years = []
        
        try:
            financials = stock.financials  # 年度損益表
            if financials is not None and not financials.empty:
                for col in financials.columns[:5]:  # 最近5年
                    year = col.year if hasattr(col, 'year') else str(col)[:4]
                    years.append(str(year))
                    
                    rev = financials.loc["Total Revenue", col] if "Total Revenue" in financials.index else None
                    ni = financials.loc["Net Income", col] if "Net Income" in financials.index else None
                    gp = financials.loc["Gross Profit", col] if "Gross Profit" in financials.index else None
                    oi = financials.loc["Operating Income", col] if "Operating Income" in financials.index else None
                    
                    # 改為 1e9 (Billion TWD) 作為底層單位，防止 LLM 在中英文間產生幻覺
                    revenue_history.append(round(float(rev)/1e9, 2) if rev and not pd.isna(rev) else None)
                    net_income_history.append(round(float(ni)/1e9, 2) if ni and not pd.isna(ni) else None)
                    gross_profit_history.append(round(float(gp)/1e9, 2) if gp and not pd.isna(gp) else None)
                    operating_income_history.append(round(float(oi)/1e9, 2) if oi and not pd.isna(oi) else None)
                
                years = list(reversed(years))
                revenue_history = list(reversed(revenue_history))
                net_income_history = list(reversed(net_income_history))
                gross_profit_history = list(reversed(gross_profit_history))
                operating_income_history = list(reversed(operating_income_history))
        except Exception as e:
            print(f"    ⚠️  財務報表獲取失敗：{e}")
        
        # === 現金流歷史 ===
        # 建立以年份為 key 的 FCF 映射，確保與 years 長度對齊
        try:
            cashflow = stock.cashflow
            if cashflow is not None and not cashflow.empty:
                fcf_by_year = {}
                for col in cashflow.columns:
                    yr_key = str(col.year if hasattr(col, 'year') else str(col)[:4])
                    ocf = cashflow.loc["Operating Cash Flow", col] if "Operating Cash Flow" in cashflow.index else None
                    capex_val = cashflow.loc["Capital Expenditure", col] if "Capital Expenditure" in cashflow.index else None
                    
                    ocf_val = float(ocf)/1e9 if ocf is not None and not pd.isna(ocf) else None
                    capex_val_f = float(capex_val)/1e9 if capex_val is not None and not pd.isna(capex_val) else 0
                    
                    if ocf_val is not None:
                        fcf_by_year[yr_key] = round(ocf_val + capex_val_f, 2)
                    else:
                        fcf_by_year[yr_key] = None
                
                # 按 years 順序對齊
                fcf_history = [fcf_by_year.get(y, None) for y in years]
        except Exception as e:
            print(f"    ⚠️  現金流數據獲取失敗：{e}")
        
        # === 資產負債歷史 ===
        try:
            balance = stock.balance_sheet
            if balance is not None and not balance.empty:
                equity_raw = []
                assets_raw = []
                for col in balance.columns[:5]:
                    eq = balance.loc["Stockholders Equity", col] if "Stockholders Equity" in balance.index else (
                         balance.loc["Total Equity Gross Minority Interest", col] if "Total Equity Gross Minority Interest" in balance.index else None)
                    ta = balance.loc["Total Assets", col] if "Total Assets" in balance.index else None
                    
                    equity_raw.append(round(float(eq)/1e9, 2) if eq and not pd.isna(eq) else None)
                    assets_raw.append(round(float(ta)/1e9, 2) if ta and not pd.isna(ta) else None)
                
                total_equity_history = list(reversed(equity_raw))
                total_assets_history = list(reversed(assets_raw))
        except Exception as e:
            print(f"    ⚠️  資產負債表獲取失敗：{e}")

        # === FinMind 台股財報備援 ===
        if is_taiwan_ticker(ticker) and DataLoader is not None:
            needs_finmind_fallback = (
                not _history_has_values(revenue_history)
                or not _history_has_values(net_income_history)
                or not _history_has_values(total_assets_history)
                or not _history_has_values(total_equity_history)
                or not _history_has_values(fcf_history)
            )
            if needs_finmind_fallback:
                try:
                    finmind_fallback = fetch_finmind_financial_statement_fallback(ticker)
                except Exception as e:
                    print(f"    ⚠️  FinMind 財報備援資料獲取失敗：{e}")
                    finmind_fallback = {}

                if finmind_fallback:
                    fallback_years = finmind_fallback.get("years", []) or []
                    rows_by_year = finmind_fallback.get("rows_by_year", {}) or {}
                    if not years or not _history_has_values(revenue_history) or not _history_has_values(net_income_history):
                        years = fallback_years

                    if not _history_has_values(revenue_history):
                        revenue_history = _align_finmind_history(years, rows_by_year, "revenue")
                    if not _history_has_values(net_income_history):
                        net_income_history = _align_finmind_history(years, rows_by_year, "net_income")
                    if not _history_has_values(gross_profit_history):
                        gross_profit_history = _align_finmind_history(years, rows_by_year, "gross_profit")
                    if not _history_has_values(operating_income_history):
                        operating_income_history = _align_finmind_history(years, rows_by_year, "operating_income")
                    if not _history_has_values(fcf_history):
                        fcf_history = _align_finmind_history(years, rows_by_year, "free_cash_flow")
                    if not _history_has_values(total_assets_history):
                        total_assets_history = _align_finmind_history(years, rows_by_year, "total_assets")
                    if not _history_has_values(total_equity_history):
                        total_equity_history = _align_finmind_history(years, rows_by_year, "total_equity")

                    data_source_notes.append(
                        "yfinance 年度財報/資產負債/現金流資料缺漏時，已使用 FinMind 台股財報 API 補齊可用年度欄位。"
                    )
        
        # === 計算衍生指標 ===
        # 計算毛利率歷史
        gross_margin_history = []
        for i in range(len(revenue_history)):
            if (revenue_history[i] and gross_profit_history and 
                i < len(gross_profit_history) and gross_profit_history[i]):
                gm = (gross_profit_history[i] / revenue_history[i]) * 100
                gross_margin_history.append(round(gm, 1))
            else:
                gross_margin_history.append(None)
        
        # 計算營業利潤率歷史
        op_margin_history = []
        for i in range(len(revenue_history)):
            if (revenue_history[i] and operating_income_history and
                i < len(operating_income_history) and operating_income_history[i]):
                om = (operating_income_history[i] / revenue_history[i]) * 100
                op_margin_history.append(round(om, 1))
            else:
                op_margin_history.append(None)
        
        # 計算淨利率歷史
        net_margin_history = []
        for i in range(len(revenue_history)):
            if (revenue_history[i] and net_income_history and
                i < len(net_income_history) and net_income_history[i]):
                nm = (net_income_history[i] / revenue_history[i]) * 100
                net_margin_history.append(round(nm, 1))
            else:
                net_margin_history.append(None)
        
        # 計算 ROE 歷史
        roe_history = []
        for i in range(len(net_income_history)):
            if (net_income_history[i] and total_equity_history and
                i < len(total_equity_history) and total_equity_history[i] and total_equity_history[i] > 0):
                roe_val = (net_income_history[i] / total_equity_history[i]) * 100
                roe_history.append(round(roe_val, 1))
            else:
                roe_history.append(None)
        
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
        revenue_cagr = "N/A"
        if len(revenue_history) >= 2 and revenue_history[0] and revenue_history[-1] and revenue_history[0] > 0:
            n = len(revenue_history) - 1
            cagr = ((revenue_history[-1] / revenue_history[0]) ** (1/n) - 1) * 100
            revenue_cagr = f"{cagr:.1f}%"
        
        # === 近期股價歷史 ===
        price_history = {}
        try:
            hist = stock.history(period="1y")
            if not hist.empty:
                # 取每月最後一個實際交易日，避免未完成月份被標成未來月末日期。
                monthly = hist.groupby(pd.Grouper(freq='ME')).tail(1)
                today = datetime.now().date()
                monthly = monthly[[d.date() <= today for d in monthly.index]]
                price_history = {
                    "dates": [str(d.date()) for d in monthly.index[-12:]],
                    "prices": [round(p, 2) for p in monthly["Close"].tolist()[-12:]]
                }
        except Exception:
            pass
            
        # === FinMind 補充台股每月營收 ===
        recent_monthly_revenue = []
        if (ticker.endswith(".TW") or ticker.endswith(".TWO")) and DataLoader is not None:
            try:
                fm_dl = DataLoader()
                fm_stock_id = ticker.replace(".TW", "").replace(".TWO", "")
                # 抓取過去 8 個月，確保至少有 6 個月的資料
                start_date = (datetime.now() - timedelta(days=240)).strftime("%Y-%m-%d")
                df_rev = fm_dl.taiwan_stock_month_revenue(stock_id=fm_stock_id, start_date=start_date)
                
                if not df_rev.empty:
                    # 取最近 6 個月
                    recent_df = df_rev.tail(6)
                    for _, row in recent_df.iterrows():
                        rm_year = row.get("revenue_year")
                        rm_month = row.get("revenue_month")
                        rm_val = row.get("revenue")
                        if rm_year and rm_month and rm_val:
                            # FinMind 營收單位為元，轉為億
                            val_yi = float(rm_val) / 1e8
                            recent_monthly_revenue.append(f"{rm_year}年{rm_month}月: NT${val_yi:.2f}億")
            except Exception as e:
                print(f"    ⚠️  FinMind 營收獲取失敗：{e}")

        # === 即時/質性資料擴充 ===
        enrichment = _run_named_fetches(
            {
                "recent_catalysts": (
                    fetch_recent_catalysts,
                    (ticker, company_name, company_identity, stock, skip_optional_http),
                    [],
                    "新聞催化劑資料彙整失敗",
                ),
                "institutional_trading": (
                    fetch_institutional_trading_trend,
                    (ticker,),
                    {},
                    "法人籌碼資料彙整失敗",
                ),
                "dynamic_peer_metrics": (
                    fetch_dynamic_peer_metrics,
                    (ticker, company_name, sector, industry, company_identity),
                    [],
                    "動態同業資料彙整失敗",
                ),
                "peer_discovery_results": (
                    (lambda *_args: []) if skip_optional_http else fetch_google_peer_discovery_results,
                    (ticker, company_name, sector, industry),
                    [],
                    "同業 discovery 資料彙整失敗",
                ),
                "pe_river_chart": (
                    build_pe_river_chart_data,
                    (ticker, years, net_income_history, shares_outstanding),
                    {"years": years, "eps_twd": [], "multiples": [10, 12, 15, 18], "bands": {}, "source": "unavailable"},
                    "P/E 河流圖資料彙整失敗",
                ),
            },
            max_workers=5,
        )
        recent_catalysts = enrichment.get("recent_catalysts", [])
        institutional_trading = enrichment.get("institutional_trading", {})
        dynamic_peer_metrics = enrichment.get("dynamic_peer_metrics", [])
        peer_discovery_results = enrichment.get("peer_discovery_results", [])
        pe_river_chart = enrichment.get(
            "pe_river_chart",
            {"years": years, "eps_twd": [], "multiples": [10, 12, 15, 18], "bands": {}, "source": "unavailable"},
        )

        # === 欄位缺漏備援補值 ===
        fmp_quote = {}
        if any(is_missing_value(v) for v in [current_price, market_cap, pe_ratio, week_52_high, week_52_low]):
            fmp_quote = fetch_fmp_quote_fallback(ticker)
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

        # === 財務一致性校準 ===
        # yfinance 的 info 欄位可能混用 TTM、季度年化與市場估值口徑。
        # 若 profitMargins/netIncomeToCommon 與 trailing EPS/P/E 推回的淨利互斥，
        # 報告端優先採用可與 P/E、市值、EPS 自洽的淨利與淨利率。
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

        net_income_from_eps = None
        if _is_number(shares_outstanding) and _is_number(trailing_eps):
            net_income_from_eps = float(shares_outstanding) * float(trailing_eps)

        net_income_from_pe = None
        if _is_number(market_cap) and _is_number(pe_ratio) and float(pe_ratio) > 0:
            net_income_from_pe = float(market_cap) / float(pe_ratio)

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
            margin_gap = None
            if _is_number(provider_profit_margin):
                margin_gap = abs(float(provider_profit_margin) - derived_profit_margin)
            if margin_gap is not None and margin_gap > 0.05:
                data_quality_notes.append(
                    "TTM 淨利率已由校準淨利 ÷ TTM 營收重算，避免與 P/E、市值、EPS 互相矛盾。"
                )
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
        
        # === 整合所有數據 ===
        data = {
            "data_schema_version": DATA_SCHEMA_VERSION,
            # 基本資訊
            "ticker": ticker,
            "company_name": company_name,
            "raw_company_name": raw_company_name,
            "company_identity": company_identity,
            "sector": sector,
            "industry": industry,
            "country": country,
            "employees": employees,
            "fetch_date": datetime.now().strftime("%Y年%m月%d日"),
            
            # 市場數據（原始）
            "current_price": current_price,
            "market_cap_raw": market_cap,
            "week_52_high": week_52_high,
            "week_52_low": week_52_low,
            
            # 市場數據（格式化）
            "current_price_fmt": f"NT${current_price:.2f}" if isinstance(current_price, (int, float)) else "N/A",
            "market_cap_fmt": format_number(market_cap, "億"),
            "week_52_high_fmt": f"NT${week_52_high:.2f}" if isinstance(week_52_high, (int, float)) else "N/A",
            "week_52_low_fmt": f"NT${week_52_low:.2f}" if isinstance(week_52_low, (int, float)) else "N/A",
            
            # 估值指標（格式化）
            "pe_ratio": f"{pe_ratio:.1f}x" if isinstance(pe_ratio, (int, float)) else "N/A",
            "forward_pe": f"{forward_pe:.1f}x" if isinstance(forward_pe, (int, float)) else "N/A",
            "pb_ratio": f"{pb_ratio:.2f}x" if isinstance(pb_ratio, (int, float)) else "N/A",
            "ps_ratio": f"{ps_ratio:.2f}x" if isinstance(ps_ratio, (int, float)) else "N/A",
            "ev_ebitda": f"{ev_ebitda:.1f}x" if isinstance(ev_ebitda, (int, float)) else "N/A",
            "shares_outstanding": format_number(shares_outstanding, "億"),
            "shares_raw": shares_outstanding,
            "forward_eps": forward_eps,
            "trailing_eps": trailing_eps,
            "forward_pe_raw": forward_pe,
            "pe_ratio_raw": pe_ratio,
            
            # 財務指標（格式化）
            "revenue_ttm": format_number(revenue_ttm, "億"),
            "revenue_ttm_raw": revenue_ttm,
            "gross_margin": format_pct(gross_margin),
            "gross_margin_raw": gross_margin,
            "operating_margin": format_pct(operating_margin),
            "operating_margin_raw": operating_margin,
            "profit_margin": format_pct(profit_margin),
            "profit_margin_raw": profit_margin,
            "profit_margin_provider": format_pct(provider_profit_margin),
            "profit_margin_provider_raw": provider_profit_margin,
            "net_income_ttm": format_number(net_income_ttm, "億"),
            "net_income_ttm_raw": net_income_ttm,
            "net_income_ttm_source": net_income_source,
            "ebitda_fmt": format_number(ebitda, "億"),
            "ebitda_raw": ebitda,
            
            # 現金流（格式化）
            "free_cash_flow": format_number(free_cash_flow, "億"),
            "free_cash_flow_raw": free_cash_flow,
            "operating_cash_flow": format_number(operating_cash_flow, "億"),
            "operating_cash_flow_raw": operating_cash_flow,
            
            # 資產負債（格式化）
            "total_debt": format_number(total_debt, "億"),
            "total_debt_raw": total_debt,
            "total_cash": format_number(total_cash, "億"),
            "total_cash_raw": total_cash,
            "debt_to_equity": f"{debt_to_equity:.2f}%" if isinstance(debt_to_equity, (int, float)) else "N/A",
            "current_ratio": f"{current_ratio:.2f}" if isinstance(current_ratio, (int, float)) else "N/A",
            
            # 股東回報（格式化）
            "roe": format_pct(roe),
            "roa": format_pct(roa),
            "dividend_yield": f"{float(dividend_yield):.2f}%" if isinstance(dividend_yield, (int, float)) else "N/A",
            "dividend_yield_raw": dividend_yield,
            "dividend_rate": f"NT${dividend_rate:.2f}" if isinstance(dividend_rate, (int, float)) else "N/A",
            "dividend_rate_raw": dividend_rate,
            "payout_ratio": format_pct(payout_ratio),
            "payout_ratio_raw": payout_ratio,
            
            # 成長率（格式化）
            "revenue_growth": f"{latest_annual_revenue_growth:.1f}%（最新年度 YoY）" if latest_annual_revenue_growth is not None else "N/A",
            "earnings_growth": f"{latest_annual_net_income_growth:.1f}%（最新年度 YoY）" if latest_annual_net_income_growth is not None else "N/A",
            "latest_annual_revenue_growth": f"{latest_annual_revenue_growth:.1f}%" if latest_annual_revenue_growth is not None else "N/A",
            "ttm_vs_latest_annual_revenue_change": f"{ttm_vs_latest_annual_revenue_change:.1f}%" if ttm_vs_latest_annual_revenue_change is not None else "N/A",
            "latest_annual_net_income_growth": f"{latest_annual_net_income_growth:.1f}%" if latest_annual_net_income_growth is not None else "N/A",
            "yahoo_revenue_growth": format_pct(yahoo_revenue_growth_raw),
            "yahoo_earnings_growth": format_pct(yahoo_earnings_growth_raw),
            "revenue_cagr_5yr": revenue_cagr,
            
            # 分析師評級
            "beta": f"{beta:.2f}" if isinstance(beta, (int, float)) else "N/A",
            "analyst_target": f"NT${analyst_target:.2f}" if isinstance(analyst_target, (int, float)) else "N/A",
            "analyst_rec": analyst_rec,
            "analyst_count": str(analyst_count),
            
            # 歷史數據（圖表用）
            "years": years,
            "revenue_history": revenue_history,
            "net_income_history": net_income_history,
            "gross_profit_history": gross_profit_history,
            "operating_income_history": operating_income_history,
            "fcf_history": fcf_history,
            "gross_margin_history": gross_margin_history,
            "op_margin_history": op_margin_history,
            "net_margin_history": net_margin_history,
            "roe_history": roe_history,
            "total_equity_history": total_equity_history,
            "total_assets_history": total_assets_history,
            "price_history": price_history,
            "recent_monthly_revenue": recent_monthly_revenue,
            "recent_catalysts": recent_catalysts,
            "institutional_trading": institutional_trading,
            "dynamic_peer_metrics": dynamic_peer_metrics,
            "peer_discovery_results": peer_discovery_results,
            "pe_river_chart": pe_river_chart,
            "data_source_notes": data_source_notes,
            "equity_multiplier": equity_multiplier,
            "equity_multiplier_note": equity_multiplier_note,
            "dupont_identity_note": dupont_identity_note,
            "wacc_capital_structure_note": wacc_capital_structure_note,
        }
        
        data["cache_generated_at"] = datetime.now().isoformat(timespec="seconds")
        set_cache_json(cache_key, data, FINANCIAL_DATA_CACHE_SECONDS)
        resolved_cache_key = f"financial_data:{ticker}"
        if resolved_cache_key != cache_key:
            set_cache_json(resolved_cache_key, data, FINANCIAL_DATA_CACHE_SECONDS)

        print(f"  ✅ {company_name} 數據獲取完成")
        return data
        
    except Exception as e:
        print(f"  ❌ 數據獲取失敗：{e}")
        return {
            "ticker": ticker,
            "company_name": ticker,
            "sector": "N/A",
            "industry": "N/A",
            "error": str(e),
            "fetch_date": datetime.now().strftime("%Y年%m月%d日"),
        }


def _cache_financial_data(data: dict, original_ticker: str):
    if not data or "error" in data:
        return

    cacheable = dict(data)
    cacheable.pop("_cache_hit", None)
    resolved_ticker = cacheable.get("ticker", original_ticker)
    set_cache_json(f"financial_data:{original_ticker}", cacheable, FINANCIAL_DATA_CACHE_SECONDS)
    if resolved_ticker != original_ticker:
        set_cache_json(f"financial_data:{resolved_ticker}", cacheable, FINANCIAL_DATA_CACHE_SECONDS)


def _merge_optional_http_bundle(data: dict, http_bundle: dict) -> dict:
    """Merge async HTTP-backed enrichment into a base yfinance/FinMind payload."""
    if not data or "error" in data or not http_bundle:
        return data

    combined_catalysts = list(data.get("recent_catalysts", []) or [])
    combined_catalysts.extend(http_bundle.get("google_catalysts", []) or [])
    combined_catalysts.extend(http_bundle.get("fmp_news", []) or [])
    if combined_catalysts:
        data["recent_catalysts"] = _dedupe_records(combined_catalysts, limit=5)[:5]

    peer_discovery = http_bundle.get("google_peer_discovery", []) or []
    if peer_discovery:
        data["peer_discovery_results"] = _dedupe_records(peer_discovery, limit=5)

    fmp_quote = http_bundle.get("fmp_quote", {}) or {}
    if isinstance(fmp_quote, dict) and fmp_quote:
        updated_fields = []
        if is_missing_value(data.get("current_price")):
            current_price = first_number(fmp_quote.get("price"), fmp_quote.get("previousClose"))
            if current_price is not None:
                data["current_price"] = current_price
                data["current_price_fmt"] = f"NT${current_price:.2f}"
                updated_fields.append("current_price")
        if is_missing_value(data.get("market_cap_raw")):
            market_cap = first_number(fmp_quote.get("marketCap"))
            if market_cap is not None:
                data["market_cap_raw"] = market_cap
                data["market_cap_fmt"] = format_number(market_cap, "億")
                updated_fields.append("market_cap")
        if is_missing_value(data.get("pe_ratio_raw")):
            pe_ratio = first_number(fmp_quote.get("pe"), fmp_quote.get("peRatio"))
            if pe_ratio is not None:
                data["pe_ratio_raw"] = pe_ratio
                data["pe_ratio"] = f"{pe_ratio:.1f}x"
                updated_fields.append("pe_ratio")
        if is_missing_value(data.get("week_52_high")):
            week_52_high = first_number(fmp_quote.get("yearHigh"), fmp_quote.get("priceAvg200"))
            if week_52_high is not None:
                data["week_52_high"] = week_52_high
                data["week_52_high_fmt"] = f"NT${week_52_high:.2f}"
                updated_fields.append("week_52_high")
        if is_missing_value(data.get("week_52_low")):
            week_52_low = first_number(fmp_quote.get("yearLow"))
            if week_52_low is not None:
                data["week_52_low"] = week_52_low
                data["week_52_low_fmt"] = f"NT${week_52_low:.2f}"
                updated_fields.append("week_52_low")

        if updated_fields:
            data.setdefault("data_source_notes", []).append(
                "部分市場欄位由 async FMP quote bundle 補值：" + ", ".join(updated_fields)
            )

    return data


async def async_fetch_stock_data(ticker: str) -> dict:
    """Fetch stock data with blocking SDK work offloaded and HTTP enrichment concurrent."""
    ticker = ticker.strip().upper()
    fmp_news_task = asyncio.create_task(fetch_fmp_news_catalysts_async(ticker))

    try:
        data = await asyncio.to_thread(fetch_stock_data, ticker, True)
    except Exception:
        await asyncio.gather(fmp_news_task, return_exceptions=True)
        raise

    if not data or "error" in data:
        await asyncio.gather(fmp_news_task, return_exceptions=True)
        return data

    resolved_ticker = str(data.get("ticker") or ticker).strip().upper()
    company_name = str(data.get("company_name") or resolved_ticker).strip()
    identity = data.get("company_identity") if isinstance(data.get("company_identity"), dict) else {}
    sector = str(data.get("sector") or "")
    industry = str(data.get("industry") or "")

    google_catalysts, peer_discovery, fmp_news = await asyncio.gather(
        fetch_google_search_catalysts_async(resolved_ticker, company_name, identity),
        fetch_google_peer_discovery_results_async(resolved_ticker, company_name, sector, industry),
        fmp_news_task,
        return_exceptions=True,
    )
    fmp_news_records = fmp_news if isinstance(fmp_news, list) else []
    if resolved_ticker != ticker and not fmp_news_records:
        try:
            retry_fmp_news = await fetch_fmp_news_catalysts_async(resolved_ticker)
        except Exception:
            retry_fmp_news = []
        fmp_news_records = retry_fmp_news if isinstance(retry_fmp_news, list) else []

    http_bundle = {
        "google_catalysts": google_catalysts if isinstance(google_catalysts, list) else [],
        "google_peer_discovery": peer_discovery if isinstance(peer_discovery, list) else [],
        "fmp_news": fmp_news_records,
    }
    data = _merge_optional_http_bundle(data, http_bundle)
    _cache_financial_data(data, ticker)
    return data
