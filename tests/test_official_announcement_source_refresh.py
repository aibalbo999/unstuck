"""Source-only ordinary announcements, replayed at the external native I/O seam.

The generated announcements below are synthetic behavior fixtures, not native
research originals and never evidence eligible for production adoption.
"""
import asyncio
from copy import deepcopy
from datetime import datetime
import json
import time

import pytest
from fastapi import HTTPException

from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.service import StockDataService
from data_fetch.types import FetchRequest
from report_refresh_service import refresh_report_data_snapshot
from storage.report_storage import InMemoryStorage
from test_report_source_refresh import saved_report
from test_report_refresh_acquisition_audit import init_db, events
from test_twse_announcement_progress import Replay, NOW
from data_fetch.market_sources import twse_company_history as history


class IssuerReplay(Replay):
    def __init__(self, monkeypatch, count=3, detail_cost=.1):
        super().__init__(monkeypatch, count=count, detail_cost=detail_cost)
        for item in self.items:
            item['link'] = item['link'].replace('2891', '2851')
            item['company'] = '中再保'
        self.by_url = {item['link']: item for item in self.items}
        monkeypatch.setattr(time, 'time', lambda: self.epoch)
        owner = self

        class ClockDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromtimestamp(owner.epoch, tz)

        monkeypatch.setattr(history, 'datetime', ClockDateTime)
        try:
            import official_announcement_source_refresh as replay
            monkeypatch.setattr(replay, 'time', self.clock)
        except ImportError:
            pass

    def collect(self, argv, end, **kwargs):
        parts, rc, error = super().collect(argv, end, **kwargs)
        parts['body'] = (parts['body'].replace(b'2891', b'2851')
            .replace('中信金'.encode(), '中再保'.encode())
            .replace(b'\\u4e2d\\u4fe1\\u91d1', b'\\u4e2d\\u518d\\u4fdd'))
        return parts, rc, error

    def fetch(self):
        return history.fetch_recent_company_announcements('2851.TW', now=NOW)


def identity():
    return {'ticker': '2851.TW', 'company_name': '中再保 / Central Reinsurance Corporation',
            'quote_type': 'EQUITY', 'company_identity': {
                'ticker': '2851.TW', 'stock_id': '2851', 'official_name': '中再保',
                'instrument_type': 'EQUITY', 'forbidden_aliases': []}}


def english_identity():
    return {'ticker': '2354.TW', 'company_name': '鴻準 / FOXCONN TECHNOLOGY CO., LTD.',
            'quote_type': 'EQUITY', 'company_identity': {
                'ticker': '2354.TW', 'stock_id': '2354', 'official_name': '鴻準',
                'legal_name': '鴻準精密工業股份有限公司',
                'english_names': ['FOXCONN TECHNOLOGY CO., LTD.'],
                'instrument_type': 'EQUITY', 'forbidden_aliases': []}}


