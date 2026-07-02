from __future__ import annotations

import json
import sys
import types

import pytest

import cache_backends
import cache_store
from cache_backends import CacheBackend, InMemoryCache, LocalRedisCache, SqliteCacheBackend


class FakeRedis:
    def __init__(self):
        self.values: dict[str, bytes] = {}
        self.set_calls: list[tuple[str, str, int]] = []
        self.deleted: list[str] = []
        self.closed = False

    def set(self, name, value, ex):
        self.set_calls.append((name, value, ex))
        self.values[name] = value.encode("utf-8")
        return True

    def get(self, name):
        return self.values.get(name)

    def delete(self, name):
        self.deleted.append(name)
        return int(self.values.pop(name, None) is not None)

    def close(self):
        self.closed = True


class RecordingLock:
    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class InterleavingLock(RecordingLock):
    def __init__(self, on_enter):
        super().__init__()
        self._on_enter = on_enter

    def __enter__(self):
        super().__enter__()
        self._on_enter()
        return self


class ClosingInMemoryCache(InMemoryCache):
    def __init__(self):
        super().__init__()
        self.closed = False

    def close(self):
        self.closed = True


def test_local_redis_cache_namespaces_and_round_trips_json():
    redis_client = FakeRedis()
    cache = LocalRedisCache(redis_client=redis_client, namespace="stock:test")
    value = {"ticker": "台積電", "unsupported": object()}

    cache.set_json("quote", value, ttl_seconds=60)

    key, serialized, ttl = redis_client.set_calls[0]
    assert key == "stock:test:quote"
    assert json.loads(serialized)["ticker"] == "台積電"
    assert ttl == 60
    assert cache.get_json("quote") == {
        "ticker": "台積電",
        "unsupported": str(value["unsupported"]),
    }
    assert cache.delete("quote") is True
    assert cache.delete("quote") is False
    cache.close()
    assert redis_client.closed is True


def test_local_redis_cache_rejects_non_positive_ttl():
    cache = LocalRedisCache(redis_client=FakeRedis())

    with pytest.raises(ValueError, match="ttl_seconds"):
        cache.set_json("quote", {}, ttl_seconds=0)


def test_local_redis_cache_defaults_to_local_docker_redis(monkeypatch):
    captured = {}

    class RedisFactory:
        @staticmethod
        def from_url(redis_url):
            captured["redis_url"] = redis_url
            return FakeRedis()

    monkeypatch.setitem(sys.modules, "redis", types.SimpleNamespace(Redis=RedisFactory))

    cache = LocalRedisCache()

    assert captured["redis_url"] == "redis://localhost:6379/0"
    cache.close()


def test_local_redis_cache_does_not_swallow_connection_failures():
    class FailingRedis(FakeRedis):
        def get(self, name):
            raise ConnectionError("redis unavailable")

    cache = LocalRedisCache(redis_client=FailingRedis())

    with pytest.raises(ConnectionError, match="redis unavailable"):
        cache.get_json("quote")


def test_in_memory_cache_deep_copies_values_and_expires_with_time(monkeypatch):
    now = 100.0
    monkeypatch.setattr(cache_backends.time, "time", lambda: now)
    cache = InMemoryCache()
    original = {"items": [1]}
    cache.set_json("key", original, ttl_seconds=60)
    original["items"].append(2)

    cached = cache.get_json("key")
    assert cached == {"items": [1]}
    cached["items"].append(3)
    assert cache.get_json("key") == {"items": [1]}

    now = 160.0
    assert cache.get_json("key") is None


def test_in_memory_cache_delete_cleanup_and_protocol(monkeypatch):
    now = 100.0
    monkeypatch.setattr(cache_backends.time, "time", lambda: now)
    cache = InMemoryCache()
    assert isinstance(cache, CacheBackend)
    cache.set_json("expired", 1, ttl_seconds=1)
    cache.set_json("current", 2, ttl_seconds=60)

    now = 102.0
    assert cache.cleanup_expired() == 1
    assert cache.delete("current") is True
    assert cache.delete("missing") is False
    cache.close()


def test_sqlite_cache_backend_round_trip_delete_cleanup_and_close(tmp_path, monkeypatch):
    now = 100.0
    monkeypatch.setattr(cache_backends.time, "time", lambda: now)
    path = tmp_path / "cache.sqlite3"
    cache = SqliteCacheBackend(path)
    assert isinstance(cache, CacheBackend)
    cache.set_json("current", {"ticker": "台積電"}, ttl_seconds=60)
    cache.set_json("expired", [1, 2], ttl_seconds=1)
    assert cache.get_json("current") == {"ticker": "台積電"}

    now = 101.0
    assert cache.cleanup_expired() == 1
    assert cache.get_json("expired") is None
    assert cache.delete("current") is True
    assert cache.delete("current") is False

    cache.close()
    cache.set_json("after-close", True, ttl_seconds=60)
    assert cache.get_json("after-close") is True
    cache.reset()


