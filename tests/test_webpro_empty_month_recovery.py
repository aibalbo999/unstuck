"""An empty annual index must not hide a verified event's monthly materials."""
from datetime import date
import time

import pytest


@pytest.fixture
def recovery(monkeypatch):
    import official_financials
    import official_financials_webpro_conference as webpro
    import data_fetch.earnings_call_fetcher as flow
    from search_provider_runtime import SourceResponseError

    calls = []
    event = {'ticker': '2324', 'company_name': '仁寶', 'date': '2026-07-16',
             'title': '仁寶法人說明會', 'summary': '公司公布營運成果',
             'source': 'MOPS investor conference',
             'source_url': 'https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1',
             'materials': [{'label': '簡報檔案',
                            'url': 'https://mopsov.twse.com.tw/nas/STR/232420260716M001.pdf'}]}
    state = {'cache_hit': False, 'events': [event], 'error': None,
             'detail_changes': {}, 'context_changes': {}}

    def mops(ticker, *, year=None, month=None, diagnostics=None, **kwargs):
        calls.append((ticker, year, month))
        if month is None:
            diagnostics.update(status='success', outcome='valid_empty', cache_hit=False,
                               stale=False, http_request_sent=True, http_request_count=1,
                               fetched_at_epoch=time.time())
            return []
        if state['error']:
            raise SourceResponseError(state['error'])
        diagnostics.update(status='skipped_fresh_cache' if state['cache_hit'] else 'success',
                           cache_hit=state['cache_hit'], stale=False,
                           http_request_sent=not state['cache_hit'],
                           http_request_count=int(not state['cache_hit']),
                           fetched_at_epoch=time.time()-60)
        diagnostics.update(state['detail_changes'])
        return state['events']

    def index(ticker, *, diagnostics=None):
        diagnostics.update(actual_provider=webpro.PROVIDER, cache_hit=False, stale=False,
                           http_request_sent=True, http_request_count=2,
                           fetched_at_epoch=time.time())
        return {'ticker': '2324', 'date': event['date'], 'source': webpro.PROVIDER,
                'source_url': webpro.INDEX_URL, 'coverage_status': 'metadata_only',
                'summary': '', 'materials': [], 'transcript_available': False,
                **state['context_changes']}

    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', mops)
    monkeypatch.setattr(webpro, 'fetch_webpro_conference_context', index)
    monkeypatch.setattr(flow, '_fetch_twse_iih_notice_fallback', lambda *a, **k: {})
    monkeypatch.setattr(flow, '_fetch_irengage_fallback', lambda ticker, context, *a, **k: context)
    return flow, state, calls, event


@pytest.mark.parametrize('cached', [False, True])
def test_empty_annual_uses_exact_month_to_recover_official_record(recovery, cached):
    flow, state, calls, event = recovery
    state['cache_hit'] = cached
    diagnostic = {}
    value = flow._fetch_official_index_context('2324.TW', diagnostics=diagnostic)
    assert value['materials'] == event['materials']
    assert value['summary'] == event['summary']
    assert value['transcript_available'] is False
    assert value['transcript_excerpt'] == ''
    assert 'documents' not in value
    assert diagnostic['actual_provider'] == 'MOPS investor conference'
    assert diagnostic['status'] == ('skipped_fresh_cache' if cached else 'success')
    assert diagnostic['cache_hit'] is cached
    assert diagnostic['http_request_count'] == (4 if cached else 5)
    assert diagnostic['component_statuses']['MOPS']['status'] == 'valid_empty'
    assert diagnostic['component_statuses']['MOPS_event_month']['matched_event_date'] == event['date']
    assert calls == [('2324.TW', None, None), ('2324.TW', date.today().year-1, None),
                     ('2324.TW', 2026, 7)]


@pytest.mark.parametrize('invalid', ['ticker', 'date', 'source', 'duplicate', 'timeout', 'empty'])
def test_month_failure_or_ambiguous_match_retains_metadata(recovery, invalid):
    flow, state, calls, event = recovery
    if invalid in {'ticker', 'date', 'source'}:
        state['events'] = [{**event, invalid: {'ticker': '2303', 'date': '2026-07-17',
                                            'source': 'unverified'}[invalid]}]
    elif invalid == 'duplicate':
        state['events'] = [event, dict(event)]
    elif invalid == 'timeout':
        state['error'] = 'timeout'
    else:
        state['events'] = []
    diagnostic = {}
    value = flow._fetch_official_index_context('2324.TW', diagnostics=diagnostic)
    assert value['coverage_status'] == 'metadata_only'
    assert value['materials'] == []
    assert calls[-1] == ('2324.TW', 2026, 7)
    assert 'MOPS_event_month' in diagnostic['component_statuses']


