from __future__ import annotations

import os

import pytest

from news_fetchers import fetch_google_news_rss
from official_financials import fetch_mops_balance_sheet, fetch_twse_institutional_trades


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_FREE_DATA_TESTS") != "1",
    reason="set RUN_LIVE_FREE_DATA_TESTS=1 to call public external sources",
)


def test_google_news_live_returns_standard_shape():
    records = fetch_google_news_rss("台積電", limit=1)

    assert not records or set(records[0]) == {"title", "link", "published_date", "source", "summary"}


def test_twse_institutional_live_is_shaped_or_controlled_none():
    result = fetch_twse_institutional_trades("2330.TW", "2026-06-18")

    assert result is None or {
        "ticker",
        "date",
        "foreign_net",
        "investment_trust_net",
        "dealer_net",
        "total_net",
        "source",
    } <= set(result)


def test_mops_balance_sheet_live_is_shaped_or_controlled_none():
    result = fetch_mops_balance_sheet("2330.TW", 2025, 4)

    assert result is None or {
        "ticker",
        "year",
        "season",
        "statement_scope",
        "unit",
        "source",
        "raw_line_items",
    } <= set(result)
