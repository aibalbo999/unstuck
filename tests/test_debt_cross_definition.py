"""Do not compare total liabilities and interest-bearing debt as one metric."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from data_cross_validator import apply_cross_validation_to_data, cross_validate_sources
from external_data_twse import _build_payload
from data_fetch.core_provider_merge import merge_core_provider_result
from data_fetch.types import ProviderResult


def definition(value, meaning, provider, **changes):
    return {
        'schema': 'financial-field-definition.v1', 'field': 'total_debt_raw',
        'definition': meaning, 'provider': provider, 'source_field': 'reported debt',
        'value': value, 'unit': 'currency', 'currency': 'TWD',
        'as_of': '2026-06-30', 'report_scope': 'individual', **changes,
    }


def payload(value, meaning, provider, **changes):
    return {'total_debt_raw': value, 'financial_field_definitions': {
        'total_debt_raw': definition(value, meaning, provider, **changes)}}


def test_actual_liabilities_row_emits_its_definition_without_changing_value():
    result = _build_payload([], [{'date': '2026-06-30', 'type': 'Liabilities', 'value': 3_831_832_000}], [], 'FinMind_TWSE')
    assert result['total_debt_raw'] == 3_831_832_000
    basis = result['financial_field_definitions']['total_debt_raw']
    assert basis['definition'] == 'total_liabilities'
    assert basis['source_field'] == 'Liabilities'
    assert basis['as_of'] == '2026-06-30'
    assert basis['report_scope'] is None
    assert basis['value'] == result['total_debt_raw']


def test_different_debt_definitions_never_create_a_median_or_false_mismatch():
    primary = payload(2_898_373_120, 'interest_bearing_debt', 'yfinance')
    secondary = payload(3_831_832_000, 'total_liabilities', 'FinMind_TWSE')
    result = cross_validate_sources(primary, {'twse': secondary})
    debt = result['fields']['total_debt_raw']
    assert debt['verdict'] == 'different_definition'
    assert debt['consensus_value'] is None
    assert debt['max_divergence_pct'] is None
    assert result['divergent_fields'] == result['conflict_fields'] == []
    assert result['overall_verdict'] == 'unassessed'
    assert result['notes']  # Keep the limitation; no automatic confidence upgrade.
    assert primary['total_debt_raw'] == 2_898_373_120
    assert secondary['total_debt_raw'] == 3_831_832_000


@pytest.mark.parametrize('changes', [{'as_of': None}, {'report_scope': None}, {'currency': None}, {'value': 999}])
def test_unverified_or_stale_definition_binding_is_unknown(changes):
    primary = payload(100, 'interest_bearing_debt', 'yfinance')
    secondary = payload(100, 'interest_bearing_debt', 'other')
    secondary['financial_field_definitions']['total_debt_raw'].update(changes)
    result = cross_validate_sources(primary, {'other': secondary})['fields']['total_debt_raw']
    assert result['verdict'] == 'unknown'
    assert result['consensus_value'] is None


def test_legacy_debt_without_definition_is_unknown_even_when_values_match():
    result = cross_validate_sources({'total_debt_raw': 100}, {'twse': {'total_debt_raw': 100}})
    assert result['fields']['total_debt_raw']['verdict'] == 'unknown'
    assert result['overall_verdict'] == 'unassessed'


@pytest.mark.parametrize('other_value, verdict', [(101, 'aligned'), (120, 'divergent'), (300, 'conflict')])
def test_same_definition_aligned_basis_keeps_existing_numeric_thresholds(other_value, verdict):
    primary = payload(100, 'interest_bearing_debt', 'yfinance')
    secondary = payload(other_value, 'interest_bearing_debt', 'other')
    result = cross_validate_sources(primary, {'other': secondary})
    assert result['fields']['total_debt_raw']['verdict'] == verdict
    assert result['fields']['total_debt_raw']['comparison_status'] == 'comparable'
    if verdict != 'aligned':
        assert result['notes']


def test_fallback_copies_true_definition_and_never_claims_two_independent_values():
    primary = {'total_debt_raw': None, 'financial_field_definitions': {
        'total_debt_raw': definition(None, 'interest_bearing_debt', 'yfinance')}}
    secondary = payload(100, 'total_liabilities', 'FinMind_TWSE')
    merge_core_provider_result(primary, ProviderResult(source='twse_official', provider='FinMind_TWSE', status='success', value=secondary))
    assert primary['total_debt_raw'] == 100
    assert primary['financial_field_definitions']['total_debt_raw'] == secondary['financial_field_definitions']['total_debt_raw']
    result = primary['cross_validation']['fields']['total_debt_raw']
    assert result['verdict'] == 'unknown'
    assert 'independent_source_not_established' in result['definition_reason_codes']


def test_normal_flow_keeps_existing_notes_and_both_source_values():
    primary = payload(100, 'interest_bearing_debt', 'yfinance')
    primary['data_source_notes'] = ['historical source warning']
    secondary = payload(120, 'total_liabilities', 'TWSE')
    before = deepcopy(secondary)
    apply_cross_validation_to_data(primary, {'twse': secondary})
    assert 'historical source warning' in primary['data_source_notes']
    assert primary['cross_validation']['fields']['total_debt_raw']['values'] == {'yfinance': 100.0, 'twse': 120.0}
    assert primary['total_debt_raw'] == 100 and secondary == before


def test_yfinance_definition_requires_the_actual_info_field_to_match():
    from debt_field_definitions import yfinance_debt_definition
    context = {'total_debt': 100, 'info': {'totalDebt': 100}, 'financial_currency': 'TWD'}
    basis = yfinance_debt_definition(context)
    assert basis['definition'] == 'interest_bearing_debt'
    assert basis['source_field'] == 'info.totalDebt'
    assert basis['as_of'] is None and basis['report_scope'] is None
    assert yfinance_debt_definition({**context, 'total_debt': 200})['definition'] == 'unknown'
    assert yfinance_debt_definition({'total_debt': 100})['definition'] == 'unknown'


@pytest.mark.parametrize('rows,meaning', [
    ([{'date': '2026-06-30', 'type': 'TotalDebt', 'value': 100}], 'unknown'),
    ([{'date': '2026-06-30', 'type': 'ShortTermBorrowings', 'value': 100}], 'partial_borrowing_components'),
])
def test_ambiguous_or_partial_adapter_fields_are_not_complete_debt(rows, meaning):
    result = _build_payload([], rows, [], 'FinMind_TWSE')
    assert result['total_debt_raw'] == 100
    assert result['financial_field_definitions']['total_debt_raw']['definition'] == meaning


@pytest.mark.parametrize('changes', [
    {'as_of': 'unknown'}, {'as_of': '2026-02-30'}, {'report_scope': 'unknown'},
    {'currency': 'unknown'}, {'unit': 'unknown'},
])
def test_matching_unverified_basis_labels_are_not_promoted_to_comparable(changes):
    primary = payload(100, 'interest_bearing_debt', 'yfinance', **changes)
    secondary = payload(100, 'interest_bearing_debt', 'other', **changes)
    assert cross_validate_sources(primary, {'other': secondary})['fields']['total_debt_raw']['verdict'] == 'unknown'


@pytest.mark.parametrize('changes', [
    {'definition': []}, {'provider': []}, {'source_field': {}}, {'report_scope': []},
])
def test_malformed_definition_metadata_remains_unknown(changes):
    primary = payload(100, 'interest_bearing_debt', 'yfinance')
    secondary = payload(100, 'interest_bearing_debt', 'other')
    secondary['financial_field_definitions']['total_debt_raw'].update(changes)
    assert cross_validate_sources(primary, {'other': secondary})['fields']['total_debt_raw']['verdict'] == 'unknown'


def test_normal_scoring_preserves_core_failure_and_source_note_penalties(monkeypatch):
    import data_trust_scoring
    data = {
        'current_price': 100, 'years': ['2024', '2025'],
        'revenue_history': [100, 110], 'total_debt_raw': 100,
        'twse_official': {'total_debt_raw': 120},
        'data_source_notes': ['Existing financial basis limitation'],
        'source_audit': [{'source': 'market_data', 'status': 'success'},
                         {'source': 'financial_statements', 'status': 'error'}],
    }
    original_note = list(data['data_source_notes'])
    monkeypatch.setattr(data_trust_scoring, 'apply_provider_sla_to_trust', lambda data, trust: trust)
    before = data_trust_scoring.build_data_trust(deepcopy(data))
    apply_cross_validation_to_data(data, {'twse': data['twse_official']})
    after = data_trust_scoring.build_data_trust(data)
    assert all(note in data['data_source_notes'] for note in original_note)
    assert data['cross_validation']['fields']['total_debt_raw']['verdict'] == 'unknown'
    assert data['cross_validation']['fields']['total_debt_raw']['consensus_value'] is None
    assert before['score'] == after['score'] == 56


def test_snapshot_size_governance_preserves_definition_provenance():
    from data_trust_snapshot_integrity import apply_snapshot_size_governance
    primary = payload(100, 'interest_bearing_debt', 'yfinance')
    before = deepcopy(primary['financial_field_definitions'])
    snapshot = {'data': {**primary, 'nonessential_fixture': 'x' * 10000}}
    saved = apply_snapshot_size_governance(snapshot, max_bytes=2000)
    assert saved['snapshot_truncated'] is True
    assert saved['data']['financial_field_definitions'] == before
    assert 'nonessential_fixture' not in saved['data']


@pytest.mark.parametrize('reference_key', ['official_income_reference', 'official_segment_reference'])
def test_snapshot_size_governance_preserves_opt_in_official_reference(reference_key):
    from data_trust_snapshot_integrity import apply_snapshot_size_governance
    reference = {'schema': 'fixture-only', 'facts': [{'period': '2025', 'value': 100}]}
    snapshot = {'data': {reference_key: reference, 'nonessential_fixture': 'x' * 10000}}
    saved = apply_snapshot_size_governance(snapshot, max_bytes=2000)
    assert saved['snapshot_truncated'] is True
    assert saved['data'][reference_key] == reference
    assert 'nonessential_fixture' not in saved['data']
