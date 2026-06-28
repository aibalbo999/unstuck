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


class FakeRichScreenerDataSource:
    provider_name = "Rich Test Source"

    def __init__(self):
        self.calls = 0

    def fetch_institutional_frame(self, scan_date):
        self.calls += 1
        return pd.DataFrame([
            {"date": "2026-06-26", "stock_id": "2330", "company_name": "台積電", "name": "Foreign_Investor", "buy": 3_000_000, "sell": 500_000},
            {"date": "2026-06-26", "stock_id": "2330", "company_name": "台積電", "name": "Investment_Trust", "buy": 1_200_000, "sell": 200_000},
            {"date": "2026-06-26", "stock_id": "2330", "company_name": "台積電", "name": "Dealer", "buy": 800_000, "sell": 200_000},
            {"date": "2026-06-26", "stock_id": "2449", "company_name": "京元電子", "name": "Foreign_Investor", "buy": 900_000, "sell": 100_000},
            {"date": "2026-06-26", "stock_id": "2449", "company_name": "京元電子", "name": "Investment_Trust", "buy": 300_000, "sell": 100_000},
            {"date": "2026-06-26", "stock_id": "2449", "company_name": "京元電子", "name": "Dealer", "buy": 200_000, "sell": 250_000},
        ])

    def fetch_daily_frame(self, scan_date):
        rows = []
        start = date(2026, 6, 1)
        for offset in range(20):
            day = start + timedelta(days=offset)
            rows.append({
                "date": day.isoformat(),
                "stock_id": "2330",
                "company_name": "台積電",
                "close": 100 + offset,
                "Trading_Volume": 1_000_000,
            })
            rows.append({
                "date": day.isoformat(),
                "stock_id": "2449",
                "company_name": "京元電子",
                "close": 80,
                "Trading_Volume": 1_000_000,
            })
        rows.append({
            "date": "2026-06-26",
            "stock_id": "2330",
            "company_name": "台積電",
            "close": 180,
            "Trading_Volume": 6_000_000,
            "rsi_14": 62.5,
            "macd": 1.4,
            "macd_signal": 0.7,
            "macd_histogram": 0.7,
            "revenue_growth_yoy_pct": 18.2,
        })
        rows.append({
            "date": "2026-06-26",
            "stock_id": "2449",
            "company_name": "京元電子",
            "close": 82,
            "Trading_Volume": 1_100_000,
            "rsi_14": 76.0,
            "macd": -0.2,
            "macd_signal": 0.1,
            "macd_histogram": -0.3,
            "revenue_growth_yoy_pct": -4.0,
        })
        return pd.DataFrame(rows)


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


def test_scan_taiwan_market_filters_pages_and_reports_freshness():
    import market_screener

    result = market_screener.scan_taiwan_market(
        scan_date=date(2026, 6, 26),
        data_source=FakeRichScreenerDataSource(),
        top_n=5,
        filters={
            "fundamental": {"revenue_growth_yoy_pct_min": 10},
            "technical": {"rsi_min": 50, "rsi_max": 70, "macd_histogram_min": 0},
            "institutional": {"foreign_net_buy_shares_min": 2_000_000, "investment_trust_net_buy_shares_min": 500_000, "dealer_net_buy_shares_min": 100_000},
        },
        limit=1,
        offset=0,
        sort_by="rsi_14",
        sort_direction="desc",
    )

    assert result["pagination"] == {"limit": 1, "offset": 0, "total": 1, "has_more": False}
    assert result["last_updated_time"].startswith("2026-06-26")
    assert result["candidates"][0]["ticker"] == "2330.TW"
    assert result["candidates"][0]["metrics"]["rsi_14"] == 62.5
    assert result["candidates"][0]["metrics"]["macd_histogram"] == 0.7
    assert result["candidates"][0]["metrics"]["revenue_growth_yoy_pct"] == 18.2
    assert result["candidates"][0]["metrics"]["dealer_net_buy_shares"] == 600_000
    assert result["candidates"][0]["watchlist_status"]["in_watchlist"] is False


def test_scan_taiwan_market_can_use_cached_candidate_page(monkeypatch):
    import market_screener

    cache = {}
    source = FakeRichScreenerDataSource()
    monkeypatch.setattr(market_screener, "get_cache_json", cache.get)
    monkeypatch.setattr(market_screener, "set_cache_json", lambda key, value, ttl_seconds: cache.__setitem__(key, value))

    first = market_screener.scan_taiwan_market(
        scan_date=date(2026, 6, 26),
        data_source=source,
        top_n=5,
        use_cache=True,
        cache_ttl_seconds=120,
    )
    second = market_screener.scan_taiwan_market(
        scan_date=date(2026, 6, 26),
        data_source=source,
        top_n=5,
        use_cache=True,
        cache_ttl_seconds=120,
    )

    assert source.calls == 1
    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert second["candidates"] == first["candidates"]


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


def test_run_daily_market_screener_prunes_stale_auto_screener_items(monkeypatch, tmp_path):
    import market_screener
    import watchlist_service

    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()
    watchlist_service.upsert_watchlist_item({
        "ticker": "1522.TW",
        "pipeline": "v4",
        "enabled": True,
        "tags": ["Auto-Screener", "technical_heat"],
        "trigger_source": "daily_screener",
        "triggers": [{
            "key": "daily_screener",
            "type": "daily_screener",
            "category": "technical_heat",
            "reason": "乖離率 -100.0%",
            "metrics": {"close": 0, "bias_pct": -100},
        }],
    })
    watchlist_service.upsert_watchlist_item({
        "ticker": "2308.TW",
        "pipeline": "v2",
        "enabled": True,
        "tags": [],
    })
    monkeypatch.setattr(market_screener, "FINMIND_API_TOKEN", "")

    result = market_screener.run_daily_market_screener(
        now=datetime(2026, 6, 26, 18, 5, tzinfo=watchlist_service.TAIPEI),
        data_loader_cls=FakeFinMindLoader,
        top_n=1,
    )

    tickers = {(item["ticker"], item["pipeline"]) for item in watchlist_service.list_watchlist()["items"]}
    assert result["pruned_count"] == 1
    assert ("1522.TW", "v4") not in tickers
    assert ("2308.TW", "v2") in tickers
    assert {("2330.TW", "v4"), ("2449.TW", "v4")} <= tickers


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
