"""YFinance snapshot fetch and snapshot-to-payload adapter."""

from __future__ import annotations

import time

from .audit_helpers import _append_source_fetch_audit
from .market_sources.ticker_resolver import get_market_data_provider
from .yfinance_error_payload import build_fetch_error_payload


class InvalidTickerError(RuntimeError):
    pass


def fetch_yfinance_snapshot(ticker: str) -> dict:
    """Resolve ticker and collect raw yfinance objects for downstream assembly."""
    ticker = str(ticker or "").strip().upper()
    provider = get_market_data_provider(ticker)
    stock, info, is_valid, resolved_ticker, attempts = provider.resolve_stock(ticker)
    return {
        "kind": "yfinance_snapshot",
        "original_ticker": ticker,
        "ticker": str(resolved_ticker or ticker).strip().upper() if is_valid else ticker,
        "stock": stock,
        "info": info or {},
        "is_valid": bool(is_valid),
        "resolved_ticker": str(resolved_ticker or ticker).strip().upper(),
        "attempts": list(attempts or []),
        "provider_name": getattr(provider, "name", provider.__class__.__name__),
    }


class SnapshotMarketDataProvider:
    """Adapter matching the market-data provider resolve_stock protocol."""

    def __init__(self, snapshot: dict):
        self.snapshot = snapshot or {}
        self.name = str(self.snapshot.get("provider_name") or "yfinance")

    def resolve_stock(self, ticker: str):
        snapshot = self.snapshot
        return (
            snapshot.get("stock"),
            snapshot.get("info") or {},
            bool(snapshot.get("is_valid", True)),
            str(snapshot.get("resolved_ticker") or snapshot.get("ticker") or ticker).strip().upper(),
            list(snapshot.get("attempts") or [{"ticker": ticker, "valid": bool(snapshot.get("is_valid", True))}]),
        )


def fetch_stock_data_from_snapshot(snapshot: dict, skip_optional_http: bool = False) -> dict:
    """Assemble a legacy-compatible payload from a pre-resolved yfinance snapshot."""
    from .yfinance_core_fetch import fetch_stock_data

    snapshot = snapshot or {}
    original_ticker = str(snapshot.get("original_ticker") or snapshot.get("ticker") or "").strip().upper()
    if not bool(snapshot.get("is_valid", True)):
        now = time.time()
        return build_fetch_error_payload(
            original_ticker,
            InvalidTickerError(f"yfinance 無法驗證股票代號：{original_ticker}"),
            fetch_started_epoch=now,
            finished_at_epoch=now,
            append_source_fetch_audit=_append_source_fetch_audit,
        )
    return fetch_stock_data(
        original_ticker,
        skip_optional_http=skip_optional_http,
        market_data_provider=SnapshotMarketDataProvider(snapshot),
    )
