"""A listing board cannot consume a bounded industry peer candidate budget."""
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from data_fetch.market_sources import identity, peers
from data_fetch.market_sources.peer_recovery import resolve_legacy_peer_candidates

TODAY = date(2026, 9, 26)
# Actual rejected candidate order in the saved 2254 report. The dated master
# fixture is deliberately reduced; external metrics below are controlled.
BOARD_FIRST_IDS = ["3150", "6645", "6771", "6534", "6854", "6924", "6949", "6951", "2258", "6988"]


def master(stock_id, category):
    return {"stock_id": stock_id, "stock_name": "巨鎧精密-創" if stock_id == "2254" else stock_id,
            "industry_category": category, "type": "twse", "date": TODAY.isoformat()}


def rows(board):
    return [master("2254", board), master("2254", "汽車工業"),
            *(master(stock_id, board) for stock_id in BOARD_FIRST_IDS), master("6605", "汽車工業")]


@pytest.mark.parametrize("board", ["創新板股票", "創新版股票"])
def test_identity_uses_industry_instead_of_listing_board(monkeypatch, board):
    monkeypatch.setattr(identity, "load_taiwan_stock_info_records", lambda: rows(board))
    result = identity.build_company_identity("2254.TW", {"quoteType": "EQUITY"}, "Coplus Inc.")
    assert result["industry_categories"] == [board, "汽車工業"]  # retain source facts
    assert result["same_industry_peers"] == [{"stock_id": "6605", "stock_name": "6605"}]


@pytest.mark.parametrize("board", ["創新板股票", "創新版股票"])
def test_cached_board_first_identity_cannot_displace_real_industry_peers(monkeypatch, board):
    monkeypatch.setattr(peers, "_today", lambda: TODAY)
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: rows(board))
    calls = []
    def quote(ticker):
        calls.append(ticker)
        return type("Quote", (), {"info": {"symbol": ticker, "quoteType": "EQUITY",
            "industry": "Auto Parts" if ticker == "6605.TW" else "Software - Application",
            "priceToBook": 2, "trailingPE": 15}})()
    monkeypatch.setattr(peers.yf, "Ticker", quote)
    monkeypatch.setattr(peers, "fetch_peer_valuation_fallback", lambda *a, **k: pytest.fail("Unexpected fallback"))
    cached_identity = {"same_industry_peers": [{"stock_id": s} for s in [*BOARD_FIRST_IDS, "6605"]]}
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics("2254.TW", "Coplus Inc.", "Consumer Cyclical", "Auto Parts", cached_identity)
    assert calls == ["6605.TW"]
    assert [row["ticker"] for row in result["peers"]] == ["6605.TW"]
    assert result["audit"]["usable_count"] == 1
    assert result["audit"]["current_industry_categories"] == ["汽車工業"]
    assert result["peers"][0]["comparison_status"] == "business_industry_matched"
    assert result["peers"][0]["metrics_status"] == "partial"


@pytest.mark.parametrize("board", ["創新板股票", "創新版股票"])
def test_board_only_master_does_not_invent_an_industry(board):
    selected, audit = resolve_legacy_peer_candidates("2254.TW", {},
        [master("2254", board), master("6605", board)], today=TODAY)
    assert selected == []
    assert audit["selection_status"] == "broad_industry_only"


def test_real_industry_still_requires_business_match_and_caps_downloads(monkeypatch):
    ids = [str(1100 + i) for i in range(15)]
    monkeypatch.setattr(peers, "_today", lambda: TODAY)
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [master("2254", "汽車工業"), *(master(s, "汽車工業") for s in ids)])
    calls = []
    def quote(ticker):
        calls.append(ticker)
        return type("Quote", (), {"info": {"industry": "Auto Manufacturers", "priceToBook": 2, "trailingPE": 15}})()
    monkeypatch.setattr(peers.yf, "Ticker", quote)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics("2254.TW", "Coplus", "", "Auto Parts", {})
    assert len(calls) == 10
    assert result["peers"] == []
    assert result["audit"]["business_industry_rejected_count"] == 10
