"""Stock payload cache write boundary."""

from __future__ import annotations

from .cache_helpers import _cache_financial_data


def cache_financial_payload(data: dict, original_ticker: str) -> None:
    _cache_financial_data(data, original_ticker)