class EnglishIssuerReplay(Replay):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch, count=1, detail_cost=.1)
        monkeypatch.setattr(time, 'time', lambda: self.epoch)
        owner = self
        class ClockDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromtimestamp(owner.epoch, tz)
        monkeypatch.setattr(history, 'datetime', ClockDateTime)
        self.title = "Announcement That the Company's Losses from Derivatives Trading Have Reached the Prescribed Loss Limit"
        self.company = 'FOXCONN TECHNOLOGY CO., LTD.'
        self.link = ('https://emops.twse.com.tw/server-java/t05sr01_1_e?&isNew=Y&seq_no=1'
                     '&spoke_time=154044&spoke_date=20261012&co_id=2354')
        self.items = [{'link': self.link, 'title': self.title, 'company': self.company}]
        self.by_url = {self.link: self.items[0]}
        self.failures[f'{history.INDEX_URL}?code=2354'] = ('transport_error', 200)

    def detail(self, item):
        html = (
            "<html><head><title>Today's Information</title></head><table>"
            "<tr><td>Provided by: FOXCONN TECHNOLOGY CO., LTD.</td></tr>"
            "<tr><td>SEQ_NO</td><td>1</td><td>Date of announcement</td><td>2026/10/12</td>"
            "<td>Time of announcement</td><td>15:40:44</td></tr>"
            f"<tr><td>Subject</td><td colspan='5'>{item['title']}</td></tr>"
            "<tr><td>Statement</td><td colspan='5'>The company hereby announces the loss limit event with supporting transaction details and dates.</td></tr>"
            "</table></html>"
        )
        return html.encode('ascii')

    def collect(self, argv, end, **kwargs):
        from data_fetch.market_sources import twse_history_transport as transport
        url = argv[2] if argv[1].endswith('mops_monthly_http_child.py') else argv[-1]
        if url.startswith(transport.IIH_EN_URL):
            payload = {'info': {'status': 'success', 'data': {
                'code': '2354', 'name': self.company, 'shortName': '',
            }}, 'news': [{'companyId': '2354', 'companyName': 'FTC', 'subject': self.title,
                          'date': '2026/10/12', 'time': '15:40', 'link': self.link}],
                'fina': [], 'conference': []}
            body, mime, cost = json.dumps(payload).encode(), 'application/json', .1
        elif url == self.link:
            body, mime, cost = self.detail(self.items[0]), 'text/html; charset=big5', self.detail_cost
        else:
            return super().collect(argv, end, **kwargs)
        self.calls.append(url)
        self.advance(cost)
        parts = {'body': body,
                 'headers': f'HTTP/2 200\r\nContent-Type: {mime}\r\n\r\n'.encode(),
                 'metadata': json.dumps({'http_code': 200, 'url_effective': url, 'num_redirects': 0}).encode(),
                 'process_started': True}
        if self.after_transfer:
            self.after_transfer(url, parts)
        return parts, 0, None

    def fetch(self):
        return history.fetch_recent_company_announcements('2354.TW', now=NOW)


def service():
    return StockDataService(registry=ProviderRegistry([TwseCompanyHistoryProvider()]))


def report():
    storage = InMemoryStorage()
    name, keys, old = saved_report(storage)
    old['ticker'] = '2851.TW'
    old['conclusion_generated_at'] = old['generated_at']
    old['rerun_context'] = {'analyses':{'3':'original analysis'},'structured_outputs':{},
        'parsed':{},'pipeline_id':'v4','pipeline_label':None,'agent_sequence':None}
    old['data'].update(identity())
    old['analysis_completeness'] = {'status': 'quality_warning', 'missing_agents': [3]}
    old['oos_evaluation_inputs'] = {'pipeline_id': 'v4', 'trade_setup': {'action': 'Neutral'}}
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    return storage, name, keys, old


def test_public_service_admits_originals_for_exact_2851_before_recording_sla(monkeypatch):
    init_db()
    replay = IssuerReplay(monkeypatch)
    result = asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2851.TW'),
        'official_announcements', context={'data': identity()}))
    assert len(result.data['recent_catalysts']) == 3
    assert result.source_audit[0]['status'] == 'success'
    assert result.source_audit[0]['http_request_count'] == 4
    assert len(replay.calls) == 4
    assert len(events()) == 1 and events()[0]['record_count'] == 3


def test_english_iih_fallback_passes_original_receipt_replay_before_sla(monkeypatch):
    init_db()
    replay = EnglishIssuerReplay(monkeypatch)
    data = english_identity()
    result = asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2354.TW'),
        'official_announcements', context={'data': data}))
    audit = result.source_audit[0]
    assert len(result.data['recent_catalysts']) == 1, {
        key: audit.get(key) for key in ('status', 'error_kind', 'message', 'rejected_reason_counts',
            'request_observations', 'english_index_status', 'english_index_error_kind')}
    row = result.data['recent_catalysts'][0]
    assert row['issuer_identity_basis'] == 'TWSE English company ID + English MOPS detail header'
    assert row['official_event']['policy'] == 'ordinary-mops-event-en-v1'
    assert row['link'] == replay.link
    assert result.source_audit[0]['status'] == 'success'
    assert result.source_audit[0]['http_request_count'] == 3
    assert replay.calls == [f'{history.INDEX_URL}?code=2354', f'{history.EN_INDEX_URL}?code=2354', replay.link]
    assert len(events()) == 1 and events()[0]['record_count'] == 1 and events()[0]['status'] == 'success'


