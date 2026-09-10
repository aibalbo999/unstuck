"""Exact official exchange endpoint identities for OOS captures."""

from __future__ import annotations

import re
from urllib.parse import urlencode


TICKER_RE = re.compile(r"[0-9A-Z]{4,8}\.(?:TW|TWO)")


def official_url(ticker: str, month: str) -> str:
    if TICKER_RE.fullmatch(ticker) is None:
        raise ValueError("official ticker is invalid")
    try:
        year, month_number = month.split("-")
        valid_month = (
            len(year) == 4
            and len(month_number) == 2
            and year.isdigit()
            and 1 <= int(month_number) <= 12
        )
    except (AttributeError, ValueError):
        valid_month = False
    if not valid_month:
        raise ValueError("official month is invalid")
    symbol, market = ticker.rsplit(".", 1)
    if market == "TW":
        query = urlencode([
            ("response", "json"),
            ("date", f"{year}{month_number}01"),
            ("stockNo", symbol),
        ])
        return f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?{query}"
    query = urlencode([
        ("code", symbol),
        ("date", f"{year}/{month_number}/01"),
        ("response", "json"),
    ])
    return f"https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?{query}"