@pytest.mark.parametrize('changes', [
    {'stale': True}, {'fetched_at_epoch': True}, {'fetched_at_epoch': float('nan')},
    {'fetched_at_epoch': 1.0}, {'status': None},
])
def test_unverified_month_observation_cannot_promote_a_row(recovery, changes):
    flow, state, _, _ = recovery
    state['detail_changes'] = changes
    value = flow._fetch_official_index_context('2324.TW', diagnostics={})
    assert value['coverage_status'] == 'metadata_only' and value['materials'] == []


@pytest.mark.parametrize('changes', [
    {'ticker': '2303'}, {'date': 'not-a-date'}, {'date': '2099-01-01'}, {'source': 'unverified'},
])
def test_unverified_webpro_candidate_does_not_trigger_a_month_query(recovery, changes):
    flow, state, calls, _ = recovery
    state['context_changes'] = changes
    flow._fetch_official_index_context('2324.TW', diagnostics={})
    assert len(calls) == 2 and all(month is None for _, _, month in calls)


def test_recovery_does_not_certify_latest_when_a_webpro_category_failed(recovery):
    flow, state, _, _ = recovery
    state['context_changes'] = {'recency_comparison_complete': False, 'incomplete_categories': [148]}
    diagnostic = {}
    value = flow._fetch_official_index_context('2324.TW', diagnostics=diagnostic)
    assert value['selection_status'] == 'partial' and value['incomplete_categories'] == [148]
    assert diagnostic['coverage_status'] == 'partial'


def test_saved_native_month_body_recovers_through_real_cache_and_provider(monkeypatch):
    """Annual-empty is controlled; monthly parsing uses an unmodified live body."""
    import gzip
    from hashlib import sha256
    from pathlib import Path
    from types import SimpleNamespace
    import cache_store
    from cache_backends import InMemoryCache
    import official_financials_mops_conference as mops
    import official_financials_webpro_conference as webpro
    import data_fetch.earnings_call_fetcher as flow
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest

    raw = gzip.decompress((Path(__file__).parent / 'fixtures/source_acquisition/webpro_month_2812_20261017.gz').read_bytes())
    assert sha256(raw).hexdigest() == '04e536bf09f0915391cacb34b786fd303dc805e2b917c6b376dea8b770f80f50'
    calls = []
    def post(url, **kwargs):
        form = kwargs['data']
        calls.append((form['co_id'], form['year'], form['month']))
        body = raw if form['month'] == '08' else '<html><body>查無資料</body></html>'.encode()
        return SimpleNamespace(content=body, text=body.decode('utf-8'), encoding='utf-8', status_code=200)
    def candidate(ticker, *, diagnostics):
        diagnostics.update(http_request_sent=False, http_request_count=0,
                           cache_hit=True, stale=False, fetched_at_epoch=time.time()-60)
        return {'ticker': '2812', 'date': '2026-08-17', 'source': webpro.PROVIDER,
                'source_url': webpro.INDEX_URL, 'recency_comparison_complete': True,
                'materials': [], 'coverage_status': 'metadata_only'}
    monkeypatch.setattr(mops, '_http_post', post)
    monkeypatch.setattr(webpro, 'fetch_webpro_conference_context', candidate)
    monkeypatch.setattr(flow, '_fetch_twse_iih_notice_fallback', lambda *a, **k: pytest.fail('unexpected weaker fallback'))
    cache_store.set_cache_backend(InMemoryCache())
    try:
        first = EarningsCallProvider().fetch(FetchRequest.from_ticker('2812.TW'))
        assert first.status == 'success'
        assert first.audit['webpro_month_recovery'] is True
        assert first.audit['http_request_count'] == 3
        assert first.value['date'] == '2026-08-17' and len(first.value['materials']) == 2
        assert first.value['source'] == 'MOPS investor conference'
        assert first.value['transcript_available'] is False and 'documents' not in first.value
        stamp = first.audit['fetched_at_epoch']
        second = EarningsCallProvider().fetch(FetchRequest.from_ticker('2812.TW'))
        assert second.status == 'skipped_fresh_cache'
        assert second.audit['http_request_count'] == 0
        assert second.audit['fetched_at_epoch'] == stamp
        assert second.value == first.value
        assert calls == [('2812', str(date.today().year-1911), ''),
                         ('2812', str(date.today().year-1912), ''), ('2812', '115', '08')]
    finally:
        cache_store.reset_cache_store_for_tests()
