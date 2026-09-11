"""Provider key availability and model-circuit behavior for KeyRotator."""

from llm_daily_budget import AllKeysRpdDisabledError, DailyBudgetBlockedError
from llm_model_circuits import (
    ModelCircuitOpenError,
    is_shared_model_circuit_open,
    open_shared_model_circuit,
    shared_model_circuit_wait,
)
from llm_provider_routes import provider_for_model


class KeyAvailabilityMixin:
    def _rpd_disabled_wait(self, key: str, model: str) -> float:
        limiter = self._shared_limiter if self._shared_limiter and self._shared_limiter.enabled else self._local_rpd_limiter
        if not hasattr(limiter, "rpd_disabled_wait"):
            return 0.0
        return float(limiter.rpd_disabled_wait(key, model) or 0.0)

    def _available_candidate_key_positions(self, model: str, request_units: int = 1) -> tuple[str, list[str], list[tuple[int, str]]]:
        circuit_wait = self.model_circuit_wait(model)
        if circuit_wait > 0:
            raise ModelCircuitOpenError(model, circuit_wait)
        provider, keys, candidates = self._candidate_key_positions(model)
        remaining = {} if self._provider_quota_authoritative() else self._daily_remaining(model)
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

    def provider_quota_exhausted(self, model: str) -> bool:
        _, keys = self._keys_for_model(model)
        return bool(keys) and all(self._rpd_disabled_wait(key, model) > 0 for key in keys)

    def eligible_key_slots(self, model: str) -> set[int]:
        """Return anonymous ledger slots eligible for this provider/model."""
        _, keys = self._keys_for_model(model)
        try:
            remaining = {} if self._provider_quota_authoritative() else self._daily_remaining(model)
        except DailyBudgetBlockedError:
            return set()
        return {self.keys.index(key) + 1 for key in keys
                if self._rpd_disabled_wait(key, model) <= 0 and remaining.get(key, 1) > 0}

    def model_circuit_wait(self, model: str) -> float:
        return max(self._model_circuits.wait(model), shared_model_circuit_wait(self._shared_limiter, model))

    def model_retry_wait(self, model: str) -> float:
        _, keys = self._keys_for_model(model)
        try:
            remaining = {} if self._provider_quota_authoritative() else self._daily_remaining(model)
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
