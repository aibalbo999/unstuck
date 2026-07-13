"""API key rotation and local RPM/TPM throttling."""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass

from config import API_KEY_SETUP_MESSAGE, RPM_LIMITS, TPM_LIMITS
from llm_provider_routes import provider_for_model
from runtime_events import emit_log
from shared_runtime_guards import LocalFixedWindowRateLimiter, create_shared_llm_limiter


@dataclass
class TokenBucket:
    capacity: float
    refill_per_second: float
    tokens: float
    updated_at: float

    @classmethod
    def per_minute(cls, limit: int | float) -> "TokenBucket":
        capacity = max(float(limit), 1.0)
        return cls(
            capacity=capacity,
            refill_per_second=capacity / 60.0,
            tokens=capacity,
            updated_at=time.monotonic(),
        )

    def reserve(self, amount: int | float = 1) -> float:
        amount = min(max(float(amount), 1.0), self.capacity)
        now = time.monotonic()

        if now < self.updated_at:
            wait = self.updated_at - now + amount / self.refill_per_second
            self.updated_at += amount / self.refill_per_second
            return wait

        elapsed = now - self.updated_at
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated_at = now

        if self.tokens >= amount:
            self.tokens -= amount
            return 0.0

        shortage = amount - self.tokens
        wait = shortage / self.refill_per_second
        self.tokens = 0.0
        self.updated_at = now + wait
        return wait

    def peek_wait(self, amount: int | float = 1) -> float:
        amount = min(max(float(amount), 1.0), self.capacity)
        now = time.monotonic()

        if now < self.updated_at:
            return self.updated_at - now + amount / self.refill_per_second

        tokens = min(self.capacity, self.tokens + (now - self.updated_at) * self.refill_per_second)
        if tokens >= amount:
            return 0.0
        return (amount - tokens) / self.refill_per_second

    def penalize(self, seconds: float) -> None:
        self.tokens = 0.0
        self.updated_at = max(self.updated_at, time.monotonic() + max(seconds, 0.0))


class AllKeysRpdDisabledError(RuntimeError):
    """Raised when every configured key for a model is disabled by RPD reset time."""

    def __init__(self, model: str, retry_wait_seconds: float):
        super().__init__(f"所有 API key 對模型 {model} 的每日額度已暫停，約 {retry_wait_seconds:.1f} 秒後恢復。")
        self.model = model
        self.retry_wait_seconds = retry_wait_seconds


