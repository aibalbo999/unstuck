from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from data_fetch.market_sources.tcfhc_audited_financial import parse_book
from data_fetch.market_sources.financial_institution_xbrl import FIELDS
from source_pdf_reader import extract_pdf_pages, SourcePdfError

D = Path(__file__).resolve().parents[1] / 'docs/evidence/source-acquisition/20261014/remaining-four-next'
CF = 'ifrs-full:CashFlowsFromUsedInOperatingActivities'
INTANGIBLE = 'ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'


@pytest.mark.parametrize('year,cfo', [(2021, 59274498), (2022, 46957311), (2023, 2157615), (2024, -2604248), (2025, 6034782)])
def test_full_official_books_supply_ten_position_bound_current_and_comparative_facts(year, cfo):
    raw = (D / f'tcfhc-audited-{year}-english-pdf.body').read_bytes()
    result = parse_book(raw, year)
    assert set(result['facts']) == {year, year-1}
    assert all(set(row) == set(FIELDS) for row in result['facts'].values())
    assert all(type(n) is int for row in result['facts'].values() for n in row.values())
    assert result['facts'][year][CF] == cfo * 1000
    assert result['facts'][year][INTANGIBLE] < 0
    assert result['Chinese_original_prevails'] is True
    assert result['report_scope'] == 'consolidated'
    assert result['source_unit'] == 'TWD_thousand'


def test_generic_reader_still_rejects_large_page_count():
    raw = (D / 'tcfhc-audited-2022-english-pdf.body').read_bytes()
    with pytest.raises(SourcePdfError, match='page_limit'):
        extract_pdf_pages(raw)

from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
import json

import data_fetch.market_sources.tcfhc_audited_financial as annual
import tcfhc_annual_pdf_reader as reader
from data_fetch.market_sources.official_xbrl_financial import FilingError

TAGS = [
    'ifrs-full:Assets', 'ifrs-full:EquityAttributableToOwnersOfParent',
    'ifrs-full:RevenueFromInterest', 'tifrs-bsci-fh:NetInterestIncomeExpense',
    'tifrs-bsci-fh:NetServiceFeeChargeAndCommissionsIncomeLoss', 'tifrs-bsci-fh:NetIncomeLoss',
    'ifrs-full:ProfitLossAttributableToOwnersOfParent', CF,
    'ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities', INTANGIBLE,
]
PRIMARY_THOUSANDS = {
    2021: [4433836855,236227474,49330655,36002902,8439492,54412693,20533879,59274498,-1083618,-193369],
    2022: [4476167813,215446776,63731513,37763642,7743550,53182152,20248985,46957311,-1271544,-525906],
    2023: [4803702956,239890248,93411635,31963093,8816239,61377038,17263694,2157615,-1144371,-493026],
    2024: [5165509688,254049424,106304142,30173537,11080365,65823692,19219939,-2604248,-1238112,-723211],
    2025: [5380837935,279252593,109078102,34530572,10652110,74387625,21294771,6034782,-1456332,-498732],
}


@pytest.fixture(scope='module')
def originals():
    return {y: (D / f'tcfhc-audited-{y}-english-pdf.body').read_bytes() for y in range(2021, 2026)}


@pytest.fixture(scope='module')
def positioned(originals):
    return {y: reader.extract_tcfhc_book(raw, y) for y, raw in originals.items()}


def page(value, number):
    return next(p for p in value['pages'] if p['page_number'] == number)


def segment(value, number, text):
    p = page(value, number)
    direct = next((s for s in p['segments'] if s['text'] == text), None)
    if direct is not None:
        return direct
    # Native PDF sometimes emits one character per text-show operation. Join
    # only the exact original positioned span to make the counterexample edit.
    for row in annual._rows(p):
        span = next((s for s in row['spans'] if s['text'].strip() == text), None)
        if span is None:
            continue
        covered = [s for s in p['segments'] if abs(s['y'] - row['y']) <= 1.5 and
                   span['x'] - .01 <= s['x'] and s['end_x'] <= span['end_x'] + .01]
        assert covered
        for original in covered:
            p['segments'].remove(original)
        joined = {**span, 'y': row['y'], 'text': span['text'].strip()}
        p['segments'].append(joined)
        return joined
    raise AssertionError(f'native segment not found: {number} {text}')


