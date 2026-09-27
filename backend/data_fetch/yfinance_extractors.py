"""Small yfinance/FinMind extraction helpers for legacy payload assembly."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from collections import Counter
import math
import time
from uuid import uuid4

import pandas as pd

from .yfinance_enrichment_extractors import extract_dividend_history, extract_event_calendar, extract_price_history_ranges
from runtime_events import emit_log
from .market_sources.taiwan import (
    DataLoader,
    _align_finmind_history,
    _history_has_values,
    fetch_finmind_financial_statement_fallback,
    audited_finmind_financial_statement_fallback,
)
from source_audit import audited_fetch
from provider_correlation import current_correlation
from .financial_statement_observation import observe_financial_statements


def _financial_period_key(value):
    """Require a real statement end date; a year label alone cannot join tables."""
    if isinstance(value, (date, datetime)) and not pd.isna(value):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str) and len(value) >= 10 and value[4] == value[7] == "-":
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            pass
    return None


def _financial_number(value):
    if value is None or pd.api.types.is_bool(value) or pd.isna(value):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _financial_billions(value):
    number = _financial_number(value)
    return round(number / 1e9, 2) if number is not None else None


def _reported_free_cash_flow(cashflow, column):
    """Use one finite numeric reported total; do not infer missing components."""
    if list(cashflow.index).count("Free Cash Flow") != 1:
        return None
    value = cashflow.loc["Free Cash Flow", column]
    if not pd.api.types.is_number(value) or pd.api.types.is_bool(value):
        return None
    try:
        return _financial_billions(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _store_financial_period(mapping, period, value):
    if period is not None:
        # Two representations of the same date are ambiguous, never last-wins.
        mapping[period] = None if period in mapping else value


def _reproject_retained_history(original_years, periods, original_values, final_years, final_periods, fallback_values):
    if not _history_has_values(original_values):
        return fallback_values
    if len(original_values) != len(periods) or len(periods) != len(original_years):
        return [None] * len(final_years)
    original_counts, final_counts = Counter(map(str, original_years)), Counter(map(str, final_years))
    by_period = {(str(year), period): value for year, period, value in zip(original_years, periods, original_values)
               if period and str(year) == period[:4] and original_counts[str(year)] == 1}
    return [by_period.get((str(year), period)) if period and final_counts[str(year)] == 1 else None
            for year, period in zip(final_years, final_periods)]


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


def extract_financial_histories(stock, ticker: str, data_source_notes: list, data_loader_cls=DataLoader, *, quote_type: str = "") -> dict:
    if str(quote_type).upper() in {"ETF", "MUTUALFUND"}:
        return {**{key: [] for key in ("years", "revenue_history", "net_income_history", "gross_profit_history",
                                      "operating_income_history", "fcf_history", "total_assets_history", "total_equity_history")},
                "finmind_financial_fallback_audit": None, "primary_financial_audit": None}
    revenue_history = []
    net_income_history = []
    gross_profit_history = []
    operating_income_history = []
    fcf_history = []
    total_assets_history = []
    total_equity_history = []
    years = []
    income_periods = []
    reported_fcf_periods = set()
    finmind_financial_fallback_audit = None
    primary_started_at = time.time()
    primary_metadata = {**current_correlation(), "ticker": ticker, "operation_id": uuid4().hex}
    primary_metadata.pop("attempt_id", None)
    primary_tables = {}
    primary_errors = {}

    try:
        financials = stock.financials
        primary_tables["financials"] = financials
        if financials is not None and not financials.empty:
            for col in financials.columns[:5]:
                year = col.year if hasattr(col, "year") else str(col)[:4]
                years.append(str(year))
                income_periods.append(_financial_period_key(col))
                rev = financials.loc["Total Revenue", col] if "Total Revenue" in financials.index else None
                ni = financials.loc["Net Income", col] if "Net Income" in financials.index else None
                gp = financials.loc["Gross Profit", col] if "Gross Profit" in financials.index else None
                oi = financials.loc["Operating Income", col] if "Operating Income" in financials.index else None
                revenue_history.append(_financial_billions(rev))
                net_income_history.append(_financial_billions(ni))
                gross_profit_history.append(_financial_billions(gp))
                operating_income_history.append(_financial_billions(oi))
            years = list(reversed(years))
            income_periods = list(reversed(income_periods))
            revenue_history = list(reversed(revenue_history))
            net_income_history = list(reversed(net_income_history))
            gross_profit_history = list(reversed(gross_profit_history))
            operating_income_history = list(reversed(operating_income_history))
    except Exception as e:
        primary_errors["financials"] = type(e).__name__
        emit_log(f"    ⚠️  財務報表獲取失敗：{e}")

    fcf_history = [None] * len(income_periods)
    total_assets_history = [None] * len(income_periods)
    total_equity_history = [None] * len(income_periods)
    try:
        cashflow = stock.cashflow
        primary_tables["cashflow"] = cashflow
        if cashflow is not None and not cashflow.empty:
            fcf_by_period = {}
            for col in cashflow.columns:
                period = _financial_period_key(col)
                ocf = cashflow.loc["Operating Cash Flow", col] if "Operating Cash Flow" in cashflow.index else None
                capex_val = cashflow.loc["Capital Expenditure", col] if "Capital Expenditure" in cashflow.index else None
                ocf_val, capex_val_f = _financial_number(ocf), _financial_number(capex_val)
                fcf = round(ocf_val / 1e9 + capex_val_f / 1e9, 2) if ocf_val is not None and capex_val_f is not None else None
                if fcf is None and period is not None:
                    fcf = _reported_free_cash_flow(cashflow, col)
                    if fcf is not None:
                        reported_fcf_periods.add(period)
                _store_financial_period(fcf_by_period, period, fcf)
            fcf_history = [fcf_by_period.get(period) for period in income_periods]
    except Exception as e:
        primary_errors["cashflow"] = type(e).__name__
        emit_log(f"    ⚠️  現金流數據獲取失敗：{e}")

    # A candidate rejected by period ambiguity or a table error was not used.
    reported_fcf_periods.intersection_update(
        period for period, value in zip(income_periods, fcf_history) if value is not None
    )

    try:
        balance = stock.balance_sheet
        primary_tables["balance_sheet"] = balance
        if balance is not None and not balance.empty:
            equity_by_period = {}
            assets_by_period = {}
            for col in balance.columns[:5]:
                period = _financial_period_key(col)
                eq = balance.loc["Stockholders Equity", col] if "Stockholders Equity" in balance.index else (
                    balance.loc["Total Equity Gross Minority Interest", col] if "Total Equity Gross Minority Interest" in balance.index else None)
                ta = balance.loc["Total Assets", col] if "Total Assets" in balance.index else None
                _store_financial_period(equity_by_period, period, _financial_billions(eq))
                _store_financial_period(assets_by_period, period, _financial_billions(ta))
            total_equity_history = [equity_by_period.get(period) for period in income_periods]
            total_assets_history = [assets_by_period.get(period) for period in income_periods]
    except Exception as e:
        primary_errors["balance_sheet"] = type(e).__name__
        emit_log(f"    ⚠️  資產負債表獲取失敗：{e}")

    primary_histories = {
        "years": years, "revenue_history": revenue_history, "net_income_history": net_income_history,
        "gross_profit_history": gross_profit_history, "operating_income_history": operating_income_history,
        "fcf_history": fcf_history, "total_assets_history": total_assets_history,
        "total_equity_history": total_equity_history,
    }
    primary_financial_audit = observe_financial_statements(
        tables=primary_tables, errors=primary_errors, metadata=primary_metadata,
        started_at=primary_started_at, finished_at=time.time(),
        histories=primary_histories,
    )

    fallback_reanchored = False
    final_periods = income_periods
    if data_loader_cls is not None and (ticker.endswith(".TW") or ticker.endswith(".TWO")):
        needs_finmind_fallback = (
            not _history_has_values(revenue_history)
            or not _history_has_values(net_income_history)
            or not _history_has_values(total_assets_history)
            or not _history_has_values(total_equity_history)
            or not _history_has_values(fcf_history)
        )
        if needs_finmind_fallback:
            finmind_fallback_result = audited_finmind_financial_statement_fallback(
                ticker, fetcher=fetch_finmind_financial_statement_fallback, audit_fetch=audited_fetch,
            )
            finmind_fallback = finmind_fallback_result.get("value") or {}
            finmind_financial_fallback_audit = finmind_fallback_result.get("audit")

            if finmind_fallback:
                fallback_years = finmind_fallback.get("years", []) or []
                rows_by_year = finmind_fallback.get("rows_by_year", {}) or {}
                if not years or not _history_has_values(revenue_history) or not _history_has_values(net_income_history):
                    years = fallback_years
                    final_periods = [_financial_period_key(rows_by_year.get(str(year), {}).get("statement_date"))
                                     for year in years]
                    fallback_reanchored = True
                final_counts = Counter(map(str, years))
                rows_by_year = {str(year): rows_by_year[str(year)] for year, period in zip(years, final_periods)
                                if period and period[:4] == str(year) and final_counts[str(year)] == 1
                                and _financial_period_key(rows_by_year.get(str(year), {}).get("statement_date")) == period}
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

    if fallback_reanchored:
        # Keep the existing fallback fill policy. Only reindex primary values
        # that it retained; new/ambiguous years stay missing, without refetching.
        aligned = {key: _reproject_retained_history(primary_histories["years"], income_periods,
                   primary_histories[key], years, final_periods, values) for key, values in {
            "revenue_history": revenue_history, "net_income_history": net_income_history,
            "gross_profit_history": gross_profit_history, "operating_income_history": operating_income_history,
            "fcf_history": fcf_history, "total_assets_history": total_assets_history,
            "total_equity_history": total_equity_history,
        }.items()}
        revenue_history, net_income_history = aligned["revenue_history"], aligned["net_income_history"]
        gross_profit_history, operating_income_history = aligned["gross_profit_history"], aligned["operating_income_history"]
        fcf_history = aligned["fcf_history"]
        total_assets_history, total_equity_history = aligned["total_assets_history"], aligned["total_equity_history"]

    used_reported_periods = sorted({period for period, value in zip(final_periods, fcf_history)
                                    if period in reported_fcf_periods and value is not None})
    if used_reported_periods:
        data_source_notes.append(
            "yfinance 現金流分項仍不足；" + "、".join(used_reported_periods)
            + " 已採用同一現金流報表、相同截止日的原始 Free Cash Flow 欄位，未補推營業現金流或資本支出。"
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
        "primary_financial_audit": primary_financial_audit,
    }


def fetch_monthly_revenue_records(ticker: str, data_loader_cls=DataLoader) -> tuple[list, dict | None]:
    recent_monthly_revenue = []
    monthly_revenue_audit = None
    if not (ticker.endswith(".TW") or ticker.endswith(".TWO")) or data_loader_cls is None:
        return recent_monthly_revenue, monthly_revenue_audit

    def fetch_records():
        fm_dl = data_loader_cls()
        fm_stock_id = ticker.replace(".TWO", "").replace(".TW", "")
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
