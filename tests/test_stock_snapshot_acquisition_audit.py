"""The default public snapshot route must retain real service fetch observations."""
from copy import deepcopy
import json
import sqlite3
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import provider_sla
import api_routes.stock_snapshot as route_module
import data_fetch.service as service_module


def client(monkeypatch, tmp_path, *, status='success', failed=False):
    path = tmp_path / 'snapshot-operational.sqlite3'
    monkeypatch.setattr(provider_sla, 'TASK_DB_PATH', str(path))
    calls = []
    original_epoch = time.time() - 300
    async def acquire(request, *, registry=None):
        calls.append(request)
        audit = {'source': 'market_data', 'provider': 'snapshot public fixture', 'status': status,
                 'record_count': 0 if failed else 1, 'fetched_at_epoch': original_epoch,
                 'cache_hit': status == 'skipped_fresh_cache', 'stale': False,
                 'http_request_sent': status != 'skipped_fresh_cache',
                 'event_kind': 'cache_hit' if status == 'skipped_fresh_cache' else 'sdk_operation'}
        data = {'ticker': request.ticker, 'company_name': 'Apple Inc.', 'current_price': 200.,
                'source_audit': [audit]}
        if failed:
            data['error'] = 'fixture provider unavailable'
        return deepcopy(data)
    # Both aliases point to the same external workflow seam. Neither branch
    # may reach Redis, an API, or a model in this isolated check.
    monkeypatch.setattr(route_module, 'fetch_payload_async', acquire, raising=False)
    monkeypatch.setattr(service_module, 'fetch_payload_async', acquire)
    app = FastAPI()
    app.include_router(route_module.create_stock_snapshot_router())
    return TestClient(app), path, calls, original_epoch


def events(path):
    if not path.exists():
        return []
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute('select * from provider_sla_events order by id')]


def test_default_snapshot_records_one_successful_observation_with_current_fetch_identity(monkeypatch, tmp_path):
    api, path, calls, epoch = client(monkeypatch, tmp_path)
    response = api.get('/api/stocks/aapl/snapshot')
    assert response.status_code == 200 and response.json()['quote']['price'] == 200.
    observed = events(path)
    assert len(observed) == 1
    row = observed[0]
    detail = json.loads(row['details_json'])
    assert row['status'] == 'success' and row['record_count'] == 1
    assert detail['ticker'] == 'AAPL' and detail['fetch_id']
    assert 'job_id' not in detail
    assert len(calls) == 1 and calls[0].options.skip_optional_http is False
    assert calls[0].options.force_refresh is False and calls[0].options.record_provider_sla is True


def test_rejected_snapshot_keeps_the_original_failed_observation(monkeypatch, tmp_path):
    api, path, _calls, _epoch = client(monkeypatch, tmp_path, status='error', failed=True)
    response = api.get('/api/stocks/AAPL/snapshot')
    assert response.status_code == 502 and response.json()['detail'] == 'fixture provider unavailable'
    observed = events(path)
    assert len(observed) == 1 and observed[0]['status'] == 'error' and observed[0]['record_count'] == 0
    assert json.loads(observed[0]['details_json'])['fetch_id']


def test_cached_snapshot_is_not_counted_as_a_new_fetch(monkeypatch, tmp_path):
    api, path, _calls, _epoch = client(monkeypatch, tmp_path, status='skipped_fresh_cache')
    assert api.get('/api/stocks/AAPL/snapshot').status_code == 200
    observed = events(path)
    assert len(observed) == 1 and observed[0]['status'] == 'skipped_fresh_cache'
    detail = json.loads(observed[0]['details_json'])
    assert detail['cache_hit'] is True and detail['fetch_id']
    from provider_acquisition import get_provider_acquisition_summary
    summary = get_provider_acquisition_summary('last_24h')
    row = next(source for source in summary['sources'] if source['source'] == 'market_data')
    assert row['fetch_attempts'] == 0 and row['fresh_cache_count'] == 1
