"""Saved native bodies through the collector and public news projection; no HTTP."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from data_fetch.market_sources import twse_company_history as history
from news_freshness_policy import apply_news_freshness, apply_news_only_freshness

HERE = Path(__file__).resolve().parents[1] / 'docs/evidence/source-acquisition/20261016/remaining-source-expansion/remaining-gap-triage/staged'
INPUT = json.loads((HERE.parent / '1216-dedupe-input.json').read_text())
ORIGINALS = json.loads((HERE / 'fixtures/originals.json').read_text())

def collect():
    calls = []
    index = []
    bodies = {}
    for entry in ORIGINALS:
        raw = (HERE / 'fixtures' / (entry['raw_sha256'] + '.html')).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['raw_sha256']
        bodies[entry['url']] = raw
        index.append({'companyId': '1216', 'companyName': '統一', 'subject': entry['title'],
                      'date': entry['date'], 'time': entry['time'][:5], 'link': entry['url']})
    def get(url, **kwargs):
        calls.append(url)
        request = httpx.Request('GET', url)
        if url == history.INDEX_URL:
            return httpx.Response(200, request=request, json={
                'info': {'status': 'success', 'data': {'code': '1216', 'shortName': '統一', 'name': '統一企業'}},
                'news': index, 'fina': [], 'conference': []})
        return httpx.Response(200, request=request, content=bodies[url])
    records, audit = history.fetch_recent_company_announcements(
        '1216.TW', now=datetime.fromisoformat(INPUT['cutoff']), get=get)
    assert len(records) == 3 and len(calls) == 4
    assert audit['status'] == 'success'
    return records

def project(records, *, context=None, only=False):
    data = deepcopy(context or INPUT['context'])
    fn = apply_news_only_freshness if only else apply_news_freshness
    fn(data, records=deepcopy(records), cutoff=INPUT['cutoff'], limit=20)
    return data

def selected(data):
    return data['recent_catalysts'] + data['additional_recent_catalysts']

def test_saved_native_collector_keeps_distinct_events_with_shared_title():
    records = collect()
    assert len({r['title'] for r in records}) == 2
    assert len(selected(project(records))) == 3

def test_same_url_remains_one_event():
    row = collect()[0]
    assert len(selected(project([row, deepcopy(row)]))) == 1


@pytest.mark.parametrize('field,value', [
    ('ticker', '1217.TW'), ('source', 'Example Daily'), ('source_type', 'news'),
    ('issuer_identity_basis', 'headline'), ('content_truncated', True),
    ('date', '2026-09-23T15:48:25+08:00'),
    ('published_at', '2026-09-23T15:48:25+08:00'),
    ('content_sha256', '0' * 64), ('text', 'changed body'),
    ('official_event_sha256', '0' * 64),
])
def test_changed_record_binding_uses_conservative_title_dedupe(field, value):
    first, second, _ = collect()
    second[field] = value
    assert len(selected(project([first, second]))) == 1


@pytest.mark.parametrize('key,value', [
    ('COMPANY_ID', '1217'), ('SPOKE_DATE', '20260921'), ('SPOKE_TIME', '153117'),
    ('SEQ_NO', '2'), ('SEQ_NO', '0'), ('SEQ_NO', 'true'),
])
def test_url_issuer_date_clock_and_valid_changed_sequence_cannot_bypass_binding(key, value):
    first, second, _ = collect()
    from urllib.parse import urlencode
    params = {k: v[0] for k, v in parse_qs(urlsplit(second['link']).query).items()}
    params[key] = value
    second['link'] = second['link'].split('?')[0] + '?' + urlencode(params)
    assert len(selected(project([first, second]))) == 1


@pytest.mark.parametrize('field', ['official_event', 'official_event_sha256'])
def test_half_binding_does_not_bypass_title(field):
    first, second, _ = collect()
    second.pop(field)
    assert len(selected(project([first, second]))) == 1


def test_legacy_rows_stay_conservative_without_adding_binding():
    rows = collect()
    for row in rows:
        row.pop('official_event')
        row.pop('official_event_sha256')
    original = deepcopy(rows)
    result = selected(project(rows))
    assert len(result) == 2 and rows == original
    assert all('official_event' not in r for r in result)


def test_generic_same_title_different_urls_still_dedupe_and_same_url_new_title_still_dedupe():
    first, second, _ = collect()
    for row in (first, second):
        row.update(source='Example Daily', source_type='news')
    assert len(selected(project([first, second]))) == 1
    second.update(link=first['link'], title='另一個標題')
    assert len(selected(project([first, second]))) == 1


def test_same_event_query_order_and_zero_padding_do_not_create_second_event():
    first = collect()[0]
    second = deepcopy(first)
    from urllib.parse import urlencode, parse_qsl
    second['link'] = second['link'].split('?')[0] + '?' + urlencode(
        list(reversed(parse_qsl(second['link'].split('?')[1]))))
    second['link'] = second['link'].replace('SEQ_NO=1', 'SEQ_NO=01')
    from official_event_identity import ordinary_event_key
    assert ordinary_event_key(first, '1216.TW') == ordinary_event_key(second, '1216.TW')
    assert len(selected(project([first, second]))) == 1


def test_record_selection_and_news_only_projection_keep_binding_and_original_dates():
    from source_content_selection import select_company_records
    rows = collect()
    accepted, audit = select_company_records(rows, INPUT['context'], cutoff=INPUT['cutoff'])
    assert len(accepted) == audit['usable_count'] == 3
    result = project(accepted, only=True)
    for row in selected(result):
        original = next(r for r in rows if r['link'] == row['link'])
        assert row['official_event'] == original['official_event']
        assert row['official_event_sha256'] == original['official_event_sha256']
        assert row['published_at'] == original['published_at']
    again = deepcopy(result)
    apply_news_only_freshness(again, cutoff=INPUT['cutoff'], limit=20)
    assert again == result
    historical = deepcopy(result)
    apply_news_only_freshness(historical, cutoff='2026-11-30T00:00:00+00:00', limit=20)
    assert len(historical['historical_catalysts']) == 3 and not selected(historical)


def test_public_source_only_normal_path_keeps_same_title_different_sequences(monkeypatch, tmp_path):
    import asyncio
    from test_official_announcement_source_refresh import IssuerReplay, init_db, report, service
    from report_refresh_service import refresh_report_data_snapshot
    init_db()
    replay = IssuerReplay(monkeypatch)
    for row in replay.items:
        row['title'] = '公告本公司董事會決議'
    storage, name, keys, old = report()
    asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
        refresh_service=service(), source='official_announcements', return_refreshed_data=True))
    saved = json.loads(storage.get_report(keys.data_key).content)
    rows = selected(saved['data'])
    assert len(rows) == 3 and len({r['official_event']['sequence'] for r in rows}) == 3
    assert saved['rerun_context'] == old['rerun_context']


@pytest.mark.parametrize('mutation', ['legacy', 'half', 'digest', 'body'])
def test_public_warm_cache_legacy_shape_or_tamper(monkeypatch, mutation):
    import asyncio
    from test_official_announcement_source_refresh import IssuerReplay, init_db, service, identity
    from data_fetch.types import FetchRequest
    from provider_acquisition import observation_kind
    init_db()
    replay, svc = IssuerReplay(monkeypatch), service()
    request = FetchRequest.from_ticker('2851.TW')
    first = asyncio.run(svc.fetch_source_async(request, 'official_announcements', context={'data': identity()}))
    calls = list(replay.calls)
    found = 0
    for key, (raw, until) in list(replay.cache._entries.items()):
        if not key.startswith('shared_provider:v1:'):
            continue
        value = deepcopy(raw)
        rows = value['value'][0]
        for row in rows:
            if mutation == 'legacy':
                row.pop('official_event'); row.pop('official_event_sha256')
            elif mutation == 'half':
                row.pop('official_event_sha256')
            elif mutation == 'digest':
                row['official_event_sha256'] = '0' * 64
            else:
                row['text'] += '不屬於原件'
        replay.cache._entries[key] = (value, until)
        found += 1
    assert found == 1
    warm = asyncio.run(svc.fetch_source_async(request, 'official_announcements', context={'data': identity()}))
    assert replay.calls == calls
    if mutation == 'legacy':
        assert len(warm.data['recent_catalysts']) == 3
        assert all('official_event' not in r for r in warm.data['recent_catalysts'])
        audit = warm.source_audit[0]
        assert audit['http_request_count'] == 0 and audit['detail_new_body_count'] == 0
        assert audit['fetched_at_epoch'] == first.source_audit[0]['fetched_at_epoch']
        assert observation_kind({'provider': audit['provider'], 'status': audit['status'],
            'record_count': audit['record_count'], 'message': '', 'details': audit}) == 'fresh_cache_count'
    else:
        assert warm.data['recent_catalysts'] == [] and warm.source_audit[0]['status'] == 'error'
