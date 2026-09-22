"""Dashboard stale timestamps are attention hints, never proof of dead workers."""
import sqlite3
import pytest


@pytest.mark.parametrize('registry_state,reason,health', [
    ('unknown', 'registry_unknown', 'unknown'),
    ('missing', 'registry_missing', 'needs_check'),
    ('started', '', 'normal'),
])
def test_dashboard_preserves_running_and_labels_stale_timestamp_as_suspicion(monkeypatch, registry_state, reason, health):
    import job_ops_dashboard as dashboard
    calls = []
    def inspect(queue, jobs):
        calls.append([row['job_id'] for row in jobs])
        return {row['job_id']: {'state': registry_state} for row in jobs}
    monkeypatch.setattr(dashboard, 'inspect_job_registries', inspect, raising=False)
    with sqlite3.connect(':memory:') as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE analysis_jobs (job_id TEXT, ticker TEXT, pipeline_id TEXT, status TEXT, updated_at REAL, started_at REAL, created_at REAL)')
        conn.executemany('INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?, ?, ?)', [
            ('a', 'TEST.TW', 'v4', 'running', 100, 50, 50),
            ('b', 'TEST2.TW', 'v4', 'running', 100, 50, 50),
            ('c', 'DONE.TW', 'v4', 'error', 100, 50, 50),
        ])
        rows = dashboard._stuck_job_rows(conn, 2000, 900)
        assert [row['job_id'] for row in rows] == ['a', 'b']
        assert calls == [['a', 'b']]
        for row in rows:
            assert row['status'] == row['execution_state'] == 'running'
            assert row['execution_reason_code'] == reason
            assert row['execution_health'] == health
            assert row['registry']['state'] == registry_state
            assert row['stall_assessment'] == 'suspected_stall'
            assert row['stall_basis'] == 'updated_at_heuristic'
            assert row['stall_label'] == '疑似停滯，需核對'
        assert conn.execute("SELECT status FROM analysis_jobs WHERE job_id='a'").fetchone()[0] == 'running'


def test_empty_dashboard_also_defines_non_authoritative_stall_semantics(tmp_path):
    from job_ops_dashboard import build_ops_dashboard_snapshot
    value = build_ops_dashboard_snapshot(db_path=str(tmp_path / 'missing.sqlite3'))['stuck_jobs']
    assert value['count'] == 0
    assert value['assessment'] == 'suspected_stall'
    assert value['label'] == '疑似停滯，需核對'
    assert value['basis'] == 'updated_at_heuristic'


def test_status_and_quota_browser_assets_have_current_cachebusters():
    import re
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / 'backend/static/index.html').read_text()
    for name in ('job_execution_labels', 'active_jobs_panel', 'analysis_stream_events', 'api_quota_usage_helpers'):
        assert re.search(r'/static/' + name + r'\.js\?v=20260922-[^" ]+', html), name