def replace_page_text(value, number, old, new):
    p = page(value, number)
    assert old in p['text']
    p['text'] = p['text'].replace(old, new)
    for s in p['segments']:
        s['text'] = s['text'].replace(old, new)


@pytest.mark.parametrize('year', range(2021, 2026))
def test_all_ten_primary_values_native_coordinates_and_comparative_revisions(positioned, originals, year):
    value = positioned[year]
    result = annual.parse_positioned_book(value, year)
    assert result['complete_original_sha256'] == sha256(originals[year]).hexdigest()
    assert result['facts'][year] == dict(zip(TAGS, (n * 1000 for n in PRIMARY_THOUSANDS[year])))
    assert result['selected_full_physical_pages'] == list(reader.SELECTED[year])
    assert result['original_page_count'] == reader.PAGE_COUNTS[year]
    assert result['whole_book_text_coverage_claimed'] is False
    assert len(result['physical_fact_basis']) == 10
    assert all(len(b['monetary_cells']) == 2 and b['period_years'] == [year, year-1] for b in result['physical_fact_basis'])
    if year > 2021:
        expected = dict(zip(TAGS, (n * 1000 for n in PRIMARY_THOUSANDS[year-1])))
        if year == 2024:
            expected['ifrs-full:Assets'] = 4797206197 * 1000
        assert result['facts'][year-1] == expected


@pytest.mark.parametrize('number,old,new', [
    (1,'Taiwan','Other'), (3,'TCFHC','Other'), (8,'CONSOLIDATED','SEPARATE'),
    (9,'2025','2023'), (15,'Thousands','Millions'), (7,'shall','may'),
])
def test_identity_scope_annual_period_unit_translation_tampering_is_rejected(positioned, number, old, new):
    value = deepcopy(positioned[2025])
    replace_page_text(value, number, old, new)
    with pytest.raises((FilingError, SourcePdfError)):
        annual.parse_positioned_book(value, 2025)


@pytest.mark.parametrize('mutation', ['current-prior','amount-percent','missing','duplicate','positive-purchase','nonfinite','bool','position','parent-label','parent-section','column-header','percentage','invalid-grouping'])
def test_position_and_monetary_boundaries_fail_closed(positioned, mutation):
    value = deepcopy(positioned[2025])
    s = segment(value, 15, '(498,732)')
    if mutation == 'current-prior':
        current, previous = segment(value, 15, '2025'), segment(value, 15, '2024')
        current['text'], previous['text'] = '2024', '2025'
    elif mutation == 'amount-percent':
        s = segment(value, 9, '34,530,572')
        s['x'], s['end_x'] = 345, 364
    elif mutation == 'missing':
        page(value, 15)['segments'].remove(s)
    elif mutation == 'duplicate':
        page(value, 15)['segments'].append(deepcopy(s))
    elif mutation == 'positive-purchase':
        s['text'] = '498,732'
    elif mutation == 'nonfinite':
        s['x'] = float('nan')
    elif mutation == 'bool':
        s['y'] = True
    elif mutation == 'position':
        s['x'] = s['end_x'] + 1
    elif mutation == 'parent-label':
        segment(value, 12, 'Owners of TCFHC')['text'] = 'Non-controlling interests'
    elif mutation == 'parent-section':
        segment(value, 12, 'NET INCOME ATTRIBUTABLE TO:')['text'] = 'COMPREHENSIVE INCOME ATTRIBUTABLE TO:'
    elif mutation == 'column-header':
        segment(value, 9, 'Amount')['text'] = '%'
    elif mutation == 'percentage':
        # Native percentage is independently required, but never a TWD amount.
        segment(value, 9, '46')['text'] = 'unknown'
    elif mutation == 'invalid-grouping':
        s['text'] = '(49,8732)'
    with pytest.raises((FilingError, SourcePdfError)):
        annual.parse_positioned_book(value, 2025)


