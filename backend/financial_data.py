# ============================================================
# financial_data.py - 從 yfinance 獲取完整財務數據
# ============================================================

import asyncio
import json
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
from functools import lru_cache
import warnings
from cache_store import get_cache_json, set_cache_json
from config import (
    CATALYST_LOOKBACK_DAYS,
    FINANCIAL_DATA_CACHE_SECONDS,
    FMP_API_KEY,
    FMP_BASE_URL,
    GOOGLE_CSE_ID,
    GOOGLE_SEARCH_API_KEY,
    INSTITUTIONAL_LOOKBACK_DAYS,
)
from financial_tools import build_financial_tool_context, raw_twd_to_billion_twd, safe_float
warnings.filterwarnings("ignore")

DATA_SCHEMA_VERSION = 3

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


def is_taiwan_ticker(ticker: str) -> bool:
    stock_id = str(ticker).replace(".TW", "").replace(".TWO", "")
    return ticker.endswith(".TW") or ticker.endswith(".TWO") or (stock_id.isdigit() and len(stock_id) == 4)


def _stock_id_from_ticker(ticker: str) -> str:
    return str(ticker).replace(".TW", "").replace(".TWO", "")


def _dedupe_records(records: list[dict], key: str = "title", limit: int = 6) -> list[dict]:
    kept = []
    seen = set()
    for record in records:
        marker = str(record.get(key) or record.get("link") or "").strip().lower()
        if not marker or marker in seen:
            continue
        kept.append(record)
        seen.add(marker)
        if len(kept) >= limit:
            break
    return kept


def fetch_google_search_catalysts(ticker: str, company_name: str, identity: dict) -> list[dict]:
    """Fetch catalyst-like headlines from Google Custom Search when configured."""
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []

    official_name = identity.get("official_name") or company_name or ticker
    query = f"{official_name} {ticker} 法說會 展望 供應鏈 營收 投資"
    try:
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": GOOGLE_SEARCH_API_KEY,
                "cx": GOOGLE_CSE_ID,
                "q": query,
                "num": 5,
                "dateRestrict": f"d{CATALYST_LOOKBACK_DAYS}",
                "lr": "lang_zh-TW",
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        print(f"    ⚠️  Google Search 催化劑資料獲取失敗：{e}")
        return []

    records = []
    for item in payload.get("items", []) or []:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        metatags = item.get("pagemap", {}).get("metatags", [{}]) or [{}]
        records.append({
            "date": metatags[0].get("article:published_time", ""),
            "title": title,
            "summary": str(item.get("snippet", "")).strip(),
            "source": item.get("displayLink", "Google Search"),
            "link": item.get("link", ""),
            "source_type": "google_search",
        })
    return records


