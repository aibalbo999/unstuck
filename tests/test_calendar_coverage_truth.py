from datetime import date


def test_missing_year_uses_conservative_ttl_and_preserves_calendar_provenance(monkeypatch):
    import data_freshness
    monkeypatch.setattr(data_freshness, 'calendar_coverage', lambda _: {
        'source': 'missing', 'coverage_status': 'unknown', 'valid_year': None, 'calendar_version': None})
    policy = data_freshness.freshness_policy('2330.TW', market_session=False)
    assert policy['max_age_seconds'] == data_freshness.FINANCIAL_DATA_MARKET_CACHE_SECONDS
    assert policy['policy'] == 'calendar_unknown_conservative'
    assert policy['calendar']['coverage_status'] == 'unknown'


def test_past_calendar_records_do_not_prove_future_window_empty():
    from short_term_events import future_event_context
    calendar = {"as_of_date": "2026-09-23", "events": [
        {"date": "1994-05-05", "label": "除息日", "source": "yfinance calendar"}]}
    result = future_event_context(calendar, as_of=date(2026, 9, 23))
    assert result["availability"] != "known_empty"
    assert result["empty_scope"] is None


def test_known_empty_requires_explicit_successful_full_window_coverage():
    from short_term_events import future_event_context
    calendar = {"as_of_date": "2026-09-23", "status": "success", "source": "issuer calendar", "events": [],
                "coverage_start": "2026-09-23", "coverage_end": "2026-10-07", "coverage_complete": True}
    assert future_event_context(calendar, as_of=date(2026, 9, 23))["availability"] == "known_empty"
    calendar["coverage_end"] = "2026-09-30"
    assert future_event_context(calendar, as_of=date(2026, 9, 23))["availability"] != "known_empty"


def test_calendar_year_without_seed_is_explicitly_unknown(tmp_path):
    from market_calendar_store import load_market_calendar
    calendar = load_market_calendar("tw", 2027, calendar_dir=str(tmp_path))
    assert calendar["coverage_status"] == "unknown"
    assert calendar["source"] == "missing"


def test_calendar_extraction_records_failure_and_does_not_invent_coverage():
    from data_fetch.yfinance_enrichment_extractors import extract_event_calendar
    class Stock:
        @property
        def calendar(self):
            raise RuntimeError("transport failed")
    result = extract_event_calendar(Stock(), {})
    assert result["status"] == "unavailable"
    assert result["coverage_complete"] is False
    assert result["events"] == []
