"""Pure validation of Macronix's published quarterly-results JSON and rows.

No HTTP, cache or storage access. Descriptor self-consistency is distinct from
membership in the complete acquired index; callers must verify both.
"""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
from zoneinfo import ZoneInfo
import json
import math
import re
import time

YEARS_URL = 'https://www.macronix.com/_layouts/15/zMacronixPortal2016/getColumnListByLanguageJson.aspx?listName=QuarterlyResults&selectColumn=Year&lan=EN'
POLICY = 'latest_published_past_quarter_from_complete_issuer_index_v2'
ROW_FIELDS = frozenset(('Year', 'Quarter', 'AnnounceDate', 'Webcast', 'Id', 'release', 'fcon', 'webcast_PPT', 'FI'))
DESCRIPTOR_FIELDS = frozenset(('title', 'pdf_url', 'event_date', 'document_date', 'cover_month',
                             'period_label', 'selection_policy', 'history_scope', 'index_year',
                             'quarter', 'index_sha256', 'row_sha256', 'selected_row'))
_QUARTERS = ('First', 'Second', 'Third', 'Fourth')
_ZONE = ZoneInfo('Asia/Taipei')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _year(value):
    _require(type(value) is int and 1000 <= value <= 9999, 'year must be a four-digit integer')
    return value


def _day(epoch):
    _require(type(epoch) in (int, float), 'invalid observation epoch')
    try:
        _require(math.isfinite(epoch) and epoch > 0, 'invalid observation epoch')
        return datetime.fromtimestamp(epoch, _ZONE).date()
    except (ValueError, OverflowError, OSError) as exc:
        raise ValueError('invalid observation epoch') from exc


def _clock(epoch, as_of_epoch):
    observed = time.time() if as_of_epoch is None else as_of_epoch
    received_day, observed_day = _day(epoch), _day(observed)
    _require(epoch <= observed, 'original acquisition is in the future')
    return received_day, observed_day


