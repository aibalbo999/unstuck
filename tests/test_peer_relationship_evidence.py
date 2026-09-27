"""Reported peer clues require local identities, affirmative business text and provenance."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import pytest

from external_search_types import SearchResult
import external_search_providers as search

FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/peer_relationship_3324_20260927.json'


@pytest.fixture
def captured(monkeypatch):
    case = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(time, 'time', lambda: case['now_epoch'])
    return case


def install(monkeypatch, captured, *, records=None):
    import cache_store
    calls, lookups = [], []
    monkeypatch.setattr(search, '_provider_order', lambda: ['google_news_rss'])
    def cached(key):
        lookups.append(key)
        return deepcopy(captured['cache'].get(key))
    monkeypatch.setattr(cache_store, 'get_cache_json', cached)
    async def fetch(client, provider, query, *, max_results, lookback_days):
        calls.append((query, max_results))
        raw = records if records is not None else next(q['results'] for q in captured['queries'] if q['query'] == query)
        return [SearchResult(**row) for row in raw[:max_results]]
    monkeypatch.setattr(search, '_fetch_provider_results', fetch)
    return calls, lookups


def run(captured, **kwargs):
    return asyncio.run(search.fetch_alternative_peer_discovery_async(
        '3324.TWO', captured['issuer']['company_name'], 'Technology', 'Electronic Components',
        company_context=captured['issuer'], **kwargs))


def positive(captured):
    return deepcopy(captured['queries'][1]['results'][5])


def test_actual_top8_reaches_second_stage_and_preserves_reported_business_evidence(captured, monkeypatch):
    calls, lookups = install(monkeypatch, captured)
    audit = {}
    rows = run(captured, diagnostics=audit)
    assert calls == [('雙鴻 同業', 8), ('雙鴻 競爭對手', 8)]
    assert len(rows) == 1, [(r['reason'], r['record']['title']) for r in audit['source_record_archive']]
    row = rows[0]
    assert row['relationship_kind'] == 'reported_business_peer_comparison'
    assert row['relationship_basis'] == 'headline_or_snippet'
    assert row['numeric_comparability_verified'] is False
    assert row['counterparty']['ticker'] == '3017.TW'
    assert row['counterparty']['identity_basis'] == 'existing_cached_self_identity'
    assert row['counterparty']['market_data_fetched_at_epoch'] == captured['cache']['financial_data:3017.TW']['market_data_fetched_at_epoch']
    assert row['reported_scope'] == '液冷佈局'
    assert row['evidence_span'] in row['title']
    assert row['published_at'] == positive(captured)['published_at']
    assert row['source'] == 'pocket.tw'
    assert row['link'] == positive(captured)['link']
    assert row['published_at'].startswith('Wed, 18 Mar 2026')  # Long-lived clue, never recent catalyst.
    assert set(lookups) == {'financial_data:3017.TW', 'financial_data:3017.TWO'}
    assert len(lookups) == 2
    assert audit['raw_count'] == 16 and audit['usable_count'] == 1
    assert len(audit['source_record_archive']) >= 15
    assert audit['selection_policy'] == 'reported-peer-comparison-v1'


@pytest.mark.parametrize('text', [
    '雙鴻 (3324) 與奇鋐 (3017) 不是競爭對手而是客戶，液冷佈局深度比較',
    '雙鴻 (3324) 與奇鋐 (3017) 供應鏈合作，液冷佈局深度比較',
    '雙鴻 (3324) 與奇鋐 (3017) 外資買超大漲，液冷佈局深度比較',
    '雙鴻 (3324) 與奇鋐 (3017) 散熱概念股名錄，液冷佈局深度比較',
    '雙鴻 (3324) 與奇鋐 (3017) 誰的股價漲更多？',
    '雙鴻 (3324) 與奇鋐 (3017) 營收創高',
    '雙鴻 (3324) 與神秘公司 (3017) 液冷佈局深度比較',
    '雙鴻 (3324) 與奇鋐 (3017) 與台積電 (2330) 液冷佈局深度比較',
])
def test_negative_relationships_are_archived_never_accepted(captured, monkeypatch, text):
    row = positive(captured)
    row.update(title=text, snippet=text)
    _, lookups = install(monkeypatch, captured, records=[row])
    audit = {}
    assert run(captured, diagnostics=audit) == []
    assert audit['source_record_archive']
    assert all(entry['record']['title'] == text for entry in audit['source_record_archive'])
    assert len(lookups) <= 2


@pytest.mark.parametrize('mutation', ['missing', 'expired_market', 'future_cache', 'unknown_market_time', 'wrong_ticker', 'wrong_exchange', 'not_equity', 'forbidden_name', 'market_conflict'])
def test_unverified_counterparty_cache_cannot_supply_identity(captured, monkeypatch, mutation):
    cached = captured['cache']['financial_data:3017.TW']
    if mutation == 'missing': captured['cache']['financial_data:3017.TW'] = None
    elif mutation == 'expired_market': cached['market_data_fetched_at_epoch'] = captured['now_epoch'] - 86401
    elif mutation == 'future_cache': cached['cache_generated_at_epoch'] = captured['now_epoch'] + 1
    elif mutation == 'unknown_market_time': cached.pop('market_data_fetched_at_epoch')
    elif mutation == 'wrong_ticker': cached['ticker'] = '3018.TW'
    elif mutation == 'wrong_exchange': cached['exchange'] = 'TWO'
    elif mutation == 'not_equity': cached['quote_type'] = 'ETF'
    elif mutation == 'forbidden_name': cached['company_identity']['forbidden_aliases'] = ['奇鋐']
    else:
        other = deepcopy(cached)
        other.update(ticker='3017.TWO', exchange='TWO')
        other['company_identity']['ticker'] = '3017.TWO'
        captured['cache']['financial_data:3017.TWO'] = other
    install(monkeypatch, captured, records=[positive(captured)])
    assert run(captured) == []


@pytest.mark.parametrize('field,value', [('published_at',''), ('published_at','Tue, 02 Oct 2099 07:00:00 GMT'), ('link','javascript:alert(1)'), ('source','')])
def test_missing_or_future_provenance_is_rejected(captured, monkeypatch, field, value):
    row=positive(captured);row[field]=value
    install(monkeypatch,captured,records=[row])
    assert run(captured)==[]


def test_missing_verified_taiwan_issuer_does_not_query(captured, monkeypatch):
    calls, _ = install(monkeypatch,captured)
    captured['issuer']['company_identity'] = {}
    assert run(captured)==[]
    assert calls==[]


def test_us_queries_and_result_shape_remain_compatible(monkeypatch):
    calls=[]
    async def fake(query, **kwargs):
        calls.append(query)
        return [] if len(calls)==1 else [SearchResult('US competitor','text','https://example.com/a','source','', 'google_news_rss')]
    monkeypatch.setattr(search,'fetch_web_search_results_async',fake)
    rows=asyncio.run(search.fetch_alternative_peer_discovery_async('AAPL','Apple Inc.','Technology','Consumer Electronics'))
    assert calls==['Apple Inc. competitors','Apple Inc. Consumer Electronics peers']
    assert rows==[{'title':'US competitor','snippet':'text','source':'source','link':'https://example.com/a','source_type':'alternative_peer_discovery','provider':'google_news_rss'}]


def test_expired_deadline_neither_searches_nor_looks_up_identity(captured,monkeypatch):
    calls,lookups=install(monkeypatch,captured)
    assert run(captured,deadline=time.monotonic()-1)==[]
    assert not calls and not lookups


def test_pending_cancellation_propagates_without_cache_lookup(captured,monkeypatch):
    calls,lookups=install(monkeypatch,captured,records=[positive(captured)])
    async def cancel():
        task=asyncio.current_task()
        task.cancel()
        return await search.fetch_alternative_peer_discovery_async('3324.TWO',captured['issuer']['company_name'],'','',company_context=captured['issuer'])
    with pytest.raises(asyncio.CancelledError):asyncio.run(cancel())
    assert lookups==[]


def test_provider_preserves_policy_dates_and_archive(captured, monkeypatch):
    from data_fetch.enrichment_search_providers import AlternativePeerDiscoveryProvider
    from data_fetch.types import FetchRequest
    install(monkeypatch, captured)
    result = asyncio.run(AlternativePeerDiscoveryProvider().fetch_async(
        FetchRequest.from_ticker('3324'), {'data': captured['issuer']}))
    assert result.status == 'success'
    assert result.audit['selection_policy'] == 'reported-peer-comparison-v1'
    assert result.audit['record_count'] == 1
    assert result.audit['usable_count'] == 1
    assert result.audit['source_record_archive']
    assert result.value[0]['published_at'] == positive(captured)['published_at']


def test_provider_error_still_marks_new_policy(captured, monkeypatch):
    from data_fetch.enrichment_search_providers import AlternativePeerDiscoveryProvider
    from data_fetch.types import FetchRequest
    async def broken(*args, **kwargs):
        raise ValueError('offline provider failure')
    monkeypatch.setattr(search, 'fetch_alternative_peer_discovery_async', broken)
    result = asyncio.run(AlternativePeerDiscoveryProvider().fetch_async(
        FetchRequest.from_ticker('3324'), {'data': captured['issuer']}))
    assert result.status == 'error'
    assert result.value == []
    assert result.audit['selection_policy'] == 'reported-peer-comparison-v1'


def test_compatibility_bundle_preserves_dates_and_peer_diagnostics(captured, monkeypatch):
    import external_data_clients as clients
    install(monkeypatch, captured)
    async def empty(*args, **kwargs): return []
    monkeypatch.setattr(clients, 'fetch_alternative_search_catalysts_async', empty)
    monkeypatch.setattr(clients, 'fetch_fmp_news_catalysts_async', empty)
    issuer = captured['issuer']
    bundle = asyncio.run(clients.fetch_optional_http_data_bundle(
        issuer['ticker'], issuer['company_name'], issuer['company_identity'], company_context=issuer))
    assert bundle['search_peer_discovery'][0]['published_at'] == positive(captured)['published_at']
    assert bundle['_peer_discovery_audit']['selection_policy'] == 'reported-peer-comparison-v1'
    assert bundle['_peer_discovery_audit']['source_record_archive']


def test_optional_workflow_snapshot_and_prompt_preserve_relation_not_raw(captured, monkeypatch):
    import data_fetch.optional_enrichment as workflow
    from prompt_evidence import prompt_evidence_copy
    install(monkeypatch, captured)
    async def empty(*args, **kwargs): return []
    monkeypatch.setattr(workflow, 'fetch_alternative_search_catalysts_async', empty)
    monkeypatch.setattr(workflow, 'cache_financial_payload', lambda *args, **kwargs: None)
    data = deepcopy(captured['issuer'])
    data['peer_discovery_results'] = [{'title': 'legacy raw', 'link': 'https://example.com/legacy'}]
    result = asyncio.run(workflow.enrich_optional_http_async('3324', data))
    row = result['peer_discovery_results'][0]
    assert row['published_at'] == positive(captured)['published_at']
    assert result['source_record_archive']
    prompt = prompt_evidence_copy(result)
    assert 'source_record_archive' not in json.dumps(prompt)
    assert 'legacy raw' not in json.dumps(prompt)
    assert prompt['peer_discovery_results'][0]['numeric_comparability_verified'] is False
    assert prompt['peer_discovery_results'][0]['relationship_basis'] == 'headline_or_snippet'
    assert not result.get('dynamic_peer_metrics')


def merge_with_policy(captured, incoming, previous, *, status='success'):
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    data = deepcopy(captured['issuer'])
    data.update(peer_discovery_results=previous, source_audit=[{
        'source': 'peer_discovery', 'provider': 'Alternative Search', 'status': status,
        'selection_policy': 'reported-peer-comparison-v1',
        'record_count': len(incoming), 'fetched_at_epoch': captured['now_epoch']}])
    return _merge_optional_http_bundle(data, {'search_peer_discovery': incoming}, refreshed_sources=['peer_discovery'])


def test_new_verified_beats_eight_old_raw_and_same_url(captured, monkeypatch):
    install(monkeypatch, captured, records=[positive(captured)])
    fresh = run(captured)[0]
    old = [{'title': f'legacy {i}', 'link': f'https://example.com/{i}'} for i in range(7)]
    old.append({'title': fresh['title'], 'link': fresh['link'], 'published_at': ''})
    result = merge_with_policy(captured, [fresh], old)
    assert result['peer_discovery_results'] == [fresh]
    archived = result['source_record_archive']
    assert len([r for r in archived if r['reason'] == 'legacy_peer_relationship_unverified']) == 8
    assert result['source_audit'][-1]['record_count'] == 1
    assert result['source_audit'][-1]['status'] == 'success'


@pytest.mark.parametrize('status', ['degraded_enrichment', 'error'])
def test_new_empty_cannot_be_success_from_old_raw(captured, status):
    old = [{'title': 'legacy unverified', 'link': 'https://example.com/old'}]
    result = merge_with_policy(captured, [], old, status=status)
    assert result['peer_discovery_results'] == []
    assert result['source_record_archive'][0]['record'] == old[0]
    assert result['source_audit'][-1]['status'] != 'success'
    assert result['source_audit'][-1]['record_count'] == 0


def test_existing_verified_clue_retains_stale_status_on_new_empty(captured, monkeypatch):
    install(monkeypatch, captured, records=[positive(captured)])
    old = run(captured)
    result = merge_with_policy(captured, [], old, status='degraded_enrichment')
    assert result['peer_discovery_results'] == old
    assert result['source_audit'][-1]['status'] == 'degraded_enrichment'
    assert result['source_audit'][-1]['stale'] is True
    assert result['source_audit'][-1]['cache_hit'] is True


def test_no_new_policy_keeps_legacy_merge_contract(captured):
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    old = {'title': 'old raw', 'link': 'https://example.com/old'}
    new = {'title': 'new raw', 'link': 'https://example.com/new'}
    data = {'ticker': 'AAPL', 'peer_discovery_results': [old]}
    result = _merge_optional_http_bundle(data, {'search_peer_discovery': [new]}, refreshed_sources=['peer_discovery'])
    assert result['peer_discovery_results'] == [old, new]
    assert not result.get('source_record_archive')


def test_cache_deadline_does_not_accept_late_identity_or_start_second_lookup(captured, monkeypatch):
    import cache_store
    from peer_relationship_evidence import PeerRelationshipSelector
    calls = []
    def slow(key):
        calls.append(key)
        time.sleep(0.03)
        return captured['cache'].get(key)
    monkeypatch.setattr(cache_store, 'get_cache_json', slow)
    async def check():
        selector = PeerRelationshipSelector(captured['issuer'], deadline=time.monotonic()+0.005)
        await selector.consider(positive(captured))
        assert selector.records == []
        assert selector.audit()['rejected_reason_counts'] == {'identity_deadline_exhausted': 1}
    asyncio.run(check())
    assert calls == ['financial_data:3017.TW']


def test_counterparty_identity_is_memoized_within_fetch(captured, monkeypatch):
    rows = [positive(captured), positive(captured)]
    rows[1]['title'] = rows[1]['title'].replace('散熱雙雄誰勝出？', '業務觀察：')
    rows[1]['link'] = 'https://example.com/second-comparison'
    _, calls = install(monkeypatch, captured, records=rows)
    assert len(run(captured)) == 2
    assert len(calls) == 2


@pytest.mark.parametrize('field,value', [('quote_type', None), ('quote_type','ETF'), ('exchange',None), ('exchange','TAI')])
def test_missing_or_conflicting_issuer_market_fails_closed(captured,monkeypatch,field,value):
    if value is None:
        captured['issuer'].pop(field, None)
    else:
        captured['issuer'][field] = value
    calls,lookups = install(monkeypatch,captured)
    assert run(captured) == []
    assert calls == [] and lookups == []


def test_taiwan_result_budget_remains_at_most_eight(captured,monkeypatch):
    calls,_ = install(monkeypatch,captured)
    assert len(run(captured,max_results=30)) == 1
    assert all(limit == 8 for _,limit in calls)


def test_invalid_new_raw_cannot_refresh_retained_verified_clue(captured,monkeypatch):
    install(monkeypatch,captured,records=[positive(captured)])
    old = run(captured)
    result = merge_with_policy(captured,[{'title':'unverified new','link':'https://example.com/raw'}],old)
    assert result['peer_discovery_results'] == old
    assert result['source_audit'][-1]['status'] == 'degraded_enrichment'
    assert result['source_audit'][-1]['stale'] is True


@pytest.mark.parametrize('word', ['否認', '並不', '不再'])
def test_other_explicit_negations_fail_closed(captured,monkeypatch,word):
    row = positive(captured)
    row.update(title=f'雙鴻 (3324) 與奇鋐 (3017) {word}是競爭對手，液冷佈局深度比較')
    install(monkeypatch,captured,records=[row])
    assert run(captured) == []


def test_cache_company_name_must_agree_with_its_self_identity(captured,monkeypatch):
    captured['cache']['financial_data:3017.TW']['company_name'] = '未知企業'
    row = positive(captured)
    row.update(title=row['title'].replace('奇鋐', '未知企業'))
    install(monkeypatch,captured,records=[row])
    assert run(captured) == []


def test_main_provider_plan_retains_archive_and_one_verified_peer(captured,monkeypatch):
    from data_fetch.workflow import _run_optional_provider_plan
    from data_fetch import ProviderRegistry
    from data_fetch.enrichment_search_providers import AlternativePeerDiscoveryProvider
    from data_fetch.types import FetchRequest
    import data_fetch.workflow as workflow
    install(monkeypatch,captured)
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *a,**k: None)
    data = deepcopy(captured['issuer'])
    data['peer_discovery_results'] = [{'title':'old unverified','link':'https://example.com/old'}]
    result = asyncio.run(_run_optional_provider_plan(
        FetchRequest.from_ticker('3324',record_provider_sla=False),
        ProviderRegistry([AlternativePeerDiscoveryProvider()]),data,sources=['peer_discovery']))
    assert len(result['peer_discovery_results']) == 1
    assert result['peer_discovery_results'][0]['published_at'] == positive(captured)['published_at']
    assert result['source_audit'][-1]['record_count'] == 1
    assert result['source_audit'][-1]['status'] == 'success'
    assert any(r['record'].get('title') == 'old unverified' for r in result['source_record_archive'])


def test_cancellation_while_cache_lookup_pending_propagates_and_stops(captured,monkeypatch):
    import cache_store
    from peer_relationship_evidence import PeerRelationshipSelector
    import threading
    started, release = threading.Event(), threading.Event()
    calls=[]
    def pending(key):
        calls.append(key)
        started.set()
        release.wait(0.5)
        return captured['cache'].get(key)
    monkeypatch.setattr(cache_store,'get_cache_json',pending)
    async def check():
        selector = PeerRelationshipSelector(captured['issuer'],deadline=time.monotonic()+1)
        task = asyncio.create_task(selector.consider(positive(captured)))
        while not started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        assert not selector.records
    asyncio.run(check())
    assert calls == ['financial_data:3017.TW']


def test_expired_normal_cache_entry_cannot_supply_counterparty_identity(captured,monkeypatch):
    import cache_store
    from peer_relationship_evidence import PeerRelationshipSelector
    from cache_backends import SqliteCacheBackend
    # The normal backend enforces expiry before the selector sees a payload.
    # The ordinary test runner redirects CACHE_DB_PATH to a temporary database.
    from config import CACHE_DB_PATH
    backend = SqliteCacheBackend(CACHE_DB_PATH)
    monkeypatch.setattr(time, 'time', lambda: captured['now_epoch'] - 2)
    backend.set_json('financial_data:3017.TW',captured['cache']['financial_data:3017.TW'],ttl_seconds=1)
    monkeypatch.setattr(time, 'time', lambda: captured['now_epoch'])
    monkeypatch.setattr(cache_store,'get_cache_json',backend.get_json)
    async def check():
        selector = PeerRelationshipSelector(captured['issuer'],deadline=time.monotonic()+1)
        await selector.consider(positive(captured))
        assert not selector.records
        assert selector.audit()['rejected_reason_counts'] == {'counterparty_identity_missing': 1}
    asyncio.run(check())


@pytest.mark.parametrize('requested', ['2330.TW','3324.TW','2330'])
def test_requested_ticker_cannot_be_replaced_by_other_context(captured,monkeypatch,requested):
    calls,_=install(monkeypatch,captured)
    assert asyncio.run(search.fetch_alternative_peer_discovery_async(
        requested,captured['issuer']['company_name'],'','',company_context=captured['issuer'])) == []
    assert calls == []


def test_bare_ticker_uses_matching_resolved_context(captured,monkeypatch):
    install(monkeypatch,captured)
    rows = asyncio.run(search.fetch_alternative_peer_discovery_async(
        '3324',captured['issuer']['company_name'],'','',company_context=captured['issuer']))
    assert rows[0]['issuer']['ticker'] == '3324.TWO'


def test_real_negative_capture_headlines_remain_unverified(captured,monkeypatch):
    for row in captured['negative_examples']:
        install(monkeypatch,captured,records=[row])
        assert run(captured) == []


@pytest.mark.parametrize('span', [123, ['unexpected'], {'unexpected': True}, '', '   '])
def test_malformed_retained_evidence_span_is_archived_without_success(captured,monkeypatch,span):
    install(monkeypatch,captured,records=[positive(captured)])
    old = run(captured)
    old[0]['evidence_span'] = span
    result = merge_with_policy(captured, [], old, status='degraded_enrichment')
    assert result['peer_discovery_results'] == []
    assert result['source_audit'][-1]['record_count'] == 0
    assert result['source_audit'][-1]['status'] != 'success'
    assert any(item['reason'] == 'legacy_peer_relationship_unverified' and item['record'] == old[0]
               for item in result['source_record_archive'])
