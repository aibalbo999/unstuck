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


class FakeTwseOpenDataSource:
    provider_name = "TWSE Free API"

    def fetch_institutional_frame(self, scan_date):
        return FakeFinMindLoader().taiwan_stock_institutional_investors(
            start_date=scan_date.isoformat(),
            end_date=scan_date.isoformat(),
        )

    def fetch_daily_frame(self, scan_date):
        return FakeFinMindLoader().taiwan_stock_daily(
            start_date=scan_date.isoformat(),
            end_date=scan_date.isoformat(),
        )


class FakeTwseResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeTwseSession:
    def __init__(self):
        self.urls = []

    def get(self, url, **_kwargs):
        self.urls.append(url)
        if "TWT38U" in url:
            return FakeTwseResponse({
                "stat": "OK",
                "date": "20260626",
                "data": [
                    [" ", "2330  ", "台積電", "2,500,000", "500,000", "2,000,000"],
                ],
            })
        if "TWT44U" in url:
            return FakeTwseResponse({
                "stat": "OK",
                "date": "20260626",
                "data": [
                    [" ", "2330  ", "台積電", "1,500,000", "500,000", "1,000,000"],
                ],
            })
        if "STOCK_DAY_AVG_ALL" in url:
            return FakeTwseResponse([
                {"Date": "1150626", "Code": "2449", "MonthlyAveragePrice": "70.00"},
                {"Date": "1150626", "Code": "2317", "MonthlyAveragePrice": "120.00"},
            ])
        return FakeTwseResponse([
            {"Date": "1150626", "Code": "2449", "Name": "京元電子", "ClosingPrice": "95.00", "TradeVolume": "8,000,000"},
            {"Date": "1150626", "Code": "2317", "Name": "鴻海", "ClosingPrice": "0.00", "TradeVolume": "9,000,000"},
        ])


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


def test_scan_taiwan_market_accepts_non_fmp_data_source():
    import market_screener

    result = market_screener.scan_taiwan_market(
        scan_date=date(2026, 6, 26),
        data_source=FakeTwseOpenDataSource(),
        top_n=1,
    )

    assert result["providers"] == ["TWSE Free API"]
    assert result["data_sources"] == ["TWSE Free API"]
    assert result["candidate_count"] == len(result["candidates"])
    assert {candidate["ticker"] for candidate in result["candidates"]} == {"2330.TW", "2449.TW"}


def test_scan_taiwan_market_uses_free_source_when_finmind_is_disabled():
    import market_screener

    sources = market_screener._resolve_data_sources(data_loader_cls=None)

    assert [source.provider_name for source in sources] == ["TWSE Free API"]


def test_twse_free_data_source_parses_free_market_payloads():
    import market_screener

    data_source = market_screener.TwseFreeScreenerDataSource(session=FakeTwseSession())
    result = market_screener.scan_taiwan_market(
        scan_date=date(2026, 6, 26),
        data_source=data_source,
        top_n=1,
    )

    by_ticker = {candidate["ticker"]: candidate for candidate in result["candidates"]}
    assert result["providers"] == ["TWSE Free API"]
    assert by_ticker["2330.TW"]["company_name"] == "台積電"
    assert by_ticker["2330.TW"]["metrics"]["investment_trust_net_buy_shares"] == 1_000_000
    assert by_ticker["2449.TW"]["company_name"] == "京元電子"
    assert by_ticker["2449.TW"]["metrics"]["bias_pct"] > 30
    assert "2317.TW" not in by_ticker


def test_import_screener_candidates_marks_watchlist_items_for_mode_d(monkeypatch, tmp_path):
    import market_screener
    import watchlist_service

    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()

    result = market_screener.import_candidates_to_watchlist([
        {
            "ticker": "2449.TW",
            "company_name": "京元電子",
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
    assert item["triggers"][0]["company_name"] == "京元電子"
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
