"""YFinance enrichment extractors for price ranges, dividends, and events."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from .yfinance_calendar_extractors import (
    append_calendar_event as _append_calendar_event,
    calendar_value as _calendar_value,
    date_range as _date_range,
    date_value as _date_value,
    info_value as _info_value,
    read_stock_calendar as _read_stock_calendar,
)


def extract_price_history_ranges(stock) -> dict:
    try:
        hist = stock.history(period="5y")
        if hist is None or hist.empty or "Close" not in hist:
            return {}
        frame = hist[["Close"]].dropna()
        today = datetime.now().date()
        frame = frame[[index.date() <= today for index in frame.index]]
        if frame.empty:
            return {}
        ranges = {}
        for key, label, days in (
            ("1m", "1M", 30),
            ("3m", "3M", 90),
            ("6m", "6M", 180),
            ("1y", "1Y", 365),
            ("3y", "3Y", 365 * 3),
            ("5y", "5Y", 365 * 5 + 31),
        ):
            entry = _price_range_entry(frame, label=label, days=days, today=today)
            if entry:
                ranges[key] = entry
        return {"ranges": ranges, "source": "yfinance 5y history"} if ranges else {}
    except Exception:
        return {}


def _price_range_entry(frame: pd.DataFrame, *, label: str, days: int, today: date) -> dict:
    start = today - timedelta(days=days)
    scoped = frame[[index.date() >= start for index in frame.index]]
    if len(scoped) < 2:
        scoped = frame.tail(2)
    if len(scoped) < 2:
        return {}
    sampled = _sample_price_frame(scoped)
    prices = [round(float(price), 4) for price in sampled["Close"].tolist()]
    dates = [str(index.date()) for index in sampled.index]
    return_pct = round((prices[-1] / prices[0] - 1) * 100, 2) if prices[0] else None
    return {
        "label": label,
        "dates": dates,
        "prices": prices,
        "return_pct": return_pct,
    }


def _sample_price_frame(frame: pd.DataFrame, max_points: int = 90) -> pd.DataFrame:
    if len(frame) <= max_points:
        return frame
    last = len(frame) - 1
    positions = sorted({round(index * last / (max_points - 1)) for index in range(max_points)})
    return frame.iloc[positions]


def extract_dividend_history(stock) -> dict:
    dividend_history = {}
    try:
        dividends = getattr(stock, "dividends", None)
        if dividends is None or dividends.empty:
            return {}
        series = dividends.dropna()
        today = datetime.now().date()
        series = series[[index.date() <= today for index in series.index]]
        if series.empty:
            return {}
        annual = series.groupby(series.index.year).sum().tail(5)
        records = [
            {"date": str(index.date()), "amount": round(float(amount), 4)}
            for index, amount in series.tail(20).items()
        ]
        dividend_history = {
            "years": [str(year) for year in annual.index],
            "dividends": [round(float(amount), 4) for amount in annual.tolist()],
            "records": records,
            "source": "yfinance dividends",
        }
    except Exception:
        pass
    return dividend_history


def extract_event_calendar(stock, info: dict) -> dict:
    events = []
    calendar = _read_stock_calendar(stock)

    earnings_start, earnings_end = _date_range(
        _calendar_value(calendar, ("Earnings Date", "Earnings Date Start")),
        _info_value(info, "earningsTimestampStart", "earningsTimestamp"),
        _info_value(info, "earningsTimestampEnd"),
    )
    if earnings_start:
        _append_calendar_event(
            events,
            event_type="earnings_date",
            label="財報日",
            date_value=earnings_start,
            end_date=earnings_end,
            source="yfinance calendar" if calendar else "yfinance info",
        )

    ex_dividend_date = _date_value(
        _calendar_value(calendar, ("Ex-Dividend Date", "Ex Dividend Date")),
        _info_value(info, "exDividendDate"),
    )
    if ex_dividend_date:
        _append_calendar_event(
            events,
            event_type="ex_dividend_date",
            label="除息日",
            date_value=ex_dividend_date,
            source="yfinance calendar" if _calendar_value(calendar, ("Ex-Dividend Date", "Ex Dividend Date")) else "yfinance info",
        )

    dividend_pay_date = _date_value(_info_value(info, "dividendDate"))
    if dividend_pay_date:
        _append_calendar_event(
            events,
            event_type="dividend_pay_date",
            label="股利發放日",
            date_value=dividend_pay_date,
            source="yfinance info",
        )

    most_recent_quarter = _date_value(_info_value(info, "mostRecentQuarter"))
    if most_recent_quarter:
        _append_calendar_event(
            events,
            event_type="most_recent_quarter",
            label="最近財報季度",
            date_value=most_recent_quarter,
            source="yfinance info",
        )

    next_fiscal_year_end = _date_value(_info_value(info, "nextFiscalYearEnd"))
    if next_fiscal_year_end:
        _append_calendar_event(
            events,
            event_type="fiscal_year_end",
            label="會計年度結束",
            date_value=next_fiscal_year_end,
            source="yfinance info",
        )

    if not events:
        return {}
    return {
        "as_of_date": datetime.now().date().isoformat(),
        "events": events,
    }
