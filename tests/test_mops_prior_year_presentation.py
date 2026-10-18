"""Public boundary checks. Original private-data replay cases remain local."""

def test_previous_year_selection_age_and_calendar_are_bounded():
    from mops_previous_year import eligible_previous
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime(2026, 10, 18, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    valid = {'event_date': '2025-12-29', 'event_end_date': '2025-12-29'}
    assert eligible_previous(valid, 2026, now)
    assert not eligible_previous({'event_date': '2025-01-01', 'event_end_date': '2025-01-01'}, 2026, now)
    assert not eligible_previous({'event_date': '2026-01-01', 'event_end_date': '2026-01-01'}, 2026, now)
    assert not eligible_previous(valid, 2027, now)
