"""Fail-closed native quarterly-table qualification, without transport or fact ingestion.

The two independently inspected quarters establish a text-layout contract, not
a PDF hash allowlist. Original bytes and complete native pages remain the
collector's responsibility; this pure qualifier supplies restricted role metadata.
"""
from datetime import date
from decimal import Decimal
from hashlib import sha256
import re

POLICY = 'macronix-quarterly-financial-results-v1'
COMPANY = 'Macronix International Co., Ltd.'
COPYRIGHT = 'Copyright © ' + COMPANY
TITLE = 'Quarterly Financial Results'
SAFE_HARBOR = '''Safe Harbor Statement
The presentation and discussion contain certain forward-looking statements with
respect to the results of operation, financial condition and current expectation. The
forward-looking statements are subject to known and unknown uncertainties and
risks that could cause actual results to differ materially from those expressed or
implied by such statements.
Such risks and uncertainties include but are not limited to the impact of competitive
products and pricing, timely design acceptance by our customers, timely introduction
of new technologies, ability to ramp new products into volume, industry wide shifts
in supply and demand for semiconductor products, industry overcapacity, availability
of manufacturing capacity, financial stability in end markets, and other risks.
The forward-looking statements in this release reflect the current belief of Macronix
as of the date of this release and Macronix undertakes no obligation to update these
forward-looking statements for events or circumstances that occur subsequent to
such date.'''

# Labels are the actual variants observed in Q1/Q2; order and cell counts matter.
ROWS = (
    ('net_sales', ('Net Sales',), 'TWD_million', 'percent'),
    ('gross_profit', ('Gross Profit',), 'TWD_million', 'percent'),
    ('gross_margin', ('Gross Margin%',), 'percent', 'ppt'),
    ('operating_expenses', ('Operating Expenses',), 'TWD_million', 'percent'),
    ('operating_income_loss', ('Operating Income (Loss)',), 'TWD_million', 'percent'),
    ('operating_margin', ('Operating Margin%',), 'percent', 'ppt'),
    ('non_operating_income_loss', ('Net Non-Operating Income (Loss)',), 'TWD_million', None),
    ('income_loss_before_taxes', ('(Loss)Income Before Taxes', 'Income (Loss) Before Taxes'), 'TWD_million', 'percent'),
    ('income_taxes', ('Income Taxes Benefit (Expense)', 'Income Taxes (Expense) Benefit'), 'TWD_million', None),
    ('net_income_loss', ('Net (Loss)Income', 'Net Income (Loss)'), 'TWD_million', 'percent'),
    ('basic_eps', ('Basic EPS (NT$)',), 'TWD_per_share', None),
    ('ebitda', ('EBITDA',), 'TWD_million', None),
    ('ebitda_margin', ('EBITDA %',), 'percent', None),
    ('weighted_average_shares', ('Weighted avg outstanding million shares',), 'million_shares', None),
)


def _fail(reason):
    raise ValueError('macronix_presentation_semantics:' + reason)


def _space(text):
    return ' '.join(text.split())


def _lines(page):
    return [_space(line) for line in page['text'].splitlines() if line.strip()]


def _body(page):
    lines = _lines(page)
    number = str(page['page_number'])
    if lines.count(COPYRIGHT) != 1 or lines.count(number) != 1:
        _fail('page_identity_or_footer')
    return [line for line in lines if line not in (COPYRIGHT, number)]


def _bad_text(text):
    return ('\ufffd' in text or re.search(r'\(cid:\d+\)', text) or any(
        0xe000 <= ord(c) <= 0xf8ff or 0xf0000 <= ord(c) <= 0xffffd
        or 0x100000 <= ord(c) <= 0x10fffd or 0xd800 <= ord(c) <= 0xdfff
        or (ord(c) < 32 and c not in '\n\r\t') for c in text))


def _native_pages(native):
    if not isinstance(native, dict):
        _fail('native_shape')
    count, pages = native.get('page_count'), native.get('pages')
    if (type(count) is not int or not 3 <= count <= 100 or not isinstance(pages, list)
            or len(pages) != count or not isinstance(native.get('parser_version'), str)
            or not native['parser_version'] or not isinstance(native.get('content_sha256'), str)
            or not re.fullmatch('[0-9a-f]{64}', native['content_sha256'])):
        _fail('native_shape')
    for n, page in enumerate(pages, 1):
        if (not isinstance(page, dict) or set(page) != {'page_number', 'text'}
                or type(page['page_number']) is not int or page['page_number'] != n
                or not isinstance(page['text'], str)):
            _fail('native_page_sequence')
    if sum(len(page['text']) for page in pages) > 200_000:
        _fail('native_text_limit')
    for key in ('empty_pages', 'garbled_pages'):
        values = native.get(key)
        if (not isinstance(values, list) or any(type(n) is not int or not 1 <= n <= count for n in values)
                or values != sorted(set(values))):
            _fail('native_coverage')
    if native['empty_pages'] != [p['page_number'] for p in pages if not p['text'].strip()]:
        _fail('native_empty_mismatch')
    if native.get('coverage_status') != ('partial' if native['empty_pages'] or native['garbled_pages'] else 'complete'):
        _fail('native_coverage')
    return pages


def _number(token, unit):
    if len(token) > 32:
        _fail('numeric_cell')
    negative = token.startswith('(') and token.endswith(')')
    text = token[1:-1] if negative else token
    suffix = '%' if unit == 'percent' else 'ppt' if unit == 'ppt' else ''
    if suffix:
        if not text.endswith(suffix):
            _fail('numeric_unit')
        text = text[:-len(suffix)]
    decimal = r'(?:\.[0-9]{1,2})?' if unit in ('percent', 'ppt', 'TWD_per_share') else ''
    if not re.fullmatch(r'(?:0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+)' + decimal, text):
        _fail('numeric_cell')
    value = Decimal(text.replace(',', ''))
    # Preserve the printed negative zero and decimal precision; no calculated facts.
    return ('-' if negative else '') + str(value)