def test_public_report_source_only_preserves_original_analysis_and_core(monkeypatch, tmp_path):
    init_db()
    replay = IssuerReplay(monkeypatch)
    storage, name, keys, old = report()
    result = asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
        refresh_service=service(), source='official_announcements', return_refreshed_data=True))
    saved = json.loads(storage.get_report(keys.data_key).content)
    assert len(replay.calls) == 4
    assert len(saved['data']['recent_catalysts']) == 3
    assert saved['data']['news_selection']['publisher_count'] == 1
    for key in ('analysis_evidence', 'analysis_completeness', 'oos_evaluation_inputs', 'rerun_context',
                'conclusion_generated_at', 'report_lint', 'final_audit', 'evidence_exit_gate',
                'content_credibility', 'report_conformance'):
        assert saved.get(key) == old.get(key), key
    for key in ('current_price', 'years', 'revenue_history', 'earnings_call', 'peer_discovery_results'):
        assert saved['data'].get(key) == old['data'].get(key), key
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'
    assert result['analysis_text_stale'] is True
    assert len(events()) == 1


def test_conflicting_identity_is_rejected_before_any_provider_or_sla(monkeypatch, tmp_path):
    init_db()
    replay = IssuerReplay(monkeypatch)
    storage, name, keys, old = report()
    old['data']['quote_type'] = 'ETF'
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    before = storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException) as failure:
        asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
            refresh_service=service(), source='official_announcements'))
    assert failure.value.status_code == 400
    assert replay.calls == [] and events() == []
    assert storage.get_report(keys.data_key).content == before


@pytest.mark.parametrize('change', [
    lambda d: d.update(ticker='2851.TWO'),
    lambda d: d['company_identity'].update(ticker='2891.TW'),
    lambda d: d['company_identity'].update(stock_id='2891'),
    lambda d: d['company_identity'].update(official_name='中信金'),
    lambda d: d['company_identity'].update(instrument_type='ETF'),
    lambda d: d['company_identity'].update(forbidden_aliases=['中再保']),
    lambda d: d.update(instrument_type=False),
    lambda d: d.update(quoteType='UNKNOWN'),
    lambda d: d.update(company_identity=[]),
])
def test_public_context_conflicts_never_call_provider(monkeypatch, change):
    init_db()
    replay = IssuerReplay(monkeypatch)
    data = identity()
    change(data)
    with pytest.raises(RuntimeError):
        asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2851.TW'),
            'official_announcements', context={'data': data}))
    assert replay.calls == [] and events() == []


@pytest.mark.parametrize('field', ['text', 'date', 'title', 'link', 'publisher', 'missing_archive'])
def test_damaged_provider_output_fails_before_sla_success(monkeypatch, field):
    from hashlib import sha256
    init_db()
    replay = IssuerReplay(monkeypatch)

    class Tampered(TwseCompanyHistoryProvider):
        def fetch(self, request, context=None):
            result = super().fetch(request, context)
            if field == 'missing_archive':
                result.audit.pop('source_record_archive', None)
            else:
                result.value[0][field] += 'tampered'
                if field == 'text':
                    result.value[0]['content_sha256'] = sha256(result.value[0]['text'].encode()).hexdigest()
            return result

    svc = StockDataService(registry=ProviderRegistry([Tampered()]))
    result = asyncio.run(svc.fetch_source_async(FetchRequest.from_ticker('2851.TW'),
        'official_announcements', context={'data': identity()}))
    assert len(replay.calls) == 4
    assert result.data['recent_catalysts'] == []
    assert len(events()) == 1 and events()[0]['status'] == 'error'
    assert events()[0]['record_count'] == 0


