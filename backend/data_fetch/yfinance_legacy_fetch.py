"""Deprecated compatibility facade for yfinance core fetch helpers."""

from __future__ import annotations

import warnings

from . import yfinance_core_fetch as _core
from .yfinance_core_fetch import *  # noqa: F401,F403


def _warn_deprecated(name: str) -> None:
    warnings.warn(
        f"data_fetch.yfinance_legacy_fetch.{name} is deprecated; use data_fetch.yfinance_core_fetch instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def fetch_stock_data(ticker: str, skip_optional_http: bool = False, market_data_provider=None) -> dict:
    _warn_deprecated("fetch_stock_data")
    return _core.fetch_stock_data(ticker, skip_optional_http=skip_optional_http, market_data_provider=market_data_provider)


async def async_fetch_stock_data(ticker: str) -> dict:
    _warn_deprecated("async_fetch_stock_data")
    return await _core.async_fetch_stock_data(ticker)


def __getattr__(name: str):
    return getattr(_core, name)
