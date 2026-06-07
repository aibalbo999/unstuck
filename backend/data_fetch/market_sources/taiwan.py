"""FinMind-backed Taiwan market source helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from config import CATALYST_LOOKBACK_DAYS, INSTITUTIONAL_LOOKBACK_DAYS
from financial_tools import safe_float

from .common import _run_named_fetches
from .identity import _stock_id_from_ticker, is_taiwan_ticker

try:
    from FinMind.data import DataLoader
except ImportError:
    DataLoader = None


def fetch_finmind_news_catalysts(ticker: str) -> list[dict]:
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return []
    stock_id = _stock_id_from_ticker(ticker)
    start_date = (datetime.now() - timedelta(days=CATALYST_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    try:
        df = DataLoader().taiwan_stock_news(stock_id=stock_id, start_date=start_date)
    except Exception:
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


def fetch_monthly_revenue_records(ticker: str, data_loader_cls=DataLoader) -> tuple[list, dict | None]:
    from source_audit import audited_fetch

    recent_monthly_revenue = []
    monthly_revenue_audit = None
    if not is_taiwan_ticker(ticker) or data_loader_cls is None:
        return recent_monthly_revenue, monthly_revenue_audit

    def fetch_records():
        fm_dl = data_loader_cls()
        stock_id = _stock_id_from_ticker(ticker)
        start_date = (datetime.now() - timedelta(days=240)).strftime("%Y-%m-%d")
        df_rev = fm_dl.taiwan_stock_month_revenue(stock_id=stock_id, start_date=start_date)
        records = []
        if df_rev is not None and not df_rev.empty:
            for _, row in df_rev.tail(6).iterrows():
                year = row.get("revenue_year")
                month = row.get("revenue_month")
                value = row.get("revenue")
                if year and month and value:
                    records.append(f"{year}年{month}月: NT${float(value) / 1e8:.2f}億")
        return records

    monthly_revenue_result = audited_fetch(
        "monthly_revenue",
        "FinMind TaiwanStockMonthRevenue",
        fetch_records,
        default=[],
        unavailable_message="FinMind 月營收未回傳可用資料。",
    )
    return monthly_revenue_result.get("value") or [], monthly_revenue_result.get("audit")


def fetch_institutional_trading_trend(ticker: str) -> dict:
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return {}
    stock_id = _stock_id_from_ticker(ticker)
    start_date = (datetime.now() - timedelta(days=max(INSTITUTIONAL_LOOKBACK_DAYS + 15, 45))).strftime("%Y-%m-%d")
    try:
        df = DataLoader().taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date)
    except Exception:
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
    for _year, year_dates in by_year.items():
        year_dates = sorted(year_dates)
        annual = [date for date in year_dates if date.endswith("12-31")]
        selected.append(annual[-1] if annual else year_dates[-1])
    return sorted(selected)[-5:]


def fetch_finmind_financial_statement_fallback(ticker: str) -> dict:
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
