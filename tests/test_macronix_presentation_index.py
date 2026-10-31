"""Offline published-index boundaries for dynamic Macronix presentations."""
from pathlib import Path
from datetime import datetime
from datetime import timedelta
from copy import deepcopy
from hashlib import sha256
from zoneinfo import ZoneInfo
import importlib
import importlib.util
import json
import pytest

R = Path(__file__).resolve().parents[1]
E = R / 'docs/evidence/source-acquisition/20261015/macronix-dynamic-originals'


def source():
    name = 'data_fetch.market_sources.macronix_presentation_index'
    assert importlib.util.find_spec(name) is not None, 'Future-quarter published index has no dynamic selector'
    return importlib.import_module(name)


def stamp(day):
    return datetime.fromisoformat(day + 'T12:00:00').replace(tzinfo=ZoneInfo('Asia/Taipei')).timestamp()


def test_new_published_quarter_uses_its_own_same_row_attachment():
    s = source()
    rows = json.loads((E / 'results.body').read_bytes())
    rows[2].update(release='2026q3_release_en.pdf', fcon='2026q3_fcon_en.pdf',
                   webcast_PPT='2026q3 webcast_ppt_en.pdf')
    raw = json.dumps(rows).encode()
    selected = s.select_presentation(raw, stamp('2026-10-28'), index_year=2026,
                                     as_of_epoch=stamp('2026-10-28'))
    assert selected['period_label'] == '2026Q3'
    assert selected['pdf_url'] == 'https://www.macronix.com/Lists/QuarterlyResults/Attachments/658/2026q3%20webcast_ppt_en.pdf'
    assert selected['selected_row'] == rows[2]
    assert s.validate_selected_descriptor(selected) == selected
    assert s.verify_selected_in_index(selected, raw, stamp('2026-10-28'), as_of_epoch=stamp('2026-10-28')) == selected


def rows():
    return json.loads((E / 'results.body').read_bytes())


def choose(value, day='2026-10-16', *, year=2026, received=None):
    raw = json.dumps(value, separators=(',', ':')).encode()
    return source().select_presentation(raw, stamp(received or day), index_year=year, as_of_epoch=stamp(day))


def published_row(year, quarter, date, *, row_id='999'):
    return {'Year': str(year), 'Quarter': str(quarter), 'AnnounceDate': date,
            'Webcast': '', 'Id': row_id, 'release': f'{year}q{quarter}_release_en.pdf',
            'fcon': f'{year}q{quarter}_fcon_en.pdf',
            'webcast_PPT': f'{year}q{quarter} webcast_ppt_en.pdf', 'FI': None}


def test_saved_official_years_and_urls_are_exact():
    s = source()
    assert s.parse_years((E / 'years.body').read_bytes(), stamp('2026-10-16'), stamp('2026-10-16')) == list(range(2026, 2012, -1))
    assert s.YEARS_URL == 'https://www.macronix.com/_layouts/15/zMacronixPortal2016/getColumnListByLanguageJson.aspx?listName=QuarterlyResults&selectColumn=Year&lan=EN'
    assert s.index_url(2027) == 'https://www.macronix.com/_layouts/15/zMacronixPortal2016/about/getQuarterlyResultsJson.aspx?Year=2027&Language=EN'
    assert s.parse_years(b'["2025","2026"]', stamp('2026-10-16'), stamp('2026-10-16')) == [2026, 2025]


@pytest.mark.parametrize('raw', [b'[]', b'{}', b'[2026]', b'[true]', b'["02026"]', b'["2026","2026"]',
                                  b'["2027"]', b'["2026",null]', b'NaN', b'\xff', b'["2026"]tail',
                                  b'{"Year":"2026","Year":"2026"}'])
def test_years_reject_ambiguous_schema_duplicates_and_future(raw):
    with pytest.raises(ValueError): source().parse_years(raw, stamp('2026-10-16'), stamp('2026-10-16'))


@pytest.mark.parametrize('year', [True, False, 2026.0, '2026', None, 999, 10000])
def test_index_url_requires_a_canonical_integer_year(year):
    with pytest.raises(ValueError): source().index_url(year)


@pytest.mark.parametrize('epoch', [True, False, None, '1', -1, 0, float('nan'), float('inf'), 10**400])
def test_invalid_epochs_are_value_errors(epoch):
    with pytest.raises(ValueError): source().parse_years(b'["2026"]', epoch, stamp('2026-10-16'))
    if epoch is not None:  # None explicitly means the current clock for as_of.
        with pytest.raises(ValueError): source().select_presentation(b'[]', stamp('2026-10-16'), index_year=2026, as_of_epoch=epoch)


