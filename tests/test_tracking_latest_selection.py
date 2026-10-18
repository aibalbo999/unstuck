"""Latest selection preserves current evidence and publication semantics."""
import pytest
import tracking_latest_reports as selection
from decision_tracking_service import latest_reports_for_ticker


def row(name, timestamp, mode='v4', ticker='1301.TW'):
    return dict(filename=name, timestamp=timestamp, pipeline_id=mode, ticker=ticker)


def install(monkeypatch, rows, snapshots):
    reads, projections, syncs = [], [], []
    def query(**kw):
        syncs.append(kw['sync_metadata'])
        start = (kw['page'] - 1) * 100
        return rows[start:start + 100], len(rows)
    def read(item):
        reads.append(item['filename'])
        return snapshots.get(item['filename'], {})
    def project(item, *, snapshot):
        projections.append(item['filename'])
        return {**item, 'pipeline_id': selection.resolve_report_pipeline_id(item['filename'], stored_pipeline=item['pipeline_id'], snapshot=snapshot), 'quality': snapshot.get('quality', 'passed')}
    monkeypatch.setattr(selection, 'query_report_metadata', query)
    monkeypatch.setattr(selection, '_read_snapshot', read)
    monkeypatch.setattr(selection, 'row_to_report', project)
    return reads, projections, syncs


@pytest.mark.parametrize('kind', ['saved_analysis_replay', 'saved_data_repair_validation', 'partial_analysis'])
def test_new_nonprediction_falls_back_without_hydrating_discarded_versions(monkeypatch, kind):
    rows = [row('excluded', 3), row('blocked', 2), row('older_good', 1)]
    reads, projections, _ = install(monkeypatch, rows, {'excluded': {'publication_identity': {'kind': kind}}, 'blocked': {'quality': 'blocked'}})
    result = latest_reports_for_ticker('1301.TW', 'unused')
    assert result[0]['filename'] == 'blocked' and result[0]['quality'] == 'blocked'
    assert reads == ['excluded', 'blocked'] and projections == ['blocked']


def test_all_pages_timestamp_ties_and_ticker_filter(monkeypatch):
    rows = [row('tie_first', 5), row('false_match', 100, ticker='2301.TW')] + [row(f'old{i}', 1) for i in range(99)] + [row('newer_second_page', 6, 'v2'), row('tie_second', 5)]
    reads, projections, syncs = install(monkeypatch, rows, {})
    result = latest_reports_for_ticker('1301', 'unused')
    assert [x['filename'] for x in result] == ['newer_second_page', 'tie_first']
    assert set(reads) == set(projections) == {'newer_second_page', 'tie_first'}
    assert syncs == [True, False]


def test_missing_stored_mode_uses_snapshot_and_placeholder_does_not_hide_it(monkeypatch):
    rows = [row('a_v1_report.html', 3, 'N/A'), row('b_v1_report.html', 2, ''), row('older', 1, 'v2')]
    reads, projections, _ = install(monkeypatch, rows, {'a_v1_report.html': {'pipeline': 'v2'}, 'b_v1_report.html': {'pipeline': 'v4'}})
    assert [x['pipeline_id'] for x in latest_reports_for_ticker('1301.TW', 'unused')] == ['v2', 'v4']
    assert projections == ['a_v1_report.html', 'b_v1_report.html'] and 'older' not in reads


def test_repeat_reads_recheck_source_and_rule_changes_without_result_cache(monkeypatch):
    snapshots = {'new': {'quality': 'passed'}}
    reads, projections, _ = install(monkeypatch, [row('new', 2), row('old', 1)], snapshots)
    assert latest_reports_for_ticker('1301.TW', 'unused')[0]['quality'] == 'passed'
    snapshots['new']['quality'] = 'blocked'
    assert latest_reports_for_ticker('1301.TW', 'unused')[0]['quality'] == 'blocked'
    snapshots['new']['publication_identity'] = {'kind': 'partial_analysis'}
    assert latest_reports_for_ticker('1301.TW', 'unused')[0]['filename'] == 'old'
    assert projections == ['new', 'new', 'old']


def test_empty_snapshot_keeps_canonical_missing_snapshot_forecast_behavior(monkeypatch):
    install(monkeypatch, [row('missing', 2), row('older', 1)], {})
    assert latest_reports_for_ticker('1301.TW', 'unused')[0]['filename'] == 'missing'


@pytest.mark.parametrize('content', [None, 'not json', '{}', '{"pipeline":"v4","data":{"ticker":"1301.TW"}}'])
def test_prefetched_snapshot_matches_original_mapper_and_current_rule_is_rechecked(tmp_path, monkeypatch, content):
    import report_index_rows as mapper
    from copy import deepcopy
    path = tmp_path / 'fixture.data.json'
    if content is not None:
        path.write_text(content)
    item = {**row('1301_TW_v4_report_20261002_090000.html', 1790893200), 'company_name': 'sample', 'report_date': '2026-10-02 09:00', 'recommendation_json': '{}', 'data_trust_json': '{}', 'data_snapshot_filename': path.name, 'output_dir': str(tmp_path), 'analysis_text_stale': 0, 'analysis_text_stale_message': ''}
    snapshot = mapper._read_snapshot(item)
    original = mapper.row_to_report(item)
    monkeypatch.setattr(mapper, '_read_snapshot', lambda _: pytest.fail('selected snapshot reread'))
    assert mapper.row_to_report(item, snapshot=snapshot) == original
    before = deepcopy(snapshot)
    monkeypatch.setattr(mapper, 'project_evidence_exit_gate', lambda *_: {'verdict': 'blocked', 'reason_codes': ['test_current_rule']})
    assert mapper.row_to_report(item, snapshot=snapshot)['evidence_exit_gate']['verdict'] == 'blocked'
    assert snapshot == before
