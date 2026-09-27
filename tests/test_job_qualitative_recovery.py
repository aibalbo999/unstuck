"""Recover recruitment evidence without inventing counts or hiding primary failures."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import alternative_data_fetcher as jobs
from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
from data_fetch.types import FetchRequest


DATA = {'ticker': '1623.TW', 'company_name': '大東電 / 大亞',
        'company_identity': {'official_name': '大東電', 'allowed_aliases': ['大東電', '大東電業廠'],
                             'forbidden_aliases': ['大亞']},
        'job_opening_keywords': ['營運']}
SHELL = '<html><title>找工作－104</title><body><div id="app"></div><script src="/app.js"></script></body></html>'
CHALLENGE = '<html><title>Loading</title><body>背景驗證中<script>{"totalCount":0}</script></body></html>'


def news(title='大東電招募人才', link='https://publisher.test/recruitment', date='2026-09-25'):
    return {'title': title, 'link': link, 'published_date': date}


def setup_sources(monkeypatch, rows, html104=SHELL, html1111=CHALLENGE):
    import news_fetchers
    import news_freshness_policy
    monkeypatch.setattr(news_freshness_policy, 'news_cutoff', lambda cutoff=None: datetime(2026, 9, 27, tzinfo=timezone.utc))
    requests, searches = [], []
    def get(url, **kwargs):
        requests.append((url, kwargs.get('params')))
        text = html104 if '104.' in url else html1111
        if isinstance(text, Exception):
            raise text
        return SimpleNamespace(text=text, status_code=200)
    def search(query, **kwargs):
        searches.append(query)
        return deepcopy(rows)
    monkeypatch.setattr(jobs, 'sync_get', get)
    monkeypatch.setattr(news_fetchers, 'fetch_google_news_rss', search)
    return requests, searches


def test_provider_recovers_blocked_pages_once_with_full_identity_and_unique_evidence(monkeypatch):
    rows = [news(), news('大東電招募訊息更新'), news('大亞徵才', 'https://publisher.test/other'),
            news('大東電營收成長', 'https://publisher.test/non-recruitment'),
            news('大東電徵才舊闻', 'https://publisher.test/old', '2025-01-01'),
            news('大東電徵才未來', 'https://publisher.test/future', '2026-09-28'),
            news('大東電徵才日期未知', 'https://publisher.test/unknown', '')]
    requests, searches = setup_sources(monkeypatch, rows)
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('1623.TW'), {'data': deepcopy(DATA)})
    assert result.value['recruitment_news_count'] == 1
    assert len(result.value['recent_recruitment_news']) == 1
    assert len(searches) == 1
    assert '大東電' in searches[0] and '大亞' not in searches[0] and ' / ' not in searches[0]
    assert 'when:30d' in searches[0]
    assert len(requests) == 2
    assert result.status == 'degraded_enrichment'
    assert result.value['status'] == 'qualitative_only'
    assert result.value['numeric_count_coverage'] == 0
    assert result.audit['record_count'] == 1
    for key, reason in [('job_openings_104', 'client_rendered'), ('job_openings_1111', 'access_denied')]:
        payload = result.value[key]
        assert payload['job_count'] is None
        assert payload['reason_code'] == payload['fallback_reason'] == reason
        assert payload['coverage_status'] == 'partial'
        assert payload['actual_provider'] == 'Google News RSS'
        assert payload['http_status'] == 200
        assert payload['primary_status'] == 'unavailable'
        assert payload['recent_recruitment_news'][0]['issuer_match'] == '大東電'
    assert result.value['job_openings_104']['recent_recruitment_news'] is not result.value['job_openings_1111']['recent_recruitment_news']


@pytest.mark.parametrize('primary', ['<html><body>目前沒有可解析數字</body></html>', TimeoutError('offline')])
def test_unparseable_or_transport_failure_keeps_unknown_when_news_has_no_eligible_evidence(monkeypatch, primary):
    _, searches = setup_sources(monkeypatch, [news('其他公司招募')], html104=primary, html1111=primary)
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('1623.TW'), {'data': deepcopy(DATA)})
    assert len(searches) == 1
    assert result.value['recruitment_news_count'] == 0
    assert result.value['status'] == 'unavailable'
    assert all(result.value[k]['job_count'] is None for k in ('job_openings_104', 'job_openings_1111'))
    expected = 'transport_failure' if isinstance(primary, Exception) else 'parse_failure'
    assert all(result.value[k]['reason_code'] == expected for k in ('job_openings_104', 'job_openings_1111'))


def test_numeric_zero_and_positive_do_not_search_recruitment_fallback(monkeypatch):
    _, searches = setup_sources(monkeypatch, [], '<html><body>共 0 筆工作</body></html>', '<html><body>共 12 筆工作</body></html>')
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('1623.TW'), {'data': deepcopy(DATA)})
    assert searches == []
    assert result.value['numeric_count_coverage'] == 2
    assert result.value['job_openings_104']['job_count'] == 0
    assert result.value['job_openings_1111']['job_count'] == 12


def test_unexpected_parser_bug_is_not_masked_by_fallback(monkeypatch):
    _, searches = setup_sources(monkeypatch, [news()], '<html><body>normal</body></html>')
    def broken_parser(html):
        raise ValueError('unexpected parser bug')
    monkeypatch.setattr(jobs, '_extract_104_job_count', broken_parser)
    with pytest.raises(ValueError, match='unexpected parser bug'):
        AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('1623.TW'), {'data': deepcopy(DATA)})
    assert searches == []


def test_qualitative_presence_and_primary_failure_survive_merge_and_sla(monkeypatch):
    import json
    import sqlite3
    import provider_sla
    from data_trust import source_record_count
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    setup_sources(monkeypatch, [news()])
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('1623.TW'), {'data': deepcopy(DATA)})
    assert result.audit['record_count'] == 1
    assert result.audit['numeric_count_coverage'] == 0
    assert source_record_count('alternative_data', {**DATA, 'alternative_data': result.value}) == 1
    merged = _merge_optional_http_bundle({**deepcopy(DATA), 'source_audit': [result.audit]},
            {'alternative_data': result.value}, refreshed_sources=['alternative_data'])
    assert merged['alternative_data']['status'] == 'qualitative_only'
    assert source_record_count('alternative_data', merged) == 1
    audit = [a for a in merged['source_audit'] if a['source'] == 'alternative_data'][-1]
    assert audit['status'] == 'degraded_enrichment' and audit['record_count'] == 1
    provider_sla.record_source_audit_entries([result.audit])
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as db:
        details = json.loads(db.execute('SELECT details_json FROM provider_sla_events ORDER BY id DESC LIMIT 1').fetchone()[0])
    components = details['component_statuses']
    assert components['104_1']['primary_provider'] == '104 Job Search'
    assert components['1111_1']['primary_provider'] == '1111 Job Search'
    assert all(c['primary_status'] == 'unavailable' and c['fallback_status'] == 'qualitative_only' for c in components.values())
    assert all(c['provider'] == 'Google News RSS' for c in components.values())
    assert all('source_url' not in c and 'query' not in c for c in components.values())


def test_recruitment_memo_shares_identical_query_but_never_another_issuer(monkeypatch):
    _, searches = setup_sources(monkeypatch, [news()])
    memo = {}
    for data, keyword in [(DATA, '營運'), (DATA, '研發'),
                          ({'ticker': '2330.TW', 'company_name': '台積電'}, '營運')]:
        jobs.fetch_104_job_openings_count(data['company_name'], keyword, company_context=data, fallback_memo=memo)
    assert len(searches) == 2
    assert '台積電' in searches[-1] and '大東電' not in searches[-1]


def test_three_keywords_two_primary_sites_share_one_recruitment_query(monkeypatch):
    requests, searches = setup_sources(monkeypatch, [news()])
    data = {**deepcopy(DATA), 'job_opening_keywords': ['營運', '工程師', '研發']}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('1623.TW'), {'data': data})
    assert len(requests) == 6
    assert len(searches) == 1
    assert result.value['recruitment_news_count'] == result.audit['record_count'] == 1
    assert [x['keyword'] for x in result.value['job_openings_104']] == data['job_opening_keywords']
    assert [x['keyword'] for x in result.value['job_openings_1111']] == data['job_opening_keywords']
