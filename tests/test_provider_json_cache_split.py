"""Source guards must not write/checkpoint the large report/checkpoint database."""
import json
from pathlib import Path
import sqlite3
import time

import pytest

import cache_store
from cache_backends import SqliteCacheBackend


def test_configured_provider_cache_never_opens_report_database_for_writing(tmp_path, monkeypatch):
    report = tmp_path / 'reports.sqlite3'
    dedicated = tmp_path / 'provider-json.sqlite3'
    with sqlite3.connect(report) as conn:
        conn.execute('CREATE TABLE checkpoints (value TEXT)')
        conn.execute("INSERT INTO checkpoints VALUES ('original')")
    seeded = SqliteCacheBackend(dedicated)
    seeded.set_json('source-guard', {'retry_at': time.time() + 600}, ttl_seconds=600)
    seeded.close()
    cache_store.reset_cache_store_for_tests()
    monkeypatch.setattr(cache_store, 'CACHE_DB_PATH', str(report))
    monkeypatch.setattr(cache_store, 'JSON_CACHE_DB_PATH', str(dedicated), raising=False)
    connect = sqlite3.connect
    def checked(database, *args, **kwargs):
        name = str(database)
        if str(report) in name:
            assert kwargs.get('uri') and 'mode=ro' in name, 'report database write connection on source cache hot path'
        return connect(database, *args, **kwargs)
    monkeypatch.setattr(sqlite3, 'connect', checked)
    try:
        assert cache_store.get_cache_json('source-guard')['retry_at'] > time.time()
        cache_store.set_cache_json('second-guard', {'state': 'unchanged-policy'}, ttl_seconds=600)
        assert cache_store.get_cache_json('second-guard') == {'state': 'unchanged-policy'}
    finally:
        cache_store.reset_cache_store_for_tests()


def test_missing_migration_cannot_replace_existing_cache_with_empty_guard_store(tmp_path, monkeypatch):
    report = tmp_path / 'reports.sqlite3'
    dedicated = tmp_path / 'missing-provider-cache.sqlite3'
    previous = SqliteCacheBackend(report)
    previous.set_json('source-guard', {'retry_at': time.time() + 600}, ttl_seconds=600)
    previous.close()
    cache_store.reset_cache_store_for_tests()
    monkeypatch.setattr(cache_store, 'CACHE_DB_PATH', str(report))
    monkeypatch.setattr(cache_store, 'JSON_CACHE_DB_PATH', str(dedicated), raising=False)
    try:
        with pytest.raises(RuntimeError, match='migration'):
            cache_store.get_cache_json('source-guard')
        assert not dedicated.exists()
    finally:
        cache_store.reset_cache_store_for_tests()


def test_copy_preserves_all_keys_values_ttl_and_cooldowns(tmp_path):
    from provider_json_cache_migration import copy_cache_entries, ensure_cache_destination
    report, dedicated = tmp_path / 'report.sqlite3', tmp_path / 'json.sqlite3'
    seed = SqliteCacheBackend(report)
    now = time.time()
    seed.set_json('cooldown', {'retry_at': now + 600, 'error_kind': 'rate_limited'}, ttl_seconds=700)
    seed.set_json('original', {'fetched_at_epoch': now - 300, 'response_sha256': 'a' * 64}, ttl_seconds=600)
    seed.close()
    with sqlite3.connect(report) as conn:
        conn.execute('INSERT INTO cache_entries VALUES(?,?,?,?)', ('expired', '{"old":true}', now-60, now-120))
        conn.execute('CREATE TABLE checkpoints (value TEXT)')
        conn.execute("INSERT INTO checkpoints VALUES ('preserve original checkpoint')")
        before = conn.execute('SELECT * FROM cache_entries ORDER BY cache_key').fetchall()
    receipt = copy_cache_entries(report, dedicated)
    assert receipt['keys_values_and_expiry_preserved'] and receipt['row_count'] == 3
    ensure_cache_destination(report, dedicated)
    with sqlite3.connect(dedicated) as conn:
        assert conn.execute('SELECT * FROM cache_entries ORDER BY cache_key').fetchall() == before
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='checkpoints'").fetchone() is None
    with sqlite3.connect(report) as conn:
        assert conn.execute('SELECT * FROM cache_entries ORDER BY cache_key').fetchall() == before
        assert conn.execute('SELECT value FROM checkpoints').fetchone()[0] == 'preserve original checkpoint'
    active = SqliteCacheBackend(dedicated)
    assert active.get_json('cooldown') == {'retry_at': now + 600, 'error_kind': 'rate_limited'}
    assert active.get_json('original')['fetched_at_epoch'] == now - 300
    assert active.get_json('expired') is None
    active.close()


