"""Source observation dates are distinct from cache fetch timestamps."""
from datetime import datetime, timezone

import pytest

import data_freshness


NOW = datetime(2026, 9, 9, 8, tzinfo=timezone.utc).timestamp()


def _institutional(observed_at):
    return {"ticker": "4943.TW", "institutional_trading": {
        "source": "FinMind TaiwanStockInstitutionalInvestorsBuySell",
        "latest_date": observed_at, "total_net_buy_shares": 0,
    }}


def test_fresh_fetch_does_not_make_28_day_old_institutional_records_fresh():
    data = _institutional("2026-08-12")
    data_freshness.mark_sources_fetched(data, "4943.TW", ["institutional_trading"], fetched_at_epoch=NOW)
    entry = data["source_freshness"]["institutional_trading"]
    assert entry["is_fresh"] is False
    assert entry["fetch_is_fresh"] is True
    assert entry["observation_status"] == "stale"
    assert entry["observed_at"] == "2026-08-12"
    assert entry["observation_age_days"] == 28
    assert data_freshness.source_is_stale(data, "institutional_trading", now_epoch=NOW)
    rebuilt = data_freshness.build_source_freshness(data, "4943.TW", True, now_epoch=NOW)
    assert rebuilt["institutional_trading"]["is_fresh"] is False


@pytest.mark.parametrize("observed_at", [None, "", "not-a-date", "2026-09-10"])
def test_unknown_or_future_observation_cannot_be_certified_fresh(observed_at):
    data = _institutional(observed_at)
    data_freshness.mark_sources_fetched(data, "4943.TW", ["institutional_trading"], fetched_at_epoch=NOW)
    entry = data["source_freshness"]["institutional_trading"]
    assert entry["is_fresh"] is False
    assert entry["observation_status"] in {"unknown", "future"}
    assert entry["fetch_is_fresh"] is True


def test_zero_flow_and_recent_weekend_observation_remain_distinct_from_missing():
    monday = datetime(2026, 9, 21, 1, tzinfo=timezone.utc).timestamp()
    data = _institutional("2026-09-18")
    data_freshness.mark_sources_fetched(data, "4943.TW", ["institutional_trading"], fetched_at_epoch=monday)
    assert data["institutional_trading"]["total_net_buy_shares"] == 0
    assert data["source_freshness"]["institutional_trading"]["is_fresh"] is True
    assert data["source_freshness"]["institutional_trading"]["observation_age_days"] == 3


def test_full_fetch_audit_preserves_old_observation_staleness():
    from data_fetch.audit_policy import _append_full_fetch_audit

    data = _institutional("2026-08-12")
    data_freshness.mark_sources_fetched(data, "4943.TW", ["institutional_trading"], fetched_at_epoch=NOW)
    _append_full_fetch_audit(data, "4943.TW", "fixture", started_at_epoch=NOW,
                             fetched_at_epoch=NOW, skip_optional_http=True)
    audit = next(row for row in data["source_audit"] if row["source"] == "institutional_trading")
    assert audit["stale"] is True
