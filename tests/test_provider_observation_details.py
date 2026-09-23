import json
import sqlite3

import provider_sla
from provider_acquisition import get_provider_acquisition_summary


def test_http_and_local_block_are_distinct_and_details_persist():
    common = {'source': 'search_upstream', 'provider': 'Brave', 'status': 'unavailable',
              'record_count': 0, 'error_kind': 'rate_limited', 'http_status': 429, 'retry_at': 1900000000}
    provider_sla.record_source_audit_entries([
        {**common, 'event_kind': 'http_attempt', 'http_request_sent': True, 'outcome': 'failure'},
        {**common, 'event_kind': 'local_block', 'http_request_sent': False, 'outcome': 'cooldown',
         'api_key': 'must-not-persist'},
    ])
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as conn:
        details = [json.loads(row[0]) for row in conn.execute('SELECT details_json FROM provider_sla_events')]
    assert details[1]['retry_at'] == 1900000000
    assert details[1]['http_request_sent'] is False
    assert 'api_key' not in details[1]
    row = get_provider_acquisition_summary()['sources'][0]
    assert row['http_attempt_count'] == 1
    assert row['local_block_count'] == 1
    assert row['fetch_attempts'] == 1
    assert row['providers'][0]['last_details']['outcome'] == 'cooldown'


def test_legacy_readonly_projection_does_not_require_migration(tmp_path, monkeypatch):
    path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE provider_sla_events(id INTEGER, source TEXT, provider TEXT, status TEXT, record_count INTEGER, message TEXT, created_at REAL)')
        conn.execute("INSERT INTO provider_sla_events VALUES(1, 'news', 'legacy', 'success', 1, '', 100)")
    monkeypatch.setattr(provider_sla, 'TASK_DB_PATH', str(path))
    result = get_provider_acquisition_summary('all')
    assert result['available'] is True
    assert result['sources'][0]['http_attempt_count'] == 0
    assert result['sources'][0]['fetched_count'] == 1
