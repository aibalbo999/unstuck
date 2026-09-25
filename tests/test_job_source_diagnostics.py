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


@pytest.mark.parametrize('fetch', [jobs.fetch_104_job_openings_count, jobs.fetch_1111_job_openings_count])
def test_job_challenge_is_not_a_count_or_a_parser_failure(fetch):
    class Session:
        def get(self, *args, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(text='<html><title>Loading...</title><body>背景驗證中 完成後將自動繼續 安全驗證失敗，請重新整理頁面再試一次。<script>{"totalCount":0}</script></body></html>', status_code=200, raise_for_status=lambda: None)
    result = fetch('台積電', '工程師', session=Session())
    assert result['job_count'] is None
    assert result['reason_code'] == 'access_denied'
    assert result['page_kind'] == 'challenge'
    assert result['http_status'] == 200
    assert len(result['response_sha256']) == 64


def test_104_client_rendered_shell_is_unknown_not_empty():
    class Session:
        def get(self, *a, **k):
            from types import SimpleNamespace
            return SimpleNamespace(text='<html><title>最新找工作職缺－104人力銀行</title><body><div id="app"></div><script src="/assets/app.js"></script></body></html>', status_code=200, raise_for_status=lambda: None)
    result = jobs.fetch_104_job_openings_count('台積電', '工程師', session=Session())
    assert result['job_count'] is None
    assert result['reason_code'] == 'client_rendered'
    assert result['page_kind'] == 'client_rendered_shell'


def test_recruitment_fallback_excludes_stale_and_wrong_company(monkeypatch):
    from datetime import datetime, timezone
    import news_fetchers
    today = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(news_fetchers, 'fetch_google_news_rss', lambda *a, **k: [
        {'title': '台積電徵才工程師', 'published_date': '2025-01-01', 'link': 'https://example.test/old'},
        {'title': '其他公司徵才工程師', 'published_date': today, 'link': 'https://example.test/other'},
        {'title': '台積電徵才工程師', 'published_date': today, 'link': 'https://example.test/current'},
    ])
    result = jobs._google_news_fallback('台積電', '工程師', '104 Job Search', 'https://example.test/jobs')
    assert result['job_count'] is None
    assert len(result['recent_recruitment_news']) == 1
    assert result['recent_recruitment_news'][0]['link'] == 'https://example.test/current'
    assert result['recent_recruitment_news'][0]['content_coverage'] == 'headline_or_snippet'
    assert result['raw_count'] == 3 and result['usable_count'] == 1
    assert result['rejected_reason_counts'] == {'historical': 1, 'issuer_unverified': 1}
    assert len(result['source_record_archive']) == 2
