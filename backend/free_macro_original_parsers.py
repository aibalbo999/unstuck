"""Parse qualified free macro originals without acquisition or cache side effects.

Caller must retain and authenticate native HTTP originals separately. Parsed values
never establish HTTP acquisition, historical publication time, or cache freshness."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import csv
import io
import json
import zipfile
import math
import re
from xml.etree.ElementTree import iterparse

def body(raw, maximum):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= maximum:
        raise ValueError('invalid original body size')
    return raw

def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('numeric value outside finite range')
    return result

def number(value):
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('invalid numeric value')
    if not n.is_finite():
        raise ValueError('nonfinite numeric value')
    return n

def recent(day, asof, maximum):
    if not 0 <= (asof - day).days <= maximum:
        raise ValueError('future or stale observation')

def cboe_vix(raw, asof):
    rows = list(csv.DictReader(io.StringIO(body(raw, 2000000).decode('utf-8-sig'))))
    if not rows or set(rows[0]) != {'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE'}:
        raise ValueError('VIX schema')
    seen = set()
    valid = []
    for row in rows:
        if set(row) != {'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE'}:
            raise ValueError('VIX row schema')
        day = datetime.strptime(row['DATE'], '%m/%d/%Y').date()
        if day in seen or day > asof:
            raise ValueError('duplicate or future VIX date')
        seen.add(day)
        valid.append((day, row))
    day, row = max(valid, key=lambda x: x[0])
    recent(day, asof, 7)
    close, low, high, opening = (number(row[k]) for k in ('CLOSE', 'LOW', 'HIGH', 'OPEN'))
    if not 0 < low <= min(opening, close) <= max(opening, close) <= high:
        raise ValueError('invalid VIX OHLC')
    return {'date': day.isoformat(), 'value': finite_float(close), 'unit': 'index', 'source_series': 'VIX', 'provider': 'Cboe', 'price_field': 'CLOSE', 'historical_pit_verified': False}

def bls_cpi(raw, asof):
    payload = json.loads(body(raw, 2000000))
    series = payload.get('Results', {}).get('series', [])
    if payload.get('status') != 'REQUEST_SUCCEEDED' or len(series) != 1 or series[0].get('seriesID') != 'CUSR0000SA0':
        raise ValueError('BLS identity or status')
    rows = {}
    for row in series[0].get('data', []):
        period = row.get('period', '')
        if period == 'M13':
            continue
        if period not in {f'M{x:02d}' for x in range(1, 13)}:
            raise ValueError('invalid monthly period')
        day = date(int(row['year']), int(period[1:]), 1)
        value = None if row['value'] == '-' else number(row['value'])
        if day in rows or day > asof or (value is not None and value <= 0):
            raise ValueError('invalid CPI row')
        rows[day] = value
    if not rows:
        raise ValueError('empty CPI')
    day = max(rows)
    recent(day, asof, 90)
    prior = date(day.year - 1, day.month, 1)
    if prior not in rows or rows[day] is None or rows[prior] is None:
        raise ValueError('missing exact same-month comparison')
    return {'date': day.isoformat(), 'prior_date': prior.isoformat(), 'value': finite_float((rows[day] / rows[prior] - 1) * 100), 'unit': '%', 'source_series': 'CUSR0000SA0', 'provider': 'BLS', 'seasonal_adjustment': 'seasonally_adjusted', 'historical_pit_verified': False, 'missing_observation_dates': [x.isoformat() for x, v in rows.items() if v is None]}
FED_ATTRIBUTES = {'CURRENCY': 'NA', 'FREQ': '9', 'INSTRUMENT': 'TCMNOM', 'MATURITY': 'Y10', 'SERIES_NAME': 'RIFLGFCY10_N.B', 'UNIT': 'Percent:_Per_Year', 'UNIT_MULT': '1'}

def fed_series(attributes, rows, asof):
    if attributes != FED_ATTRIBUTES:
        raise ValueError('H15 series dimensions differ')
    valid = {}
    seen = set()
    for row in rows:
        day = date.fromisoformat(row['TIME_PERIOD'])
        if day in seen or day > asof:
            raise ValueError('duplicate or future H15 date')
        seen.add(day)
        if row.get('OBS_STATUS') != 'A':
            continue
        value = number(row['OBS_VALUE'])
        if not Decimal('-10') <= value <= Decimal('100'):
            raise ValueError('invalid yield')
        valid[day] = value
    if not valid:
        raise ValueError('no active H15 observation')
    day = max(valid)
    recent(day, asof, 7)
    return {'date': day.isoformat(), 'value': finite_float(valid[day]), 'unit': '%', 'source_series': 'RIFLGFCY10_N.B', 'provider': 'FederalReserve', 'frequency': 'daily', 'historical_pit_verified': False}

def fed_h15(raw, asof):
    archive = zipfile.ZipFile(io.BytesIO(body(raw, 16000000)))
    members = archive.infolist()
    if len(members) > 16 or len({x.filename for x in members}) != len(members) or sum((x.file_size for x in members)) > 85000000 or any((x.flag_bits & 1 for x in members)):
        raise ValueError('unsafe H15 archive')
    xml = archive.read('H15_data.xml')
    text = xml.decode('utf-8-sig')
    if '\x00' in text or re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', text, re.IGNORECASE):
        raise ValueError('DTD or entities forbidden')
    matches = []
    for _, element in iterparse(io.StringIO(text), events=('end',)):
        if element.tag.rsplit('}', 1)[-1] == 'Series':
            if element.attrib.get('SERIES_NAME') == 'RIFLGFCY10_N.B':
                matches.append(fed_series(dict(element.attrib), [dict(x.attrib) for x in element if x.tag.rsplit('}', 1)[-1] == 'Obs'], asof))
            element.clear()
    if len(matches) != 1:
        raise ValueError('H15 identity not unique')
    return matches[0]