def test_full_warm_and_new_index_old_bodies_do_not_become_new_acquisition(monkeypatch):
    import cache_store
    from provider_acquisition import observation_kind
    init_db()
    replay = IssuerReplay(monkeypatch)
    svc = service()
    request = FetchRequest.from_ticker('2851.TW')
    first = asyncio.run(svc.fetch_source_async(request, 'official_announcements', context={'data': identity()}))
    call_count = len(replay.calls)
    warm = asyncio.run(svc.fetch_source_async(request, 'official_announcements', context={'data': identity()}))
    assert len(replay.calls) == call_count
    assert warm.source_audit[0]['http_request_count'] == 0
    assert warm.source_audit[0]['fetched_at_epoch'] == first.source_audit[0]['fetched_at_epoch']
    # Only expire the external aggregate in this isolated InMemoryCache.
    for key in list(replay.cache._entries):
        if key.startswith('shared_provider:v1:'):
            replay.cache._entries.pop(key)
    mixed = asyncio.run(svc.fetch_source_async(request, 'official_announcements', context={'data': identity()}))
    audit = mixed.source_audit[0]
    assert len(replay.calls) == call_count + 1
    assert audit['status'] == 'skipped_fresh_cache' and audit['body_cache_hit'] is True
    assert audit['http_request_count'] == 1 and audit['http_request_sent'] is True
    assert audit['detail_new_body_count'] == 0
    row = events()[-1]
    row['details'] = json.loads(row['details_json'])
    assert observation_kind(row) == 'fresh_cache_count'


def test_partial_first_request_then_normal_missing_only_recovery(monkeypatch):
    init_db()
    replay = IssuerReplay(monkeypatch, count=37, detail_cost=.7)
    svc = service()
    request = FetchRequest.from_ticker('2851.TW')
    first = asyncio.run(svc.fetch_source_async(request, 'official_announcements', context={'data': identity()}))
    assert 0 < len(first.data['recent_catalysts']) < 37
    assert first.source_audit[0]['status'] == 'degraded_enrichment'
    assert first.source_audit[0]['coverage_status'] == 'partial'
    count = len(replay.calls)
    saved_links = {row['link'] for row in first.data['recent_catalysts']}
    replay.advance(61)
    second = asyncio.run(svc.fetch_source_async(request, 'official_announcements', context={'data': identity()}))
    assert len(second.data['recent_catalysts']) == 37
    assert second.source_audit[0]['coverage_status'] == 'window_complete'
    assert saved_links.isdisjoint(replay.calls[count:])


@pytest.mark.parametrize('part', ['index_method','index_url','index_parameters','index_hash',
    'index_http_unknown','body_http_unknown','index_expiry','body_expiry','coverage_upgrade'])
def test_request_bound_raw_receipt_mutations_fail_closed(monkeypatch, part):
    init_db()
    replay = IssuerReplay(monkeypatch)

    class Tampered(TwseCompanyHistoryProvider):
        def fetch(self, request, context=None):
            result = super().fetch(request, context)
            detail = result.audit['source_record_archive'][0]
            packet = result.audit['source_record_archive'][-1]
            index = packet['indexes'][0]
            if part == 'index_method': index['request']['method'] = 'POST'
            elif part == 'index_url': index['receipt']['source_url'] += '&code=2891'
            elif part == 'index_parameters': index['request']['params']['code'] = '2891'
            elif part == 'index_hash': index['receipt']['raw_response_sha256'] = '0'*64
            elif part == 'index_http_unknown': index['receipt']['http_status_observed'] = False
            elif part == 'body_http_unknown': detail['receipt']['http_status'] = None
            elif part == 'index_expiry': index['fresh_until_epoch'] = index['receipt']['retrieved_at']+1801
            elif part == 'body_expiry': detail['fresh_until_epoch'] = replay.epoch
            elif part == 'coverage_upgrade': packet['coverage_status'] = 'partial'
            return result

    svc = StockDataService(registry=ProviderRegistry([Tampered()]))
    result = asyncio.run(svc.fetch_source_async(FetchRequest.from_ticker('2851.TW'),
        'official_announcements', context={'data':identity()}))
    assert result.data['recent_catalysts'] == [] and len(replay.calls) == 4
    assert events()[-1]['status'] == 'error' and events()[-1]['record_count'] == 0


