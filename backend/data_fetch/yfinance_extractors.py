"""Small yfinance/FinMind extraction helpers for legacy payload assembly."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from runtime_events import emit_log
from .market_sources.taiwan import (
    DataLoader,
    _align_finmind_history,
    _history_has_values,
    fetch_finmind_financial_statement_fallback,
)
from source_audit import audited_fetch


def extract_price_history(stock) -> dict:
    price_history = {}
    try:
        hist = stock.history(period="1y")
        if not hist.empty:
            # Use the last real trading day in each month; avoid future month-end labels.
            monthly = hist.groupby(pd.Grouper(freq="ME")).tail(1)
            today = datetime.now().date()
            monthly = monthly[[d.date() <= today for d in monthly.index]]
            price_history = {
                "dates": [str(d.date()) for d in monthly.index[-12:]],
                "prices": [round(p, 2) for p in monthly["Close"].tolist()[-12:]],
            }
    except Exception:
        pass
    return price_history


def extract_financial_histories(stock, ticker: str, data_source_notes: list, data_loader_cls=DataLoader) -> dict:
    revenue_history = []
    net_income_history = []
    gross_profit_history = []
    operating_income_history = []
    fcf_history = []
    total_assets_history = []
    total_equity_history = []
    years = []
    finmind_financial_fallback_audit = None

    try:
        financials = stock.financials
        if financials is not None and not financials.empty:
            for col in financials.columns[:5]:
                year = col.year if hasattr(col, "year") else str(col)[:4]
                years.append(str(year))
                rev = financials.loc["Total Revenue", col] if "Total Revenue" in financials.index else None
                ni = financials.loc["Net Income", col] if "Net Income" in financials.index else None
                gp = financials.loc["Gross Profit", col] if "Gross Profit" in financials.index else None
                oi = financials.loc["Operating Income", col] if "Operating Income" in financials.index else None
                revenue_history.append(round(float(rev) / 1e9, 2) if rev and not pd.isna(rev) else None)
                net_income_history.append(round(float(ni) / 1e9, 2) if ni and not pd.isna(ni) else None)
                gross_profit_history.append(round(float(gp) / 1e9, 2) if gp and not pd.isna(gp) else None)
                operating_income_history.append(round(float(oi) / 1e9, 2) if oi and not pd.isna(oi) else None)
            years = list(reversed(years))
            revenue_history = list(reversed(revenue_history))
            net_income_history = list(reversed(net_income_history))
            gross_profit_history = list(reversed(gross_profit_history))
            operating_income_history = list(reversed(operating_income_history))
    except Exception as e:
        emit_log(f"    ⚠️  財務報表獲取失敗：{e}")

    try:
        cashflow = stock.cashflow
        if cashflow is not None and not cashflow.empty:
            fcf_by_year = {}
            for col in cashflow.columns:
                yr_key = str(col.year if hasattr(col, "year") else str(col)[:4])
                ocf = cashflow.loc["Operating Cash Flow", col] if "Operating Cash Flow" in cashflow.index else None
                capex_val = cashflow.loc["Capital Expenditure", col] if "Capital Expenditure" in cashflow.index else None
                ocf_val = float(ocf) / 1e9 if ocf is not None and not pd.isna(ocf) else None
                capex_val_f = float(capex_val) / 1e9 if capex_val is not None and not pd.isna(capex_val) else 0
                fcf_by_year[yr_key] = round(ocf_val + capex_val_f, 2) if ocf_val is not None else None
            fcf_history = [fcf_by_year.get(y, None) for y in years]
    except Exception as e:
        emit_log(f"    ⚠️  現金流數據獲取失敗：{e}")

    try:
        balance = stock.balance_sheet
        if balance is not None and not balance.empty:
            equity_raw = []
            assets_raw = []
            for col in balance.columns[:5]:
                eq = balance.loc["Stockholders Equity", col] if "Stockholders Equity" in balance.index else (
                    balance.loc["Total Equity Gross Minority Interest", col] if "Total Equity Gross Minority Interest" in balance.index else None)
                ta = balance.loc["Total Assets", col] if "Total Assets" in balance.index else None
                equity_raw.append(round(float(eq) / 1e9, 2) if eq and not pd.isna(eq) else None)
                assets_raw.append(round(float(ta) / 1e9, 2) if ta and not pd.isna(ta) else None)
            total_equity_history = list(reversed(equity_raw))
            total_assets_history = list(reversed(assets_raw))
    except Exception as e:
        emit_log(f"    ⚠️  資產負債表獲取失敗：{e}")

    if data_loader_cls is not None and (ticker.endswith(".TW") or ticker.endswith(".TWO")):
        needs_finmind_fallback = (
            not _history_has_values(revenue_history)
            or not _history_has_values(net_income_history)
            or not _history_has_values(total_assets_history)
            or not _history_has_values(total_equity_history)
            or not _history_has_values(fcf_history)
        )
        if needs_finmind_fallback:
            finmind_fallback_result = audited_fetch(
                "financial_statements",
                "FinMind financial statement fallback",
                fetch_finmind_financial_statement_fallback,
                (ticker,),
                default={},
                unavailable_message="FinMind 財報備援未回傳可用年度資料。",
            )
            finmind_fallback = finmind_fallback_result.get("value") or {}
            finmind_financial_fallback_audit = finmind_fallback_result.get("audit")

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

    return {
        "years": years,
        "revenue_history": revenue_history,
        "net_income_history": net_income_history,
        "gross_profit_history": gross_profit_history,
        "operating_income_history": operating_income_history,
        "fcf_history": fcf_history,
        "total_assets_history": total_assets_history,
        "total_equity_history": total_equity_history,
        "finmind_financial_fallback_audit": finmind_financial_fallback_audit,
    }


def fetch_monthly_revenue_records(ticker: str, data_loader_cls=DataLoader) -> tuple[list, dict | None]:
    recent_monthly_revenue = []
    monthly_revenue_audit = None
    if not (ticker.endswith(".TW") or ticker.endswith(".TWO")) or data_loader_cls is None:
        return recent_monthly_revenue, monthly_revenue_audit

    def fetch_records():
        fm_dl = data_loader_cls()
        fm_stock_id = ticker.replace(".TW", "").replace(".TWO", "")
        start_date = (datetime.now() - timedelta(days=240)).strftime("%Y-%m-%d")
        df_rev = fm_dl.taiwan_stock_month_revenue(stock_id=fm_stock_id, start_date=start_date)
        records = []
        if not df_rev.empty:
            recent_df = df_rev.tail(6)
            for _, row in recent_df.iterrows():
                rm_year = row.get("revenue_year")
                rm_month = row.get("revenue_month")
                rm_val = row.get("revenue")
                if rm_year and rm_month and rm_val:
                    val_yi = float(rm_val) / 1e8
                    records.append(f"{rm_year}年{rm_month}月: NT${val_yi:.2f}億")
        return records

    monthly_revenue_result = audited_fetch(
        "monthly_revenue",
        "FinMind TaiwanStockMonthRevenue",
        fetch_records,
        default=[],
        unavailable_message="FinMind 月營收未回傳可用資料。",
    )
    return monthly_revenue_result.get("value") or [], monthly_revenue_result.get("audit")
