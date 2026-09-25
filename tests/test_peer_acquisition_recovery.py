"""Peer identity, bounded recovery and metric provenance contracts."""
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from data_fetch.market_sources import peers
from data_fetch.market_sources.peer_selection import ranked_profiles_from_identity


TODAY = date(2026, 9, 25)


def master(stock_id, name="同業", market="twse", category="生技醫療業", day="2026-09-25"):
    return dict(stock_id=stock_id, stock_name=name, type=market,
                industry_category=category, date=day)


@pytest.fixture
def source_setup(monkeypatch):
    monkeypatch.setattr(peers, "_today", lambda: TODAY)
    monkeypatch.setattr(peers, "fetch_peer_valuation_fallback", lambda *a, **k: {"metrics": {}, "status": "valid_empty"})
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [])
    monkeypatch.setattr(peers.yf, "Ticker", lambda symbol: type("Quote", (), {"info": {}})())


def test_resolves_market_skips_delisted_preferred_and_preserves_missing_metrics(source_setup, monkeypatch):
    rows = [master("6861"), master("6497", day="2023-01-01"), master("2883A"),
            master("1234", market="emerging", day="2025-01-01"),
            master("1234", market="tpex")]
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: rows)
    called = []
    monkeypatch.setattr(peers.yf, "Ticker", lambda symbol: called.append(symbol) or type("Quote", (), {"info": {}})())
    identity = {"same_industry_peers": [{"stock_id": s} for s in ("6497", "2883A", "1234", "6861", "1234")]}
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics("6861.TW", "睿生光電", "Healthcare", "Medical Devices", identity)
    assert called == ["1234.TWO"]
    assert result["peers"][0]["ticker"] == "1234.TWO"
    assert result["peers"][0]["metrics_status"] == "unavailable"
    assert result["peers"][0]["identity_status"] == "verified_master"
    assert result["audit"]["usable_count"] == 0
    assert result["audit"]["identity_count"] == 1
    assert result["audit"]["selection_rejected_reason_counts"]["stale_master_row"] == 1


def test_no_stale_semiconductor_guess_for_current_miscellaneous_issuer(source_setup, monkeypatch):
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [
        master("5314", market="tpex", category="半導體業", day="2025-06-01"),
        master("5314", market="tpex", category="其他"), master("2330", category="半導體業")])
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics("5314.TWO", "世紀", "Technology", "Semiconductors", {"same_industry_peers": [{"stock_id": "2330"}]})
    assert result["peers"] == []
    assert result["audit"]["selection_status"] == "broad_industry_only"


def test_recent_but_historical_master_membership_is_not_current(source_setup, monkeypatch):
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [master("6861"), master("4736", day="2026-09-24")])
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics("6861.TW", "睿生", "Healthcare", "Medical Devices", {"same_industry_peers": [{"stock_id": "4736"}]})
    assert result["peers"] == []
    assert result["audit"]["selection_rejected_reason_counts"] == {"historical_master_row": 1}


def test_expands_bounded_candidates_after_first_batch_has_no_metrics(source_setup, monkeypatch):
    ids = [str(1100 + i) for i in range(15)]
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [master("6861"), *(master(s) for s in ids)])
    calls = []
    def quote(symbol):
        calls.append(symbol)
        return type("Quote", (), {"info": {"priceToBook": 2} if symbol.startswith("1105") else {}})()
    monkeypatch.setattr(peers.yf, "Ticker", quote)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics("6861.TW", "睿生", "Healthcare", "Medical Devices", {"same_industry_peers": [{"stock_id": s} for s in ids]})
    assert len(calls) == 10
    assert result["peers"][0]["ticker"] == "1105.TW"
    assert result["audit"]["candidate_attempt_count"] == 10
    assert len(result["peers"]) == 5


def test_bank_metrics_do_not_force_gross_margin_or_asset_turnover(source_setup, monkeypatch):
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [master("2892", category="金融保險"), master("2881", category="金融保險")])
    monkeypatch.setattr(peers.yf, "Ticker", lambda s: type("Quote", (), {"info": {
        "grossMargins": .4, "totalRevenue": 100, "totalAssets": 200,
        "returnOnEquity": .12, "trailingPE": float("nan")}})())
    monkeypatch.setattr(peers, "fetch_peer_valuation_fallback", lambda *a, **k: {
        "metrics": {"pe_ttm": 12.4, "pb": 1.2}, "observed_at": "2026-09-24", "status": "success",
        "source": "FinMind TaiwanStockPER"})
    records = peers.fetch_dynamic_peer_metrics("2892.TW", "第一金", "Financial Services", "Banks - Regional", {"same_industry_peers": [{"stock_id": "2881"}]})
    assert records[0]["gross_margin_pct"] is None
    assert records[0]["asset_turnover"] is None
    assert records[0]["metric_applicability"]["gross_margin_pct"] == "not_applicable_financial_institution"
    assert records[0]["pe_ttm"] == 12.4
    assert records[0]["roe_pct"] == 12
    assert records[0]["metric_sources"]["pb"]["observed_at"] == "2026-09-24"


