"""Public boundary checks. Original private-data replay cases remain local."""
from datetime import datetime
import hashlib
import json
import time
import pytest
from data_fetch.market_sources import twse_company_history as history
from test_twse_announcement_progress import Replay, NOW

class OrdinaryReplay(Replay):

    def __init__(self, monkeypatch):
        super().__init__(monkeypatch, count=2, detail_cost=0.1)
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
        parts['body'] = parts['body'].replace(b'2891', b'2059').replace('中信金'.encode(), '川湖'.encode()).replace(b'\\u4e2d\\u4fe1\\u91d1', b'\\u5ddd\\u6e56')
        from data_fetch.market_sources.twse_history_transport import IIH_URL
        if self.calls[-1].startswith(IIH_URL):
            payload = json.loads(parts['body'])
            payload['info']['data'].update(shortName='川湖', name='川湖科技股份有限公司')
            parts['body'] = json.dumps(payload).encode()
        return (parts, rc, error)

def test_native_supported_unlisted_issuer_saves_replayable_index_packet(monkeypatch):
    replay = OrdinaryReplay(monkeypatch)
    records, audit = history.fetch_recent_company_announcements('2059.TW', now=NOW)
    assert len(records) == 2 and audit['status'] == 'success'
    assert len(replay.calls) == 3
    assert all((r['text'].startswith('川湖（2059） ') for r in records))
    assert all((r['content_sha256'] == hashlib.sha256(r['text'].encode()).hexdigest() for r in records))
    archive = audit['source_record_archive']
    assert len(archive) == len(records) + 1, 'Supported native issuer omitted the request-bound index packet solely because it is not registered'
    assert archive[-1]['policy'] == 'ordinary-announcement-originals-v2'
    assert archive[-1]['ticker'] == '2059.TW'

def test_existing_special_json_and_tdr_routing_are_not_ordinary_admission():
    from official_announcement_source_refresh import supports
    from data_fetch.market_sources.mops_json_company_history import TICKERS
    assert TICKERS == {'1216.TW', '2442.TW', '2838.TW', '2845.TW', '6550.TW', '6924.TW'}
    assert all((not supports(ticker) for ticker in TICKERS | {'9103.TW', '0050.TW', '2059.TWO'}))

def test_1216_routes_through_json_history_without_legacy_fallback():
    calls = []
    from data_fetch.market_sources.twse_history_transport import JSON_URL

    def get(url, **kwargs):
        calls.append(('GET', url))
        raise AssertionError('1216 must use the verified JSON history route')

    def post(url, **kwargs):
        calls.append(('POST', url))
        assert url == JSON_URL
        return httpx.Response(200, request=httpx.Request('POST', url), json={'code': 406, 'message': '查無相符資料', 'result': None})
    records, audit = history.fetch_recent_company_announcements('1216.TW', now=NOW, get=get, post=post)
    assert records == []
    assert audit['status'] != 'success'
    assert calls and all((method == 'POST' and url == JSON_URL for method, url in calls))

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

@pytest.mark.parametrize('damage', ['short_name', 'row_name', 'invalid_short_name', 'invalid_legal_name'])
def test_normal_collector_rejects_native_index_name_conflict(monkeypatch, damage):
    replay = OrdinaryReplay(monkeypatch)
    collect = replay.collect
    from data_fetch.market_sources import twse_history_transport as transport

    def changed(*args, **kwargs):
        parts, rc, error = collect(*args, **kwargs)
        if replay.calls[-1].startswith(transport.IIH_URL):
            payload = json.loads(parts['body'])
            if damage == 'short_name':
                payload['info']['data']['shortName'] = '另一家公司'
            elif damage == 'row_name':
                for row in payload['news']:
                    row['companyName'] = '川湖測試別家公司'
            elif damage == 'invalid_short_name':
                payload['info']['data']['shortName'] = None
            else:
                payload['info']['data']['name'] = []
            parts['body'] = json.dumps(payload).encode()
        return (parts, rc, error)
    monkeypatch.setattr(transport, 'collect_capped_process', changed)
    records, audit = history.fetch_recent_company_announcements('2059.TW', now=NOW)
    assert not records and audit['status'] != 'success'
    assert not any(('ajax_t05sr01_1' in url for url in replay.calls))