def test_default_as_of_uses_current_clock(monkeypatch):
    s = source()
    monkeypatch.setattr(s.time, 'time', lambda: stamp('2026-10-16'))
    assert s.parse_years(b'["2026"]', stamp('2026-10-16')) == [2026]
    assert s.select_presentation((E / 'results.body').read_bytes(), stamp('2026-10-16'), index_year=2026)['period_label'] == '2026Q2'


def test_future_acquisition_epoch_is_rejected():
    with pytest.raises(ValueError):
        source().select_presentation(b'[]', stamp('2026-10-17'), index_year=2026, as_of_epoch=stamp('2026-10-16'))


def test_saved_complete_index_selects_past_q2_and_binds_original_bytes():
    s = source()
    raw = (E / 'results.body').read_bytes()
    selected = s.select_presentation(raw, stamp('2026-10-16'), index_year=2026, as_of_epoch=stamp('2026-10-16'))
    assert selected['title'] == 'Macronix Second Quarter 2026 Results'
    assert selected['event_date'] == selected['document_date'] == '2026-07-28'
    assert selected['cover_month'] == '2026-07' and selected['quarter'] == 2 and selected['index_year'] == 2026
    assert selected['selection_policy'] == s.POLICY and s.POLICY.endswith('_v2')
    assert selected['index_sha256'] == sha256(raw).hexdigest()
    canonical_row = json.dumps(rows()[1], sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    assert selected['row_sha256'] == sha256(canonical_row).hexdigest()
    assert len(selected) == 13


def test_future_and_same_day_rows_are_not_selected_even_with_files():
    value = rows()
    value[2]['webcast_PPT'] = '2026q3 webcast_ppt_en.pdf'
    assert choose(value)['period_label'] == '2026Q2'
    assert choose(value, '2026-10-27')['period_label'] == '2026Q2'
    assert choose(value, '2026-10-28')['period_label'] == '2026Q3'


def test_day_boundary_uses_taipei_not_utc():
    value = rows()
    value[2]['webcast_PPT'] = '2026q3 webcast_ppt_en.pdf'
    raw = json.dumps(value).encode()
    s = source()
    before = datetime.fromisoformat('2026-10-27T15:59:59+00:00').timestamp()
    after = datetime.fromisoformat('2026-10-27T16:00:00+00:00').timestamp()
    assert s.select_presentation(raw, before, index_year=2026, as_of_epoch=before)['period_label'] == '2026Q2'
    assert s.select_presentation(raw, after, index_year=2026, as_of_epoch=after)['period_label'] == '2026Q3'


def test_size_limits_do_not_parse_oversize_originals():
    s = source()
    with pytest.raises(ValueError, match='size'):
        s.parse_years(b' ' * 16_385, stamp('2026-10-16'), stamp('2026-10-16'))
    with pytest.raises(ValueError, match='size'):
        s.select_presentation(b' ' * 200_001, stamp('2026-10-16'), index_year=2026, as_of_epoch=stamp('2026-10-16'))


def test_empty_or_no_past_events_return_none_without_fetching_other_years():
    assert choose([]) is None
    assert choose([rows()[0]], '2026-04-27') is None
    assert choose([rows()[0]], '2026-04-01') is None


def test_latest_past_without_presentation_never_falls_back_to_q2():
    with pytest.raises(ValueError, match='no presentation attachment'):
        choose(rows(), '2026-10-28')


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


@pytest.mark.parametrize('field,bad', [
    ('Year', '2025'), ('Year', 2026), ('Quarter', '0'), ('Quarter', '5'), ('Quarter', True),
    ('AnnounceDate', '2026-07-28'), ('AnnounceDate', '2026/7/28'), ('AnnounceDate', '2026/02/30'),
    ('AnnounceDate', '2026/06/30'), ('AnnounceDate', '2027/07/28'),
    ('Id', '0656'), ('Id', 656), ('Id', '../656'), ('Id', '656?x=1'), ('Id', ''),
    ('webcast_PPT', '2026q1 webcast_ppt_en.pdf'), ('webcast_PPT', '../2026q2 webcast_ppt_en.pdf'),
    ('webcast_PPT', '2026q2%20webcast_ppt_en.pdf'), ('webcast_PPT', 'https://evil.example/a.pdf'),
    ('webcast_PPT', '2026q2\\webcast_ppt_en.pdf'), ('webcast_PPT', '2026q2 webcast_ppt_en.pdf?x=1'),
    ('release', '2025q2_release_en.pdf'), ('fcon', '2026q1_fcon_en.pdf'), ('FI', 'unqualified.pdf'),
    ('Webcast', 'https://www.zucast.com@evil.example/webcast/a'), ('Webcast', 1),
])
def test_row_schema_and_same_row_year_quarter_date_files_are_strict(field, bad):
    value = rows()
    value[1][field] = bad
    with pytest.raises(ValueError): choose(value)


@pytest.mark.parametrize('change', ['extra', 'missing', 'duplicate_row', 'conflicting_quarter', 'conflicting_id', 'invalid_future_row', 'not_list', 'too_many'])
def test_complete_index_cannot_hide_conflicts_in_unselected_rows(change):
    value = rows()
    if change == 'extra': value[0]['extra'] = 'ignored?'
    elif change == 'missing': value[0].pop('release')
    elif change == 'duplicate_row': value.append(deepcopy(value[0]))
    elif change == 'conflicting_quarter': value.append(dict(value[0], Id='997'))
    elif change == 'conflicting_id': value[2]['Id'] = value[1]['Id']
    elif change == 'invalid_future_row': value[2]['webcast_PPT'] = 'foreign.pdf'
    elif change == 'not_list': value = {'rows': value}
    else: value = value * 2
    with pytest.raises(ValueError): choose(value)


def test_duplicate_json_field_and_trailing_invalid_original_are_rejected():
    raw = (E / 'results.body').read_bytes()
    for changed in (raw.replace(b'"Id":"656"', b'"Id":"656","Id":"656"'), raw[:-1], raw + b'{}'):
        with pytest.raises(ValueError):
            source().select_presentation(changed, stamp('2026-10-16'), index_year=2026, as_of_epoch=stamp('2026-10-16'))


@pytest.mark.parametrize('field', sorted(('title', 'pdf_url', 'event_date', 'document_date', 'cover_month', 'period_label',
                                        'selection_policy', 'history_scope', 'index_year', 'quarter', 'index_sha256', 'row_sha256', 'selected_row')))
def test_descriptor_missing_fields_are_rejected(field):
    selected = choose(rows())
    selected.pop(field)
    with pytest.raises(ValueError): source().validate_selected_descriptor(selected)


@pytest.mark.parametrize('change', ['extra', 'url', 'date', 'period', 'title', 'policy', 'history', 'quarter_bool', 'year_float', 'row', 'row_hash', 'index_hash_shape'])
def test_descriptor_tampering_cannot_be_hidden_by_a_valid_attachment_regex(change):
    selected = choose(rows())
    if change == 'extra': selected['url_approved'] = True
    elif change == 'url': selected['pdf_url'] = selected['pdf_url'].replace('/656/', '/999/')
    elif change == 'date': selected['document_date'] = '2026-07-29'
    elif change == 'period': selected['period_label'] = '2026Q1'
    elif change == 'title': selected['title'] = 'Another issuer'
    elif change == 'policy': selected['selection_policy'] = 'v1'
    elif change == 'history': selected['history_scope'] = 'all history checked'
    elif change == 'quarter_bool': selected['quarter'] = True
    elif change == 'year_float': selected['index_year'] = 2026.0
    elif change == 'row': selected['selected_row']['Id'] = '999'
    elif change == 'row_hash': selected['row_sha256'] = '0' * 64
    else: selected['index_sha256'] = 'A' * 64
    with pytest.raises(ValueError): source().validate_selected_descriptor(selected)


def test_intrinsic_descriptor_is_not_publisher_membership_or_current_selection():
    s = source()
    original = json.dumps(rows(), separators=(',', ':')).encode()
    selected = choose(rows())
    selected['index_sha256'] = '0' * 64
    assert s.validate_selected_descriptor(selected) == selected  # Shape alone cannot prove this digest.
    with pytest.raises(ValueError): s.verify_selected_in_index(selected, original, stamp('2026-10-16'), as_of_epoch=stamp('2026-10-16'))
    # Self-consistent old/other attachment must still be rejected by full index replay.
    other = choose([rows()[0]])
    with pytest.raises(ValueError): s.verify_selected_in_index(other, original, stamp('2026-10-16'), as_of_epoch=stamp('2026-10-16'))
    selected = choose(rows())
    changed = original + b' '
    with pytest.raises(ValueError): s.verify_selected_in_index(selected, changed, stamp('2026-10-16'), as_of_epoch=stamp('2026-10-16'))


def test_returned_descriptor_is_detached_from_raw_input_and_validation_copy():
    s = source()
    selected = choose(rows())
    validated = s.validate_selected_descriptor(selected)
    validated['selected_row']['Id'] = '999'
    assert selected['selected_row']['Id'] == '656'