def test_ranked_profile_rejection_cannot_fall_back_to_unqualified_legacy():
    profile = dict(ticker="T", name="target", market="US", gics_code="10101010", market_cap_twd=100,
                   business_tags=["oil"])
    identity = {"company_profile": profile, "peer_profiles": [{**profile, "ticker": "P", "market_cap_twd": 100000}],
                "same_industry_peers": [{"stock_id": "2330"}]}
    selection = ranked_profiles_from_identity(identity)
    assert selection is not None
    assert selection[0] == []


def test_banks_do_not_use_broker_metrics_to_fill_peer_count(source_setup, monkeypatch):
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [master("2892", category="金融保險"),
        master("6005", category="金融保險"), master("5880", category="金融保險")])
    monkeypatch.setattr(peers.yf, "Ticker", lambda symbol: type("Quote", (), {"info": {
        "industry": "Capital Markets" if symbol == "6005.TW" else "Banks - Regional",
        "priceToBook": 2}})())
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics("2892.TW", "第一金", "Financial Services", "Banks - Regional",
        {"same_industry_peers": [{"stock_id": "6005"}, {"stock_id": "5880"}]})
    assert [r["ticker"] for r in result["peers"]] == ["5880.TW"]
    assert result["audit"]["business_industry_rejected_count"] == 1


def test_download_failures_preserve_verified_identity_and_safe_reasons(source_setup, monkeypatch):
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [master("6861"), master("4736")])
    def fail(*a, **k):
        raise TimeoutError("sensitive URL must not be emitted")
    monkeypatch.setattr(peers.yf, "Ticker", fail)
    monkeypatch.setattr(peers, "fetch_peer_valuation_fallback", fail)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics("6861.TW", "睿生", "Healthcare", "Medical Devices", {"same_industry_peers": [{"stock_id": "4736"}]})
    assert result["peers"][0]["ticker"] == "4736.TW"
    assert result["peers"][0]["metrics_status"] == "unavailable"
    assert result["audit"]["usable_count"] == 0
    assert "sensitive" not in str(result)
    assert "TimeoutError" in str(result)


def test_provider_does_not_count_identity_only_as_available_metrics(source_setup, monkeypatch):
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.types import FetchRequest
    from data_trust_audit import source_record_count
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [master("6861"), master("4736")])
    result = DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker("6861.TW"), {"data": {
        "ticker": "6861.TW", "industry": "Medical Devices",
        "company_identity": {"same_industry_peers": [{"stock_id": "4736"}]}}})
    assert result.status == "degraded_enrichment"
    assert result.value[0]["ticker"] == "4736.TW"
    assert result.audit["identity_count"] == 1
    assert result.audit["record_count"] == 0
    assert source_record_count("dynamic_peer_metrics", {"dynamic_peer_metrics": result.value}) == 0
    assert source_record_count("dynamic_peer_metrics", {"dynamic_peer_metrics": [
        *result.value, {"ticker": "5880.TW", "metrics_status": "partial", "pb": 1.43}]}) == 1


def test_fallback_exact_stock_date_finite_and_zero_policy():
    from data_fetch.market_sources.peer_recovery import select_peer_valuation_observation
    rows = [dict(stock_id="2330", date="2026-09-24", PER=100, PBR=50),
            dict(stock_id="1234", date="2026-08-01", PER=20, PBR=2),
            dict(stock_id="1234", date="2026-09-26", PER=21, PBR=3),
            dict(stock_id="1234", date="2026-09-24", PER=0, PBR=1.2)]
    result = select_peer_valuation_observation(rows, "1234.TWO", today=TODAY)
    assert result["metrics"] == {"pb": 1.2}
    assert result["observed_at"] == "2026-09-24"
    assert result["rejected_row_count"] == 3
    assert select_peer_valuation_observation(rows[:3], "1234.TWO", today=TODAY)["metrics"] == {}


def test_fallback_rejects_conflicting_same_day_observations():
    from data_fetch.market_sources.peer_recovery import select_peer_valuation_observation
    rows = [dict(stock_id="1234", date="2026-09-24", PER=20, PBR=2),
            dict(stock_id="1234", date="2026-09-24", PER=25, PBR=2)]
    assert select_peer_valuation_observation(rows, "1234.TWO", today=TODAY)["status"] == "conflicting_observations"
