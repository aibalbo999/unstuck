"""Connection-budget scenarios; synthetic transport replay, never live success."""
import json

import pytest

from test_twse_announcement_progress import Replay
from data_fetch.market_sources import twse_history_transport as transport
from search_provider_runtime import SourceResponseError


class ConnectReplay(Replay):
    """Model curl's connect and total limits before returning fixture bytes."""
    def __init__(self, monkeypatch, *, count=3, connect_seconds=2.6):
        super().__init__(monkeypatch, count=count, detail_cost=.1)
        self.connect_seconds = connect_seconds
        self.delayed_urls = set(self.by_url)

    def collect(self, argv, end, **kwargs):
        url = argv[-1]
        if url in self.delayed_urls:
            available = min(float(argv[argv.index('--connect-timeout') + 1]),
                            float(argv[argv.index('--max-time') + 1]),
                            max(0., end - self.mono))
            if self.connect_seconds >= available:
                self.calls.append(url)
                self.advance(available)
                return {'body': b'', 'headers': b'',
                        'metadata': json.dumps({'http_code': 0}).encode(),
                        'process_started': True}, 28, 'timeout'
            self.advance(self.connect_seconds)
        return super().collect(argv, end, **kwargs)


def test_slow_detail_connections_can_complete_inside_existing_request_budget(monkeypatch):
    replay = ConnectReplay(monkeypatch)
    records, audit = replay.fetch()
    assert len(records) == 3
    assert audit['coverage_status'] == 'window_complete'
    assert audit['detail_new_body_count'] == 3
    assert audit['detail_cache_hit_count'] == 0
    assert audit['http_request_count'] == 4
    assert replay.mono < 120.
    assert all(replay.calls.count(url) == 1 for url in replay.by_url)
    assert all(item['receipt']['raw_response_bytes'] > 0
               for item in audit['source_record_archive'] if 'receipt' in item)


def test_stalled_details_do_not_extend_request_or_source_deadline_or_retry(monkeypatch):
    replay = ConnectReplay(monkeypatch, count=6, connect_seconds=5.)
    records, audit = replay.fetch()
    assert records == []
    assert replay.mono <= 120.
    details = [o for o in audit['request_observations'] if o['url'] in replay.by_url]
    assert 1 <= len(details) <= 6
    assert all(o['elapsed_seconds'] <= 4. for o in details)
    assert all(o['error_kind'] == 'timeout' and not o['http_status_observed'] for o in details)
    assert all(replay.calls.count(url) <= 1 for url in replay.by_url)
    assert audit['detail_new_body_count'] == 0


def test_last_detail_cannot_borrow_time_beyond_remaining_source_budget(monkeypatch):
    replay = ConnectReplay(monkeypatch, count=1)
    client = transport.BoundedHistoryHttp(replay.mono + 1.5)
    with pytest.raises(SourceResponseError) as error:
        client.get(next(iter(replay.by_url)))
    assert error.value.error_kind == 'timeout'
    assert replay.mono == pytest.approx(101.5)
    assert client.http_request_count == 1
    assert client.request_observations[0]['response_complete'] is False


def test_index_connect_limit_is_unchanged(monkeypatch):
    replay = ConnectReplay(monkeypatch, count=1)
    replay.delayed_urls = {transport.IIH_URL + '?code=2891'}
    with pytest.raises(SourceResponseError) as error:
        transport.BoundedHistoryHttp(replay.mono + 20).get(transport.IIH_URL, params={'code': '2891'})
    assert error.value.error_kind == 'timeout'
    assert replay.mono == pytest.approx(102.)
    assert len(replay.calls) == 1
