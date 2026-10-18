"""Public boundary checks. Original private-data replay cases remain local."""
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
import importlib
import importlib.util
import json
import pytest

def source():
    name = 'data_fetch.market_sources.macronix_presentation_index'
    assert importlib.util.find_spec(name) is not None, 'Future-quarter published index has no dynamic selector'
    return importlib.import_module(name)

def stamp(day):
    return datetime.fromisoformat(day + 'T12:00:00').replace(tzinfo=ZoneInfo('Asia/Taipei')).timestamp()

def choose(value, day='2026-10-16', *, year=2026, received=None):
    raw = json.dumps(value, separators=(',', ':')).encode()
    return source().select_presentation(raw, stamp(received or day), index_year=year, as_of_epoch=stamp(day))

def published_row(year, quarter, date, *, row_id='999'):
    return {'Year': str(year), 'Quarter': str(quarter), 'AnnounceDate': date, 'Webcast': '', 'Id': row_id, 'release': f'{year}q{quarter}_release_en.pdf', 'fcon': f'{year}q{quarter}_fcon_en.pdf', 'webcast_PPT': f'{year}q{quarter} webcast_ppt_en.pdf', 'FI': None}

@pytest.mark.parametrize('raw', [b'[]', b'{}', b'[2026]', b'[true]', b'["02026"]', b'["2026","2026"]', b'["2027"]', b'["2026",null]', b'NaN', b'\xff', b'["2026"]tail', b'{"Year":"2026","Year":"2026"}'])
def test_years_reject_ambiguous_schema_duplicates_and_future(raw):
    with pytest.raises(ValueError):
        source().parse_years(raw, stamp('2026-10-16'), stamp('2026-10-16'))

@pytest.mark.parametrize('year', [True, False, 2026.0, '2026', None, 999, 10000])
def test_index_url_requires_a_canonical_integer_year(year):
    with pytest.raises(ValueError):
        source().index_url(year)

@pytest.mark.parametrize('epoch', [True, False, None, '1', -1, 0, float('nan'), float('inf'), 10 ** 400])
def test_invalid_epochs_are_value_errors(epoch):
    with pytest.raises(ValueError):
        source().parse_years(b'["2026"]', epoch, stamp('2026-10-16'))
    if epoch is not None:
        with pytest.raises(ValueError):
            source().select_presentation(b'[]', stamp('2026-10-16'), index_year=2026, as_of_epoch=epoch)

def test_future_acquisition_epoch_is_rejected():
    with pytest.raises(ValueError):
        source().select_presentation(b'[]', stamp('2026-10-17'), index_year=2026, as_of_epoch=stamp('2026-10-16'))

def test_size_limits_do_not_parse_oversize_originals():
    s = source()
    with pytest.raises(ValueError, match='size'):
        s.parse_years(b' ' * 16385, stamp('2026-10-16'), stamp('2026-10-16'))
    with pytest.raises(ValueError, match='size'):
        s.select_presentation(b' ' * 200001, stamp('2026-10-16'), index_year=2026, as_of_epoch=stamp('2026-10-16'))

def test_q4_can_be_published_in_next_year_q1():
    selected = choose([published_row(2026, 4, '2027/01/25')], '2027-01-26')
    assert selected['period_label'] == '2026Q4' and selected['event_date'] == '2027-01-25'
    assert '999/2026q4%20webcast_ppt_en.pdf' in selected['pdf_url']
    assert source().validate_selected_descriptor(selected) == selected

def test_future_year_and_original_acquired_before_event_are_rejected():
    with pytest.raises(ValueError, match='index year is in the future'):
        choose([], year=2027)
    with pytest.raises(ValueError, match='not past when original was acquired'):
        choose([published_row(2026, 2, '2026/07/28')], '2026-07-29', received='2026-07-28')

def test_370_day_age_is_inclusive_and_371_days_is_rejected():
    event = datetime.fromisoformat('2026-01-25').date()
    row = published_row(2025, 4, '2026/01/25')
    assert choose([row], (event + timedelta(days=370)).isoformat(), year=2025)['period_label'] == '2025Q4'
    with pytest.raises(ValueError, match='exceeds 370 days'):
        choose([row], (event + timedelta(days=371)).isoformat(), year=2025)
