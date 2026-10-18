"""2812 source-only admission through the existing native-process replay seam.

All generated index/detail responses here are synthetic behavior fixtures, not
official research originals or proof that production announcement text exists.
"""
import asyncio
from copy import deepcopy
import json

import pytest
from fastapi import HTTPException

from data_fetch.types import FetchRequest
from report_refresh_service import refresh_report_data_snapshot
from test_official_announcement_source_refresh import IssuerReplay, report, service
from test_report_refresh_acquisition_audit import events, init_db


class TaichungReplay(IssuerReplay):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch, count=2)
        for item in self.items:
            item['link'] = item['link'].replace('2851', '2812')
            item['company'] = '台中銀'
        self.by_url = {item['link']: item for item in self.items}

    def collect(self, argv, end, **kwargs):
        parts, rc, error = super().collect(argv, end, **kwargs)
        parts['body'] = (parts['body'].replace(b'2851', b'2812')
            .replace('中再保'.encode(), '台中銀'.encode())
            .replace(b'\\u4e2d\\u518d\\u4fdd', b'\\u53f0\\u4e2d\\u9280'))
        return parts, rc, error


def identity():
    # Preserve the saved snapshot's identity; do not infer legal_name or UBN.
    return {'ticker': '2812.TW', 'company_name': '台中銀', 'quote_type': 'EQUITY',
            'company_identity': {'ticker': '2812.TW', 'stock_id': '2812',
                'official_name': '台中銀', 'legal_name': None,
                'instrument_type': 'EQUITY', 'forbidden_aliases': []}}


def taichung_report():
    storage, name, keys, old = report()
    old['ticker'] = '2812.TW'
    old['data'].update(identity())
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    return storage, name, keys, old


def test_public_refresh_admits_2812_and_preserves_conclusions(monkeypatch, tmp_path):
    init_db()
    replay = TaichungReplay(monkeypatch)
    storage, name, keys, old = taichung_report()
    result = asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
        refresh_service=service(), source='official_announcements', return_refreshed_data=True))
    saved = json.loads(storage.get_report(keys.data_key).content)
    records = saved['data']['recent_catalysts']
    assert len(records) == 2 and len(replay.calls) == 3
    assert all(row['text'].startswith('台中銀（2812） ') and not row['content_truncated'] for row in records)
    assert saved['data']['company_identity'] == old['data']['company_identity']
    assert saved['data']['source_record_archive']
    for key in ('analysis_evidence', 'analysis_completeness', 'oos_evaluation_inputs', 'rerun_context',
                'conclusion_generated_at', 'report_lint', 'final_audit', 'evidence_exit_gate',
                'content_credibility', 'report_conformance'):
        assert saved.get(key) == old.get(key), key
    for key in ('current_price', 'years', 'revenue_history', 'earnings_call', 'peer_discovery_results'):
        assert saved['data'].get(key) == old['data'].get(key), key
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'
    assert result['analysis_text_stale'] is True
    assert len(events()) == 1 and events()[0]['record_count'] == 2


def test_public_service_2812_retains_and_replays_same_original_receipts(monkeypatch):
    import official_announcement_source_refresh as subject
    init_db()
    replay = TaichungReplay(monkeypatch)
    result = asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2812.TW'),
        'official_announcements', context={'data': identity()}))
    records, audit = result.data['recent_catalysts'], result.source_audit[0]
    assert len(records) == 2 and audit['status'] == 'success'
    assert audit['http_request_count'] == 3 and len(replay.calls) == 3
    packet = audit['source_record_archive'][-1]
    assert packet['ticker'] == '2812.TW'
    assert packet['indexes'][0]['request']['params'] == {'code': '2812'}
    before = deepcopy((records, audit, replay.cache._entries, replay.calls))
    subject.verify_value(records, audit, identity(), deadline=replay.mono + 2.)
    assert (records, audit, replay.cache._entries, replay.calls) == before
    assert len(events()) == 1 and events()[0]['status'] == 'success'


@pytest.mark.parametrize('field,value', [
    ('ticker', '2812.TWO'), ('stock_id', '2851'), ('official_name', '中再保'),
    ('instrument_type', 'ETF'), ('forbidden_aliases', ['台中銀']),
])
def test_2812_wrong_context_rejects_before_native_io(monkeypatch, tmp_path, field, value):
    init_db()
    replay = TaichungReplay(monkeypatch)
    storage, name, keys, old = taichung_report()
    old['data']['company_identity'][field] = value
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    before = storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException) as failure:
        asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
            refresh_service=service(), source='official_announcements'))
    assert failure.value.status_code == 400
    assert replay.calls == [] and events() == []
    assert storage.get_report(keys.data_key).content == before


@pytest.mark.parametrize('field', ['company', 'ticker'])
def test_2812_wrong_original_company_or_ticker_never_becomes_accepted_body(monkeypatch, field):
    init_db()
    replay = TaichungReplay(monkeypatch)
    original = replay.detail

    def wrong(item):
        raw = original(item)
        return (raw.replace('台中銀'.encode(), '錯誤公司'.encode()) if field == 'company'
                else raw.replace(b'2891', b'1234'))

    replay.detail = wrong
    result = asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2812.TW'),
        'official_announcements', context={'data': identity()}))
    assert result.data['recent_catalysts'] == [] and len(replay.calls) == 3
    assert events()[-1]['record_count'] == 0
    assert events()[-1]['status'] != 'success'


@pytest.mark.parametrize('part', ['packet_ticker', 'index_request_ticker', 'body_expiry'])
def test_2812_post_service_receipt_tamper_does_not_write_report(monkeypatch, tmp_path, part):
    init_db()
    replay = TaichungReplay(monkeypatch)
    storage, name, keys, _ = taichung_report()
    before = storage.get_report(keys.data_key).content
    svc = service()
    original = svc.fetch_source_async

    async def damaged(*args, **kwargs):
        result = await original(*args, **kwargs)
        archive = result.source_audit[0]['source_record_archive']
        if part == 'packet_ticker':
            archive[-1]['ticker'] = '2851.TW'
        elif part == 'index_request_ticker':
            archive[-1]['indexes'][0]['request']['params']['code'] = '2851'
        else:
            archive[0]['fresh_until_epoch'] = replay.epoch
        return result

    monkeypatch.setattr(svc, 'fetch_source_async', damaged)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
            refresh_service=svc, source='official_announcements'))
    assert failure.value.status_code == 502 and len(replay.calls) == 3
    assert storage.get_report(keys.data_key).content == before