def _json(raw, limit):
    _require(isinstance(raw, bytes) and 0 < len(raw) <= limit, 'invalid JSON original size')
    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value, 'duplicate JSON field')
            value[key] = item
        return value
    def constant(value):
        raise ValueError('non-finite JSON constant')
    try:
        return json.loads(raw.decode('utf-8-sig', 'strict'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('invalid JSON original') from exc


def index_url(year):
    return ('https://www.macronix.com/_layouts/15/zMacronixPortal2016/about/'
            'getQuarterlyResultsJson.aspx?Year=' + str(_year(year)) + '&Language=EN')


def parse_years(raw, epoch, as_of_epoch=None):
    received, observed = _clock(epoch, as_of_epoch)
    values = _json(raw, 16_384)
    _require(type(values) is list and 0 < len(values) <= 128, 'invalid published years schema')
    years = []
    for value in values:
        _require(type(value) is str and re.fullmatch(r'[1-9][0-9]{3}', value), 'invalid published year')
        year = _year(int(value))
        _require(year <= min(received.year, observed.year), 'future published year')
        _require(year not in years, 'duplicate published year')
        years.append(year)
    return sorted(years, reverse=True)


def _row(value, index_year):
    _year(index_year)
    _require(type(value) is dict and set(value) == ROW_FIELDS, 'invalid quarterly row schema')
    _require(type(value['Year']) is str and value['Year'] == str(index_year), 'row year differs from index year')
    _require(type(value['Quarter']) is str and value['Quarter'] in ('1', '2', '3', '4'), 'invalid quarter')
    quarter = int(value['Quarter'])
    text = value['AnnounceDate']
    _require(type(text) is str and re.fullmatch(r'[1-9][0-9]{3}/[0-9]{2}/[0-9]{2}', text), 'invalid announcement date')
    try:
        event = date.fromisoformat(text.replace('/', '-'))
        if quarter == 4:
            first, following = date(index_year + 1, 1, 1), date(index_year + 1, 4, 1)
        else:
            first = date(index_year, quarter * 3 + 1, 1)
            following = date(index_year + 1, 1, 1) if quarter == 3 else date(index_year, quarter * 3 + 4, 1)
    except ValueError as exc:
        raise ValueError('invalid announcement date') from exc
    _require(first <= event < following, 'announcement date conflicts with reported quarter')
    _require(type(value['Id']) is str and re.fullmatch(r'[1-9][0-9]{0,9}', value['Id']), 'invalid attachment row Id')
    prefix = str(index_year) + 'q' + str(quarter)
    for field, suffix in (('release', '_release_en.pdf'), ('fcon', '_fcon_en.pdf'), ('webcast_PPT', ' webcast_ppt_en.pdf')):
        file = value[field]
        _require(file is None or (type(file) is str and file == prefix + suffix), 'attachment name conflicts with row: ' + field)
    webcast = value['Webcast']
    _require(webcast is None or (type(webcast) is str and (webcast == '' or re.fullmatch(r'https://www\.zucast\.com/webcast/[A-Za-z0-9_-]{1,128}', webcast))), 'invalid webcast field')
    _require(value['FI'] is None, 'unqualified non-null FI field')
    return event, quarter


def _row_hash(row):
    return sha256(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _descriptor(row, index_year, index_sha256):
    event, quarter = _row(row, index_year)
    _require(row['webcast_PPT'] is not None, 'latest past event has no presentation attachment')
    from urllib.parse import quote
    period = str(index_year) + 'Q' + str(quarter)
    return {'title': 'Macronix ' + _QUARTERS[quarter - 1] + ' Quarter ' + str(index_year) + ' Results',
            'pdf_url': 'https://www.macronix.com/Lists/QuarterlyResults/Attachments/' + row['Id'] + '/' + quote(row['webcast_PPT'], safe=''),
            'event_date': event.isoformat(), 'document_date': event.isoformat(), 'cover_month': event.strftime('%Y-%m'),
            'period_label': period, 'selection_policy': POLICY,
            'history_scope': str(index_year) + ' complete official quarterly index; selected ' + period + '; future/same-day events excluded; no earlier-event fallback.',
            'index_year': index_year, 'quarter': quarter, 'index_sha256': index_sha256,
            'row_sha256': _row_hash(row), 'selected_row': deepcopy(row)}


def select_presentation(raw, epoch, *, index_year, as_of_epoch=None):
    received, observed = _clock(epoch, as_of_epoch)
    _year(index_year)
    _require(index_year <= min(received.year, observed.year), 'index year is in the future')
    values = _json(raw, 200_000)
    _require(type(values) is list and len(values) <= 4, 'invalid complete quarterly index schema')
    validated, quarters, ids, dates = [], set(), set(), set()
    for row in values:
        event, quarter = _row(row, index_year)
        _require(quarter not in quarters and row['Id'] not in ids and event not in dates, 'duplicate or conflicting quarterly rows')
        quarters.add(quarter)
        ids.add(row['Id'])
        dates.add(event)
        validated.append((event, row))
    past = [(event, row) for event, row in validated if event < observed]
    if not past:
        return None
    event, selected = max(past, key=lambda item: item[0])
    _require(event < received, 'selected event was not past when original was acquired')
    _require((observed - event).days <= 370, 'latest past event exceeds 370 days')
    return _descriptor(selected, index_year, sha256(raw).hexdigest())


def validate_selected_descriptor(selected):
    """Return canonical self-consistent fields, not proof of publisher membership."""
    _require(type(selected) is dict and set(selected) == DESCRIPTOR_FIELDS, 'invalid selected descriptor schema')
    _year(selected['index_year'])
    _require(type(selected['quarter']) is int and 1 <= selected['quarter'] <= 4, 'invalid selected quarter')
    for field in ('index_sha256', 'row_sha256'):
        _require(type(selected[field]) is str and re.fullmatch(r'[0-9a-f]{64}', selected[field]), 'invalid selected digest')
    rebuilt = _descriptor(selected['selected_row'], selected['index_year'], selected['index_sha256'])
    _require(selected == rebuilt, 'selected descriptor differs from its complete row')
    return rebuilt


def verify_selected_in_index(selected, raw, epoch, *, as_of_epoch=None):
    """Bind every selected field/hash to the actual complete acquired index."""
    rebuilt = validate_selected_descriptor(selected)
    actual = select_presentation(raw, epoch, index_year=rebuilt['index_year'], as_of_epoch=as_of_epoch)
    _require(actual is not None and actual == rebuilt, 'selected descriptor is not the selected original index row')
    return actual
