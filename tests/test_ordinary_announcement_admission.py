"""Design REDs at public boundaries; native process output is synthetic, no HTTP."""
import asyncio
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'tests')]
from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.service import StockDataService
from data_fetch.types import FetchRequest
from data_fetch.market_sources import twse_company_history as history
from test_twse_announcement_progress import Replay, NOW
from test_report_refresh_acquisition_audit import init_db, events

D = ROOT / 'docs/evidence/source-acquisition/20261016/remaining-source-expansion/announcement-admission-review'


def saved_identity():
    fixture = json.loads((D / '2059-identity-projection.json').read_text())
    return deepcopy(fixture['data'])


class OrdinaryReplay(Replay):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch, count=2, detail_cost=.1)
        for item in self.items:
            item['link'] = item['link'].replace('2891', '2059')
            item['company'] = '川湖'
        self.by_url = {i['link']: i for i in self.items}
        monkeypatch.setattr(time, 'time', lambda: self.epoch)
        owner = self

        class ClockDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromtimestamp(owner.epoch, tz)

        monkeypatch.setattr(history, 'datetime', ClockDateTime)

    def collect(self, argv, end, **kwargs):
        parts, rc, error = super().collect(argv, end, **kwargs)
        parts['body'] = (parts['body'].replace(b'2891', b'2059')
                         .replace('中信金'.encode(), '川湖'.encode())
                         .replace(b'\\u4e2d\\u4fe1\\u91d1', b'\\u5ddd\\u6e56'))
        from data_fetch.market_sources.twse_history_transport import IIH_URL
        if self.calls[-1].startswith(IIH_URL):
            payload = json.loads(parts['body'])
            payload['info']['data'].update(shortName='川湖', name='川湖科技股份有限公司')
            parts['body'] = json.dumps(payload).encode()
        return parts, rc, error


def service():
    return StockDataService(registry=ProviderRegistry([TwseCompanyHistoryProvider()]))


def test_native_supported_unlisted_issuer_saves_replayable_index_packet(monkeypatch):
    replay = OrdinaryReplay(monkeypatch)
    records, audit = history.fetch_recent_company_announcements('2059.TW', now=NOW)
    assert len(records) == 2 and audit['status'] == 'success'
    assert len(replay.calls) == 3
    assert all(r['text'].startswith('川湖（2059） ') for r in records)
    assert all(r['content_sha256'] == hashlib.sha256(r['text'].encode()).hexdigest() for r in records)
    archive = audit['source_record_archive']
    assert len(archive) == len(records) + 1, 'Supported native issuer omitted the request-bound index packet solely because it is not registered'
    assert archive[-1]['policy'] == 'ordinary-announcement-originals-v2'
    assert archive[-1]['ticker'] == '2059.TW'


def test_public_source_service_can_admit_saved_issuer_with_complete_native_chain(monkeypatch):
    init_db()
    replay = OrdinaryReplay(monkeypatch)
    result = asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2059.TW'),
                       'official_announcements', context={'data': saved_identity()}))
    assert len(result.data['recent_catalysts']) == 2
    assert result.source_audit[0]['status'] == 'success'
    assert len(replay.calls) == 3 and len(events()) == 1


@pytest.mark.parametrize('damage', ['ticker', 'stock_id', 'top_stock_id', 'etf', 'quoteType', 'forbidden'])
def test_saved_identity_conflicts_must_still_fail_before_transport(monkeypatch, damage):
    init_db()
    replay = OrdinaryReplay(monkeypatch)
    data = saved_identity()
    if damage == 'ticker':
        data['company_identity']['ticker'] = '2367.TW'
    elif damage == 'stock_id':
        data['company_identity']['stock_id'] = '2367'
    elif damage == 'top_stock_id':
        data['stock_id'] = '2367'
    elif damage == 'etf':
        data['quote_type'] = 'ETF'
    elif damage == 'quoteType':
        data['quoteType'] = 'UNKNOWN'
    else:
        data['company_identity']['forbidden_aliases'] = ['川湖']
    with pytest.raises(RuntimeError):
        asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2059.TW'),
                    'official_announcements', context={'data': data}))
    assert replay.calls == [] and events() == []


def test_existing_special_json_and_tdr_routing_are_not_ordinary_admission():
    from official_announcement_source_refresh import supports
    from data_fetch.market_sources.mops_json_company_history import TICKERS
    assert TICKERS == {'1216.TW', '2442.TW', '2838.TW', '2845.TW', '6550.TW', '6924.TW'}
    assert all(not supports(ticker) for ticker in TICKERS | {'9103.TW', '0050.TW', '2059.TWO'})


def test_1216_routes_through_json_history_without_legacy_fallback():
    calls = []
    from data_fetch.market_sources.twse_history_transport import JSON_URL

    def get(url, **kwargs):
        calls.append(('GET', url))
        raise AssertionError('1216 must use the verified JSON history route')

    def post(url, **kwargs):
        calls.append(('POST', url))
        assert url == JSON_URL
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'code': 406, 'message': '查無相符資料', 'result': None})

    records, audit = history.fetch_recent_company_announcements(
        '1216.TW', now=NOW, get=get, post=post)

    assert records == []
    assert audit['status'] != 'success'
    assert calls and all(method == 'POST' and url == JSON_URL for method, url in calls)