def test_existing_unqualified_destination_cannot_hide_legacy_guards(tmp_path):
    from provider_json_cache_migration import copy_cache_entries, ensure_cache_destination
    report, dedicated = tmp_path / 'report.sqlite3', tmp_path / 'json.sqlite3'
    for path in (report, dedicated):
        seed = SqliteCacheBackend(path); seed.set_json('guard', {'keep': str(path)}, ttl_seconds=600); seed.close()
    with pytest.raises(FileExistsError):
        copy_cache_entries(report, dedicated)
    with pytest.raises(RuntimeError, match='migration'):
        ensure_cache_destination(report, dedicated)


def test_unsupported_source_schema_keeps_original_and_does_not_publish(tmp_path):
    from provider_json_cache_migration import copy_cache_entries
    report, dedicated = tmp_path / 'report.sqlite3', tmp_path / 'json.sqlite3'
    with sqlite3.connect(report) as conn:
        conn.execute('CREATE TABLE cache_entries (unknown TEXT)')
        conn.execute("INSERT INTO cache_entries VALUES ('untouched')")
    with pytest.raises(ValueError, match='schema'):
        copy_cache_entries(report, dedicated)
    assert not dedicated.exists()
    with sqlite3.connect(report) as conn:
        assert conn.execute('SELECT unknown FROM cache_entries').fetchone()[0] == 'untouched'


def test_moved_legacy_429_guard_still_prevents_native_http(tmp_path, monkeypatch):
    from provider_json_cache_migration import copy_cache_entries
    from data_fetch.market_sources import official_issuer_master_transport as transport
    from search_provider_runtime import SourceResponseError
    report, dedicated = tmp_path / 'report.sqlite3', tmp_path / 'json.sqlite3'
    previous = SqliteCacheBackend(report)
    guard = {'error_kind': 'rate_limited', 'http_status': 429,
             'retry_after_epoch': time.time() + 600, 'fallback_eligible': True}
    previous.set_json(transport.LEGACY_RAW_KEY, guard, ttl_seconds=600)
    previous.close()
    copy_cache_entries(report, dedicated)
    cache_store.reset_cache_store_for_tests()
    monkeypatch.setattr(cache_store, 'CACHE_DB_PATH', str(report))
    monkeypatch.setattr(cache_store, 'JSON_CACHE_DB_PATH', str(dedicated), raising=False)
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError('active legacy quota guard must prevent HTTP')
    monkeypatch.setattr(transport.IssuerMasterHttp, 'download_original', forbidden)
    try:
        http = transport.IssuerMasterHttp(time.monotonic() + 3, force_refresh=False, use_cache=True)
        with pytest.raises(SourceResponseError) as error:
            http.get_receipt(transport.MASTER_URL)
        assert error.value.error_kind == 'rate_limited'
        assert calls == [] and http.http_request_count == 0
        assert cache_store.get_cache_json(transport.LEGACY_RAW_KEY) == guard
    finally:
        cache_store.reset_cache_store_for_tests()


def test_runtime_map_distinguishes_json_cache_from_report_and_checkpoint_databases(tmp_path):
    from runtime_paths import RuntimePaths
    report, dedicated = tmp_path / 'report.sqlite3', tmp_path / 'json.sqlite3'
    paths = RuntimePaths.from_values(output_dir=tmp_path/'output', cache_dir=tmp_path,
        report_index_db=report, langgraph_checkpoint_path=report, json_cache_db=dedicated)
    assert paths.json_cache_db == dedicated
    assert paths.report_index_db == paths.langgraph_checkpoint_path == report
    assert paths.as_dict()['json_cache_db']['path'] == str(dedicated)
