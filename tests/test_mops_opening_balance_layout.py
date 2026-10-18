"""Observed complete public balance sheets with a separate opening period."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import gzip
import json
import pytest

from data_fetch.market_sources.mops_public_annual import parse_statement
from data_fetch.market_sources.official_xbrl_financial import FilingError

FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition/mops_opening_balance_full_20261011'
MANIFEST = json.loads((FIXTURES / 'manifest.json').read_text())


def original(issuer):
    part = MANIFEST['parts'][issuer]
    raw = gzip.open(FIXTURES / part['filename'], 'rb').read()
    unit = gzip.open(FIXTURES / MANIFEST['unit']['filename'], 'rb').read()
    assert len(raw) == part['bytes'] and sha256(raw).hexdigest() == part['sha256']
    assert sha256(unit).hexdigest() == MANIFEST['unit']['sha256']
    return raw, unit, part['year']


@pytest.mark.parametrize('issuer', ['2023', '2466'])
def test_published_three_period_balance_uses_only_two_explicit_closing_periods(issuer):
    raw, unit, year = original(issuer)
    value = parse_statement(raw, issuer, year, 'BalanceSheet', unit)
    rows = json.loads(raw)['result']['reportList']
    for tag, label in [('Assets', '資產總額'), ('EquityAttributableToOwnersOfParent', '歸屬於母公司業主之權益合計')]:
        row = next(r for r in rows if r[0].strip() == label)
        assert value[year][tag] == int(row[1].replace(',', '')) * 1000
        assert value[year-1][tag] == int(row[3].replace(',', '')) * 1000
        assert row[3] != row[5], 'native evidence must discriminate opening from closing amount'
    assert set(value) == {year, year-1, 'company_abbreviation'}


@pytest.mark.parametrize('change', ['opening_year', 'opening_month', 'opening_day', 'opening_subcolumns',
    'closing_order', 'missing_percent', 'extra_period', 'truncated_row',
    'extra_cell', 'parent_scope', 'issuer_reference', 'template'])
def test_ambiguous_or_malformed_periods_units_scope_and_width_still_fail_closed(change):
    raw, unit, year = original('2023')
    value = json.loads(raw)
    result = value['result']; titles = result['titles']
    if change == 'opening_year': titles[3]['main'] = '111年01月01日'
    elif change == 'opening_month': titles[3]['main'] = '112年02月01日'
    elif change == 'opening_day': titles[3]['main'] = '112年01月02日'
    elif change == 'opening_subcolumns': titles[3]['sub'].reverse()
    elif change == 'closing_order': titles[1], titles[2] = titles[2], titles[1]
    elif change == 'missing_percent': titles[1]['sub'].pop()
    elif change == 'extra_period': titles.append(deepcopy(titles[3]))
    elif change in {'truncated_row', 'extra_cell'}:
        row = next(r for r in result['reportList'] if r[0].strip() == '資產總額')
        if change == 'truncated_row': row.pop()
        else: row.append('1')
    elif change == 'parent_scope': result['reportType'] = '個別'
    elif change == 'issuer_reference': result['urlList'][0]['url'] = result['urlList'][0]['url'].replace('CO_ID=2023', 'CO_ID=2466')
    elif change == 'template': unit += b' changed'
    with pytest.raises(FilingError):
        parse_statement(json.dumps(value, ensure_ascii=False).encode(), '2023', year, 'BalanceSheet', unit)


def test_two_period_balance_preserves_original_amount_columns():
    raw, unit, year = original('2466'); value = json.loads(raw)
    result = value['result']; result['titles'].pop()
    result['reportList'] = [row[:5] for row in result['reportList']]
    parsed = parse_statement(json.dumps(value, ensure_ascii=False).encode(), '2466', year, 'BalanceSheet', unit)
    assets = next(row for row in result['reportList'] if row[0].strip() == '資產總額')
    assert parsed[year-1]['Assets'] == int(assets[3].replace(',', '')) * 1000


@pytest.mark.parametrize('statement', ['IncomeStatement', 'CashflowStatement'])
def test_opening_balance_exception_never_admits_a_third_flow_statement_period(statement):
    raw, _, year = original('2023'); value = json.loads(raw); titles = value['result']['titles']
    titles[1]['main'] = str(year-1911)+'年度'; titles[2]['main'] = str(year-1912)+'年度'
    if statement == 'CashflowStatement':
        for title in titles[1:]: title['sub'] = [{'main': '金額', 'sub': []}]
    part = MANIFEST['other_units'][statement]
    unit = gzip.open(FIXTURES / part['filename'], 'rb').read()
    assert sha256(unit).hexdigest() == part['sha256']
    with pytest.raises(FilingError, match='annual amount-column alignment mismatch'):
        parse_statement(json.dumps(value, ensure_ascii=False).encode(), '2023', year, statement, unit)
