# ============================================================
# financial_data.py - 從 yfinance 獲取完整財務數據
# ============================================================

import asyncio
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
from functools import lru_cache
import warnings
from cache_store import get_cache_json, set_cache_json
from config import FINANCIAL_DATA_CACHE_SECONDS, FMP_API_KEY, FMP_BASE_URL
warnings.filterwarnings("ignore")

try:
    from FinMind.data import DataLoader
except ImportError:
    DataLoader = None


TAIWAN_BROAD_INDUSTRY_CATEGORIES = {
    "上市股票",
    "上櫃股票",
    "興櫃股票",
    "電子工業",
    "金融保險業",
}

TAIWAN_IDENTITY_OVERRIDES = {
    "1623": {
        "official_name": "大東電",
        "legal_name": "大東電業廠股份有限公司",
        "forbidden_aliases": ["大亞", "大亞電線電纜", "TA YA", "Ta Ya Electric"],
    },
    "1609": {
        "official_name": "大亞",
        "legal_name": "大亞電線電纜股份有限公司",
        "forbidden_aliases": ["大東電", "大東電業", "TA TUN", "Ta Tun Electric"],
    },
    "6806": {
        "official_name": "森崴能源",
        "legal_name": "森崴能源股份有限公司",
        "aliases": ["森崴能"],
        "forbidden_aliases": [],
    },
}


@lru_cache(maxsize=1)
def load_taiwan_stock_info_records() -> list[dict]:
    """讀取台股官方代號/中文簡稱，用於防止同業名稱被套到錯誤代號。"""
    if DataLoader is None:
        return []
    try:
        df = DataLoader().taiwan_stock_info()
        records = []
        for _, row in df.iterrows():
            stock_id = str(row.get("stock_id", "")).strip()
            stock_name = str(row.get("stock_name", "")).strip()
            industry_category = str(row.get("industry_category", "")).strip()
            if stock_id and stock_name:
                records.append({
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "industry_category": industry_category,
                    "type": str(row.get("type", "")).strip(),
                })
        return records
    except Exception as e:
        print(f"    ⚠️  台股公司身分資料獲取失敗：{e}")
        return []


def unique_nonempty(values) -> list[str]:
    """保留順序的去重工具。"""
    result = []
    seen = set()
    for value in values:
        if value is None:
            continue
        value = str(value).strip()
        if not value or value == "N/A" or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def build_company_identity(ticker: str, info: dict, company_name: str) -> dict:
    """建立可放進 prompt 與輸出驗證的公司身分錨點。"""
    stock_id = ticker.replace(".TW", "").replace(".TWO", "")
    is_taiwan_stock = ticker.endswith(".TW") or ticker.endswith(".TWO") or (stock_id.isdigit() and len(stock_id) == 4)
    override = TAIWAN_IDENTITY_OVERRIDES.get(stock_id, {})

    official_name = override.get("official_name")
    legal_name = override.get("legal_name")
    industry_categories = []
    same_industry_peers = []

    if is_taiwan_stock:
        records = load_taiwan_stock_info_records()
        current_rows = [r for r in records if r["stock_id"] == stock_id]
        if current_rows:
            official_name = official_name or current_rows[0]["stock_name"]
            industry_categories = unique_nonempty(r["industry_category"] for r in current_rows)

            narrow_categories = [
                cat for cat in industry_categories
                if cat and cat not in TAIWAN_BROAD_INDUSTRY_CATEGORIES
            ]
            peer_categories = narrow_categories or industry_categories[:1]
            peer_seen = set()
            for row in records:
                if row["stock_id"] == stock_id:
                    continue
                if row["industry_category"] not in peer_categories:
                    continue
                peer_key = (row["stock_id"], row["stock_name"])
                if peer_key in peer_seen:
                    continue
                same_industry_peers.append({
                    "stock_id": row["stock_id"],
                    "stock_name": row["stock_name"],
                })
                peer_seen.add(peer_key)

    english_names = unique_nonempty([
        safe_get(info, "longName", None),
        safe_get(info, "shortName", None),
        company_name,
    ])

    display_name = company_name
    if official_name:
        english_display = next((name for name in english_names if official_name not in name), "")
        display_name = f"{official_name} / {english_display}" if english_display else official_name

    allowed_aliases = unique_nonempty([
        official_name,
        legal_name,
        *override.get("aliases", []),
        display_name,
        company_name,
        ticker,
        stock_id,
        *english_names,
    ])

    return {
        "ticker": ticker,
        "stock_id": stock_id,
        "official_name": official_name,
        "legal_name": legal_name,
        "display_name": display_name,
        "english_names": english_names,
        "allowed_aliases": allowed_aliases,
        "forbidden_aliases": unique_nonempty(override.get("forbidden_aliases", [])),
        "industry_categories": industry_categories,
        "same_industry_peers": same_industry_peers,
    }