def fetch_google_peer_discovery_results(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    """Fetch search snippets that can help Agent 3 identify real global peers."""
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []

    query = f"{company_name} {ticker} global competitors peers gross margin {industry} {sector}"
    try:
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": GOOGLE_SEARCH_API_KEY,
                "cx": GOOGLE_CSE_ID,
                "q": query,
                "num": 5,
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        print(f"    ⚠️  Google Search 同業 discovery 失敗：{e}")
        return []

    records = []
    for item in payload.get("items", []) or []:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        records.append({
            "title": title,
            "snippet": str(item.get("snippet", "")).strip(),
            "source": item.get("displayLink", "Google Search"),
            "link": item.get("link", ""),
            "source_type": "google_peer_discovery",
        })
    return _dedupe_records(records, limit=5)


def fetch_fmp_news_catalysts(ticker: str) -> list[dict]:
    """Fetch optional FMP stock news when an API key is available."""
    if not FMP_API_KEY:
        return []
    symbol = ticker.strip().upper()
    candidates = [
        ("https://financialmodelingprep.com/api/v3/stock_news", {"tickers": symbol, "limit": 5, "apikey": FMP_API_KEY}),
        (f"{FMP_BASE_URL}/stock_news", {"tickers": symbol, "limit": 5, "apikey": FMP_API_KEY}),
    ]
    for url, params in candidates:
        try:
            response = requests.get(url, params=params, timeout=8)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                continue
            records = []
            for item in payload:
                if not isinstance(item, dict) or not item.get("title"):
                    continue
                records.append({
                    "date": item.get("publishedDate") or item.get("date") or "",
                    "title": str(item.get("title", "")).strip(),
                    "summary": str(item.get("text") or item.get("summary") or "")[:280],
                    "source": item.get("site") or "FMP",
                    "link": item.get("url") or "",
                    "source_type": "fmp_news",
                })
            if records:
                return records
        except Exception:
            continue
    return []


def fetch_finmind_news_catalysts(ticker: str) -> list[dict]:
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return []
    stock_id = _stock_id_from_ticker(ticker)
    start_date = (datetime.now() - timedelta(days=CATALYST_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    try:
        df = DataLoader().taiwan_stock_news(stock_id=stock_id, start_date=start_date)
    except Exception as e:
        print(f"    ⚠️  FinMind 新聞資料獲取失敗：{e}")
        return []
    if df is None or df.empty:
        return []
    records = []
    for _, row in df.tail(20).iloc[::-1].iterrows():
        title = str(row.get("title", "")).strip()
        if not title:
            continue
        records.append({
            "date": str(row.get("date", ""))[:19],
            "title": title,
            "summary": str(row.get("description", "") or "")[:280],
            "source": str(row.get("source", "FinMind")).strip() or "FinMind",
            "link": str(row.get("link", "")).strip(),
            "source_type": "finmind_news",
        })
    return records


def fetch_yfinance_news_catalysts(stock) -> list[dict]:
    try:
        news = getattr(stock, "news", []) or []
    except Exception:
        return []
    records = []
    for item in news[:10]:
        content = item.get("content", item) if isinstance(item, dict) else {}
        if not isinstance(content, dict):
            continue
        title = str(content.get("title", "")).strip()
        if not title:
            continue
        records.append({
            "date": content.get("pubDate") or content.get("displayTime") or "",
            "title": title,
            "summary": str(content.get("summary") or content.get("description") or "")[:280],
            "source": content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else "Yahoo Finance",
            "link": content.get("clickThroughUrl", {}).get("url") if isinstance(content.get("clickThroughUrl"), dict) else "",
            "source_type": "yfinance_news",
        })
    return records


def fetch_recent_catalysts(ticker: str, company_name: str, identity: dict, stock) -> list[dict]:
    records = []
    records.extend(fetch_google_search_catalysts(ticker, company_name, identity))
    records.extend(fetch_fmp_news_catalysts(ticker))
    records.extend(fetch_finmind_news_catalysts(ticker))
    records.extend(fetch_yfinance_news_catalysts(stock))
    return _dedupe_records(records, limit=5)[:5]


def fetch_institutional_trading_trend(ticker: str) -> dict:
    """Summarize Taiwan 3-institution net buy/sell over the recent window."""
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return {}
    stock_id = _stock_id_from_ticker(ticker)
    start_date = (datetime.now() - timedelta(days=max(INSTITUTIONAL_LOOKBACK_DAYS + 15, 45))).strftime("%Y-%m-%d")
    try:
        df = DataLoader().taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date)
    except Exception as e:
        print(f"    ⚠️  三大法人資料獲取失敗：{e}")
        return {}
    if df is None or df.empty:
        return {}

    df = df.copy()
    df["net_buy"] = df["buy"].astype(float) - df["sell"].astype(float)
    df["category"] = df["name"].map(lambda name: (
        "foreign" if "Foreign" in str(name)
        else "investment_trust" if "Investment_Trust" in str(name)
        else "dealer"
    ))
    by_day = df.groupby(["date", "category"], as_index=False)["net_buy"].sum()
    dates = sorted(by_day["date"].unique())[-INSTITUTIONAL_LOOKBACK_DAYS:]
    recent = by_day[by_day["date"].isin(dates)]
    totals = recent.groupby("category")["net_buy"].sum().to_dict()
    daily_total = recent.groupby("date")["net_buy"].sum().tail(10)
    total_net = sum(totals.values())
    last_5_net = recent[recent["date"].isin(dates[-5:])]["net_buy"].sum() if dates else 0
    if total_net > 0 and last_5_net > 0:
        trend = "accumulation"
    elif total_net < 0 and last_5_net < 0:
        trend = "distribution"
    else:
        trend = "mixed"

    return {
        "source": "FinMind TaiwanStockInstitutionalInvestorsBuySell",
        "lookback_trading_days": len(dates),
        "latest_date": str(dates[-1]) if dates else "",
        "net_buy_shares_by_category": {key: int(value) for key, value in totals.items()},
        "net_buy_thousand_shares_by_category": {key: round(value / 1000, 2) for key, value in totals.items()},
        "total_net_buy_shares": int(total_net),
        "total_net_buy_thousand_shares": round(total_net / 1000, 2),
        "last_5_trading_days_net_buy_thousand_shares": round(last_5_net / 1000, 2),
        "trend": trend,
        "daily_total_net_buy_last_10": [
            {"date": str(date), "net_buy_thousand_shares": round(value / 1000, 2)}
            for date, value in daily_total.items()
        ],
    }


GLOBAL_PEER_HINTS = [
    (["半導體", "Semiconductor", "晶圓", "foundry"], [("Intel", "INTC"), ("Samsung Electronics", "005930.KS"), ("UMC", "2303.TW"), ("SMIC", "0981.HK")]),
    (["記憶體", "Memory", "DRAM", "NAND"], [("Micron", "MU"), ("SK hynix", "000660.KS"), ("Samsung Electronics", "005930.KS")]),
    (["面板", "Display", "LCD", "OLED"], [("AUO", "2409.TW"), ("Innolux", "3481.TW"), ("LG Display", "LPL"), ("BOE", "000725.SZ")]),
    (["航運", "Shipping", "Marine"], [("Evergreen Marine", "2603.TW"), ("Yang Ming", "2609.TW"), ("Wan Hai", "2615.TW"), ("Maersk", "MAERSK-B.CO")]),
]


def infer_global_peer_tickers(ticker: str, company_name: str, sector: str, industry: str) -> list[tuple[str, str]]:
    signature = f"{company_name} {sector} {industry}"
    peers = []
    for keywords, candidates in GLOBAL_PEER_HINTS:
        if any(keyword.lower() in signature.lower() for keyword in keywords):
            peers.extend(candidates)
    return [(name, symbol) for name, symbol in peers if symbol.upper() != ticker.upper()][:5]


def fetch_dynamic_peer_metrics(ticker: str, company_name: str, sector: str, industry: str, identity: dict) -> list[dict]:
    peers = []
    for peer in (identity.get("same_industry_peers", []) or [])[:3]:
        stock_id = peer.get("stock_id")
        if stock_id:
            peers.append((peer.get("stock_name", stock_id), f"{stock_id}.TW"))
    peers.extend(infer_global_peer_tickers(ticker, company_name, sector, industry))

    records = []
    seen = set()
    for name, symbol in peers:
        if symbol in seen:
            continue
        seen.add(symbol)
        try:
            info = yf.Ticker(symbol).info
        except Exception:
            info = {}
        records.append({
            "name": name,
            "ticker": symbol,
            "source": "FinMind industry peer + yfinance metrics" if symbol.endswith(".TW") else "global peer heuristic + yfinance metrics",
            "gross_margin_pct": round(float(info.get("grossMargins")) * 100, 2) if isinstance(info.get("grossMargins"), (int, float)) else None,
            "operating_margin_pct": round(float(info.get("operatingMargins")) * 100, 2) if isinstance(info.get("operatingMargins"), (int, float)) else None,
            "profit_margin_pct": round(float(info.get("profitMargins")) * 100, 2) if isinstance(info.get("profitMargins"), (int, float)) else None,
            "pe_ttm": round(float(info.get("trailingPE")), 2) if isinstance(info.get("trailingPE"), (int, float)) else None,
            "pb": round(float(info.get("priceToBook")), 2) if isinstance(info.get("priceToBook"), (int, float)) else None,
        })
        if len(records) >= 5:
            break
    return records


def build_pe_river_chart_data(ticker: str, years: list[str], net_income_history: list, shares_outstanding) -> dict:
    shares = safe_float(shares_outstanding)
    eps = []
    for value in net_income_history or []:
        number = safe_float(value)
        eps.append(round(number * 1e9 / shares, 2) if number is not None and shares else None)

    multiples = [10, 12, 15, 18]
    source = "default multiples"
    if DataLoader is not None and is_taiwan_ticker(ticker):
        start_date = (datetime.now() - timedelta(days=365 * 5 + 30)).strftime("%Y-%m-%d")
        try:
            df = DataLoader().taiwan_stock_per_pbr(stock_id=_stock_id_from_ticker(ticker), start_date=start_date)
            per_values = [float(v) for v in df.get("PER", []) if isinstance(v, (int, float)) and 0 < float(v) < 100]
            if len(per_values) >= 20:
                series = pd.Series(per_values)
                multiples = sorted({round(float(series.quantile(q)), 1) for q in [0.25, 0.5, 0.75, 0.9]})
                source = "FinMind 5-year PER quantiles"
        except Exception as e:
            print(f"    ⚠️  P/E 河流圖資料獲取失敗：{e}")

    bands = {
        f"{multiple:g}x": [round(e * multiple, 2) if e is not None else None for e in eps]
        for multiple in multiples
    }
    return {
        "years": years or [],
        "eps_twd": eps,
        "multiples": multiples,
        "bands": bands,
        "source": source,
    }


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

        # === 即時/質性資料擴充 ===
        try:
            recent_catalysts = fetch_recent_catalysts(ticker, company_name, company_identity, stock)
        except Exception as e:
            print(f"    ⚠️  新聞催化劑資料彙整失敗：{e}")
            recent_catalysts = []

        try:
            institutional_trading = fetch_institutional_trading_trend(ticker)
        except Exception as e:
            print(f"    ⚠️  法人籌碼資料彙整失敗：{e}")
            institutional_trading = {}

        try:
            dynamic_peer_metrics = fetch_dynamic_peer_metrics(ticker, company_name, sector, industry, company_identity)
        except Exception as e:
            print(f"    ⚠️  動態同業資料彙整失敗：{e}")
            dynamic_peer_metrics = []

        try:
            peer_discovery_results = fetch_google_peer_discovery_results(ticker, company_name, sector, industry)
        except Exception as e:
            print(f"    ⚠️  同業 discovery 資料彙整失敗：{e}")
            peer_discovery_results = []

        try:
            pe_river_chart = build_pe_river_chart_data(ticker, years, net_income_history, shares_outstanding)
        except Exception as e:
            print(f"    ⚠️  P/E 河流圖資料彙整失敗：{e}")
            pe_river_chart = {"years": years, "eps_twd": [], "multiples": [10, 12, 15, 18], "bands": {}, "source": "unavailable"}

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


async def async_fetch_stock_data(ticker: str) -> dict:
    """非同步包裝既有 yfinance/FinMind 抓取流程，避免阻塞 async worker event loop。"""
    return await asyncio.to_thread(fetch_stock_data, ticker)


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


def format_data_for_prompt(data: dict) -> str:
    """將財務數據格式化為乾淨 JSON，避免單位混用與 prompt 過載。"""
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
        "schema_version": DATA_SCHEMA_VERSION,
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
