import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class FakeFinMindLoader:
    api_token = None

    def login_by_token(self, api_token):
        self.api_token = api_token

    def taiwan_stock_institutional_investors(self, stock_id="", start_date="", end_date="", timeout=None, use_async=False, stock_id_list=None):
        return pd.DataFrame([
            {"date": "2026-06-26", "stock_id": "2330", "name": "Foreign_Investor", "buy": 3_000_000, "sell": 1_000_000},
            {"date": "2026-06-26", "stock_id": "2330", "name": "Investment_Trust", "buy": 1_500_000, "sell": 500_000},
            {"date": "2026-06-26", "stock_id": "2308", "name": "Foreign_Investor", "buy": 1_200_000, "sell": 200_000},
            {"date": "2026-06-26", "stock_id": "2308", "name": "Investment_Trust", "buy": 100_000, "sell": 500_000},
        ])

    def taiwan_stock_daily(self, stock_id="", start_date="", end_date="", timeout=None, use_async=False, stock_id_list=None):
        rows = []
        start = date(2026, 6, 1)
        for offset in range(20):
            day = start + timedelta(days=offset)
            rows.append({
                "date": day.isoformat(),
                "stock_id": "2449",
                "close": 50 + offset,
                "Trading_Volume": 1_000_000,
            })
            rows.append({
                "date": day.isoformat(),
                "stock_id": "1101",
                "close": 40,
                "Trading_Volume": 1_000_000,
            })
        rows.append({"date": "2026-06-26", "stock_id": "2449", "close": 95, "Trading_Volume": 8_000_000})
        rows.append({"date": "2026-06-26", "stock_id": "1101", "close": 41, "Trading_Volume": 1_100_000})
        return pd.DataFrame(rows)


def test_scan_taiwan_market_ranks_institutional_and_technical_candidates(monkeypatch):
    import market_screener

    monkeypatch.setattr(market_screener, "FINMIND_API_TOKEN", "test-token")

    result = market_screener.scan_taiwan_market(
        scan_date=date(2026, 6, 26),
        data_loader_cls=FakeFinMindLoader,
        top_n=2,
    )

    by_ticker = {candidate["ticker"]: candidate for candidate in result["candidates"]}
    assert by_ticker["2330.TW"]["category"] == "institutional_accumulation"
    assert by_ticker["2330.TW"]["metrics"]["foreign_net_buy_shares"] == 2_000_000
    assert by_ticker["2449.TW"]["category"] == "technical_heat"
    assert by_ticker["2449.TW"]["metrics"]["volume_ratio"] > 5
    assert by_ticker["2449.TW"]["metrics"]["bias_pct"] > 20


def test_import_screener_candidates_marks_watchlist_items_for_mode_d(monkeypatch, tmp_path):
    import market_screener
    import watchlist_service

    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()

    result = market_screener.import_candidates_to_watchlist([
        {
            "ticker": "2449.TW",
            "category": "technical_heat",
            "reason": "乖離率 28.4%，成交量放大 8.0x",
            "score": 28.4,
            "metrics": {"bias_pct": 28.4, "volume_ratio": 8.0},
            "screen_date": "2026-06-26",
        }
    ])

    assert result["imported_count"] == 1
    item = watchlist_service.list_watchlist()["items"][0]
    assert item["ticker"] == "2449.TW"
    assert item["pipeline"] == "v4"
    assert item["trigger_source"] == "daily_screener"
    assert "Auto-Screener" in item["tags"]
    assert item["triggers"][0]["type"] == "daily_screener"
    assert item["triggers"][0]["screen_date"] == "2026-06-26"


def test_run_daily_market_screener_scans_and_imports(monkeypatch, tmp_path):
    import market_screener
    import watchlist_service

    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()
    monkeypatch.setattr(market_screener, "FINMIND_API_TOKEN", "")

    result = market_screener.run_daily_market_screener(
        now=datetime(2026, 6, 26, 18, 5, tzinfo=watchlist_service.TAIPEI),
        data_loader_cls=FakeFinMindLoader,
        top_n=1,
    )

    assert result["success"] is True
    assert result["screen_date"] == "2026-06-26"
    assert result["imported_count"] == 2
    tickers = {item["ticker"] for item in watchlist_service.list_watchlist()["items"]}
    assert {"2330.TW", "2449.TW"} <= tickers
