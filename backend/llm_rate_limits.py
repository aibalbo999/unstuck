"""API key rotation and local RPM/TPM throttling."""

from __future__ import annotations

import asyncio
import threading
import time

from config import API_KEY_SETUP_MESSAGE, MODEL_INPUT_TOKEN_LIMITS, RPD_LIMITS, RPM_LIMITS, TPM_LIMITS
from llm_daily_budget import AllKeysRpdDisabledError, DailyBudgetBlockedError, DailyBudgetStore
from llm_input_capacity import InputCapacityExceededError, ensure_input_capacity, estimate_text_tokens
from llm_rate_limit_buckets import TokenBucket, build_key_status
from llm_model_circuits import ModelCircuitOpenError, ModelCircuitStore, is_shared_model_circuit_open, open_shared_model_circuit, shared_model_circuit_wait
from llm_provider_routes import normalize_provider_keys as _normalize_provider_keys, provider_for_model
from runtime_events import emit_log
from shared_runtime_guards import LocalFixedWindowRateLimiter, create_shared_llm_limiter


class KeyRotator:
    """Per-key/model RPM and optional TPM buckets, locked across parallel agents."""

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
        self._model_circuits = ModelCircuitStore()
        self._daily_budget = DailyBudgetStore()

    def _daily_remaining(self, model: str) -> dict[str, int]:
        limit = RPD_LIMITS.get(model, RPD_LIMITS.get("*", 0))
        return self._daily_budget.remaining(self.keys, model, limit) if limit > 0 else {}

    def _reserve_daily_budget(self, key: str, model: str, request_units: int = 1) -> bool:
        limit = RPD_LIMITS.get(model, RPD_LIMITS.get("*", 0))
        return limit <= 0 or self._daily_budget.reserve(key, model, limit, self.keys, request_units=request_units)

    def _bucket(self, store: dict, key: str, model: str, limit: int | float) -> TokenBucket:
        bucket_key = (key, model)
        if bucket_key not in store:
            store[bucket_key] = TokenBucket.per_minute(limit)
        return store[bucket_key]

    def _minute_budget(self, key: str, model: str, estimated_tokens: int, *, reserve: bool) -> float:
        operation = "reserve" if reserve else "peek_wait"
        rpm_limit = RPM_LIMITS.get(model, RPM_LIMITS.get("*", 5))
        wait = getattr(self._bucket(self._rpm_buckets, key, model, rpm_limit), operation)(1)
        tpm_limit = TPM_LIMITS.get(model) or TPM_LIMITS.get("*")
        if tpm_limit and estimated_tokens > 0:
            wait = max(wait, getattr(self._bucket(self._tpm_buckets, key, model, tpm_limit), operation)(estimated_tokens))
        return wait

    def _reserve_for_key(self, key: str, model: str, estimated_tokens: int = 0) -> float:
        return self._minute_budget(key, model, estimated_tokens, reserve=True)

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
        return self._minute_budget(key, model, estimated_tokens, reserve=False)

    def _rpd_disabled_wait(self, key: str, model: str) -> float:
        limiter = self._shared_limiter if self._shared_limiter and self._shared_limiter.enabled else self._local_rpd_limiter
        if not hasattr(limiter, "rpd_disabled_wait"):
            return 0.0
        return float(limiter.rpd_disabled_wait(key, model) or 0.0)

    def _available_candidate_key_positions(self, model: str, request_units: int = 1) -> tuple[str, list[str], list[tuple[int, str]]]:
        shared_circuit_wait = self.model_circuit_wait(model)
        if shared_circuit_wait > 0:
            raise ModelCircuitOpenError(model, shared_circuit_wait)
        provider, keys, candidates = self._candidate_key_positions(model)
        remaining = self._daily_remaining(model)
        available = []
        disabled_waits = []
        local_blocked = False
        for position, key in candidates:
            disabled_wait = self._rpd_disabled_wait(key, model)
            if remaining.get(key, request_units) < request_units:
                disabled_wait = max(disabled_wait, self._daily_budget.reset_wait())
                local_blocked = True
            if disabled_wait > 0:
                disabled_waits.append(disabled_wait)
                continue
            available.append((position, key))
        if not available:
            retry_wait = min(disabled_waits) if disabled_waits else 60.0
            if local_blocked:
                raise DailyBudgetBlockedError(model, retry_wait, "daily_budget_exhausted")
            raise AllKeysRpdDisabledError(model, retry_wait)
        return provider, keys, available

    def _keys_for_model(self, model: str) -> tuple[str, list[str]]:
        provider = provider_for_model(model)
        keys = self.provider_keys.get(provider, [])
        if not keys:
            raise RuntimeError(f"未設定 {provider} API key，無法呼叫模型 {model}。")
        return provider, keys

    def eligible_key_slots(self, model: str) -> set[int]:
        """Return anonymous ledger slots eligible for this provider/model."""
        _, keys = self._keys_for_model(model)
        try:
            remaining = self._daily_remaining(model)
        except DailyBudgetBlockedError:
            return set()
        return {self.keys.index(key) + 1 for key in keys
                if self._rpd_disabled_wait(key, model) <= 0 and remaining.get(key, 1) > 0}

    def model_circuit_wait(self, model: str) -> float:
        return max(self._model_circuits.wait(model), shared_model_circuit_wait(self._shared_limiter, model))

    def model_retry_wait(self, model: str) -> float:
        _, keys = self._keys_for_model(model)
        try:
            remaining = self._daily_remaining(model)
        except DailyBudgetBlockedError as exc:
            return max(exc.retry_wait_seconds, self.model_circuit_wait(model))
        rpd_waits = [max(self._rpd_disabled_wait(key, model),
                        self._daily_budget.reset_wait() if remaining.get(key, 1) <= 0 else 0) for key in keys]
        daily_wait = min(rpd_waits) if rpd_waits and all(wait > 0 for wait in rpd_waits) else 0.0
        return max(daily_wait, self.model_circuit_wait(model))

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

    def _try_key(self, model: str, estimated_tokens: int, request_units: int):
        provider, keys, candidates = self._available_candidate_key_positions(model, request_units)
        reservations = [(self._wait_for_key(key, model, estimated_tokens), position, key) for position, key in candidates]
        wait, position, key = min(reservations, key=lambda item: item[0])
        if wait <= 0:
            wait = max(self._reserve_for_key(key, model, estimated_tokens),
                       self._reserve_shared_for_key(key, model, estimated_tokens))
            if wait <= 0:
                if not self._reserve_daily_budget(key, model, request_units):
                    return 0, provider, keys, None
                self._provider_indexes[provider] = (position + 1) % len(keys)
                self.index = (self.index + 1) % max(len(self.keys), 1)
        return wait, provider, keys, key

    def get_key(self, model: str, estimated_tokens: int = 0, *, request_units: int = 1) -> str:
        """Return a key after reserving RPM/TPM budget; sleeps only when budget is depleted."""
        ensure_input_capacity(model, estimated_tokens,
                              input_limit=MODEL_INPUT_TOKEN_LIMITS.get(model, MODEL_INPUT_TOKEN_LIMITS.get("*", 0)),
                              tpm_limit=TPM_LIMITS.get(model) or TPM_LIMITS.get("*"))
        while True:
            with self._sync_lock:
                wait, provider, keys, key = self._try_key(model, estimated_tokens, max(1, int(request_units)))

            if wait > 0:
                emit_log(f"    ⏳ {model} 動態限速等待 {wait:.1f} 秒...")
                time.sleep(wait)
                continue
            if key is None:
                continue
            emit_log(f"    🔑 使用 {provider} Key {keys.index(key)+1}/{len(keys)} ({self._preview_key(key)})")
            return key

    async def async_get_key(self, model: str, estimated_tokens: int = 0, *, request_units: int = 1) -> str:
        """Async version of get_key for parallel agent execution."""
        ensure_input_capacity(model, estimated_tokens,
                              input_limit=MODEL_INPUT_TOKEN_LIMITS.get(model, MODEL_INPUT_TOKEN_LIMITS.get("*", 0)),
                              tpm_limit=TPM_LIMITS.get(model) or TPM_LIMITS.get("*"))
        while True:
            async with self._async_lock:
                wait, provider, keys, key = self._try_key(model, estimated_tokens, max(1, int(request_units)))

            if wait > 0:
                emit_log(f"    ⏳ {model} 動態限速等待 {wait:.1f} 秒...")
                await asyncio.sleep(wait)
                continue
            if key is None:
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

    def open_model_circuit(
        self,
        model: str,
        *,
        cooldown_seconds: float | None = None,
        opened_until: float | None = None,
    ) -> None:
        """Publish a model circuit to other agents sharing this job rotator."""
        self._model_circuits.open(model, cooldown_seconds=cooldown_seconds, opened_until=opened_until)

    def open_shared_model_circuit(
        self,
        model: str,
        *,
        cooldown_seconds: float | None = None,
        opened_until: float | None = None,
    ) -> None:
        open_shared_model_circuit(self._shared_limiter, model, cooldown_seconds=cooldown_seconds, opened_until=opened_until)

    def is_model_circuit_open(self, model: str) -> bool:
        """Return whether a peer has opened this model circuit in this job."""
        return self._model_circuits.is_open(model)

    def is_shared_model_circuit_open(self, model: str) -> bool:
        return is_shared_model_circuit_open(self._shared_limiter, model)

    def disable_rpd_until_reset(self, key: str, model: str) -> float:
        """Disable a key/model pair until the next Pacific Time daily reset."""
        limiter = self._shared_limiter if self._shared_limiter and self._shared_limiter.enabled else self._local_rpd_limiter
        if not hasattr(limiter, "disable_rpd_until_reset"):
            return self._local_rpd_limiter.disable_rpd_until_reset(key, model)
        return float(limiter.disable_rpd_until_reset(key, model) or 0.0)

    def get_status(self) -> dict:
        return build_key_status(self.keys, self._rpm_buckets)