@pytest.mark.parametrize('damage', ['company_prefix', 'market_substring'])
def test_native_detail_header_requires_exact_issuer_and_market_tokens(monkeypatch, damage):
    replay = OrdinaryReplay(monkeypatch)
    native_detail = replay.detail

    def changed(item):
        raw = native_detail(item)
        if damage == 'company_prefix':
            return raw.replace('川湖 公司提供'.encode(), '川湖測試別家公司 公司提供'.encode())
        return raw.replace('(上市公司)'.encode(), '(非上市公司)'.encode())

    replay.detail = changed
    records, audit = history.fetch_recent_company_announcements('2059.TW', now=NOW)
    assert not records, 'Substring membership is insufficient to bind the native detail issuer and market'
    assert audit['status'] != 'success'


def fetch(data=None, svc=None):
    return asyncio.run((svc or service()).fetch_source_async(FetchRequest.from_ticker('2059.TW'),
        'official_announcements', context={'data': saved_identity() if data is None else data}))


@pytest.mark.parametrize('damage', ['short_name', 'row_name', 'invalid_short_name', 'invalid_legal_name'])
def test_normal_collector_rejects_native_index_name_conflict(monkeypatch, damage):
    replay = OrdinaryReplay(monkeypatch)
    collect = replay.collect
    from data_fetch.market_sources import twse_history_transport as transport
    def changed(*args, **kwargs):
        parts, rc, error = collect(*args, **kwargs)
        if replay.calls[-1].startswith(transport.IIH_URL):
            payload = json.loads(parts['body'])
            if damage == 'short_name': payload['info']['data']['shortName'] = '另一家公司'
            elif damage == 'row_name':
                for row in payload['news']: row['companyName'] = '川湖測試別家公司'
            elif damage == 'invalid_short_name': payload['info']['data']['shortName'] = None
            else: payload['info']['data']['name'] = []
            parts['body'] = json.dumps(payload).encode()
        return parts, rc, error
    monkeypatch.setattr(transport, 'collect_capped_process', changed)
    records, audit = history.fetch_recent_company_announcements('2059.TW', now=NOW)
    assert not records and audit['status'] != 'success'
    assert not any('ajax_t05sr01_1' in url for url in replay.calls)


@pytest.mark.parametrize('saved_legal, native_legal, admitted', [
    (None, '川湖科技股份有限公司', True),
    ('川湖科技股份有限公司', '川湖科技股份有限公司', True),
    ('另一家股份有限公司', '川湖科技股份有限公司', False),
    (None, None, True),
    ('川湖科技股份有限公司', None, False),
])
def test_native_legal_name_is_optional_but_saved_assertion_requires_original(monkeypatch, saved_legal, native_legal, admitted):
    init_db()
    replay = OrdinaryReplay(monkeypatch)
    collect = replay.collect
    from data_fetch.market_sources import twse_history_transport as transport
    def changed(*args, **kwargs):
        parts, rc, error = collect(*args, **kwargs)
        if replay.calls[-1].startswith(transport.IIH_URL) and native_legal is None:
            payload = json.loads(parts['body']); payload['info']['data'].pop('name')
            parts['body'] = json.dumps(payload).encode()
        return parts, rc, error
    monkeypatch.setattr(transport, 'collect_capped_process', changed)
    data = saved_identity(); data['company_identity']['legal_name'] = saved_legal
    result = fetch(data)
    assert bool(result.data['recent_catalysts']) is admitted
    assert result.source_audit[0]['status'] == ('success' if admitted else 'error')
    assert len(replay.calls) == 3


@pytest.mark.parametrize('damage', ['legacy_packet', 'packet_claim', 'saved_name', 'rewritten_record', 'missing_packet'])
def test_context_or_packet_cannot_replace_native_identity(monkeypatch, damage):
    from official_announcement_source_refresh import POLICY
    init_db(); replay = OrdinaryReplay(monkeypatch)
    class Tampered(TwseCompanyHistoryProvider):
        def fetch(self, request, context=None):
            result = super().fetch(request, context)
            packet = result.audit['source_record_archive'][-1]
            if damage == 'legacy_packet': packet['policy'] = POLICY
            elif damage == 'packet_claim': packet['identity'] = {'official_name':'川湖'}
            elif damage == 'missing_packet': result.audit['source_record_archive'].pop()
            elif damage == 'rewritten_record':
                for row in result.value:
                    row['text'] = row['text'].replace('川湖', '另一家公司')
                    row['summary'] = row['text'][:1500]
                    row['content_sha256'] = hashlib.sha256(row['text'].encode()).hexdigest()
            return result
    data = saved_identity()
    if damage in {'saved_name', 'rewritten_record'}: data['company_identity']['official_name'] = '另一家公司'
    result = fetch(data, StockDataService(registry=ProviderRegistry([Tampered()])))
    assert result.data['recent_catalysts'] == []
    assert events()[-1]['status'] == 'error' and events()[-1]['record_count'] == 0
    assert len(replay.calls) == 3


