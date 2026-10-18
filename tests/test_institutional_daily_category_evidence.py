"""Exact daily subgroup facts saved in real blocked reports, offline only."""
import copy
import json
from pathlib import Path

import pytest

from institutional_evidence import institutional_evidence_issues, institutional_evidence_records
from institutional_evidence_prompt import build_institutional_source_prompt
from trade_catalog_evidence import add_catalog_observations


@pytest.fixture
def saved():
    return json.loads((Path(__file__).parent / 'fixtures/source_acquisition/'
                       'institutional_9103_daily_categories_20261010.json').read_text())


def test_saved_report_daily_subgroup_claims_have_same_scope_evidence(saved):
    assert institutional_evidence_issues(saved['original_analysis_23'], saved['data']) == []


@pytest.mark.parametrize('claim', [
    '2026-10-08外資單日淨買超690000股。',
    '2026-10-08自營商單日淨買超304496股。',
    '2026-10-08投信單日買賣超0股。',
])
def test_actual_date_population_and_units_are_accepted(saved, claim):
    assert institutional_evidence_issues(claim, saved['data']) == []


@pytest.mark.parametrize('claim', [
    '2026-10-07外資單日淨買超690000股。',
    '2026-10-08投信單日淨買超690000股。',
    '外資近5個交易日淨買超690000股。',
    '2026-10-08外資單日淨買超690000千股。',
    '2026-10-08外資單日淨賣超690000股。',
])
def test_matching_number_cannot_replace_date_subject_period_unit_or_sign(saved, claim):
    assert institutional_evidence_issues(claim, saved['data'])


def test_daily_rows_are_bounded_and_use_original_row_paths(saved):
    data = saved['data']
    daily = [r for r in institutional_evidence_records(data)
             if '.daily_category_observations[' in r['path']]
    assert len(daily) == 30
    assert len({r['observed_at'] for r in daily}) == 10
    raw = data['institutional_trading']['daily_category_observations']
    for record in daily:
        index = int(record['path'].split('[')[1].split(']')[0])
        assert record['value'] == raw[index]['net_buy_shares']
        assert record['population'] == raw[index]['category']
        assert record['unit'] == raw[index]['unit'] == 'shares'
        assert record['provider'] == raw[index]['source']


def test_visible_catalog_and_allowed_reference_admit_only_matching_daily_row(saved):
    catalog = {'ticker': saved['data']['ticker'], 'short_term_market_context':
               add_catalog_observations({'as_of': '2026-10-09'}, saved['data'])}
    records = catalog['short_term_market_context']['institutional_evidence']['records']
    index = next(i for i, r in enumerate(records)
                 if r['population'] == 'foreign' and r['window'] == {'kind': 'day', 'date': '2026-10-08'})
    ref = f'short_term_market_context.institutional_evidence.records[{index}]'
    claim = '2026-10-08外資單日淨買超690000股。'
    assert institutional_evidence_issues(claim, catalog, allowed_paths=[ref]) == []
    assert institutional_evidence_issues(claim, catalog, allowed_paths=[]) != []
    assert institutional_evidence_issues(claim.replace('外資', '投信'), catalog, allowed_paths=[ref])


@pytest.mark.parametrize('field,value', [
    ('net_buy_shares', None), ('net_buy_shares', True), ('net_buy_shares', float('nan')),
    ('net_buy_shares', float('inf')), ('net_buy_shares', 690000.5),
    ('net_buy_shares', '690000'), ('unit', 'thousand_shares'),
    ('source', 'unverified provider'), ('source', ''),
])
def test_invalid_daily_fact_is_not_admitted(saved, field, value):
    data = saved['data']
    row = next(r for r in data['institutional_trading']['daily_category_observations']
               if r['date'] == '2026-10-08' and r['category'] == 'foreign')
    row[field] = value
    assert institutional_evidence_issues('2026-10-08外資單日淨買超690000股。', data)


@pytest.mark.parametrize('duplicate_delta', [0, 1])
def test_duplicate_daily_population_is_ambiguous_even_when_equal(saved, duplicate_delta):
    data = saved['data']
    row = next(r for r in data['institutional_trading']['daily_category_observations']
               if r['date'] == '2026-10-08' and r['category'] == 'foreign')
    duplicate = copy.deepcopy(row)
    duplicate['net_buy_shares'] += duplicate_delta
    data['institutional_trading']['daily_category_observations'].append(duplicate)
    assert institutional_evidence_issues('2026-10-08外資單日淨買超690000股。', data)


def test_prompt_adds_only_latest_daily_subgroups(saved):
    prompt = build_institutional_source_prompt(saved['data'])
    daily_lines = [line for line in prompt.splitlines() if 'daily_category_observations[' in line]
    assert len(daily_lines) == 3
    assert all('2026-10-08單日' in line for line in daily_lines)
    assert any('690000股' in line and '外資' in line for line in daily_lines)
    assert any('304496股' in line and '自營商' in line for line in daily_lines)


def test_invalid_latest_rows_do_not_promote_older_subgroups_in_prompt(saved):
    for row in saved['data']['institutional_trading']['daily_category_observations']:
        if row['date'] == '2026-10-08':
            row['net_buy_shares'] = None
    prompt = build_institutional_source_prompt(saved['data'])
    assert 'daily_category_observations[' not in prompt


@pytest.mark.parametrize('mutation', [
    'missing_dates', 'duplicate_dates', 'wrong_endpoint', 'wrong_count', 'oversized_rows',
])
def test_unbound_or_oversized_daily_collection_is_not_admitted(saved, mutation):
    raw = saved['data']['institutional_trading']
    if mutation == 'missing_dates':
        raw.pop('observation_dates')
    elif mutation == 'duplicate_dates':
        raw['observation_dates'].append(raw['observation_dates'][-1])
    elif mutation == 'wrong_endpoint':
        raw['latest_date'] = '2026-10-09'
    elif mutation == 'wrong_count':
        raw['observed_date_count'] = True
    else:
        raw['daily_category_observations'] += [{'date': '2026-01-01'}] * 301
    assert institutional_evidence_issues('2026-10-08外資單日淨買超690000股。', saved['data'])


def test_missing_category_does_not_fill_zero_or_discard_valid_peer(saved):
    raw = saved['data']['institutional_trading']
    raw['daily_category_observations'] = [row for row in raw['daily_category_observations']
                                        if not (row['date'] == '2026-10-08'
                                                and row['category'] == 'investment_trust')]
    assert institutional_evidence_issues('2026-10-08投信單日買賣超0股。', saved['data'])
    assert institutional_evidence_issues('2026-10-08外資單日淨買超690000股。', saved['data']) == []


def test_correct_daily_values_do_not_clear_other_saved_report_errors():
    saved = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/'
                        'institutional_2855_daily_categories_20261010.json').read_text())
    assert institutional_evidence_issues(saved['original_analysis_23'], saved['data'])
