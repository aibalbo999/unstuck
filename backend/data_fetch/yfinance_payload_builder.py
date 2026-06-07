"""Compatibility facade for legacy yfinance payload helpers.

Production code should import focused modules such as yfinance_snapshot or
yfinance_legacy_fetch directly. This facade keeps older imports working while
the data-fetch package finishes its staged migration.
"""

from __future__ import annotations

from . import yfinance_legacy_fetch as _legacy
from .yfinance_legacy_fetch import async_fetch_stock_data, fetch_stock_data
from .yfinance_snapshot import fetch_stock_data_from_snapshot, fetch_yfinance_snapshot


def __getattr__(name: str):
    return getattr(_legacy, name)