def _financial_table(page, year, quarter):
    previous = (year, quarter - 1) if quarter > 1 else (year - 1, 4)
    periods = [(year, quarter), previous, (year - 1, quarter)]
    labels = [f'{q}Q{y % 100:02}' for y, q in periods]
    lines = _body(page)
    header = 'Unit:NTD Million (except EPS) ' + ' '.join(labels) + ' QoQ YoY'
    if (len(lines) != 16 or lines[0] != TITLE
            or lines[1].replace('：', ':').replace('Unit: ', 'Unit:') != header):
        _fail('quarterly_table_header_or_rows')
    rows = []
    for line, (field, aliases, unit, change_unit) in zip(lines[2:], ROWS):
        labels_found = [label for label in aliases if line.startswith(label + ' ')]
        if len(labels_found) != 1:
            _fail('quarterly_row_label')
        label = labels_found[0]
        cells = line[len(label):].split()
        if len(cells) != (5 if change_unit else 3):
            _fail('quarterly_cell_count')
        rows.append({'field': field, 'source_label': label, 'unit': unit,
                     'values': [_number(cell, unit) for cell in cells[:3]],
                     'qoq': _number(cells[3], change_unit) if change_unit else None,
                     'yoy': _number(cells[4], change_unit) if change_unit else None,
                     'change_unit': change_unit, 'original_cells': cells})
    return {'table_kind': 'quarterly_financial_results', 'page_number': page['page_number'],
            'page_text_sha256': sha256(page['text'].encode()).hexdigest(),
            'periods': [f'{y}Q{q}' for y, q in periods], 'rows': rows,
            'scope': 'issuer_reported_presentation_summary_not_audited_financial_statement'}


def qualify_presentation(native, selected):
    """Return deterministic whole-page role metadata, or ValueError on unknown layout.

    ``selected`` must be a validated same-row published descriptor. This function
    never fetches or infers an event from a filename, and never repairs glyphs.
    The collector must bind native text/digest to its complete original before use.
    """
    from .macronix_presentation_index import validate_selected_descriptor
    selected = validate_selected_descriptor(selected)
    year, quarter = selected['index_year'], selected['quarter']
    pages = _native_pages(native)
    ordinals = ('First', 'Second', 'Third', 'Fourth')
    cover = _lines(pages[0])
    if len(cover) != 3 or cover[:2] != [COMPANY, f'{ordinals[quarter - 1]} Quarter {year} Results']:
        _fail('cover_issuer_or_period')
    months = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')
    found = re.fullmatch(r'([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})', cover[2])
    if found is None or found[1] not in months:
        _fail('cover_date')
    cover_date = date(int(found[3]), months.index(found[1]) + 1, int(found[2])).isoformat()
    if cover_date != selected['event_date'] or cover_date != selected['document_date']:
        _fail('cover_date_binding')
    if _space(' '.join(_body(pages[1]))) != _space(SAFE_HARBOR):
        _fail('complete_disclaimer')
    candidates = [page for page in pages if TITLE in _lines(page)]
    if len(candidates) != 1 or candidates[0]['page_number'] <= 2:
        _fail('unique_substantive_financial_page')
    financial = candidates[0]
    selected_pages = [pages[0], pages[1], financial]
    excluded = set(native['empty_pages'] + native['garbled_pages'])
    if any(p['page_number'] in excluded or _bad_text(p['text']) for p in selected_pages):
        _fail('required_page_incomplete_or_garbled')
    table = _financial_table(financial, year, quarter)
    allowlist = [p['page_number'] for p in selected_pages]
    return {
        'semantic_policy': POLICY, 'presentation_cover_date': cover_date,
        'content_period': selected['period_label'], 'content_periods': table['periods'],
        'role_page_allowlist': allowlist, 'semantic_tables': [table],
        'qualified_page_text_sha256': {str(p['page_number']): sha256(p['text'].encode()).hexdigest() for p in selected_pages},
        'excluded_native_text_pages': [p['page_number'] for p in pages if p['page_number'] not in allowlist],
        'coverage_status': 'partial', 'native_text_coverage': native['coverage_status'],
        'financial_statement_complete': False, 'full_visual_content_verified': False,
        'period_scope_caution': 'Qualified table columns are ' + ', '.join(table['periods']) +
            '; quarter-only results. Excluded half-year, balance-sheet, LTM/annualized and product charts are not interchangeable periods.',
        'unit_scope_caution': 'Monetary rows use NTD million; Basic EPS uses NT$ per share; weighted-average outstanding shares use million shares. % and ppt are distinct. Parentheses denote negatives. Preserve reported rounding; do not sum EPS or rebalance source numbers.',
        'financial_scope_caution': 'Issuer presentation summaries do not establish audited consolidated or parent-attributable annual facts. No annual/TTM/FCF or financial-history inputs are derived or overwritten.',
        'native_editorial_caution': 'Only the whole cover, complete Safe Harbor Statement and uniquely qualified quarterly financial table are role-eligible. All original pages remain retained; no glyph substitutions or chart associations inferred.',
        'forward_looking_caution': 'Preserve the complete Safe Harbor Statement. Management expectations are not achieved outcomes; an agenda mentioning Q&A is not a transcript.',
        'visual_semantics_caution': 'Native table text qualification does not verify all images, diagrams, layout relationships or other financial pages. Unknown table formats require separate qualification.',
    }
