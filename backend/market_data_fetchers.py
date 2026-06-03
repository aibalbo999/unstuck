"""Market data fetch helpers for financial_data."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

import pandas as pd
import yfinance as yf

from config import CATALYST_LOOKBACK_DAYS, INSTITUTIONAL_LOOKBACK_DAYS
from external_data_clients import (
    fetch_fmp_news_catalysts as fetch_fmp_news_catalysts_http,
    fetch_fmp_news_catalysts_async,
    fetch_fmp_quote_fallback as fetch_fmp_quote_fallback_http,
    fetch_google_peer_discovery_results as fetch_google_peer_discovery_results_http,
    fetch_google_peer_discovery_results_async,
    fetch_google_search_catalysts as fetch_google_search_catalysts_http,
    fetch_google_search_catalysts_async,
)
from financial_tools import safe_float

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

GLOBAL_PEER_HINTS = [
    (["半導體", "Semiconductor", "晶圓", "foundry"], [("Intel", "INTC"), ("Samsung Electronics", "005930.KS"), ("UMC", "2303.TW"), ("SMIC", "0981.HK")]),
    (["記憶體", "Memory", "DRAM", "NAND"], [("Micron", "MU"), ("SK hynix", "000660.KS"), ("Samsung Electronics", "005930.KS")]),
    (["面板", "Display", "LCD", "OLED"], [("AUO", "2409.TW"), ("Innolux", "3481.TW"), ("LG Display", "LPL"), ("BOE", "000725.SZ")]),
    (["航運", "Shipping", "Marine"], [("Evergreen Marine", "2603.TW"), ("Yang Ming", "2609.TW"), ("Wan Hai", "2615.TW"), ("Maersk", "MAERSK-B.CO")]),
]


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
    return fetch_fmp_quote_fallback_http(ticker)


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


def _run_named_fetches(fetchers: dict[str, tuple], max_workers: int = 4) -> dict:
    """Run independent blocking data fetches concurrently and keep failures isolated."""
    if not fetchers:
        return {}

    results = {}
    worker_count = max(1, min(max_workers, len(fetchers)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {}
        for name, spec in fetchers.items():
            func, args, default, warning = spec
            futures[executor.submit(func, *args)] = (name, default, warning)

        for future in as_completed(futures):
            name, default, warning = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                print(f"    ⚠️  {warning}：{e}")
                results[name] = default

    return results


def fetch_google_search_catalysts(ticker: str, company_name: str, identity: dict) -> list[dict]:
    """Fetch catalyst-like headlines from Google Custom Search when configured."""
    return fetch_google_search_catalysts_http(ticker, company_name, identity)


def fetch_google_peer_discovery_results(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    """Fetch search snippets that can help Agent 3 identify real global peers."""
    return fetch_google_peer_discovery_results_http(ticker, company_name, sector, industry)


def fetch_fmp_news_catalysts(ticker: str) -> list[dict]:
    """Fetch optional FMP stock news when an API key is available."""
    return fetch_fmp_news_catalysts_http(ticker)


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


def fetch_recent_catalysts(
    ticker: str,
    company_name: str,
    identity: dict,
    stock,
    skip_optional_http: bool = False,
) -> list[dict]:
    records = []
    fetches = {
        "finmind": (fetch_finmind_news_catalysts, (ticker,), [], "FinMind 新聞資料獲取失敗"),
        "yfinance": (fetch_yfinance_news_catalysts, (stock,), [], "Yahoo Finance 新聞資料獲取失敗"),
    }
    if not skip_optional_http:
        fetches.update({
            "google": (fetch_google_search_catalysts, (ticker, company_name, identity), [], "Google Search 催化劑資料獲取失敗"),
            "fmp": (fetch_fmp_news_catalysts, (ticker,), [], "FMP 新聞資料獲取失敗"),
        })
    for items in _run_named_fetches(fetches, max_workers=4).values():
        records.extend(items or [])
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

    seen = set()
    unique_peers = []
    for name, symbol in peers:
        if symbol in seen:
            continue
        seen.add(symbol)
        unique_peers.append((name, symbol))
        if len(unique_peers) >= 5:
            break

    def fetch_peer(name: str, symbol: str) -> dict:
        try:
            info = yf.Ticker(symbol).info
        except Exception:
            info = {}
        return {
            "name": name,
            "ticker": symbol,
            "source": "FinMind industry peer + yfinance metrics" if symbol.endswith(".TW") else "global peer heuristic + yfinance metrics",
            "gross_margin_pct": round(float(info.get("grossMargins")) * 100, 2) if isinstance(info.get("grossMargins"), (int, float)) else None,
            "operating_margin_pct": round(float(info.get("operatingMargins")) * 100, 2) if isinstance(info.get("operatingMargins"), (int, float)) else None,
            "profit_margin_pct": round(float(info.get("profitMargins")) * 100, 2) if isinstance(info.get("profitMargins"), (int, float)) else None,
            "pe_ttm": round(float(info.get("trailingPE")), 2) if isinstance(info.get("trailingPE"), (int, float)) else None,
            "pb": round(float(info.get("priceToBook")), 2) if isinstance(info.get("priceToBook"), (int, float)) else None,
        }

    fetches = {
        symbol: (fetch_peer, (name, symbol), None, f"{symbol} 同業指標獲取失敗")
        for name, symbol in unique_peers
    }
    results = _run_named_fetches(fetches, max_workers=5)
    records = [record for record in results.values() if record]
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


def _history_has_values(values: list) -> bool:
    return bool(values) and any(value is not None for value in values)


def _raw_twd_to_billion(value) -> Optional[float]:
    number = safe_float(value)
    if number is None:
        return None
    return round(number / 1e9, 2)


def _finmind_value(df: pd.DataFrame, statement_date: str, type_candidates: list[str]) -> Optional[float]:
    if df is None or df.empty:
        return None
    rows = df[(df["date"] == statement_date) & (df["type"].isin(type_candidates))]
    if rows.empty:
        return None
    return _raw_twd_to_billion(rows.iloc[0].get("value"))


def _finmind_statement_dates(*frames: pd.DataFrame) -> list[str]:
    dates = set()
    for df in frames:
        if df is not None and not df.empty and "date" in df.columns:
            dates.update(str(value)[:10] for value in df["date"].dropna().unique())

    annual_dates = sorted(date for date in dates if date.endswith("12-31"))
    if annual_dates:
        return annual_dates[-5:]

    by_year: dict[str, list[str]] = {}
    for statement_date in dates:
        year = statement_date[:4]
        if year.isdigit():
            by_year.setdefault(year, []).append(statement_date)

    selected = []
    for year, year_dates in by_year.items():
        year_dates = sorted(year_dates)
        annual = [date for date in year_dates if date.endswith("12-31")]
        selected.append(annual[-1] if annual else year_dates[-1])
    return sorted(selected)[-5:]


def fetch_finmind_financial_statement_fallback(ticker: str) -> dict:
    """Fetch Taiwan financial statement histories from FinMind when yfinance misses statements."""
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return {}

    stock_id = _stock_id_from_ticker(ticker)
    start_date = (datetime.now() - timedelta(days=365 * 6 + 30)).strftime("%Y-%m-%d")

    def fetch_financial_statement():
        return DataLoader().taiwan_stock_financial_statement(stock_id=stock_id, start_date=start_date)

    def fetch_balance_sheet():
        return DataLoader().taiwan_stock_balance_sheet(stock_id=stock_id, start_date=start_date)

    def fetch_cash_flow_statement():
        return DataLoader().taiwan_stock_cash_flows_statement(stock_id=stock_id, start_date=start_date)

    frames = _run_named_fetches(
        {
            "financials": (fetch_financial_statement, (), pd.DataFrame(), "FinMind 損益表獲取失敗"),
            "balance": (fetch_balance_sheet, (), pd.DataFrame(), "FinMind 資產負債表獲取失敗"),
            "cashflow": (fetch_cash_flow_statement, (), pd.DataFrame(), "FinMind 現金流量表獲取失敗"),
        },
        max_workers=3,
    )
    financials = frames.get("financials")
    balance = frames.get("balance")
    cashflow = frames.get("cashflow")

    statement_dates = _finmind_statement_dates(financials, balance, cashflow)
    if not statement_dates:
        return {}

    rows_by_year = {}
    for statement_date in statement_dates:
        year = statement_date[:4]
        operating_cash_flow = _finmind_value(
            cashflow,
            statement_date,
            ["NetCashInflowFromOperatingActivities", "CashFlowsFromOperatingActivities"],
        )
        capex = _finmind_value(cashflow, statement_date, ["PropertyAndPlantAndEquipment"])
        free_cash_flow = None
        if operating_cash_flow is not None:
            free_cash_flow = round(operating_cash_flow + (capex or 0), 2)

        rows_by_year[year] = {
            "statement_date": statement_date,
            "revenue": _finmind_value(financials, statement_date, ["Revenue"]),
            "net_income": _finmind_value(financials, statement_date, ["EquityAttributableToOwnersOfParent", "IncomeAfterTaxes"]),
            "gross_profit": _finmind_value(financials, statement_date, ["GrossProfit"]),
            "operating_income": _finmind_value(financials, statement_date, ["OperatingIncome"]),
            "free_cash_flow": free_cash_flow,
            "total_assets": _finmind_value(balance, statement_date, ["TotalAssets"]),
            "total_equity": _finmind_value(balance, statement_date, ["EquityAttributableToOwnersOfParent", "Equity"]),
        }

    years = sorted(rows_by_year.keys())[-5:]
    return {
        "source": "FinMind TaiwanStockFinancialStatements/BalanceSheet/CashFlowsStatement",
        "years": years,
        "rows_by_year": rows_by_year,
        "revenue_history": [rows_by_year[year]["revenue"] for year in years],
        "net_income_history": [rows_by_year[year]["net_income"] for year in years],
        "gross_profit_history": [rows_by_year[year]["gross_profit"] for year in years],
        "operating_income_history": [rows_by_year[year]["operating_income"] for year in years],
        "fcf_history": [rows_by_year[year]["free_cash_flow"] for year in years],
        "total_assets_history": [rows_by_year[year]["total_assets"] for year in years],
        "total_equity_history": [rows_by_year[year]["total_equity"] for year in years],
    }


def _align_finmind_history(years: list[str], rows_by_year: dict, key: str) -> list:
    return [rows_by_year.get(str(year), {}).get(key) for year in years]
