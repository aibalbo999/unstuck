"""Global market context helpers for optional report enrichment."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

import yfinance as yf


TECH_PROXY_SYMBOLS = (
    ("SPY", "S&P 500 ETF", "us_broad"),
    ("QQQ", "Nasdaq 100 ETF", "us_growth"),
    ("^VIX", "CBOE Volatility Index", "volatility"),
    ("SMH", "VanEck Semiconductor ETF", "semiconductors_ai"),
    ("NVDA", "NVIDIA", "semiconductors_ai"),
    ("AMD", "AMD", "semiconductors_ai"),
    ("AVGO", "Broadcom", "semiconductors_ai"),
    ("TSM", "TSMC ADR", "semiconductors_ai"),
    ("ASML", "ASML", "semiconductors_ai"),
    ("TWD=X", "USD/TWD", "fx"),
)

BROAD_PROXY_SYMBOLS = (
    ("SPY", "S&P 500 ETF", "us_broad"),
    ("QQQ", "Nasdaq 100 ETF", "us_growth"),
    ("^VIX", "CBOE Volatility Index", "volatility"),
    ("TWD=X", "USD/TWD", "fx"),
)

TECH_KEYWORDS = (
    "semiconductor",
    "ai",
    "server",
    "cooling",
    "foundry",
    "ic design",
    "networking",
    "pcb",
    "electronics",
    "半導體",
    "伺服器",
    "散熱",
    "晶圓",
)


def infer_global_market_symbols(sector: str = "", industry: str = "") -> tuple[tuple[str, str, str], ...]:
    signature = f"{sector} {industry}".lower()
    if any(keyword.lower() in signature for keyword in TECH_KEYWORDS):
        return TECH_PROXY_SYMBOLS
    return BROAD_PROXY_SYMBOLS


def fetch_global_market_context(
    ticker: str,
    company_name: str = "",
    sector: str = "",
    industry: str = "",
    *,
    symbols: Sequence[tuple[str, str, str]] | None = None,
    lookback_days: int = 5,
) -> dict:
    selected = tuple(symbols or infer_global_market_symbols(sector, industry))
    items = []
    coverage_notes = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    for symbol, label, category in selected:
        item = _market_proxy_item(symbol, label, category, lookback_days=lookback_days, fetched_at=fetched_at)
        if item:
            items.append(item)
        else:
            coverage_notes.append(f"{symbol} 無可用市場脈絡資料。")
    return {
        "as_of": fetched_at,
        "lookback_days": int(lookback_days),
        "target_ticker": str(ticker or "").strip().upper(),
        "target_company": str(company_name or "").strip(),
        "items": items,
        "coverage_notes": coverage_notes[:6],
    }


def _market_proxy_item(symbol: str, label: str, category: str, *, lookback_days: int, fetched_at: str) -> dict:
    try:
        history = yf.Ticker(symbol).history(period=f"{max(2, int(lookback_days))}d")
    except Exception:
        return {}
    closes = []
    try:
        close_series = history["Close"].dropna()
        closes = [float(value) for value in close_series.tolist()]
    except Exception:
        closes = []
    if not closes:
        return {}
    latest = closes[-1]
    previous = closes[-2] if len(closes) >= 2 else None
    first = closes[0]
    return {
        "symbol": symbol,
        "label": label,
        "category": category,
        "latest": round(latest, 4),
        "change_1d_pct": _pct_change(previous, latest),
        "change_5d_pct": _pct_change(first, latest),
        "source": "yfinance",
        "fetched_at": fetched_at,
    }


def _pct_change(start: float | None, end: float | None) -> float | None:
    if not start or end is None:
        return None
    return round((float(end) / float(start) - 1.0) * 100.0, 4)