@pytest.mark.parametrize('boundary', ['pre_sla_read', 'merge_projection'])
def test_local_replay_deadline_is_terminal_without_any_new_http(monkeypatch, tmp_path, boundary):
    import official_announcement_source_refresh as subject
    import news_freshness_policy
    init_db()
    replay = IssuerReplay(monkeypatch)
    storage, name, keys, _ = report()
    before = storage.get_report(keys.data_key).content
    if boundary == 'pre_sla_read':
        read = subject.read_response
        def slow(proof, **kwargs):
            body = read(proof, **kwargs)
            replay.advance(2.01)
            return body
        monkeypatch.setattr(subject, 'read_response', slow)
    else:
        project = news_freshness_policy.apply_news_freshness
        def slow(*args, **kwargs):
            value = project(*args, **kwargs)
            replay.advance(2.01)
            return value
        monkeypatch.setattr(news_freshness_policy, 'apply_news_freshness', slow)
    with pytest.raises(HTTPException) as error:
        asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
            refresh_service=service(), source='official_announcements'))
    assert error.value.status_code == 502
    assert storage.get_report(keys.data_key).content == before
    assert len(replay.calls) == 4
    if boundary == 'pre_sla_read':
        assert events()[-1]['status'] == 'error'


def test_shorter_physical_original_expiry_cannot_be_hidden_by_aggregate(monkeypatch):
    init_db()
    replay = IssuerReplay(monkeypatch)
    svc = service()
    request = FetchRequest.from_ticker('2851.TW')
    first = asyncio.run(svc.fetch_source_async(request, 'official_announcements', context={'data':identity()}))
    assert len(first.data['recent_catalysts']) == 3
    for key, (value, _) in list(replay.cache._entries.items()):
        if key.startswith('twse-announcement-original:'):
            replay.cache._entries[key] = (value, replay.epoch+5)
    warm = asyncio.run(svc.fetch_source_async(request, 'official_announcements', context={'data':identity()}))
    assert warm.data['recent_catalysts'] == []
    assert warm.source_audit[0]['status'] == 'error' and len(replay.calls) == 4


def test_saved_component_originals_are_excluded_from_prompt(monkeypatch, tmp_path):
    from prompt_evidence import prompt_evidence_copy
    init_db()
    replay = IssuerReplay(monkeypatch)
    storage, name, keys, old = report()
    asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
        refresh_service=service(), source='official_announcements'))
    saved = json.loads(storage.get_report(keys.data_key).content)
    assert saved['data']['source_record_archive']
    prompt = json.dumps(prompt_evidence_copy(saved['data']), ensure_ascii=False)
    assert 'raw_response_path' not in prompt and 'ordinary-announcement-originals-v1' not in prompt
    assert saved['data']['source_freshness']['market_data']['fetched_at_epoch'] == old['source_audit'][0]['fetched_at_epoch']


@pytest.mark.parametrize('change', ['promote_old_bodies','renew_body_stamp','renew_aggregate_stamp'])
def test_public_same_body_cannot_be_promoted_or_retimed(monkeypatch, change):
    init_db()
    replay = IssuerReplay(monkeypatch)
    request = FetchRequest.from_ticker('2851.TW')
    svc = service()
    first = asyncio.run(svc.fetch_source_async(request,'official_announcements',context={'data':identity()}))
    assert len(first.data['recent_catalysts']) == 3
    replay.advance(61)
    if change == 'promote_old_bodies':
        for key in list(replay.cache._entries):
            if key.startswith('shared_provider:v1:'): replay.cache._entries.pop(key)

    class Tampered(TwseCompanyHistoryProvider):
        def fetch(self, request, context=None):
            result = super().fetch(request, context)
            if change == 'promote_old_bodies':
                result.status = 'success'
                result.audit.update(status='success',cache_hit=False,event_kind='aggregate',
                    body_cache_hit=False,detail_new_body_count=len(result.value),detail_cache_hit_count=0)
            elif change == 'renew_body_stamp': result.audit['body_fetched_at_epoch'] = replay.epoch
            else: result.audit['fetched_at_epoch'] = replay.epoch
            return result

    result = asyncio.run(StockDataService(registry=ProviderRegistry([Tampered()])).fetch_source_async(
        request,'official_announcements',context={'data':identity()}))
    assert result.data['recent_catalysts'] == []
    assert events()[-1]['status'] == 'error' and events()[-1]['record_count'] == 0


