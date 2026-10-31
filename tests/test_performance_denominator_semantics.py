"""Scope labels must describe retention without changing outcomes or counts."""
import json
from datetime import date
from pathlib import Path
import pytest
import performance_population as population

FIXTURE = Path(__file__).parent / 'fixtures/performance_retention_six_reports.json'


@pytest.mark.parametrize('retention_days', [30, 0])
def test_real_six_expired_reports_keep_original_states_and_scope(monkeypatch, tmp_path, retention_days):
    fixture = json.loads(FIXTURE.read_text())
    reports = []
    for item in fixture['removed_reports']:
        filename = item['report_id']
        reports.append({'filename': filename, 'ticker': item['ticker'], 'report_date': item['published_asia_taipei']})
        (tmp_path / filename).write_text('historical fixture HTML')
        snapshot = {'rerun_context': {'parsed': {'trade_setup': fixture['parsed_plans'][filename]}}}
        (tmp_path / filename.replace('.html', '.data.json')).write_text(json.dumps(snapshot))
    monkeypatch.setattr(population, 'query_report_metadata', lambda **kw: (reports, len(reports)))
    monkeypatch.setattr(population, 'REPORT_RETENTION_DAYS', retention_days)
    result = population.indexed_population(str(tmp_path), as_of=date(2026, 10, 2), saved=fixture['saved_results'])
    assert result['report_count'] == 6 and result['expected_slots'] == 12
    assert result['state_counts'] == {'execution_plan_unavailable': 8, 'matured_missing_result': 2, 'no_trade': 2}
    assert result['excluded_non_prediction_count'] == 0
    assert result['as_of'] == '2026-10-02'
    assert result['denominator_semantics'] == {
        'kind': 'surviving_indexed_reports', 'retention_days': retention_days,
        'retention_basis': 'artifact_mtime;expired_html_removes_bundle',
        'fixed_historical_universe': False, 'cross_period_comparability': 'not_established'}
    immature = population.indexed_population(str(tmp_path), as_of=date(2026, 9, 5), saved=fixture['saved_results'])
    assert immature['state_counts'] == {'not_matured': 12}
    reports.clear()
    expired = population.indexed_population(str(tmp_path), as_of=date(2026, 10, 2), saved=fixture['saved_results'])
    assert expired['report_count'] == 0 and expired['expected_slots'] == 0
    assert expired['denominator_semantics'] == result['denominator_semantics']


def test_six_report_fixture_explains_all_cross_round_window_count_changes():
    fixture = json.loads(FIXTURE.read_text())
    before, after = fixture['before'], fixture['after']
    assert before['report_count'] - after['report_count'] == 6
    assert before['expected_slots'] - after['expected_slots'] == 12
    delta = {key: count - after['state_counts'].get(key, 0) for key, count in before['state_counts'].items()}
    assert {key: count for key, count in delta.items() if count} == {
        'execution_plan_unavailable': 8, 'matured_missing_result': 2, 'no_trade': 2}
    assert before['excluded_non_predictions'] == after['excluded_non_predictions']
    assert before['comparable_assumed_cost_net_result_count'] == after['comparable_assumed_cost_net_result_count']
