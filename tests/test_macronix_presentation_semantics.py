"""Quarterly presentation qualification uses real native text, not fixed PDF hashes."""
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'docs/evidence/source-acquisition'


def semantics():
    name = 'data_fetch.market_sources.macronix_presentation_semantics'
    assert importlib.util.find_spec(name), 'No dynamic quarterly financial-page qualifier exists'
    return importlib.import_module(name)


def example(quarter):
    path = (E / '20261016/macronix-quarter-fixture/q1-native.json' if quarter == 1
            else E / '20261015/macronix-dynamic-originals/presentation-native.json')
    value = json.loads(path.read_text())
    native = value.get('native', value)
    row = json.loads((E / '20261015/macronix-dynamic-originals/results.body').read_bytes())[quarter - 1]
    return native, row


def descriptor(row, observed=None):
    index = importlib.import_module('data_fetch.market_sources.macronix_presentation_index')
    from datetime import datetime
    from zoneinfo import ZoneInfo
    observed = observed or datetime(2026, 10, 16, 12, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    return index.select_presentation(json.dumps([row]).encode(), observed,
                                     index_year=int(row['Year']), as_of_epoch=observed)


@pytest.mark.parametrize('quarter,financial_page,net_sales,previous', [
    (1, 6, '10469', '2025Q4'), (2, 7, '19125', '2026Q1'),
])
def test_real_quarters_qualify_substantive_financial_page(quarter, financial_page, net_sales, previous):
    s = semantics()
    native, row = example(quarter)
    before = deepcopy(native)
    result = s.qualify_presentation(native, descriptor(row))
    assert native == before
    assert result['role_page_allowlist'] == [1, 2, financial_page]
    table = result['semantic_tables'][0]
    assert table['periods'] == [f'2026Q{quarter}', previous, f'2025Q{quarter}']
    assert len(table['rows']) == 14
    assert table['rows'][0]['values'][0] == net_sales
    assert table['page_number'] == financial_page
    assert result['financial_statement_complete'] is False
    assert result['full_visual_content_verified'] is False
    assert result['coverage_status'] == 'partial'


def replace_page(native, number, old, new):
    text = native['pages'][number - 1]['text']
    assert old in text
    native['pages'][number - 1]['text'] = text.replace(old, new)


@pytest.mark.parametrize('mutation', [
    'wrong_company', 'wrong_cover_quarter', 'wrong_cover_day', 'truncated_disclaimer',
    'wrong_unit', 'wrong_comparison_quarter', 'missing_row', 'duplicate_row',
    'extra_column', 'shifted_growth_cell', 'unknown_row', 'nonfinite', 'bad_grouping',
    'required_garbled_marker', 'unreported_pua', 'missing_page', 'duplicate_page',
    'only_cover_and_disclaimer', 'duplicate_financial_table',
])
def test_unknown_or_incomplete_presentation_is_rejected(mutation):
    s = semantics()
    native, row = example(2)
    if mutation == 'wrong_company':
        replace_page(native, 1, 'Macronix International', 'Different Issuer')
    elif mutation == 'wrong_cover_quarter':
        replace_page(native, 1, 'Second Quarter', 'First Quarter')
    elif mutation == 'wrong_cover_day':
        replace_page(native, 1, 'July 28', 'July 29')
    elif mutation == 'truncated_disclaimer':
        replace_page(native, 2, 'Macronix undertakes no obligation to update', 'Macronix will update')
    elif mutation == 'wrong_unit':
        replace_page(native, 7, 'NTD Million', 'USD Million')
    elif mutation == 'wrong_comparison_quarter':
        replace_page(native, 7, '2Q26 1Q26 2Q25', '2Q26 1Q26 1Q25')
    elif mutation == 'missing_row':
        replace_page(native, 7, 'Gross Profit 12,320 4,271 1,064 188% 1,058%\n', '')
    elif mutation == 'duplicate_row':
        replace_page(native, 7, 'Gross Profit 12,320 4,271 1,064 188% 1,058%',
                     'Net Sales 19,125 10,469 6,799 83% 181%')
    elif mutation == 'extra_column':
        replace_page(native, 7, 'Net Sales 19,125', 'Net Sales 999 19,125')
    elif mutation == 'shifted_growth_cell':
        replace_page(native, 7, '83% 181%', '83 181%')
    elif mutation == 'unknown_row':
        replace_page(native, 7, 'Net Income (Loss)', 'Comprehensive Income')
    elif mutation == 'nonfinite':
        replace_page(native, 7, 'Net Sales 19,125', 'Net Sales NaN')
    elif mutation == 'bad_grouping':
        replace_page(native, 7, 'Net Sales 19,125', 'Net Sales 1,91,25')
    elif mutation == 'required_garbled_marker':
        native['garbled_pages'] = sorted([7] + native['garbled_pages'])
    elif mutation == 'unreported_pua':
        replace_page(native, 7, 'Net Sales', '\uf075Net Sales')
    elif mutation == 'missing_page':
        native['pages'].pop(8)
    elif mutation == 'duplicate_page':
        native['pages'][8] = deepcopy(native['pages'][7])
    elif mutation == 'only_cover_and_disclaimer':
        replace_page(native, 7, 'Quarterly Financial Results', 'Business Update')
    elif mutation == 'duplicate_financial_table':
        native['pages'][8]['text'] = native['pages'][6]['text']
    with pytest.raises(ValueError):
        s.qualify_presentation(native, descriptor(row))


def test_same_layout_future_quarter_is_not_a_hash_allowlist():
    s = semantics()
    native, row = example(2)
    row.update(Quarter='3', AnnounceDate='2026/10/27', Id='658',
               webcast_PPT='2026q3 webcast_ppt_en.pdf', release='2026q3_release_en.pdf', fcon='2026q3_fcon_en.pdf')
    native['content_sha256'] = 'a' * 64
    replace_page(native, 1, 'Second Quarter', 'Third Quarter')
    replace_page(native, 1, 'July 28', 'October 27')
    replace_page(native, 7, '2Q26 1Q26 2Q25', '3Q26 2Q26 3Q25')
    # Different valid printed values are accepted; no claim that this synthetic
    # fixture is an acquired original or that the financial numbers are true.
    replace_page(native, 7, 'Net Sales 19,125', 'Net Sales 20,123')
    result = s.qualify_presentation(native, descriptor(row, 1793491200.))
    assert result['content_period'] == '2026Q3'
    assert result['semantic_tables'][0]['periods'] == ['2026Q3', '2026Q2', '2025Q3']
    assert result['semantic_tables'][0]['rows'][0]['values'][0] == '20123'


def test_cross_document_comparative_cells_and_distinct_units():
    s = semantics()
    one, one_row = example(1)
    two, two_row = example(2)
    first = s.qualify_presentation(one, descriptor(one_row))['semantic_tables'][0]
    second = s.qualify_presentation(two, descriptor(two_row))['semantic_tables'][0]
    for earlier, later in zip(first['rows'], second['rows']):
        assert earlier['field'] == later['field']
        assert earlier['values'][0] == later['values'][1]
    rows = {r['field']: r for r in second['rows']}
    assert rows['gross_margin']['unit'] == 'percent'
    assert rows['gross_margin']['qoq'] == '23.6' and rows['gross_margin']['change_unit'] == 'ppt'
    assert rows['operating_expenses']['values'][0] == '-3352'
    assert rows['basic_eps']['values'][0] == '3.91' and rows['basic_eps']['unit'] == 'TWD_per_share'
    assert rows['weighted_average_shares']['unit'] == 'million_shares'
    assert rows['ebitda_margin']['values'][2] == '-0'
    assert rows['non_operating_income_loss']['qoq'] is None


def test_descriptor_tamper_is_not_rescued_by_valid_native_text():
    s = semantics()
    native, row = example(2)
    selected = descriptor(row)
    selected['pdf_url'] = selected['pdf_url'].replace('/656/', '/652/')
    with pytest.raises(ValueError):
        s.qualify_presentation(native, selected)