def test_64_body_replay_is_network_free_and_within_original_two_second_budget(monkeypatch):
    import official_announcement_source_refresh as subject
    from types import SimpleNamespace
    init_db()
    replay = IssuerReplay(monkeypatch, count=64, detail_cost=.001)
    result = asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2851.TW'),
        'official_announcements', context={'data':identity()}))
    assert len(result.data['recent_catalysts']) == 64
    calls, cache = list(replay.calls), deepcopy(replay.cache._entries)
    # Real wall-clock monotonic measurement of local replay, while archived
    # observation epochs remain the fixture's original time.
    clock = time.monotonic
    monkeypatch.setattr(subject, 'time', SimpleNamespace(monotonic=clock,time=lambda:replay.epoch))
    started = clock()
    subject.verify_value(result.data['recent_catalysts'],result.source_audit[0],identity(),
                         deadline=started+2.)
    elapsed = clock()-started
    print(f'64 complete synthetic detail originals local replay: {elapsed:.6f}s')
    assert elapsed < 2. and replay.calls == calls and replay.cache._entries == cache


def test_post_service_tamper_cannot_write_report(monkeypatch, tmp_path):
    init_db()
    replay = IssuerReplay(monkeypatch)
    storage, name, keys, _ = report()
    before = storage.get_report(keys.data_key).content
    svc = service()
    original = svc.fetch_source_async
    async def damaged(*args, **kwargs):
        result = await original(*args, **kwargs)
        result.data['recent_catalysts'][0]['summary'] = '非原始公告內容'
        return result
    monkeypatch.setattr(svc, 'fetch_source_async', damaged)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
            refresh_service=svc, source='official_announcements'))
    assert failure.value.status_code == 502 and len(replay.calls) == 4
    assert storage.get_report(keys.data_key).content == before


def test_partial_retry_with_only_old_bodies_remains_partial_and_not_new_acquisition(monkeypatch):
    from provider_acquisition import observation_kind
    init_db()
    replay = IssuerReplay(monkeypatch)
    replay.failures[replay.items[0]['link']] = ('timeout', 200)
    svc = service()
    request = FetchRequest.from_ticker('2851.TW')
    first = asyncio.run(svc.fetch_source_async(request,'official_announcements',context={'data':identity()}))
    assert len(first.data['recent_catalysts']) == 2
    replay.advance(61)
    second = asyncio.run(svc.fetch_source_async(request,'official_announcements',context={'data':identity()}))
    assert len(second.data['recent_catalysts']) == 2
    audit = second.source_audit[0]
    assert audit['status'] == 'degraded_enrichment' and audit['coverage_status'] == 'partial'
    assert audit['http_request_count'] == 2 and audit['detail_new_body_count'] == 0
    assert audit['cache_hit'] is False and audit['body_cache_hit'] is True
    assert audit['event_kind'] == 'aggregate'
    assert audit['fetched_at_epoch'] == first.source_audit[0]['fetched_at_epoch']
    row = events()[-1]; row['details'] = json.loads(row['details_json'])
    assert observation_kind(row) == 'degraded_count'


def test_expired_stored_body_does_not_block_new_native_when_optional_writes_fail(monkeypatch):
    init_db()
    replay = IssuerReplay(monkeypatch)
    svc = service(); request = FetchRequest.from_ticker('2851.TW')
    first = asyncio.run(svc.fetch_source_async(request,'official_announcements',context={'data':identity()}))
    assert len(first.data['recent_catalysts']) == 3
    old_epoch = first.source_audit[0]['body_fetched_at_epoch']
    replay.advance(1801)
    write = replay.cache.set_json
    def no_optional_write(key, *args, **kwargs):
        if key.startswith(('shared_provider:v1:', 'twse-announcement-original:')):
            raise OSError('isolated optional cache write outage')
        return write(key, *args, **kwargs)
    monkeypatch.setattr(replay.cache, 'set_json', no_optional_write)
    new = asyncio.run(svc.fetch_source_async(request,'official_announcements',context={'data':identity()}))
    assert len(new.data['recent_catalysts']) == 3 and len(replay.calls) == 8
    assert new.source_audit[0]['status'] == 'success'
    assert new.source_audit[0]['detail_new_body_count'] == 3
    assert new.source_audit[0]['body_fetched_at_epoch'] > old_epoch+1800
    assert all(not e['reusable'] for e in new.source_audit[0]['source_record_archive'][:-1])
