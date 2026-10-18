"""Saved official future-webcast card must not hide the published transcript."""
from datetime import datetime
import gzip
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import pytest

from test_delta_conference import harness, INDEX, PDF

OBSERVED = 1792136496.4587252
FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/delta2308_index_20261016.gz'


def original():
    return gzip.decompress(FIXTURE.read_bytes())


def edited(change):
    soup = BeautifulSoup(original().decode('utf-8'), 'html.parser')
    label = next(x for x in soup.select('span') if x.get_text(' ', strip=True) == '3Q Analyst Meeting')
    card = label.parent.parent
    region = card.find_parent(attrs={'role': 'region'})
    button = soup.find(id=region['aria-labelledby'])
    marker = next(x for x in card.select('span') if not x.find('span') and 'Live webcast will start' in x.get_text())
    change(soup, card, region, button, marker)
    return str(soup).encode('utf-8')


def test_saved_official_upcoming_card_keeps_latest_published_transcript():
    from data_fetch.market_sources.delta_conference import select_transcript
    selected = select_transcript(original(), as_of_epoch=OBSERVED)
    assert (selected['event_date'], selected['period'], selected['url']) == ('2026-07-30', '2026Q2', PDF)


def test_public_fetch_replays_full_transcript_with_saved_upcoming_card(harness, monkeypatch):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    from data_fetch.market_sources.delta_conference import verify_context
    monkeypatch.setattr(time, 'time', lambda: OBSERVED)
    bodies, calls = harness
    bodies[INDEX] = original()
    diagnostic = {}
    value = fetch_free_earnings_call_context('2308.TW', diagnostics=diagnostic)
    assert value.get('documents'), 'Future webcast card must not discard the published official 13-page transcript'
    assert value['period'] == '2026Q2'
    assert value['documents'][0]['page_count'] == 13
    assert value['documents'][0]['translation_accuracy_verified'] is False
    assert value['coverage_status'] == 'partial'
    assert diagnostic['delta_originals_verified'] is True
    assert verify_context(value, '2308.TW', max_age=1800)
    assert calls[-2:] == [INDEX, PDF]


@pytest.mark.parametrize('when', ['2026-10-29T09:00:00', '2026-10-30T09:00:00'])
def test_webcast_on_or_before_today_cannot_fall_back_to_old_quarter(when, monkeypatch):
    from data_fetch.market_sources.delta_conference import select_transcript
    epoch = datetime.fromisoformat(when).replace(tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    monkeypatch.setattr(time, 'time', lambda: epoch)
    with pytest.raises(ValueError, match='scheduled event is no longer future'):
        select_transcript(original(), as_of_epoch=epoch)


@pytest.mark.parametrize('change', [
    lambda s,c,r,b,m: m.clear(),
    lambda s,c,r,b,m: m.string.replace_with('Live webcast will start on Nov 31, 3 PM'),
    lambda s,c,r,b,m: m.string.replace_with('Live webcast will start on Oct 29, 13 PM'),
    lambda s,c,r,b,m: m.string.replace_with('Live webcast will start on Oct 29, 3 PM maybe'),
    lambda s,c,r,b,m: r.attrs.pop('aria-labelledby'),
    lambda s,c,r,b,m: b.attrs.update({'aria-controls': 'different-region'}),
    lambda s,c,r,b,m: b.clear(),
    lambda s,c,r,b,m: b.append(' and 2027'),
    lambda s,c,r,b,m: s.body.append(BeautifulSoup(str(b), 'html.parser')),
    lambda s,c,r,b,m: c.append(BeautifulSoup(str(m), 'html.parser')),
])
def test_unverified_future_card_still_rejects_entire_selection(change):
    from data_fetch.market_sources.delta_conference import select_transcript
    with pytest.raises(ValueError):
        select_transcript(edited(change), as_of_epoch=OBSERVED)


def test_future_year_comes_from_the_bound_official_section(monkeypatch):
    from data_fetch.market_sources.delta_conference import select_transcript
    epoch = datetime(2026, 12, 31, 9, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    monkeypatch.setattr(time, 'time', lambda: epoch)
    def separate_year(s,c,r,b,m):
        m.string.replace_with('Live webcast will start on Jan 29, 3 PM')
        label = next(x for x in c.select('span') if x.get_text(' ', strip=True) == '3Q Analyst Meeting')
        label.string.replace_with('1Q Analyst Meeting')
        section = s.new_tag('div')
        button = s.new_tag('button', id='delta-2027-year', attrs={'aria-controls': 'delta-2027-events'})
        button.string = '2027'
        region = s.new_tag('div', id='delta-2027-events', attrs={'role': 'region', 'aria-labelledby': 'delta-2027-year'})
        section.append(button)
        section.append(region)
        region.append(c.extract())
        s.body.append(section)
    assert select_transcript(edited(separate_year), as_of_epoch=epoch)['period'] == '2026Q2'


def test_past_section_year_cannot_be_guessed_as_current_year():
    from data_fetch.market_sources.delta_conference import select_transcript
    def year(s,c,r,b,m):
        for node in b.find_all(string=True):
            if node.strip() == '2026':
                node.replace_with('2025')
    with pytest.raises(ValueError):
        select_transcript(edited(year), as_of_epoch=OBSERVED)
