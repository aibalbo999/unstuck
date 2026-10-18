"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import json
import pytest

def selected(data):
    return data['recent_catalysts'] + data['additional_recent_catalysts']

def test_public_source_only_normal_path_keeps_same_title_different_sequences(monkeypatch, tmp_path):
    import asyncio
    from test_official_announcement_source_refresh import IssuerReplay, init_db, report, service
    from report_refresh_service import refresh_report_data_snapshot
    init_db()
    replay = IssuerReplay(monkeypatch)
    for row in replay.items:
        row['title'] = '公告本公司董事會決議'
    storage, name, keys, old = report()
    asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage, refresh_service=service(), source='official_announcements', return_refreshed_data=True))
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
    replay, svc = (IssuerReplay(monkeypatch), service())
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
                row.pop('official_event')
                row.pop('official_event_sha256')
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
        assert all(('official_event' not in r for r in warm.data['recent_catalysts']))
        audit = warm.source_audit[0]
        assert audit['http_request_count'] == 0 and audit['detail_new_body_count'] == 0
        assert audit['fetched_at_epoch'] == first.source_audit[0]['fetched_at_epoch']
        assert observation_kind({'provider': audit['provider'], 'status': audit['status'], 'record_count': audit['record_count'], 'message': '', 'details': audit}) == 'fresh_cache_count'
    else:
        assert warm.data['recent_catalysts'] == [] and warm.source_audit[0]['status'] == 'error'
