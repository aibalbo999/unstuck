"""Independent-review regressions: projections must not erase source defects."""
from copy import deepcopy
from datetime import date
from itertools import permutations

import pandas as pd
import pytest

from market_session_admission import assess_daily_session_integrity
from short_term_market_data import normalize_daily_market_data, build_short_term_market_context


AS_OF = date(2026, 10, 27)


def bar(day, close=60, volume=0):
    return dict(date=day, open=close, high=close, low=close, close=close, volume=volume)


def context(daily):
    return build_short_term_market_context({"ticker": "2356.TW", "daily_market_data": daily}, as_of=AS_OF)


@pytest.mark.parametrize("order", sorted(set(permutations((61, 99, 61)))))
def test_conflicting_duplicates_select_no_variant_and_remain_unresolved_across_projection(order):
    rows = [bar("2026-10-21")] + [bar("2026-10-22", value) for value in order] + [bar("2026-10-27", 62)]
    original = deepcopy(rows)
    daily = normalize_daily_market_data(rows, ticker="2356.TW", as_of=AS_OF)
    assert not daily["session_integrity"]["eligible"]
    assert "conflicting_duplicate_session" in daily["session_integrity"]["reason_codes"]
    assert "2026-10-22" not in [row["date"] for row in daily["bars"]]
    conflict = next(row for row in daily["quarantined_session_rows"] if row["reason"] == "conflicting_duplicate_session")
    assert [row["close"] for row in conflict["observations"]] == [61., 99.]
    assert conflict["source_selection_evidence_status"] == "missing"
    assert rows == original
    before = deepcopy(daily)
    first = context(daily)
    second = context(first["daily_market_data"])
    assert first["daily_market_data"]["quarantined_session_rows"] == second["daily_market_data"]["quarantined_session_rows"]
    assert first["daily_market_data"]["session_integrity"] == second["daily_market_data"]["session_integrity"]
    assert not second["daily_market_data"]["session_integrity"]["eligible"]
    assert first["technical_indicators"]["sample_count"] == second["technical_indicators"]["sample_count"] == 0
    assert daily == before


def test_identical_duplicates_deduplicate_without_changing_the_valid_zero_volume_bar():
    rows = [bar("2026-10-22", 61), bar("2026-10-22", 61), bar("2026-10-27", 62)]
    original = deepcopy(rows)
    daily = normalize_daily_market_data(rows, ticker="2356.TW", as_of=AS_OF)
    assert daily["session_integrity"]["eligible"]
    assert daily["bars"] == [bar("2026-10-22", 61.), bar("2026-10-27", 62.)]
    assert daily["excluded_row_count"] == 1
    assert rows == original


@pytest.mark.parametrize("reverse", [False, True])
def test_invalid_dated_duplicate_cannot_make_valid_looking_variant_authoritative(reverse):
    candidates = [bar("2026-10-22", 61), {**bar("2026-10-22", 99), "high": 61}]
    if reverse:
        candidates.reverse()
    original = deepcopy(candidates)
    daily = normalize_daily_market_data(candidates + [bar("2026-10-27")], ticker="2356.TW", as_of=AS_OF)
    assert "2026-10-22" not in [row["date"] for row in daily["bars"]]
    assert not daily["session_integrity"]["eligible"]
    assert "duplicate_session_evidence_unusable" in daily["session_integrity"]["reason_codes"]
    assert not context(daily)["daily_market_data"]["session_integrity"]["eligible"]
    assert candidates == original


@pytest.mark.parametrize("day", ["2026-10-21", "2026-10-27"])
def test_conflict_at_either_window_edge_is_not_lost_when_no_variant_is_selected(day):
    rows = [bar("2026-10-22")] + [bar(day, 61), bar(day, 99)]
    daily = normalize_daily_market_data(rows, ticker="2356.TW", as_of=AS_OF)
    assert day not in [row["date"] for row in daily["bars"]]
    assert not daily["session_integrity"]["eligible"]
    assert "conflicting_duplicate_session" in context(daily)["daily_market_data"]["session_integrity"]["reason_codes"]


@pytest.mark.parametrize("bad_quarantine", [
    [{"date": {}, "state": "unknown"}], [{"date": [], "state": "unknown"}],
    [{"date": None, "state": "unknown"}], [None], [[]], [{}], None, {}, "unknown",
])
def test_malformed_quarantine_never_disappears_or_upgrades_through_context(bad_quarantine):
    daily = {"ticker": "2356.TW", "as_of": "2026-10-27", "bars": [bar("2026-10-27")],
             "quarantined_session_rows": deepcopy(bad_quarantine)}
    original = deepcopy(daily)
    assert not assess_daily_session_integrity(daily)["eligible"]
    first = context(daily)
    second = context(first["daily_market_data"])
    for result in (first, second):
        assert not result["daily_market_data"]["session_integrity"]["eligible"]
        assert result["technical_indicators"]["sample_count"] == 0
    assert first["daily_market_data"]["quarantined_session_rows"] == second["daily_market_data"]["quarantined_session_rows"]
    assert first["daily_market_data"]["session_integrity"] == second["daily_market_data"]["session_integrity"]
    assert daily == original


def test_unvalidated_selection_metadata_cannot_resolve_a_conflict():
    daily = {"ticker": "2356.TW", "as_of": "2026-10-27", "bars": [bar("2026-10-22"), bar("2026-10-27")],
             "quarantined_session_rows": [{"date": "2026-10-22", "state": "unknown",
                "reason": "conflicting_duplicate_session", "resolved": True,
                "source_selection_evidence_status": "verified"}]}
    assert not assess_daily_session_integrity(daily)["eligible"]
    assert not context(daily)["daily_market_data"]["session_integrity"]["eligible"]


def test_yfinance_duplicate_history_cannot_reach_usable_technical_analysis(monkeypatch):
    from data_fetch.yfinance_enrichment_extractors import extract_market_history_bundle
    from data_fetch.market_sources import twse_session_observation
    monkeypatch.setattr(twse_session_observation, "official_observation", lambda *args: {"status": "unavailable"})
    class Stock:
        ticker = "2356.TW"
        def history(self, **kwargs):
            prices = [60., 61., 99., 62.]
            return pd.DataFrame({**{key: prices for key in ("Open", "High", "Low", "Close", "Adj Close")},
                                 "Volume": [0.] * 4},
                                index=pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-22", "2026-10-27"]))
    result = extract_market_history_bundle(Stock(), as_of=AS_OF)
    assert not result["daily_market_data"]["session_integrity"]["eligible"]
    assert result["technical_indicators"]["sample_count"] == 0
