import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import llm_rate_limits  # noqa: E402
import provider_resilience  # noqa: E402
from shared_runtime_guards import RedisFixedWindowRateLimiter  # noqa: E402


def test_redis_llm_limiter_hashes_secret_keys():
    class FakeRedis:
        def __init__(self):
            self.eval_args = None

        def eval(self, *args):
            self.eval_args = args
            return 0

    redis_client = FakeRedis()
    limiter = RedisFixedWindowRateLimiter(redis_client, namespace="test")

    wait = limiter.reserve("super-secret-api-key", "gemini-test", rpm_limit=5, tpm_limit=100, estimated_tokens=7)

    assert wait == 0
    keys = redis_client.eval_args[2:5]
    assert all("super-secret-api-key" not in key for key in keys)
    assert all("gemini-test" not in key for key in keys)


def test_key_rotator_reserves_shared_budget(monkeypatch):
    class FakeLimiter:
        enabled = True

        def __init__(self):
            self.calls = []
            self.penalties = []

        def reserve(self, key, model, **kwargs):
            self.calls.append((key, model, kwargs))
            return 0

        def penalize(self, key, model, wait_seconds):
            self.penalties.append((key, model, wait_seconds))

    limiter = FakeLimiter()
    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: limiter)

    rotator = llm_rate_limits.KeyRotator(["key-one"])
    assert rotator.get_key("gemini-test", estimated_tokens=12) == "key-one"
    rotator.penalize("key-one", "gemini-test", 9)

    assert limiter.calls[0][1] == "gemini-test"
    assert limiter.calls[0][2]["estimated_tokens"] == 12
    assert limiter.penalties == [("key-one", "gemini-test", 9)]


def test_key_rotator_uses_provider_specific_keys(monkeypatch):
    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: None)
    rotator = llm_rate_limits.KeyRotator({
        "google": ["google-key"],
        "openai": ["openai-key"],
        "anthropic": ["anthropic-key"],
    })

    assert rotator.get_key("openai:gpt-4.1-mini") == "openai-key"
    assert rotator.get_key("anthropic:claude-4-sonnet") == "anthropic-key"
    assert rotator.get_key("gemini-3.5-flash") == "google-key"


def test_provider_resilience_uses_shared_circuit_store(monkeypatch):
    class FakeStore:
        enabled = True

        def __init__(self):
            self.open = False
            self.failures = []

        def state(self, provider):
            return {
                "open": self.open,
                "failures": len(self.failures),
                "opened_until": 9999999999.0 if self.open else 0.0,
                "last_error": self.failures[-1] if self.failures else "",
            }

        def record_success(self, provider):
            self.failures.clear()
            self.open = False

        def record_failure(self, provider, error, threshold, cooldown_seconds):
            self.failures.append(error)
            if len(self.failures) >= threshold:
                self.open = True

        def clear(self, provider=None):
            self.failures.clear()
            self.open = False

    store = FakeStore()
    monkeypatch.setattr(provider_resilience, "_SHARED_CIRCUIT_STORE", store)
    monkeypatch.setenv("PROVIDER_CIRCUIT_BREAKER_THRESHOLD", "1")

    with pytest.raises(ValueError):
        provider_resilience.call_provider_with_resilience("provider-x", lambda: (_ for _ in ()).throw(ValueError("boom")))
    with pytest.raises(provider_resilience.ProviderCircuitOpenError):
        provider_resilience.call_provider_with_resilience("provider-x", lambda: "ok")