def safe_get(obj, key, default="N/A"):
    """安全取得字典值"""
    try:
        val = obj.get(key, default)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return val
    except Exception:
        return default


def is_missing_value(value) -> bool:
    if value is None or value == "N/A":
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def first_number(*values):
    for value in values:
        if is_missing_value(value):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def fetch_fmp_quote_fallback(ticker: str) -> dict:
    """Fetch optional FMP quote data when yfinance misses key market fields."""
    if not FMP_API_KEY:
        return {}

    symbol = ticker.strip().upper()
    url = f"{FMP_BASE_URL}/quote"
    try:
        response = requests.get(url, params={"symbol": symbol, "apikey": FMP_API_KEY}, timeout=8)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload:
            return payload[0] if isinstance(payload[0], dict) else {}
        if isinstance(payload, dict):
            return payload
    except Exception as e:
        print(f"    ⚠️  FMP 備援資料獲取失敗：{e}")
    return {}


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


def fetch_stock_data(ticker: str) -> dict:
    """
    從 yfinance 獲取股票完整財務數據
    返回格式化的數據字典
    """
    ticker = ticker.strip().upper()
    original_ticker = ticker
    cache_key = f"financial_data:{original_ticker}"
    cached = get_cache_json(cache_key)
    if cached:
        cached["_cache_hit"] = True
        print(f"  ✅ 使用快取的 {cached.get('ticker', original_ticker)} 財務數據")
        return cached

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

        # === 欄位缺漏備援補值 ===
        data_source_notes = []
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
        
        # === 整合所有數據 ===
        data = {
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
            
            # 財務指標（格式化）
            "revenue_ttm": format_number(revenue_ttm, "億"),
            "revenue_ttm_raw": revenue_ttm,
            "gross_margin": format_pct(gross_margin),
            "operating_margin": format_pct(operating_margin),
            "profit_margin": format_pct(profit_margin),
            "profit_margin_raw": profit_margin,
            "ebitda_fmt": format_number(ebitda, "億"),
            
            # 現金流（格式化）
            "free_cash_flow": format_number(free_cash_flow, "億"),
            "free_cash_flow_raw": free_cash_flow,
            "operating_cash_flow": format_number(operating_cash_flow, "億"),
            "operating_cash_flow_raw": operating_cash_flow,
            
            # 資產負債（格式化）
            "total_debt": format_number(total_debt, "億"),
            "total_cash": format_number(total_cash, "億"),
            "debt_to_equity": f"{debt_to_equity:.2f}%" if isinstance(debt_to_equity, (int, float)) else "N/A",
            "current_ratio": f"{current_ratio:.2f}" if isinstance(current_ratio, (int, float)) else "N/A",
            
            # 股東回報（格式化）
            "roe": format_pct(roe),
            "roa": format_pct(roa),
            "dividend_yield": f"{float(dividend_yield):.2f}%" if isinstance(dividend_yield, (int, float)) else "N/A",
            "dividend_rate": f"NT${dividend_rate:.2f}" if isinstance(dividend_rate, (int, float)) else "N/A",
            "payout_ratio": format_pct(payout_ratio),
            
            # 成長率（格式化）
            "revenue_growth": format_pct(revenue_growth),
            "earnings_growth": format_pct(earnings_growth),
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


async def async_fetch_stock_data(ticker: str) -> dict:
    """非同步包裝既有 yfinance/FinMind 抓取流程，避免阻塞 async worker event loop。"""
    return await asyncio.to_thread(fetch_stock_data, ticker)


def format_data_for_prompt(data: dict) -> str:
    """將財務數據格式化為 Agent 可讀的文字"""
    # 計算隱含預估淨利
    implied_forward_ni_fmt = "N/A"
    implied_forward_revenue_fmt = "N/A"
    implied_forward_revenue_growth_fmt = "N/A"
    shares = data.get("shares_raw")
    f_eps = data.get("forward_eps")
    profit_margin_raw = data.get("profit_margin_raw")
    revenue_ttm_raw = data.get("revenue_ttm_raw")
    if isinstance(shares, (int, float)) and isinstance(f_eps, (int, float)) and shares != "N/A":
        implied_ni = shares * f_eps
        implied_forward_ni_fmt = format_number(implied_ni, "億")
        if isinstance(profit_margin_raw, (int, float)) and profit_margin_raw > 0:
            implied_revenue = implied_ni / profit_margin_raw
            implied_forward_revenue_fmt = format_number(implied_revenue, "億")
            if isinstance(revenue_ttm_raw, (int, float)) and revenue_ttm_raw > 0:
                implied_growth = (implied_revenue / revenue_ttm_raw - 1) * 100
                implied_forward_revenue_growth_fmt = f"{implied_growth:.1f}%"

    latest_revenue_growth_fmt = "N/A"
    latest_fcf_conversion_fmt = "N/A"
    rev_hist = data.get("revenue_history", [])
    ni_hist = data.get("net_income_history", [])
    fcf_hist = data.get("fcf_history", [])
    if len(rev_hist) >= 2 and rev_hist[-2] and rev_hist[-1] and rev_hist[-2] > 0:
        latest_revenue_growth = (rev_hist[-1] / rev_hist[-2] - 1) * 100
        latest_revenue_growth_fmt = f"{latest_revenue_growth:.1f}%"
    if ni_hist and fcf_hist and ni_hist[-1] and fcf_hist[-1]:
        latest_fcf_conversion = (fcf_hist[-1] / ni_hist[-1]) * 100
        latest_fcf_conversion_fmt = f"{latest_fcf_conversion:.1f}%"

    identity = data.get("company_identity", {}) or {}
    official_name = identity.get("official_name")
    legal_name = identity.get("legal_name")
    english_names = identity.get("english_names", [])
    forbidden_aliases = identity.get("forbidden_aliases", [])
    preferred_name = official_name or data.get("company_name", data.get("ticker", "本公司"))

    identity_lines = []
    if identity:
        identity_lines = [
            "",
            "🚨【標的身份鎖定（最高優先級）】",
            f"  本報告唯一分析標的：{data.get('ticker', 'N/A')} {data.get('company_name', 'N/A')}",
            f"  股票代號：{identity.get('stock_id', data.get('ticker', 'N/A'))}",
            f"  官方中文簡稱：{official_name or 'N/A'}",
            f"  官方/法定名稱：{legal_name or 'N/A'}",
            f"  英文名稱：{', '.join(english_names) if english_names else 'N/A'}",
            f"  全篇稱呼標的時，請使用「{preferred_name}」或「{data.get('ticker', 'N/A')}」。",
            "  嚴禁把同業、可比公司、新聞案例或其他股票代號的公司名稱當作本公司。",
            "  若前序摘要或外部常識與本身份鎖定衝突，必須以本段為準，並明確修正錯誤。",
        ]
        if forbidden_aliases:
            identity_lines.append(
                f"  特別禁止：不可把 {', '.join(forbidden_aliases)} 稱為 {data.get('ticker', 'N/A')}，也不可把其商業模式或專案套用為本公司主體。"
            )

    lines = [
        f"━━━ {data['ticker']} {data['company_name']} 財務數據摘要 ━━━",
        f"產業：{data.get('sector', 'N/A')} | {data.get('industry', 'N/A')}",
        f"員工人數：{data.get('employees', 'N/A')}",
        f"數據日期：{data.get('fetch_date', 'N/A')}",
        *identity_lines,
        "",
        "⚠️【單位與邏輯防呆宣告（非常重要）】",
        "1. 歷史財務表：下方【歷年財務數據】中所有數字的單位為 Billion TWD (10億台幣)。例如 19.0 = NT$19.0B = 約190億台幣。請在分析時統一使用 Billion 作為英文語境單位。",
        "2. TTM 指標（即時指標）：本表中【財務體質】、【現金流】、【資產負債】所有標示「億」的數字，單位均為「億台幣」(= 0.1 Billion)，請除以10後換算為Billion再與歷史數據比較，切勿直接拿億當Billion使用！",
        "3. 負債比率：本表中的「負債權益比 (Debt to Equity)」已經是百分比。若標示為 4.98%，代表負債極低，絕對不可誤讀為 498%！",
        "4. 數量級防呆：1B = 10億台幣。如果預估營收為 290億台幣，必須精確寫作 29.0B 或 290億台幣。絕對不可寫成 290B（這會變成2900億，在投行是不可原諒的低級錯誤）！",
        "5. 物理與商業常識防呆：實體硬體製造業（包含金屬機構件、導軌）的營收大幅成長通常需要產能、設備、人力與營運資金同步擴張。若預測營收成長超過 50%，必須明確說明產能來源、CapEx、折舊、良率/學習曲線與客戶第二供應商壓價風險；若缺乏證據，必須下修利潤率或估值，不可假設「營收暴增但淨利率完全不掉」。",
        "",
        "【估值邏輯防呆檢驗】",
        f"  總發行股數：{data.get('shares_outstanding', 'N/A')}",
        f"  近四季 EPS (Trailing EPS)：NT${data.get('trailing_eps', 'N/A')}",
        f"  預估 EPS (Forward EPS)：NT${data.get('forward_eps', 'N/A')}",
        f"  隱含預估未來淨利 (Forward EPS × 股數)：{implied_forward_ni_fmt}",
        f"  若維持目前淨利率，Forward EPS 隱含所需營收：約 {implied_forward_revenue_fmt}（相對 TTM 營收成長 {implied_forward_revenue_growth_fmt}）",
        "  ⚠️ 警告：當你預測未來的營收與淨利時，必須與上述的「隱含預估未來淨利」進行交叉比對。若你預測的未來總營收甚至低於此淨利，代表你的營收預測過度保守，或是華爾街的 Forward P/E 給出的預期過度樂觀。請在報告中提出合理質疑！",
        "  ⚠️ 雙重樂觀防呆：若 Forward EPS 已隱含營收需成長超過 50%，估值倍數必須折讓或明確下修，嚴禁同時採用「極端營收暴增」與「高於歷史/同業的高本益比」。",
        "",
        "【自由現金流品質防呆】",
        f"  最近年度營收成長率：{latest_revenue_growth_fmt}",
        f"  最近年度 FCF/淨利轉換率：{latest_fcf_conversion_fmt}",
        "  ⚠️ 警告：硬體製造業若在營收成長超過 50% 時仍出現 FCF/淨利 >100%，預設應視為一次性營運資金釋放、CapEx 遞延或資料需查核，不可當成可重複的 DCF 基準。除非現金流量表能證明客戶預付款或其他具體來源，否則估值必須使用 normalized FCF。",
        "",
        "【杜邦分析防呆錨點】",
        f"  真實權益乘數 (Total Assets / Equity)：{data.get('equity_multiplier', 'N/A')}",
        f"  {data.get('equity_multiplier_note', '')}",
        f"  {data.get('dupont_identity_note', '')}",
        "  ⚠️ 警告：杜邦分析是會計恒等式：ROE = 淨利率 × 資產周轉率 × 權益乘數。只有同期間、同口徑資料可拿來驗算；若 Yahoo ROA/ROE 與最新資產負債表拼接後有差距，只能解釋為資料口徑或期間不一致，嚴禁歸因為「應付帳款等非計息負債槓桿」。",
        "",
        "【WACC 資本結構防呆錨點】",
        f"  {data.get('wacc_capital_structure_note', 'N/A')}",
        "  ⚠️ 警告：公開市場股票的 WACC 權重必須優先使用市場價值（Market Value）。不可用帳面 D/E 直接推出 95%/5% 權重；若市值遠大於有息負債，股權權重應接近 100%。",
        "",
        "【市場數據】",
        f"  當前股價：{data.get('current_price_fmt', 'N/A')}",
        f"  市值：{data.get('market_cap_fmt', 'N/A')}",
        f"  52週高/低：{data.get('week_52_high_fmt', 'N/A')} / {data.get('week_52_low_fmt', 'N/A')}",
        "",
        "【估值指標】",
        f"  本益比 P/E（TTM）：{data.get('pe_ratio', 'N/A')}",
        f"  預期本益比（Forward P/E）：{data.get('forward_pe', 'N/A')}",
        f"  股價淨值比 P/B：{data.get('pb_ratio', 'N/A')}",
        f"  股價營收比 P/S：{data.get('ps_ratio', 'N/A')}",
        f"  EV/EBITDA：{data.get('ev_ebitda', 'N/A')}",
        "",
        "【財務體質】",
        f"  年營收（TTM）：{data.get('revenue_ttm', 'N/A')}",
        f"  毛利率：{data.get('gross_margin', 'N/A')}",
        f"  營業利潤率：{data.get('operating_margin', 'N/A')}",
        f"  淨利率：{data.get('profit_margin', 'N/A')}",
        f"  EBITDA：{data.get('ebitda_fmt', 'N/A')}",
        "",
        "【現金流】",
        f"  自由現金流：{data.get('free_cash_flow', 'N/A')}",
        f"  營業現金流：{data.get('operating_cash_flow', 'N/A')}",
        "",
        "【資產負債】",
        f"  總負債：{data.get('total_debt', 'N/A')}",
        f"  現金及約當現金：{data.get('total_cash', 'N/A')}",
        f"  負債權益比：{data.get('debt_to_equity', 'N/A')}",
        f"  流動比率：{data.get('current_ratio', 'N/A')}",
        "",
        "【股東回報】",
        f"  股東權益報酬率 ROE：{data.get('roe', 'N/A')}",
        f"  資產報酬率 ROA：{data.get('roa', 'N/A')}",
        f"  ⚠️ ROE/ROA 說明：Yahoo Finance 的 ROE 與 ROA 使用的是不同期間的平均資產/股東權益計算，請勿以最新一期資產負債表數字進行驗算，可能出現偏差。",
        f"  殖利率：{data.get('dividend_yield', 'N/A')}",
        f"  每股配息：{data.get('dividend_rate', 'N/A')}",
        f"  配息率：{data.get('payout_ratio', 'N/A')}",
        "",
        "【成長指標】",
        f"  營收年增率：{data.get('revenue_growth', 'N/A')}",
        f"  獲利年增率：{data.get('earnings_growth', 'N/A')}",
        f"  5年營收 CAGR：{data.get('revenue_cagr_5yr', 'N/A')}",
        "",
        "【市場參考】",
        f"  Beta 係數：{data.get('beta', 'N/A')}",
        f"  分析師目標價：{data.get('analyst_target', 'N/A')}",
        f"  分析師建議：{data.get('analyst_rec', 'N/A')}（{data.get('analyst_count', 'N/A')}位分析師）",
    ]
    
    # 補充：台股近期每月營收（若有）
    recent_monthly_revenue = data.get("recent_monthly_revenue")
    if recent_monthly_revenue:
        lines.append("")
        lines.append("【近期每月營收動能 (FinMind 官方數據)】")
        for rm in recent_monthly_revenue:
            lines.append(f"  {rm}")

    data_source_notes = data.get("data_source_notes")
    if data_source_notes:
        lines.append("")
        lines.append("【資料補值與限制】")
        for note in data_source_notes:
            lines.append(f"  - {note}")
        lines.append("  ⚠️ 補值欄位只能作為交叉檢查，不可包裝成官方完整資料。")
            
    # 加入歷史財務數據
    if data.get("years") and data.get("revenue_history"):
        lines.append("")
        lines.append("【歷年財務數據（Billion TWD / 10億台幣）】")
        years = data["years"]
        rev = data["revenue_history"]
        ni = data.get("net_income_history", [])
        fcf = data.get("fcf_history", [])
        gm = data.get("gross_margin_history", [])
        roe_h = data.get("roe_history", [])
        
        header = "  年度     " + "  ".join(f"{y:>8}" for y in years)
        lines.append(header)
        
        if rev:
            row = "  營收     " + "  ".join(f"{v:>7.1f}" if v else "    N/A" for v in rev)
            lines.append(row)
        if ni:
            row = "  淨利     " + "  ".join(f"{v:>7.1f}" if v else "    N/A" for v in ni)
            lines.append(row)
        if fcf:
            row = "  自由現金 " + "  ".join(f"{v:>7.1f}" if v else "    N/A" for v in fcf)
            lines.append(row)
        if gm:
            row = "  毛利率   " + "  ".join(f"{v:>6.1f}%" if v else "   N/A" for v in gm)
            lines.append(row)
        if roe_h:
            row = "  ROE      " + "  ".join(f"{v:>6.1f}%" if v else "   N/A" for v in roe_h)
            lines.append(row)
    
    return "\n".join(lines)
