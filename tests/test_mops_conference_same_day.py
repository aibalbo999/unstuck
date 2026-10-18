"""Real MOPS schedule cannot become a completed call before its local start."""
from datetime import date,datetime
import gzip
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import official_financials_mops_conference as mops


class Day(date):
    @classmethod
    def today(cls):return cls(2026,10,12)


def original():return gzip.decompress((Path(__file__).parent/'fixtures/source_acquisition/mops2408_same_day_conference_20261012.html.gz').read_bytes()).decode('utf-8')


def clock(monkeypatch,hour,minute=0):
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,10,12,hour,minute,tzinfo=tz)
    monkeypatch.setattr(mops,'date',Day)
    monkeypatch.setattr(mops,'datetime',Clock,raising=False)


def test_same_day_1500_call_is_not_completed_at_0800_and_prior_rows_stay(monkeypatch):
    clock(monkeypatch,8)
    rows=mops.parse_conference_response(original(),'2408',http_status=200)
    assert len(rows)==17 and not any(r['date']=='2026-10-12'for r in rows)
    assert any(r['date']=='2026-09-21' and r['time']=='14:00'for r in rows)


def test_past_local_start_time_keeps_the_existing_scheduled_event_metadata(monkeypatch):
    clock(monkeypatch,16)
    rows=mops.parse_conference_response(original(),'2408',http_status=200)
    assert len(rows)==18 and rows[0]['date']=='2026-10-12' and rows[0]['time']=='15:00'


def test_past_dates_and_original_material_file_date_are_exactly_retained(monkeypatch):
    clock(monkeypatch,16);before=mops.parse_conference_response(original(),'2408',http_status=200)
    clock(monkeypatch,8);after=mops.parse_conference_response(original(),'2408',http_status=200)
    assert after==[r for r in before if r['date']<'2026-10-12']
    assert any(m['url'].endswith('240820260819E001.pdf')for r in after for m in r['materials'])


def test_midnight_uses_one_taipei_instant_for_calendar_and_start_time(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,10,13,0,0,tzinfo=tz)
    monkeypatch.setattr(mops,'date',Day)
    monkeypatch.setattr(mops,'datetime',Clock)
    rows=mops.parse_conference_response(original(),'2408',http_status=200)
    assert len(rows)==18 and rows[0]['date']=='2026-10-12'
    assert rows[0]['time']=='15:00' and rows[0]['materials']==[]


@pytest.mark.parametrize('unknown_time', ['未公告', '00:99', '24:00'])
def test_unknown_or_invalid_same_day_start_is_not_established(monkeypatch,unknown_time):
    clock(monkeypatch,23)
    soup=BeautifulSoup(original(),'html.parser')
    row=next(r for r in soup.find_all('tr') if '115/10/12' in r.get_text())
    cells=row.find_all('td',recursive=False)
    assert cells[2].get_text(strip=True)=='115/10/12' and cells[3].get_text(strip=True)=='15:00'
    cells[3].string=unknown_time
    text=str(soup)
    rows=mops.parse_conference_response(text,'2408',http_status=200)
    assert not any(r['date']=='2026-10-12'for r in rows)
