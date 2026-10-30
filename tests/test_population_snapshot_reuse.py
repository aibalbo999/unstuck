"""Request-local reuse must preserve exclusions, missing plans and date semantics."""
import json
from datetime import date
import pytest
import performance_population as population
from report_publication_identity import read_report_publication_identity
from storage.report_storage import LocalFileStorage


def test_explicit_snapshot_does_not_read_storage(monkeypatch):
    import report_publication_identity as identity
    monkeypatch.setattr(identity, 'read_report_publication_snapshot', lambda *a, **kw: pytest.fail('duplicate snapshot read'))
    assert read_report_publication_identity({'filename': 'x.html'}, 'unused', snapshot={'saved_analysis_replay': {'source_filename': 'old.html'}})['prediction_eligible'] is False
    assert read_report_publication_identity({'filename': 'x.html'}, 'unused', snapshot=None)['kind'] == 'forecast'


def test_population_reads_once_and_reuses_calendar_per_call(monkeypatch, tmp_path):
    reports = []
    storage = LocalFileStorage(str(tmp_path))
    for i in range(4):
        filename = f'2330_TW_v4_report_20260101_09000{i}.html'
        reports.append({'filename': filename, 'ticker': '2330.TW', 'report_date': '2026-01-01 09:00:00'})
        (tmp_path/filename).write_text('html')
        snapshot = {'rerun_context': {'parsed': {'trade_setup': {'trade_direction': 'Long'}}}}
        if i == 3:
            snapshot['saved_analysis_replay'] = {'source_filename': 'original.html'}
        (tmp_path/filename.replace('.html', '.data.json')).write_text(json.dumps(snapshot))
    monkeypatch.setattr(population, 'query_report_metadata', lambda **kw: (reports, len(reports)))
    monkeypatch.setattr(population, 'storage_for_existing_output_dir', lambda *a: storage)
    reads = []
    original_get = storage.get_report
    monkeypatch.setattr(storage, 'get_report', lambda key: (reads.append(key), original_get(key))[1])
    windows = []
    original_window = population.session_window
    monkeypatch.setattr(population, 'session_window', lambda *a: (windows.append(a), original_window(*a))[1])
    first = population.indexed_population(str(tmp_path), as_of=date(2026,1,15), saved=[])
    assert len(reads) == 4 and len(set(reads)) == 4
    assert len(windows) == 2
    assert first['expected_slots'] == 6 and first['excluded_non_prediction_count'] == 1
    assert first['state_counts'] == {'matured_missing_result': 6}
    second = population.indexed_population(str(tmp_path), as_of=date(2026,1,2), saved=[])
    assert second['state_counts'] == {'not_matured': 6}
    assert len(reads) == 8 and len(windows) == 4  # No persistent cache.


@pytest.mark.parametrize('content,html,expected', [
    ('{"saved_analysis_replay":{"source_filename":"x.html"}}', False, 'excluded'),
    ('{"saved_data_repair_validation":{"source_filename":"x.html"}}', False, 'excluded'),
    ('{"publication_identity":{"kind":"partial_analysis"}}', False, 'excluded'),
    ('{"rerun_context":{"parsed":{"trade_setup":{"trade_direction":"Long"}}}}', False, 'execution_plan_unavailable'),
    ('broken json', True, 'execution_plan_unavailable'),
    ('[]', True, 'execution_plan_unavailable'),
])
def test_identity_does_not_depend_on_html_but_plan_still_does(monkeypatch, tmp_path, content, html, expected):
    filename = '2330_TW_v4_report_20260101_090000.html'
    (tmp_path/filename.replace('.html', '.data.json')).write_text(content)
    if html: (tmp_path/filename).write_text('html')
    reports = [{'filename': filename, 'ticker': '2330.TW', 'report_date': '2026-01-01'}]
    monkeypatch.setattr(population, 'query_report_metadata', lambda **kw: (reports, 1))
    result = population.indexed_population(str(tmp_path), as_of=date(2026,1,15), saved=[])
    if expected == 'excluded':
        assert result['expected_slots'] == 0 and result['excluded_non_prediction_count'] == 1
    else:
        assert result['state_counts'] == {expected: 2}