@pytest.mark.parametrize('damage', [None, 'market', 'header', 'company', 'legal'])
def test_ez_only_requires_same_native_code_market_company_and_body(monkeypatch, damage):
    from data_fetch.market_sources import twse_history_transport as transport
    init_db(); replay = OrdinaryReplay(monkeypatch)
    replay.failures[transport.IIH_URL+'?code=2059'] = ('timeout', 200)
    collect = replay.collect
    def changed(*args, **kwargs):
        parts, rc, error = collect(*args, **kwargs)
        if replay.calls[-1] == transport.EZ_URL and damage in {'market','company'}:
            payload = json.loads(parts['body'])
            for row in payload['data']: row['TYPEK' if damage == 'market' else 'COMPANY_NAME'] = '上櫃' if damage == 'market' else '別家公司'
            parts['body'] = json.dumps(payload).encode()
        elif 'ajax_t05sr01_1' in replay.calls[-1] and damage == 'header':
            parts['body'] = parts['body'].replace('(上市公司)'.encode(), '(非上市公司)'.encode())
        return parts, rc, error
    monkeypatch.setattr(transport, 'collect_capped_process', changed)
    data = saved_identity()
    if damage == 'legal': data['company_identity']['legal_name'] = '川湖科技股份有限公司'
    result = fetch(data)
    assert bool(result.data['recent_catalysts']) is (damage is None)
    if damage is None:
        assert result.source_audit[0]['status'] == 'success'
        indexes = result.source_audit[0]['source_record_archive'][-1]['indexes']
        assert len(indexes) == 1 and indexes[0]['request']['url'] == transport.EZ_URL
    else: assert result.source_audit[0]['status'] != 'success'
    assert len(replay.calls) <= 4


def test_warm_dynamic_packet_preserves_epoch_and_never_counts_new_acquisition(monkeypatch):
    from provider_acquisition import observation_kind
    init_db(); replay = OrdinaryReplay(monkeypatch); svc = service()
    first = fetch(svc=svc); replay.advance(61)
    warm = fetch(svc=svc)
    assert len(warm.data['recent_catalysts']) == 2 and len(replay.calls) == 3
    audit = warm.source_audit[0]
    assert audit['status'] == 'skipped_fresh_cache'
    assert audit['http_request_count'] == 0 and audit['detail_new_body_count'] == 0
    assert audit['fetched_at_epoch'] == first.source_audit[0]['fetched_at_epoch']
    row = events()[-1]; row['details'] = json.loads(row['details_json'])
    assert observation_kind(row) == 'fresh_cache_count'


@pytest.mark.parametrize('damage', ['missing_packet', 'body_physical_ttl', 'original_ttl'])
def test_warm_old_or_expired_packet_cannot_be_fabricated_or_renewed(monkeypatch, damage):
    init_db(); replay = OrdinaryReplay(monkeypatch); svc = service()
    first = fetch(svc=svc); assert len(first.data['recent_catalysts']) == 2
    if damage == 'body_physical_ttl':
        for key, (value, until) in list(replay.cache._entries.items()):
            if key.startswith('twse-announcement-original:'):
                replay.cache._entries[key] = (value, replay.epoch+5)
    else:
        for key, (value, until) in list(replay.cache._entries.items()):
            if key.startswith('shared_provider:v1:'):
                archive = value['value'][1]['source_record_archive']
                if damage == 'missing_packet': archive.pop()
                else: archive[-1]['indexes'][0]['fresh_until_epoch'] = replay.epoch
    warm = fetch(svc=svc)
    assert warm.data['recent_catalysts'] == [] and len(replay.calls) == 3
    assert events()[-1]['status'] == 'error'


def test_dynamic_public_report_merge_preserves_analysis_and_requires_same_originals(monkeypatch, tmp_path):
    from report_refresh_service import refresh_report_data_snapshot
    from test_official_announcement_source_refresh import report
    init_db(); replay = OrdinaryReplay(monkeypatch)
    storage, name, keys, old = report()
    old['ticker'] = '2059.TW'; old['data'].update(saved_identity())
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    result = asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
        refresh_service=service(), source='official_announcements', return_refreshed_data=True))
    saved = json.loads(storage.get_report(keys.data_key).content)
    assert len(saved['data']['recent_catalysts']) == 2 and len(replay.calls) == 3
    assert result['analysis_text_stale'] is True
    for key in ('analysis_evidence','analysis_completeness','oos_evaluation_inputs','rerun_context',
                'conclusion_generated_at','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
        assert saved.get(key) == old.get(key), key
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'


@pytest.mark.parametrize('damage', ['TDR', 'identity_quote_type', 'identity_quoteType'])
def test_instrument_conflicts_never_reach_transport(monkeypatch, damage):
    init_db(); replay = OrdinaryReplay(monkeypatch); data = saved_identity()
    if damage == 'TDR': data['company_identity']['official_name'] = '川湖-DR'
    else: data['company_identity'][damage.removeprefix('identity_')] = 'ETF'
    with pytest.raises(RuntimeError): fetch(data)
    assert replay.calls == [] and events() == []
