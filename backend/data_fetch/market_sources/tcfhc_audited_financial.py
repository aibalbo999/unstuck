"""Position-bound holding-company facts in TCFHC's English annual books.

Only the selected full native pages are read. This is an English translation;
the Chinese original prevails. Comparative revisions are preserved, not resolved
here, and these financial-institution fields are not industrial revenue facts.
"""
from copy import deepcopy
from datetime import datetime
import math
import re
import time

from source_pdf_reader import SourcePdfError
from tcfhc_annual_pdf_reader import extract_tcfhc_book, validate_positioned_book
from .financial_institution_xbrl import FIELDS
from .official_xbrl_financial import FilingError

POLICY = 'tcfhc-audited-english-2021-2025-native-positioned.v1'
LEGAL = 'Taiwan Cooperative Financial Holding Co., Ltd.'
MONEY = re.compile(r'\$?(?:\(\d{1,3}(?:,\d{3})*\)|\(\d+\)|\d{1,3}(?:,\d{3})*|\d+|-)\Z')
PERCENT = re.compile(r'(?:\(\d+\)|\d+|-)\Z')
BANDS = {
    'balance': ((530, 610), (620, 650), (655, 735), (745, 775)),
    'income': ((250, 330), (340, 367), (375, 455), (465, 493), (500, 557)),
    'cash': ((395, 475), (480, 558)),
}
LABEL_END = {'balance': 525, 'income': 249, 'cash': 390}


def _compact(text):
    return re.sub(r'\s+', '', text).lower()


def _bad(reason):
    raise FilingError('TCFHC audited book ' + reason)


def _rows(page):
    groups = []
    for segment in sorted(page['segments'], key=lambda s: (-s['y'], s['x'])):
        if not segment['text'].strip():
            continue
        group = next((g for g in groups if abs(g['y'] - segment['y']) <= 1.5), None)
        if group is None:
            group = {'y': segment['y'], 'parts': []}
            groups.append(group)
        group['parts'].append(segment)
    for group in groups:
        spans = []
        seen = set()
        for s in sorted(group['parts'], key=lambda part: part['x']):
            identity = (s['x'], s['end_x'], s['y'], s['text'])
            if identity in seen:
                _bad('duplicated native text position')
            seen.add(identity)
            if spans and s['x'] - spans[-1]['end_x'] <= max(1.5, min(s['font_height'], spans[-1]['font_height']) / 2):
                spans[-1]['text'] += s['text']
                spans[-1]['end_x'] = s['end_x']
            else:
                spans.append({k: s[k] for k in ('text', 'x', 'end_x', 'font_height')})
        group.update(spans=spans, text=' '.join(s['text'] for s in spans))
    return groups


def _require(page, *phrases):
    # Independently emitted plain text and native coordinates must agree on
    # the issuer, statement role, annual period and unit, never just metadata.
    texts = (_compact(page['text']), _compact(' '.join(r['text'] for r in page['rows'])))
    if any(_compact(phrase) not in text for text in texts for phrase in phrases):
        _bad('issuer, annual period, statement role or unit invalid')


def _left(row, kind):
    return _compact(''.join(s['text'] for s in row['spans'] if s['end_x'] <= LABEL_END[kind]))


def _one(rows, predicate, reason='required financial row missing or duplicated'):
    found = [row for row in rows if predicate(row)]
    if len(found) != 1:
        _bad(reason)
    return found[0]


def _cells(row, kind):
    cells = [''] * len(BANDS[kind])
    for span in row['spans']:
        if span['end_x'] <= LABEL_END[kind]:
            continue
        indexes = [i for i, (lo, hi) in enumerate(BANDS[kind]) if lo <= span['x'] and span['end_x'] <= hi]
        if len(indexes) != 1:
            _bad('financial column position invalid')
        cells[indexes[0]] += re.sub(r'\s+', '', span['text'])
    return cells


def _header(page, year, kind):
    rows = page['rows']
    expected = [str(year), str(year - 1)] if kind == 'cash' else [str(year), '', str(year - 1), '']
    if kind == 'income':
        expected.append('(Decrease)')
    header_y = {'balance': 1033, 'income': 639 if year == 2024 else 625, 'cash': 650}[kind]
    header = _one(rows, lambda r: abs(r['y'] - header_y) <= 2 and [s['text'].strip() for s in r['spans']][:2] == [str(year), str(year - 1)],
                  'physical annual column header invalid')
    if _cells(header, kind) != expected:
        _bad('physical annual column order or position invalid')
    if kind != 'cash':
        amount_header = _one(rows, lambda r: _compact(r['text']).endswith('amount%amount%' + ('%' if kind == 'income' else '')),
                             'amount and percentage header invalid')
        if _cells(amount_header, kind) != ['Amount', '%', 'Amount', '%'] + (['%'] if kind == 'income' else []):
            _bad('amount and percentage columns invalid')
        if not 8 < header['y'] - amount_header['y'] < 17:
            _bad('amount header annual alignment invalid')
    return header


