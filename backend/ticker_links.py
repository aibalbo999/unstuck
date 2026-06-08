"""Helpers for turning ticker-like autolinks into real quote URLs."""

from __future__ import annotations

import re
from urllib.parse import urlparse


TAIWAN_TICKER_RE = re.compile(r"^(?P<code>\d{4,6})\.(?P<suffix>TW|TWO)$", re.IGNORECASE)


def quote_url_for_ticker(ticker: str) -> str:
    text = str(ticker or "").strip().upper()
    if not TAIWAN_TICKER_RE.match(text):
        return ""
    return f"https://tw.stock.yahoo.com/quote/{text}"


def quote_url_from_autolink_href(href: str) -> str:
    parsed = urlparse(str(href or ""))
    if parsed.scheme not in {"http", "https"} or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return ""
    host = (parsed.hostname or "").upper()
    return quote_url_for_ticker(host)
