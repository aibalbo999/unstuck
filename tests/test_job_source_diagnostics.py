"""Keep unknown job counts and their source failures visible in persisted audit."""
import json
import sqlite3

import pytest

from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
from data_fetch.types import FetchRequest
import alternative_data_fetcher as jobs
import provider_sla


def test_job_components_preserve_distinct_failures_in_sla(monkeypatch):
    monkeypatch.setattr(jobs, 'fetch_104_job_openings_count', lambda *a: {
        'status': 'unavailable', 'job_count': None, 'reason_code': 'parse_failure'})
    monkeypatch.setattr(jobs, 'fetch_1111_job_openings_count', lambda *a: {
        'status': 'unavailable', 'job_count': None, 'reason_code': 'transport_failure'})
    result = AlternativeJobOpeningsProvider()._fetch_uncached(
        FetchRequest.from_ticker('2330.TW'),
        {'data': {'company_name': '台積電', 'job_opening_keywords': ['工程師', '研發']}})
    assert result.status == 'degraded_enrichment'
    assert result.audit['record_count'] == 0
    provider_sla.record_source_audit_entries([result.audit])
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as db:
        details = json.loads(db.execute('SELECT details_json FROM provider_sla_events ORDER BY id DESC LIMIT 1').fetchone()[0])
    components = details['component_statuses']
    assert len(components) == 4
    assert {v['reason_code'] for v in components.values()} == {'parse_failure', 'transport_failure'}
    assert {v['provider'] for v in components.values()} == {'104 Job Search', '1111 Job Search'}
    assert all(v['status'] == 'unavailable' for v in components.values())
    assert components == result.value['component_statuses']


@pytest.mark.parametrize('payload, expected', [
    ({'status': 'success', 'job_count': 0}, 'valid_empty'),
    ({'status': 'success', 'job_count': 4}, 'success'),
    ({'status': 'success', 'job_count': None, 'recent_recruitment_news': [{'title': 'news'}],
      'fallback_reason': 'transport_failure', 'actual_provider': 'Google News RSS'}, 'qualitative_only'),
    ({'status': 'success', 'job_count': True}, 'unavailable'),
])
def test_job_diagnostics_do_not_promote_news_or_unknown_to_numeric(monkeypatch, payload, expected):
    monkeypatch.setattr(jobs, 'fetch_104_job_openings_count', lambda *a: dict(payload))
    monkeypatch.setattr(jobs, 'fetch_1111_job_openings_count', lambda *a: dict(payload))
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2330.TW'))
    components = result.audit['component_statuses']
    assert all(v['status'] == expected for v in components.values())
    if expected == 'qualitative_only':
        assert all(v['reason_code'] == 'transport_failure' for v in components.values())
        assert all(v['provider'] == 'Google News RSS' for v in components.values())
        assert result.audit['record_count'] == 0