def _amount(cell):
    if not isinstance(cell, str) or len(cell) > 25 or not MONEY.fullmatch(cell):
        _bad('monetary cell invalid')
    cell = cell.removeprefix('$')
    if cell == '-':
        return 0  # Explicit printed dash only. A missing cell is never zero.
    number = int(cell.strip('()').replace(',', ''))
    return (-number if cell.startswith('(') else number) * 1000


def _values(page, row, header, kind):
    if not row['y'] < header['y']:
        _bad('financial row above annual header')
    cells = _cells(row, kind)
    indexes = (0, 1) if kind == 'cash' else (0, 2)
    for i, cell in enumerate(cells):
        if i not in indexes and not PERCENT.fullmatch(cell):
            _bad('percentage column invalid')
    values = [_amount(cells[i]) for i in indexes]
    basis = {'page': page['page_number'], 'row_y': row['y'], 'original_row': row['text'],
             'header_y': header['y'], 'header_original': header['text'],
             'monetary_cells': [cells[i] for i in indexes],
             'column_ranges': [list(BANDS[kind][i]) for i in indexes],
             'values_TWD': values}
    return values, basis


def _follow(rows, first, expected_label):
    index = rows.index(first)
    if index + 1 >= len(rows):
        _bad('wrapped financial row incomplete')
    row = rows[index + 1]
    if not 8 < first['y'] - row['y'] < 17 or not re.fullmatch(expected_label, _left(row, 'income')):
        _bad('wrapped financial row alignment invalid')
    if any(_cells(first, 'income')):
        _bad('wrapped financial row contains ambiguous values')
    return row