class KeyRotator:
    """
    API Key rotator with per-key/model token buckets.

    RPM is always enforced. TPM is enforced when configured for the model.
    The async path uses an asyncio lock so parallel agents can share one rotator
    without racing each other into a 429.
    """

    def __init__(self, keys: list[str] | dict[str, list[str]]):
        self.provider_keys = _normalize_provider_keys(keys)
        if not any(self.provider_keys.values()):
            raise RuntimeError(API_KEY_SETUP_MESSAGE)
        self.keys = [key for provider_keys in self.provider_keys.values() for key in provider_keys]
        self.index = 0
        self._provider_indexes = {provider: 0 for provider in self.provider_keys}
        self._rpm_buckets: dict[tuple[str, str], TokenBucket] = {}
        self._tpm_buckets: dict[tuple[str, str], TokenBucket] = {}
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._shared_limiter = create_shared_llm_limiter()
        self._local_rpd_limiter = LocalFixedWindowRateLimiter()

    def _bucket(self, store: dict, key: str, model: str, limit: int | float) -> TokenBucket:
        bucket_key = (key, model)
        if bucket_key not in store:
            store[bucket_key] = TokenBucket.per_minute(limit)
        return store[bucket_key]

    def _reserve_for_key(self, key: str, model: str, estimated_tokens: int = 0) -> float:
        rpm_limit = RPM_LIMITS.get(model, RPM_LIMITS.get("*", 5))
        wait = self._bucket(self._rpm_buckets, key, model, rpm_limit).reserve(1)

        tpm_limit = TPM_LIMITS.get(model) or TPM_LIMITS.get("*")
        if tpm_limit and estimated_tokens > 0:
            token_wait = self._bucket(self._tpm_buckets, key, model, tpm_limit).reserve(estimated_tokens)
            wait = max(wait, token_wait)

        return wait

    def _reserve_shared_for_key(self, key: str, model: str, estimated_tokens: int = 0) -> float:
        if not self._shared_limiter or not self._shared_limiter.enabled:
            return 0.0
        rpm_limit = RPM_LIMITS.get(model, RPM_LIMITS.get("*", 5))
        tpm_limit = TPM_LIMITS.get(model) or TPM_LIMITS.get("*")
        return self._shared_limiter.reserve(
            key,
            model,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            estimated_tokens=estimated_tokens,
        )

    def _wait_for_key(self, key: str, model: str, estimated_tokens: int = 0) -> float:
        rpm_limit = RPM_LIMITS.get(model, RPM_LIMITS.get("*", 5))
        wait = self._bucket(self._rpm_buckets, key, model, rpm_limit).peek_wait(1)

        tpm_limit = TPM_LIMITS.get(model) or TPM_LIMITS.get("*")
        if tpm_limit and estimated_tokens > 0:
            token_wait = self._bucket(self._tpm_buckets, key, model, tpm_limit).peek_wait(estimated_tokens)
            wait = max(wait, token_wait)

        return wait

    def _rpd_disabled_wait(self, key: str, model: str) -> float:
        limiter = self._shared_limiter if self._shared_limiter and self._shared_limiter.enabled else self._local_rpd_limiter
        if not hasattr(limiter, "rpd_disabled_wait"):
            return 0.0
        return float(limiter.rpd_disabled_wait(key, model) or 0.0)

    def _available_candidate_key_positions(self, model: str) -> tuple[str, list[str], list[tuple[int, str]]]:
        provider, keys, candidates = self._candidate_key_positions(model)
        available = []
        disabled_waits = []
        for position, key in candidates:
            disabled_wait = self._rpd_disabled_wait(key, model)
            if disabled_wait > 0:
                disabled_waits.append(disabled_wait)
                continue
            available.append((position, key))
        if not available:
            retry_wait = min(disabled_waits) if disabled_waits else 60.0
            raise AllKeysRpdDisabledError(model, retry_wait)
        return provider, keys, available

    def _keys_for_model(self, model: str) -> tuple[str, list[str]]:
        provider = provider_for_model(model)
        keys = self.provider_keys.get(provider, [])
        if not keys:
            raise RuntimeError(f"未設定 {provider} API key，無法呼叫模型 {model}。")
        return provider, keys

    def _candidate_key_positions(self, model: str) -> tuple[str, list[str], list[tuple[int, str]]]:
        provider, keys = self._keys_for_model(model)
        start_index = self._provider_indexes.get(provider, 0)
        candidates = []
        for offset in range(len(keys)):
            position = (start_index + offset) % len(keys)
            candidates.append((position, keys[position]))
        return provider, keys, candidates

    def _preview_key(self, key: str) -> str:
        return f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"

    def get_key(self, model: str, estimated_tokens: int = 0) -> str:
        """Return a key after reserving RPM/TPM budget; sleeps only when budget is depleted."""
        while True:
            with self._sync_lock:
                provider, keys, candidates = self._available_candidate_key_positions(model)
                reservations = [
                    (self._wait_for_key(key, model, estimated_tokens), position, key)
                    for position, key in candidates
                ]
                wait, key_position, key = min(reservations, key=lambda item: item[0])
                if wait <= 0:
                    wait = max(
                        self._reserve_for_key(key, model, estimated_tokens),
                        self._reserve_shared_for_key(key, model, estimated_tokens),
                    )
                    if wait <= 0:
                        self._provider_indexes[provider] = (key_position + 1) % len(keys)
                        self.index = (self.index + 1) % max(len(self.keys), 1)

            if wait > 0:
                emit_log(f"    ⏳ {model} 動態限速等待 {wait:.1f} 秒...")
                time.sleep(wait)
                continue

            emit_log(f"    🔑 使用 {provider} Key {keys.index(key)+1}/{len(keys)} ({self._preview_key(key)})")
            return key

    async def async_get_key(self, model: str, estimated_tokens: int = 0) -> str:
        """Async version of get_key for parallel agent execution."""
        while True:
            async with self._async_lock:
                provider, keys, candidates = self._available_candidate_key_positions(model)
                reservations = [
                    (self._wait_for_key(key, model, estimated_tokens), position, key)
                    for position, key in candidates
                ]
                wait, key_position, key = min(reservations, key=lambda item: item[0])
                if wait <= 0:
                    wait = max(
                        self._reserve_for_key(key, model, estimated_tokens),
                        self._reserve_shared_for_key(key, model, estimated_tokens),
                    )
                    if wait <= 0:
                        self._provider_indexes[provider] = (key_position + 1) % len(keys)
                        self.index = (self.index + 1) % max(len(self.keys), 1)

            if wait > 0:
                emit_log(f"    ⏳ {model} 動態限速等待 {wait:.1f} 秒...")
                await asyncio.sleep(wait)
                continue

            emit_log(f"    🔑 使用 {provider} Key {keys.index(key)+1}/{len(keys)} ({self._preview_key(key)})")
            return key

    def penalize(self, key: str, model: str, wait_seconds: float = 60) -> None:
        """Push a key/model pair into cooldown after provider-side rate limiting."""
        with self._sync_lock:
            rpm_limit = RPM_LIMITS.get(model, RPM_LIMITS.get("*", 5))
            self._bucket(self._rpm_buckets, key, model, rpm_limit).penalize(wait_seconds)
            tpm_limit = TPM_LIMITS.get(model) or TPM_LIMITS.get("*")
            if tpm_limit:
                self._bucket(self._tpm_buckets, key, model, tpm_limit).penalize(wait_seconds)
            if self._shared_limiter:
                self._shared_limiter.penalize(key, model, wait_seconds)

    def disable_rpd_until_reset(self, key: str, model: str) -> float:
        """Disable a key/model pair until the next Pacific Time daily reset."""
        limiter = self._shared_limiter if self._shared_limiter and self._shared_limiter.enabled else self._local_rpd_limiter
        if not hasattr(limiter, "disable_rpd_until_reset"):
            return self._local_rpd_limiter.disable_rpd_until_reset(key, model)
        return float(limiter.disable_rpd_until_reset(key, model) or 0.0)

    def get_status(self) -> dict:
        now = time.monotonic()
        status = {}
        for i, key in enumerate(self.keys):
            key_name = f"Key-{i+1}"
            status[key_name] = {}
            for (bucket_key, model), bucket in self._rpm_buckets.items():
                if bucket_key != key:
                    continue
                available_in = max(bucket.updated_at - now, 0.0)
                status[key_name][model] = {
                    "rpm_tokens": round(bucket.tokens, 2),
                    "available_in_seconds": round(available_in, 2),
                }
        return status


def estimate_text_tokens(text: str, response_budget: int = 0) -> int:
    """Small local estimate for TPM throttling; intentionally conservative."""
    if not text:
        return max(response_budget, 1)
    return max(int(len(text) / 3.5) + response_budget, 1)


def _normalize_provider_keys(keys: list[str] | dict[str, list[str]]) -> dict[str, list[str]]:
    if isinstance(keys, dict):
        return {
            str(provider or "").strip().lower(): list(dict.fromkeys(str(key).strip() for key in provider_keys if str(key).strip()))
            for provider, provider_keys in keys.items()
        }
    return {"google": list(dict.fromkeys(str(key).strip() for key in keys if str(key).strip()))}
