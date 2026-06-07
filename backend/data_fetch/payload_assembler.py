"""Deprecated compatibility shim for core stock-data payload assembly.

Production code should use StockDataService/FetchRequest. Tests that need
low-level implementation seams should import data_fetch.core_assembler.
"""

from __future__ import annotations

import warnings

from . import core_assembler as _core
from .core_assembler import *  # noqa: F401,F403
from .service import StockDataService
from .types import FetchRequest


def _warn_deprecated(name: str) -> None:
    warnings.warn(
        f"data_fetch.payload_assembler.{name} is deprecated; use StockDataService/FetchRequest instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def fetch_stock_data(ticker: str, skip_optional_http: bool = False) -> dict:
    _warn_deprecated("fetch_stock_data")
    request = FetchRequest.from_ticker(ticker, skip_optional_http=skip_optional_http)
    return StockDataService().fetch(request).data


async def async_fetch_stock_data(ticker: str) -> dict:
    _warn_deprecated("async_fetch_stock_data")
    return (await StockDataService().fetch_async(FetchRequest.from_ticker(ticker))).data


def __getattr__(name: str):
    return getattr(_core, name)
