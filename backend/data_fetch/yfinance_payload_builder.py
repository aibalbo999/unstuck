"""Compatibility facade for yfinance payload helpers.

Production code should import focused modules such as yfinance_snapshot or
yfinance_core_fetch directly. This facade keeps older imports working while
the data-fetch package finishes its staged migration.
"""

from __future__ import annotations

from . import yfinance_core_fetch as _core
from .yfinance_core_fetch import async_fetch_stock_data, fetch_stock_data
from .yfinance_snapshot import fetch_stock_data_from_snapshot, fetch_yfinance_snapshot


def __getattr__(name: str):
    return getattr(_core, name)
