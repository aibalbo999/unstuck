"""Deprecated package-level stock-data orchestrator compatibility facade."""

from __future__ import annotations

import warnings

from . import core_assembler as _assembler
from .core_assembler import *  # noqa: F401,F403


def _warn_deprecated(name: str) -> None:
    warnings.warn(
        f"data_fetch.orchestrator.{name} is deprecated; use StockDataService/FetchRequest instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def fetch_stock_data(ticker: str, skip_optional_http: bool = False) -> dict:
    _warn_deprecated("fetch_stock_data")
    return _assembler.fetch_stock_data(ticker, skip_optional_http=skip_optional_http)


async def async_fetch_stock_data(ticker: str) -> dict:
    _warn_deprecated("async_fetch_stock_data")
    return await _assembler.async_fetch_stock_data(ticker)


def __getattr__(name: str):
    return getattr(_assembler, name)
