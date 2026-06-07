"""Optional Redis-backed guards shared across RQ workers."""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

from config import REDIS_URL, TASK_QUEUE_BACKEND

try:
    import redis
except Exception:  # pragma: no cover - redis is optional outside RQ deployments
    redis = None


RATE_LIMIT_LUA = """
local rpm_count = tonumber(redis.call('GET', KEYS[1]) or '0')
local tpm_count = tonumber(redis.call('GET', KEYS[2]) or '0')
local cooldown_ttl = redis.call('PTTL', KEYS[3])
local rpm_limit = tonumber(ARGV[1])
local tpm_limit = tonumber(ARGV[2])
local tokens = tonumber(ARGV[3])
local ttl_ms = tonumber(ARGV[4])
if cooldown_ttl and cooldown_ttl > 0 then
  return cooldown_ttl
end
if rpm_count >= rpm_limit or (tpm_limit > 0 and (tpm_count + tokens) > tpm_limit) then
  local rpm_ttl = redis.call('PTTL', KEYS[1])
  local tpm_ttl = redis.call('PTTL', KEYS[2])
  local wait_ttl = math.max(rpm_ttl, tpm_ttl)
  if wait_ttl < 0 then wait_ttl = ttl_ms end
  return wait_ttl
end
local new_rpm = redis.call('INCR', KEYS[1])
if new_rpm == 1 then redis.call('PEXPIRE', KEYS[1], ttl_ms) end
if tpm_limit > 0 then
  local new_tpm = redis.call('INCRBYFLOAT', KEYS[2], tokens)
  if tonumber(new_tpm) == tokens then redis.call('PEXPIRE', KEYS[2], ttl_ms) end
end
return 0
"""


def shared_guard_enabled(env_name: str) -> bool:
    backend = os.getenv(env_name, "auto").strip().lower()
    if backend in {"redis", "rq"}:
        return True
    if backend in {"local", "memory", "off", "disabled", "none"}:
        return False
    return TASK_QUEUE_BACKEND == "rq"


def create_redis_client(env_name: str):
    if redis is None or not shared_guard_enabled(env_name):
        return None
    try:
        client = redis.Redis.from_url(
            REDIS_URL,
            socket_connect_timeout=0.2,
            socket_timeout=1.0,
            decode_responses=True,
        )
        client.ping()
        return client
    except Exception:
        return None


def guard_hash(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


class RedisFixedWindowRateLimiter:
    def __init__(self, client: Any, *, namespace: str = "stock-agent"):
        self._client = client
        self._namespace = namespace
        self.enabled = client is not None

    def reserve(
        self,
        api_key: str,
        model: str,
        *,
        rpm_limit: int | float,
        tpm_limit: int | float | None = None,
        estimated_tokens: int = 0,
    ) -> float:
        if not self.enabled:
            return 0.0
        window = int(time.time() // 60)
        key_hash = guard_hash(api_key)
        model_hash = guard_hash(model)
        keys = [
            f"{self._namespace}:llm:{model_hash}:{key_hash}:{window}:rpm",
            f"{self._namespace}:llm:{model_hash}:{key_hash}:{window}:tpm",
            f"{self._namespace}:llm:{model_hash}:{key_hash}:cooldown",
        ]
        try:
            wait_ms = self._client.eval(
                RATE_LIMIT_LUA,
                len(keys),
                *keys,
                max(int(rpm_limit), 1),
                max(int(tpm_limit or 0), 0),
                max(int(estimated_tokens or 0), 1),
                60_000,
            )
            return max(float(wait_ms or 0) / 1000.0, 0.0)
        except Exception:
            self.enabled = False
            return 0.0

    def penalize(self, api_key: str, model: str, wait_seconds: float) -> None:
        if not self.enabled:
            return
        try:
            cooldown_key = f"{self._namespace}:llm:{guard_hash(model)}:{guard_hash(api_key)}:cooldown"
            self._client.set(cooldown_key, "1", px=max(int(wait_seconds * 1000), 1))
        except Exception:
            self.enabled = False


class RedisProviderCircuitStore:
    def __init__(self, client: Any, *, namespace: str = "stock-agent"):
        self._client = client
        self._namespace = namespace
        self.enabled = client is not None

    def state(self, provider: str) -> dict | None:
        if not self.enabled:
            return None
        try:
            fail_key = self._fail_key(provider)
            open_key = self._open_key(provider)
            raw = self._client.hgetall(fail_key) or {}
            ttl_ms = int(self._client.pttl(open_key) or -1)
            last_error = self._client.get(open_key) or raw.get("last_error") or ""
            return {
                "open": ttl_ms > 0,
                "failures": int(raw.get("failures") or 0),
                "opened_until": time.time() + ttl_ms / 1000.0 if ttl_ms > 0 else 0.0,
                "last_error": last_error,
            }
        except Exception:
            self.enabled = False
            return None

    def record_success(self, provider: str) -> None:
        if not self.enabled:
            return
        try:
            self._client.delete(self._fail_key(provider), self._open_key(provider))
        except Exception:
            self.enabled = False

    def record_failure(self, provider: str, error: str, threshold: int, cooldown_seconds: float) -> None:
        if not self.enabled:
            return
        try:
            fail_key = self._fail_key(provider)
            failures = int(self._client.hincrby(fail_key, "failures", 1))
            self._client.hset(fail_key, mapping={"last_error": error[:240]})
            self._client.expire(fail_key, 24 * 60 * 60)
            if failures >= threshold:
                self._client.set(self._open_key(provider), error[:240], ex=max(int(cooldown_seconds), 1))
        except Exception:
            self.enabled = False

    def clear(self, provider: str | None = None) -> None:
        if not self.enabled:
            return
        try:
            if provider is None:
                for key in self._client.scan_iter(f"{self._namespace}:provider-circuit:*"):
                    self._client.delete(key)
            else:
                self._client.delete(self._fail_key(provider), self._open_key(provider))
        except Exception:
            self.enabled = False

    def _fail_key(self, provider: str) -> str:
        return f"{self._namespace}:provider-circuit:{guard_hash(provider)}:fail"

    def _open_key(self, provider: str) -> str:
        return f"{self._namespace}:provider-circuit:{guard_hash(provider)}:open"


def create_shared_llm_limiter() -> RedisFixedWindowRateLimiter | None:
    client = create_redis_client("LLM_RATE_LIMIT_BACKEND")
    return RedisFixedWindowRateLimiter(client) if client is not None else None


def create_shared_provider_circuit_store() -> RedisProviderCircuitStore | None:
    client = create_redis_client("PROVIDER_CIRCUIT_BACKEND")
    return RedisProviderCircuitStore(client) if client is not None else None