def parse_positioned_book(value, year):
    """Pure seam; inputs still receive the complete child-boundary validation."""
    validate_positioned_book(value, year)
    pages = {p['page_number']: {**p, 'rows': _rows(p)} for p in value['pages']}
    annual = f'December 31, {year} and {year - 1}'
    _require(pages[1], LEGAL + ' and Subsidiaries', 'Consolidated Financial Statements',
             'for the Years Ended ' + annual, 'Independent Auditors’ Report')
    _require(pages[3], 'INDEPENDENT AUDITORS’ REPORT', LEGAL + ' (TCFHC)', 'and its subsidiaries',
             'consolidated balance sheets as of ' + annual, 'In our opinion',
             'consolidated financial performance', 'consolidated cash flows')
    _require(pages[7], 'Deloitte & Touche', 'Notice to Readers',
             'translated into English from the original Chinese',
             'Chinese-language independent auditors’ report and consolidated financial statements shall prevail')
    audit_dates = re.findall(r'March\s+(\d{1,2}),\s*' + str(year + 1), pages[7]['text'])
    if len(audit_dates) != 1:
        _bad('auditor report date invalid')
    audited_on = datetime(year + 1, 3, int(audit_dates[0])).date().isoformat()
    income_pages = (9, 10, 11) if year == 2024 else (9, 10, 11, 12)
    cash_pages = (13, 14, 15) if year == 2024 else (14, 15, 16)
    headers = {}
    for n in (8,) + income_pages + cash_pages:
        kind = 'balance' if n == 8 else 'income' if n in income_pages else 'cash'
        role = {'balance': 'CONSOLIDATED BALANCE SHEETS', 'income': 'CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME',
                'cash': 'CONSOLIDATED STATEMENTS OF CASH FLOWS'}[kind]
        _require(pages[n], LEGAL + ' AND SUBSIDIARIES', role, annual, 'In Thousands of New Taiwan Dollars')
        if kind != 'balance':
            _require(pages[n], 'FOR THE YEARS ENDED ' + annual)
        headers[n] = _header(pages[n], year, kind)
    facts = {year: {}, year - 1: {}}
    basis = []

    def add(page_number, row, kind, tag, label_prefix=None):
        values, proof = _values(pages[page_number], row, headers[page_number], kind)
        if 'PurchaseOf' in tag and any(v > 0 for v in values):
            _bad('purchase cash-flow sign invalid')
        if tag in ('ifrs-full:Assets', 'ifrs-full:EquityAttributableToOwnersOfParent') and any(v <= 0 for v in values):
            _bad('holding-company balance value invalid')
        for period, amount in zip((year, year - 1), values):
            facts[period][tag] = amount
        basis.append({**proof, 'fact': tag, 'period_years': [year, year - 1], **({'label_prefix': label_prefix} if label_prefix else {})})
        return values

    balance = pages[8]['rows']
    liabilities = _one(balance, lambda r: _left(r, 'balance') == 'liabilitiesandequity')
    totals = [r for r in balance if _left(r, 'balance') == 'total']
    if len(totals) != 2 or not totals[0]['y'] > liabilities['y'] > totals[1]['y']:
        _bad('assets and liabilities balance sections invalid')
    assets = add(8, totals[0], 'balance', 'ifrs-full:Assets')
    if assets != _values(pages[8], totals[1], headers[8], 'balance')[0]:
        _bad('assets and liabilities totals disagree')
    equity_heading = _one(balance, lambda r: _left(r, 'balance') == 'equityattributabletoownersoftcfhc')
    parent_equity = _one(balance, lambda r: _left(r, 'balance') == 'totalequityattributabletoownersoftcfhc')
    total_equity = _one(balance, lambda r: _left(r, 'balance') == 'totalequity')
    if not liabilities['y'] > equity_heading['y'] > parent_equity['y'] > total_equity['y'] > totals[1]['y']:
        _bad('parent equity hierarchy invalid')
    add(8, parent_equity, 'balance', 'ifrs-full:EquityAttributableToOwnersOfParent')
    income = pages[9]['rows']
    interest = _one(income, lambda r: re.fullmatch(r'interestrevenue\(notes\d+', _left(r, 'income')))
    interest_row = _follow(income, interest, r'and\d+\)')
    add(9, interest_row, 'income', 'ifrs-full:RevenueFromInterest', interest['text'])
    add(9, _one(income, lambda r: _left(r, 'income') == 'netinterest'), 'income', 'tifrs-bsci-fh:NetInterestIncomeExpense')
    fee = _one(income, lambda r: _left(r, 'income') == 'servicefeeandcommissionincome,')
    fee_row = _follow(income, fee, r'net\(notes(?:\d+,)*\d+and\d+\)')
    add(9, fee_row, 'income', 'tifrs-bsci-fh:NetServiceFeeChargeAndCommissionsIncomeLoss', fee['text'])
    net_page = 10 if year == 2025 else 9
    add(net_page, _one(pages[net_page]['rows'], lambda r: _left(r, 'income') == 'totalnetrevenues'),
        'income', 'tifrs-bsci-fh:NetIncomeLoss')
    owner_page = 12 if year == 2025 else 11
    owner_rows = pages[owner_page]['rows']
    owner_heading = _one(owner_rows, lambda r: _left(r, 'income') == 'netincomeattributableto:')
    owner = _follow(owner_rows, owner_heading, 'ownersoftcfhc')
    add(owner_page, owner, 'income', 'ifrs-full:ProfitLossAttributableToOwnersOfParent', owner_heading['text'])
    cash_page = 14 if year == 2024 else 15
    cash = pages[cash_page]['rows']
    cfo = _one(cash, lambda r: _left(r, 'cash') in {
        'netcashgeneratedfrom(usedin)operatingactivities', 'netcashgeneratedfromoperatingactivities',
        'netcash(usedin)generatedfromoperatingactivities'})
    investing = _one(cash, lambda r: _left(r, 'cash') == 'cashflowsfrominvestingactivities')
    financing = _one(cash, lambda r: _left(r, 'cash') == 'cashflowsfromfinancingactivities')
    if not cfo['y'] > investing['y'] > financing['y']:
        _bad('cash-flow sections invalid')
    add(cash_page, cfo, 'cash', 'ifrs-full:CashFlowsFromUsedInOperatingActivities')
    for label, tag in (
        ('acquisitionofpropertiesandequipment', 'ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'),
        ('acquisitionofintangibleassets', 'ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'),
    ):
        row = _one(cash, lambda r: _left(r, 'cash') == label)
        if not investing['y'] > row['y'] > financing['y']:
            _bad('purchase outside investing section')
        add(cash_page, row, 'cash', tag)
    if any(set(row) != set(FIELDS) or any(type(n) is not int for n in row.values()) for row in facts.values()):
        _bad('ten annual financial-institution facts incomplete')
    return {'facts': facts, 'physical_fact_basis': basis,
            'selected_full_physical_pages': list(value['selected_full_physical_pages']),
            'source_unit': 'TWD_thousand', 'unit_multiplier': 1000, 'currency': 'TWD',
            'report_scope': 'consolidated', 'source_language': 'en', 'Chinese_original_prevails': True,
            'parent_profit_basis': 'explicit_net_income_attributable_to_owners_of_TCFHC_not_comprehensive_income',
            'audited_on': audited_on, 'complete_original_sha256': value['content_sha256'],
            'original_page_count': value['page_count'], 'parser_version': value['parser_version'],
            'coverage_status': 'selected_native_text_complete', 'whole_book_text_coverage_claimed': False,
            'comparative_revisions_preserved': True, 'policy': POLICY}


def parse_book(raw, year, *, timeout_seconds=10):
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 10:
        raise SourcePdfError('invalid_input')
    deadline = time.monotonic() + timeout_seconds
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SourcePdfError('timeout')
    value = extract_tcfhc_book(raw, year, timeout_seconds=remaining)
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')
    result = parse_positioned_book(value, year)
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')
    result = deepcopy(result)
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')
    return result
