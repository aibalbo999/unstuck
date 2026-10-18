"""Official brokerage membership must survive exact issuer and business checks."""

from datetime import date
import json


TODAY = date(2026, 10, 8)
BROKERS = [
    {"出表日期": "1151008", "營利事業統一編號": "23218183", "業務種類": "經紀、自營、承銷", "證券代號": "5850"},
    {"出表日期": "1151008", "營利事業統一編號": "22956035", "業務種類": "經紀、自營、承銷", "證券代號": "9100"},
    {"出表日期": "1151008", "營利事業統一編號": "12345678", "業務種類": "自營", "證券代號": "2210"},
]
LISTED = [
    {"出表日期": "1151007", "公司代號": "2855", "公司簡稱": "統一證", "營利事業統一編號": "23218183"},
    {"出表日期": "1151007", "公司代號": "6005", "公司簡稱": "群益證", "營利事業統一編號": "22956035"},
    {"出表日期": "1151007", "公司代號": "6024", "公司簡稱": "群益期", "營利事業統一編號": "12345678"},
]
MASTER = [
    {"date": "2026-10-08", "stock_id": row["公司代號"], "stock_name": row["公司簡稱"],
     "type": "twse", "industry_category": "金融保險"}
    for row in LISTED
]


def test_official_broker_join_finds_only_same_business_current_listed_peer():
    from data_fetch.market_sources.official_broker_cohort import parse_official_rosters, select_broker_candidates

    rosters = parse_official_rosters(json.dumps(BROKERS).encode(), json.dumps(LISTED).encode())
    result = select_broker_candidates("2855.TW", rosters, MASTER, today=TODAY)
    assert [row["ticker"] for row in result] == ["6005.TW"]
    assert result[0]["comparison_status"] == "industry_candidate_only"
    assert result[0]["identity_status"] == "official_ubid_and_current_master"
    assert result[0]["broker_business_kind"] == "經紀、自營、承銷"
    assert result[0]["issuer_registered_business_number"] == "23218183"
    assert result[0]["peer_registered_business_number"] == "22956035"


def test_official_broker_join_rejects_mismatched_identity_or_stale_observation():
    from data_fetch.market_sources.official_broker_cohort import parse_official_rosters, select_broker_candidates

    for changed_brokers, changed_listed, changed_master in (
        ([{**BROKERS[0], "營利事業統一編號": "99999999"}, *BROKERS[1:]], LISTED, MASTER),
        (BROKERS, [{**LISTED[1], "營利事業統一編號": "99999999"}, LISTED[0], LISTED[2]], MASTER),
        (BROKERS, LISTED, [{**MASTER[1], "stock_name": "別家公司"}, MASTER[0], MASTER[2]]),
        (BROKERS, LISTED, [{**MASTER[1], "date": "2026-09-01"}, MASTER[0], MASTER[2]]),
        ([{**BROKERS[0], "出表日期": "1150901"}, *BROKERS[1:]], LISTED, MASTER),
    ):
        rosters = parse_official_rosters(json.dumps(changed_brokers).encode(), json.dumps(changed_listed).encode())
        assert select_broker_candidates("2855.TW", rosters, changed_master, today=TODAY) == []


def test_official_roster_ignores_reused_zero_business_number_placeholder():
    from data_fetch.market_sources.official_broker_cohort import parse_official_rosters

    placeholders = [
        {"公司代號": "9103", "公司簡稱": "外國存託憑證甲", "營利事業統一編號": "00000000"},
        {"公司代號": "9105", "公司簡稱": "外國存託憑證乙", "營利事業統一編號": "00000000"},
    ]
    rosters = parse_official_rosters(json.dumps(BROKERS).encode(), json.dumps(LISTED + placeholders).encode())
    assert "9103" not in rosters["listed_by_code"]
    assert "9105" not in rosters["listed_by_code"]


def test_stale_official_cache_does_not_supply_a_peer(monkeypatch):
    from data_fetch.market_sources import official_broker_cohort as cohort

    rosters = cohort.parse_official_rosters(json.dumps(BROKERS).encode(), json.dumps(LISTED).encode())
    monkeypatch.setattr(cohort, "shared_fetch", lambda *_args, **_kwargs: (
        rosters, {"cache_hit": True, "stale": True}))
    result = cohort.get_official_broker_candidates("2855.TW", MASTER, today=TODAY)
    assert result == {"candidates": [], "status": "stale_or_unavailable"}


def test_broker_candidate_is_attempted_ahead_of_broad_financial_codes(monkeypatch):
    from data_fetch.market_sources import peers

    legacy = [{"name": f"銀行 {code}", "ticker": f"{code}.TW", "comparison_status": "industry_candidate_only"}
              for code in range(2801, 2812)]
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: MASTER)
    monkeypatch.setattr(peers, "resolve_legacy_peer_candidates", lambda *_args, **_kwargs: (
        legacy, {"selection_status": "selected", "selection_basis": "current_master_industry"}))
    monkeypatch.setattr(peers, "get_official_broker_candidates", lambda ticker, rows, *, today: {
        "candidates": select_broker_fixture(ticker, rows, today), "status": "success"})

    class Stock:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            return {"symbol": self.symbol, "quoteType": "EQUITY",
                    "industry": "Capital Markets" if self.symbol == "6005.TW" else "Banks - Regional",
                    "trailingPE": 7.3, "priceToBook": 1.3}

    monkeypatch.setattr(peers.yf, "Ticker", Stock)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        "2855.TW", "統一證", "Financial Services", "Capital Markets", {})
    assert [row["ticker"] for row in result["peers"]] == ["6005.TW"]
    assert result["peers"][0]["comparison_status"] == "business_industry_matched"
    assert result["audit"]["official_broker_candidate_status"] == "success"
    assert result["audit"]["candidate_attempt_count"] <= 10


def test_official_broker_download_failure_keeps_existing_candidate_path(monkeypatch):
    from data_fetch.market_sources import peers

    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: MASTER)
    monkeypatch.setattr(peers, "resolve_legacy_peer_candidates", lambda *_args, **_kwargs: (
        [{"name": "既有同業", "ticker": "6005.TW", "comparison_status": "industry_candidate_only"}],
        {"selection_status": "selected", "selection_basis": "current_master_industry"}))
    monkeypatch.setattr(peers, "get_official_broker_candidates", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        TimeoutError("private upstream URL must not leak")))

    class Stock:
        info = {"symbol": "6005.TW", "quoteType": "EQUITY", "industry": "Capital Markets",
                "trailingPE": 7.3, "priceToBook": 1.3}

    monkeypatch.setattr(peers.yf, "Ticker", lambda _symbol: Stock())
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        "2855.TW", "統一證", "Financial Services", "Capital Markets", {})
    assert [row["ticker"] for row in result["peers"]] == ["6005.TW"]
    assert result["audit"]["official_broker_candidate_status"] == "download_failed:TimeoutError"
    assert "private upstream URL" not in str(result)


def select_broker_fixture(ticker, rows, today):
    from data_fetch.market_sources.official_broker_cohort import parse_official_rosters, select_broker_candidates

    rosters = parse_official_rosters(json.dumps(BROKERS).encode(), json.dumps(LISTED).encode())
    return select_broker_candidates(ticker, rosters, rows, today=today)


import pytest
@pytest.fixture(autouse=True)
def replay_acquisition_day(monkeypatch):
    import time
    from datetime import datetime, timezone
    from data_fetch.market_sources import peers
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    monkeypatch.setattr(time, 'time', lambda: datetime(TODAY.year, TODAY.month, TODAY.day, 6, tzinfo=timezone.utc).timestamp())
