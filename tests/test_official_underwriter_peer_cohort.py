"""Dated underwriting peer examples must retain current issuer identity checks."""

from datetime import date


TODAY = date(2026, 10, 9)
MASTER = [
    {"stock_id": "3587", "stock_name": "閎康", "type": "tpex", "industry_category": "其他電子類", "date": "2026-10-09"},
    {"stock_id": "3289", "stock_name": "宜特", "type": "tpex", "industry_category": "其他電子類", "date": "2026-10-09"},
    {"stock_id": "6830", "stock_name": "汎銓", "type": "twse", "industry_category": "其他電子業", "date": "2026-10-09"},
]


def test_documented_underwriter_candidates_are_dated_and_identity_checked():
    from data_fetch.market_sources.official_underwriter_peer_cohort import documented_peer_candidates

    rows = documented_peer_candidates("3587.TWO", MASTER, today=TODAY)
    assert [row["ticker"] for row in rows] == ["6830.TW", "3289.TWO"]
    assert all(row["comparison_status"] == "underwriter_documented_candidate" for row in rows)
    assert all(row["business_comparability_verified_current"] is False for row in rows)
    assert all(row["underwriter_document_url"].startswith("https://") for row in rows)
    assert all(row["master_observed_at"] == TODAY.isoformat() for row in rows)


def test_documented_underwriter_candidates_reject_stale_or_changed_identity():
    from data_fetch.market_sources.official_underwriter_peer_cohort import documented_peer_candidates

    stale_target = [{**MASTER[0], "date": "2026-09-01"}, *MASTER[1:]]
    assert documented_peer_candidates("3587.TWO", stale_target, today=TODAY) == []
    changed_peer = [MASTER[0], {**MASTER[1], "stock_name": "別家公司"}, MASTER[2]]
    assert [row["ticker"] for row in documented_peer_candidates("3587.TWO", changed_peer, today=TODAY)] == ["6830.TW"]
    wrong_market = [MASTER[0], MASTER[1], {**MASTER[2], "type": "tpex"}]
    assert [row["ticker"] for row in documented_peer_candidates("3587.TWO", wrong_market, today=TODAY)] == ["3289.TWO"]
    yesterday_peer = [MASTER[0], {**MASTER[1], "date": "2026-10-08"}, MASTER[2]]
    rows = documented_peer_candidates("3587.TWO", yesterday_peer, today=TODAY)
    assert next(row for row in rows if row["ticker"] == "3289.TWO")["master_observed_at"] == "2026-10-08"
    assert documented_peer_candidates("3587.TW", MASTER, today=TODAY) == []
    assert documented_peer_candidates("1605.TW", MASTER, today=TODAY) == []


def test_documented_candidates_are_attempted_before_broad_industry_peers(monkeypatch):
    from data_fetch.market_sources import peers

    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: MASTER)
    monkeypatch.setattr(peers, "resolve_legacy_peer_candidates", lambda *_args, **_kwargs: (
        [{"name": f"泛分類 {code}", "ticker": f"{code}.TWO", "comparison_status": "industry_candidate_only"}
         for code in range(3500, 3512)],
        {"selection_status": "selected", "selection_basis": "current_master_industry"},
    ))

    class Stock:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            return {"symbol": self.symbol, "quoteType": "EQUITY", "industry": "Semiconductor Equipment & Materials",
                    "trailingPE": 20.0, "priceToBook": 2.0}

    monkeypatch.setattr(peers.yf, "Ticker", Stock)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        "3587.TWO", "閎康", "Technology", "Scientific & Technical Instruments", {})
    assert [row["ticker"] for row in result["peers"][:2]] == ["6830.TW", "3289.TWO"]
    assert result["audit"]["official_underwriter_candidate_count"] == 2
    assert result["audit"]["candidate_attempt_count"] <= 10
    assert result["peers"][0]["comparison_status"] == "underwriter_documented_candidate"


def test_historical_underwriter_candidate_does_not_set_automatic_peer_valuation():
    from stock_snapshot.peers_valuation import _peer_comparison
    from reporting.analysis_overlays import build_peer_comparison_rows

    data = {
        "ticker": "3587.TWO", "company_name": "閎康", "pe_ratio": 36.0,
        "dynamic_peer_metrics": [{
            "ticker": "6830.TW", "name": "汎銓", "pe_ttm": 2120.0,
            "comparison_status": "underwriter_documented_candidate",
            "business_comparability_verified_current": False,
        }],
    }
    result = _peer_comparison(data)
    assert result["summary"]["peer_count"] == 0
    assert result["summary"]["peer_pe_median"] is None
    assert result["summary"]["valuation_label"] == "同業資料不足"
    assert len(build_peer_comparison_rows(data)) == 1


import pytest
@pytest.fixture(autouse=True)
def replay_acquisition_day(monkeypatch):
    import time
    from datetime import datetime, timezone
    from data_fetch.market_sources import peers
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    monkeypatch.setattr(time, 'time', lambda: datetime(TODAY.year, TODAY.month, TODAY.day, 6, tzinfo=timezone.utc).timestamp())
