"""YFinance enrichment extractors for price ranges, dividends, and events."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

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

def _read_stock_calendar(stock):
    try:
        calendar = getattr(stock, "calendar", None)
        return calendar() if callable(calendar) else calendar
    except Exception:
        return None

def _calendar_value(calendar, labels: tuple[str, ...]):
    if calendar is None:
        return None
    if isinstance(calendar, dict):
        normalized = {_normalized_key(key): value for key, value in calendar.items()}
        for label in labels:
            if label in calendar:
                return calendar[label]
            value = normalized.get(_normalized_key(label))
            if value is not None:
                return value
        return None
    if isinstance(calendar, pd.Series):
        normalized = {_normalized_key(key): value for key, value in calendar.items()}
        for label in labels:
            if label in calendar.index:
                return calendar.loc[label]
            value = normalized.get(_normalized_key(label))
            if value is not None:
                return value
        return None
    if isinstance(calendar, pd.DataFrame):
        for label in labels:
            if label in calendar.index:
                row = calendar.loc[label]
                values = row.tolist() if hasattr(row, "tolist") else [row]
                return _first_present(values)
            if label in calendar.columns:
                values = calendar[label].dropna().tolist()
                return _first_present(values)
        normalized_index = {_normalized_key(key): key for key in calendar.index}
        normalized_columns = {_normalized_key(key): key for key in calendar.columns}
        for label in labels:
            key = normalized_index.get(_normalized_key(label))
            if key is not None:
                row = calendar.loc[key]
                values = row.tolist() if hasattr(row, "tolist") else [row]
                return _first_present(values)
            key = normalized_columns.get(_normalized_key(label))
            if key is not None:
                values = calendar[key].dropna().tolist()
                return _first_present(values)
    return None

def _info_value(info: dict, *keys: str):
    for key in keys:
        value = info.get(key) if isinstance(info, dict) else None
        if value not in (None, "", "N/A"):
            return value
    return None

def _append_calendar_event(events: list[dict], *, event_type: str, label: str, date_value: str, source: str, end_date: str | None = None) -> None:
    if any(item.get("type") == event_type and item.get("date") == date_value for item in events):
        return
    event = {
        "type": event_type,
        "label": label,
        "date": date_value,
        "source": source,
    }
    if end_date and end_date != date_value:
        event["end_date"] = end_date
    events.append(event)

def _date_range(*values) -> tuple[str, str]:
    dates = []
    for value in values:
        dates.extend(_date_values(value))
    dates = sorted(set(dates))
    if not dates:
        return "", ""
    return dates[0], dates[-1]

def _date_value(*values) -> str:
    for value in values:
        dates = _date_values(value)
        if dates:
            return dates[0]
    return ""

def _date_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, pd.Series, pd.Index)):
        dates = []
        for item in value:
            parsed = _parse_date(item)
            if parsed:
                dates.append(parsed)
        return sorted(set(dates))
    parsed = _parse_date(value)
    return [parsed] if parsed else []

def _parse_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return ""
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        try:
            return datetime.fromtimestamp(timestamp).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return ""
    parsed = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.date().isoformat()

def _normalized_key(value) -> str:
    return str(value).strip().lower().replace("-", " ").replace("_", " ")

def _first_present(values):
    for value in values:
        if value not in (None, "", "N/A") and not (isinstance(value, float) and pd.isna(value)):
            return value
    return None
