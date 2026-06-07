"""Ticker resolution through market-specific yfinance providers."""

from __future__ import annotations

import yfinance as yf

from .identity import is_taiwan_ticker


class MarketDataProvider:
    name = "yfinance"

    def supports(self, ticker: str) -> bool:
        return True

    def ticker_candidates(self, ticker: str) -> list[str]:
        return [str(ticker or "").strip().upper()]

    def get_valid_info(self, ticker: str):
        stock = yf.Ticker(ticker)
        info = stock.info
        valid = "currentPrice" in info or "regularMarketPrice" in info or "previousClose" in info
        return stock, info, valid

    def resolve_stock(self, ticker: str):
        attempts = []
        last_stock = None
        last_info = {}
        normalized = str(ticker or "").strip().upper()
        for candidate in self.ticker_candidates(normalized):
            stock, info, valid = self.get_valid_info(candidate)
            attempts.append({"ticker": candidate, "valid": bool(valid)})
            last_stock = stock
            last_info = info
            if valid:
                return stock, info, True, candidate, attempts
        return last_stock, last_info, False, normalized, attempts


class USStockProvider(MarketDataProvider):
    name = "us_yfinance"


class TaiwanStockProvider(MarketDataProvider):
    name = "taiwan_yfinance_finmind"

    def supports(self, ticker: str) -> bool:
        return is_taiwan_ticker(ticker)

    def ticker_candidates(self, ticker: str) -> list[str]:
        normalized = str(ticker or "").strip().upper()
        candidates = [normalized]
        if normalized.endswith(".TW"):
            candidates.append(normalized.replace(".TW", ".TWO"))
        elif normalized.endswith(".TWO"):
            candidates.append(normalized.replace(".TWO", ".TW"))
        elif normalized.isdigit() and len(normalized) == 4:
            candidates.extend([f"{normalized}.TW", f"{normalized}.TWO"])
        return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def get_market_data_provider(ticker: str) -> MarketDataProvider:
    providers: list[MarketDataProvider] = [TaiwanStockProvider(), USStockProvider()]
    for provider in providers:
        if provider.supports(str(ticker or "").strip().upper()):
            return provider
    return USStockProvider()