@pytest.mark.parametrize('field,bad', [('page_count',True),('page_count',246),('selected_full_physical_pages',[1,3,7,8,9,10,11,12,14,15]),('coverage_status','partial'),('content_sha256','invalid'),('parser_version','0'),('garbled_pages',[7])])
def test_child_profile_cannot_be_asserted_by_coercion_or_partial_result(positioned, field, bad):
    value = deepcopy(positioned[2025]); value[field] = bad
    with pytest.raises(SourcePdfError):
        annual.parse_positioned_book(value, 2025)


@pytest.mark.parametrize('year', [True,2025.0,'2025',2020,2026,None])
def test_unsupported_year_never_starts_child(originals, monkeypatch, year):
    monkeypatch.setattr(reader, '_run_worker', lambda *_a,**_k: pytest.fail('child must not start'))
    with pytest.raises(SourcePdfError):
        annual.parse_book(originals[2025], year)


@pytest.mark.parametrize('timeout', [True,0,-1,11,float('inf'),float('nan'),None])
def test_invalid_timeout_is_rejected_before_child(originals, monkeypatch, timeout):
    monkeypatch.setattr(reader, '_run_worker', lambda *_a,**_k: pytest.fail('child must not start'))
    with pytest.raises(SourcePdfError):
        annual.parse_book(originals[2025], 2025, timeout_seconds=timeout)


@pytest.mark.parametrize('stage', ['reader','parser','handoff'])
def test_one_deadline_includes_reader_parser_and_final_copy(positioned, originals, monkeypatch, stage):
    clock = [10.0]
    monkeypatch.setattr(annual, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    real_parse = annual.parse_positioned_book
    real_copy = annual.deepcopy
    def extract(*a, **kw):
        if stage == 'reader': clock[0] = 20.0
        return positioned[2025]
    def parse(*a, **kw):
        result = real_parse(*a, **kw)
        if stage == 'parser': clock[0] = 20.0
        return result
    def copied(value):
        result = real_copy(value)
        if stage == 'handoff': clock[0] = 20.0
        return result
    monkeypatch.setattr(annual, 'extract_tcfhc_book', extract)
    monkeypatch.setattr(annual, 'parse_positioned_book', parse)
    monkeypatch.setattr(annual, 'deepcopy', copied)
    with pytest.raises(SourcePdfError, match='timeout'):
        annual.parse_book(originals[2025], 2025)


@pytest.mark.parametrize('reason', ['parser_warning','memory_limit','stream_limit','timeout','encrypted_pdf'])
def test_private_child_guard_results_stay_fatal(originals, monkeypatch, reason):
    monkeypatch.setattr(reader, '_run_worker', lambda *a,**kw: json.dumps({'error':reason}).encode())
    with pytest.raises(SourcePdfError, match=reason):
        annual.parse_book(originals[2025],2025)


def test_native_explicit_dash_is_zero_missing_is_not(positioned):
    value = deepcopy(positioned[2025])
    segment(value,15,'(498,732)')['text'] = '-'
    result = annual.parse_positioned_book(value,2025)
    assert result['facts'][2025][INTANGIBLE] == 0


def test_positioned_result_is_not_linked_to_mutable_input(positioned):
    value = deepcopy(positioned[2025])
    result = annual.parse_positioned_book(value,2025)
    segment(value,15,'(498,732)')['text'] = '(1)'
    assert result['facts'][2025][INTANGIBLE] == -498732000
    assert result['physical_fact_basis'][-1]['monetary_cells'][0] == '(498,732)'


@pytest.mark.parametrize('payload', ['\ufffd', '\ue001', '\ud800', '(cid:17)'])
def test_positioned_seam_rejects_garbled_selected_text_even_if_status_claims_complete(positioned, payload):
    value = deepcopy(positioned[2025])
    page(value, 1)['text'] += payload
    with pytest.raises(SourcePdfError):
        annual.parse_positioned_book(value, 2025)


def test_deadline_exhausted_before_child_is_timeout_not_restarted(originals, monkeypatch):
    calls = iter((10.0, 20.0))
    monkeypatch.setattr(annual, 'time', SimpleNamespace(monotonic=lambda: next(calls)))
    monkeypatch.setattr(annual, 'extract_tcfhc_book', lambda *a,**kw: pytest.fail('deadline child must not start'))
    with pytest.raises(SourcePdfError, match='timeout'):
        annual.parse_book(originals[2025], 2025)
