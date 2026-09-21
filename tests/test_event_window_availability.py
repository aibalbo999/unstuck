"""A normal empty future window is distinct from unavailable calendar evidence."""
from datetime import date

import pytest

from short_term_events import future_event_context


TODAY = date(2026, 9, 21)


def test_dated_sourced_events_outside_window_are_known_empty_not_fetch_failure():
    result = future_event_context({"as_of_date": "2026-09-21", "events": [
        {"date": "2026-09-18", "label": "past event", "source": "issuer"},
        {"date": "2026-12-31", "label": "later event", "source": "issuer"},
    ]}, as_of=TODAY)
    assert result["availability"] == "known_empty"
    assert result["events"] == []
    assert result["excluded_outside_window_count"] == 2
    assert result["reason_codes"] == ["no_events_in_provided_calendar_window"]


def test_explicit_successful_empty_calendar_can_be_known_empty():
    result = future_event_context({"status": "success", "source": "issuer",
                                   "as_of_date": "2026-09-21", "events": []}, as_of=TODAY)
    assert result["availability"] == "known_empty"


@pytest.mark.parametrize("calendar", [None, {}, {"events": []},
    {"status": "error", "source": "issuer", "as_of_date": "2026-09-21", "events": []},
    {"events": [{"label": "date unknown", "source": "issuer"}]},
    {"events": [{"date": "2026-09-18", "label": "unattributed"}]},
    {"events": [{"date": "2026-09-18"}]},
])
def test_missing_failed_or_undated_calendar_is_not_known_empty(calendar):
    result = future_event_context(calendar, as_of=TODAY)
    assert result["availability"] != "known_empty"


def test_failed_source_with_retained_old_events_cannot_hide_failure_as_known_empty():
    result = future_event_context({"status": "failed", "events": [
        {"date": "2026-09-18", "label": "old event", "source": "issuer"},
    ]}, as_of=TODAY)
    assert result["availability"] == "unavailable"
    assert "event_source_failed" in result["reason_codes"]


@pytest.mark.parametrize("events", [[], [
    {"date": "2026-09-18", "label": "past event", "source": "issuer"},
]])
@pytest.mark.parametrize("date_key", ["as_of_date", "as_of"])
def test_future_source_date_cannot_assert_a_current_known_empty_window(events, date_key):
    result = future_event_context({"status": "success", "source": "issuer",
        date_key: "2027-01-01", "events": events}, as_of=TODAY)
    assert result["availability"] == "unavailable"
    assert result["empty_scope"] is None
    assert result["reason_codes"] == ["event_source_date_future"]


def test_future_event_date_is_allowed_when_source_observation_is_current():
    result = future_event_context({"status": "success", "source": "issuer",
        "as_of_date": "2026-09-21", "events": [
            {"date": "2026-09-25", "label": "scheduled event", "source": "issuer"},
        ]}, as_of=TODAY)
    assert result["availability"] == "available"
    assert result["events"][0]["date_status"] == "scheduled"
    assert result["reason_codes"] == []


def test_future_source_date_retains_visible_events_with_partial_warning():
    result = future_event_context({"status": "success", "source": "issuer",
        "as_of_date": "2027-01-01", "events": [
            {"date": "2026-09-25", "label": "scheduled event", "source": "issuer"},
        ]}, as_of=TODAY)
    assert result["availability"] == "partial"
    assert len(result["events"]) == 1
    assert result["reason_codes"] == ["event_source_date_future"]