def test_sqlite_cache_backend_releases_thread_local_connection_after_operations(tmp_path):
    cache = SqliteCacheBackend(tmp_path / "cache.sqlite3")

    cache.set_json("current", {"ticker": "MOPS"}, ttl_seconds=60)
    assert getattr(cache._resource._local, "conn", None) is None

    assert cache.get_json("current") == {"ticker": "MOPS"}
    assert getattr(cache._resource._local, "conn", None) is None

    assert cache.delete("current") is True
    assert getattr(cache._resource._local, "conn", None) is None

    assert cache.cleanup_expired() == 0
    assert getattr(cache._resource._local, "conn", None) is None


def test_sqlite_cache_backend_removes_invalid_json(tmp_path):
    cache = SqliteCacheBackend(tmp_path / "cache.sqlite3")
    cache.set_json("broken", {"valid": True}, ttl_seconds=60)
    with cache._resource.connect() as conn:
        conn.execute("UPDATE cache_entries SET value = ? WHERE cache_key = ?", ("{", "broken"))

    assert cache.get_json("broken") is None
    assert cache.delete("broken") is False
    cache.close()


def test_sqlite_cache_backend_locks_get_json_cleanup_writes(tmp_path, monkeypatch):
    now = 100.0
    monkeypatch.setattr(cache_backends.time, "time", lambda: now)
    cache = SqliteCacheBackend(tmp_path / "cache.sqlite3")
    cache.set_json("expired", {"valid": True}, ttl_seconds=1)
    cache.set_json("broken", {"valid": True}, ttl_seconds=60)
    with cache._resource.connect() as conn:
        conn.execute("UPDATE cache_entries SET value = ? WHERE cache_key = ?", ("{", "broken"))

    now = 102.0
    lock = RecordingLock()
    cache._lock = lock

    assert cache.get_json("expired") is None
    assert cache.get_json("broken") is None
    assert lock.entered == 2
    cache.close()


def test_sqlite_cache_backend_cleanup_does_not_delete_replaced_rows(tmp_path, monkeypatch):
    now = 100.0
    monkeypatch.setattr(cache_backends.time, "time", lambda: now)
    cache = SqliteCacheBackend(tmp_path / "cache.sqlite3")
    cache.set_json("expired", {"old": True}, ttl_seconds=1)
    cache.set_json("broken", {"old": True}, ttl_seconds=60)
    with cache._resource.connect() as conn:
        conn.execute("UPDATE cache_entries SET value = ? WHERE cache_key = ?", ("{", "broken"))

    now = 102.0

    def replace_expired_row():
        with cache._resource.connect() as conn:
            conn.execute(
                """
                UPDATE cache_entries
                SET value = ?, expires_at = ?, updated_at = ?
                WHERE cache_key = ?
                """,
                (json.dumps({"fresh": "expired"}), 500.0, now, "expired"),
            )

    cache._lock = InterleavingLock(replace_expired_row)
    assert cache.get_json("expired") is None
    assert cache.get_json("expired") == {"fresh": "expired"}

    def replace_broken_row():
        with cache._resource.connect() as conn:
            conn.execute(
                """
                UPDATE cache_entries
                SET value = ?, expires_at = ?, updated_at = ?
                WHERE cache_key = ?
                """,
                (json.dumps({"fresh": "broken"}), 500.0, now, "broken"),
            )

    cache._lock = InterleavingLock(replace_broken_row)
    assert cache.get_json("broken") is None
    assert cache.get_json("broken") == {"fresh": "broken"}
    cache.close()


def test_cache_store_facade_delegates_and_closes_replaced_backend():
    first = ClosingInMemoryCache()
    second = InMemoryCache()
    cache_store.set_cache_backend(first)
    cache_store.set_cache_json("key", {"value": 1}, 60)
    assert cache_store.get_cache_json("key") == {"value": 1}

    cache_store.set_cache_backend(second)
    assert first.closed is True
    assert cache_store.get_cache_json("key") is None
    cache_store.set_cache_json("expired", 1, 1)
    assert cache_store.cleanup_expired_cache_entries() == 0
    cache_store.close_cache_store()


def test_cache_store_lazy_backend_uses_current_monkeypatched_path(tmp_path, monkeypatch):
    first_path = tmp_path / "first.sqlite3"
    second_path = tmp_path / "second.sqlite3"
    monkeypatch.setattr(cache_store, "CACHE_DB_PATH", str(first_path))
    cache_store.reset_cache_store_for_tests()
    cache_store.set_cache_json("first", {"path": 1}, 60)
    assert first_path.exists()

    monkeypatch.setattr(cache_store, "CACHE_DB_PATH", str(second_path))
    cache_store.reset_cache_store_for_tests()
    cache_store.set_cache_json("second", ["any", "json"], 60)

    assert second_path.exists()
    assert cache_store.get_cache_json("second") == ["any", "json"]
