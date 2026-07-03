import asyncio
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import source_audit  # noqa: E402
import provider_resilience  # noqa: E402
import cache_store  # noqa: E402
from data_trust import (  # noqa: E402
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
)
from data_fetch.market_sources.common import _run_named_fetches  # noqa: E402


def test_audited_fetch_records_success_error_and_unavailable():
    provider_resilience.clear_provider_circuits()
    success = source_audit.audited_fetch(
        "recent_catalysts",
        "fake provider",
        lambda: [{"title": "A"}, {"title": "B"}],
        default=[],
    )
    assert success["value"] == [{"title": "A"}, {"title": "B"}]
    assert success["audit"]["status"] == AUDIT_STATUS_SUCCESS
    assert success["audit"]["provider"] == "fake provider"
    assert success["audit"]["record_count"] == 2
    assert success["audit"]["duration_ms"] >= 0

    unavailable = source_audit.audited_fetch(
        "peer_discovery",
        "fake provider",
        lambda: [],
        default=[],
    )
    assert unavailable["value"] == []
    assert unavailable["audit"]["status"] == AUDIT_STATUS_UNAVAILABLE
    assert unavailable["audit"]["record_count"] == 0

    def boom():
        raise RuntimeError("provider exploded")

    failed = source_audit.audited_fetch(
        "market_data",
        "fake provider",
        boom,
        default={"fallback": True},
    )
    assert failed["value"] == {"fallback": True}
    assert failed["audit"]["status"] == AUDIT_STATUS_ERROR
    assert failed["audit"]["error_kind"] == "RuntimeError"
    assert "provider exploded" in failed["audit"]["message"]


def test_audited_fetch_async_records_cache_hit():
    provider_resilience.clear_provider_circuits()
    async def fake_async():
        return ["cached headline"]

    result = asyncio.run(
        source_audit.audited_fetch_async(
            "recent_catalysts",
            "async fake",
            fake_async,
            default=[],
            cache_hit=True,
        )
    )

    assert result["value"] == ["cached headline"]
    assert result["audit"]["status"] == AUDIT_STATUS_SUCCESS
    assert result["audit"]["cache_hit"] is True


def test_run_named_fetches_include_audit_preserves_old_mode():
    def boom():
        raise ValueError("bad source")

    fetches = {
        "ok": (lambda: [1, 2], (), [], "ok warning", "recent_catalysts", "fake ok"),
        "empty": (lambda: [], (), [], "empty warning", "peer_discovery", "fake empty"),
        "boom": (boom, (), [], "boom warning", "market_data", "fake boom"),
    }

    audited = _run_named_fetches(fetches, max_workers=2, include_audit=True)
    assert audited["values"]["ok"] == [1, 2]
    assert audited["values"]["empty"] == []
    assert audited["values"]["boom"] == []

    statuses = {entry["provider"]: entry["status"] for entry in audited["audit"]}
    assert statuses["fake ok"] == AUDIT_STATUS_SUCCESS
    assert statuses["fake empty"] == AUDIT_STATUS_UNAVAILABLE
    assert statuses["fake boom"] == AUDIT_STATUS_ERROR

    legacy = _run_named_fetches({"ok": (lambda: [1], (), [], "legacy warning")}, max_workers=1)
    assert legacy == {"ok": [1]}


def test_provider_resilience_retries_and_opens_circuit(monkeypatch):
    provider_resilience.clear_provider_circuits()
    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("PROVIDER_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("PROVIDER_RETRY_JITTER_SECONDS", "0")
    monkeypatch.setenv("PROVIDER_CIRCUIT_BREAKER_THRESHOLD", "1")
    monkeypatch.setenv("PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "60")
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        raise RuntimeError("down")

    failed = source_audit.audited_fetch("market_data", "retry-provider", flaky, default={})
    assert calls["count"] == 2
    assert failed["audit"]["status"] == AUDIT_STATUS_ERROR
    assert provider_resilience.provider_circuit_state("retry-provider")["open"] is True
    skipped = source_audit.audited_fetch("market_data", "retry-provider", lambda: {"ok": True}, default={})
    assert skipped["audit"]["status"] == AUDIT_STATUS_UNAVAILABLE
    assert skipped["audit"]["error_kind"] == "ProviderCircuitOpenError"
    provider_resilience.clear_provider_circuits()


def test_provider_resilience_enforces_min_interval_between_provider_calls(monkeypatch):
    provider_resilience.clear_provider_circuits()
    provider_resilience.clear_provider_throttles()
    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("PROVIDER_RATE_LIMIT_MIN_INTERVAL_SECONDS", "2")
    now = {"value": 1_000.0}
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        now["value"] += seconds

    monkeypatch.setattr(provider_resilience.time, "time", lambda: now["value"])
    monkeypatch.setattr(provider_resilience.time, "sleep", fake_sleep)

    assert provider_resilience.call_provider_with_resilience("paced-provider", lambda: "first") == "first"
    now["value"] += 0.25
    assert provider_resilience.call_provider_with_resilience("paced-provider", lambda: "second") == "second"

    assert sleeps == [1.75]
    provider_resilience.clear_provider_throttles()
    provider_resilience.clear_provider_circuits()


def test_provider_resilience_cools_down_after_http_rate_limit(monkeypatch):
    provider_resilience.clear_provider_circuits()
    provider_resilience.clear_provider_throttles()
    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS", "30")
    now = {"value": 1_000.0}
    calls = {"count": 0}

    class FakeResponse:
        status_code = 429

    class FakeHTTPStatusError(RuntimeError):
        response = FakeResponse()

    def restricted():
        calls["count"] += 1
        raise FakeHTTPStatusError("429 Too Many Requests")

    monkeypatch.setattr(provider_resilience.time, "time", lambda: now["value"])

    with pytest.raises(FakeHTTPStatusError):
        provider_resilience.call_provider_with_resilience("rate-limited-provider", restricted)

    state = provider_resilience.provider_throttle_state("rate-limited-provider")
    assert state["cooldown_until"] == 1_030.0

    with pytest.raises(provider_resilience.ProviderRateLimitOpenError):
        provider_resilience.call_provider_with_resilience("rate-limited-provider", lambda: "skipped")
    assert calls["count"] == 1

    now["value"] += 31.0
    assert provider_resilience.call_provider_with_resilience("rate-limited-provider", lambda: "ok") == "ok"
    provider_resilience.clear_provider_throttles()
    provider_resilience.clear_provider_circuits()


def test_audited_fetch_treats_provider_rate_limit_cooldown_as_unavailable(monkeypatch):
    provider_resilience.clear_provider_circuits()
    provider_resilience.clear_provider_throttles()
    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS", "30")

    class FakeResponse:
        status_code = 429

    class FakeHTTPStatusError(RuntimeError):
        response = FakeResponse()

    first = source_audit.audited_fetch(
        "recent_catalysts",
        "cooldown-provider",
        lambda: (_ for _ in ()).throw(FakeHTTPStatusError("429 Too Many Requests")),
        default=[],
    )
    second = source_audit.audited_fetch("recent_catalysts", "cooldown-provider", lambda: ["late"], default=[])

    assert first["audit"]["status"] == AUDIT_STATUS_ERROR
    assert second["audit"]["status"] == AUDIT_STATUS_UNAVAILABLE
    assert second["audit"]["error_kind"] == "ProviderRateLimitOpenError"
    provider_resilience.clear_provider_throttles()
    provider_resilience.clear_provider_circuits()


def test_provider_rate_limit_provider_specific_env_override(monkeypatch):
    provider_resilience.clear_provider_throttles()
    monkeypatch.setenv("PROVIDER_RATE_LIMIT_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("PROVIDER_RATE_LIMIT_YFINANCE_MIN_INTERVAL_SECONDS", "2.5")

    state = provider_resilience.provider_throttle_state("yfinance")

    assert state["min_interval_seconds"] == 2.5
    provider_resilience.clear_provider_throttles()


def test_provider_rate_limit_configuration_is_documented():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    operator_guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")

    assert "PROVIDER_RATE_LIMIT_MIN_INTERVAL_SECONDS" in readme
    assert "PROVIDER_RATE_LIMIT_YFINANCE_MIN_INTERVAL_SECONDS" in readme
    assert "PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS" in operator_guide


def test_circuit_snapshot_is_pure_and_does_not_transition_expired_open_state(monkeypatch):
    breaker = provider_resilience.CircuitBreaker(failure_threshold=1, recovery_timeout=60)
    monkeypatch.setattr(provider_resilience.time, "time", lambda: 1_000.0)

    breaker.record_failure("rate limited")
    monkeypatch.setattr(provider_resilience.time, "time", lambda: 1_061.0)

    snapshot = breaker.snapshot()

    assert snapshot["open"] is True
    assert snapshot["state"] == "OPEN"
    assert breaker.state == "OPEN"


def test_provider_resilience_persists_open_circuit_to_sqlite_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_store, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    cache_store.reset_cache_store_for_tests()
    monkeypatch.setattr(provider_resilience, "_SHARED_CIRCUIT_STORE", None)
    monkeypatch.setenv("PROVIDER_CIRCUIT_BREAKER_THRESHOLD", "1")
    monkeypatch.setenv("PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "60")
    provider_resilience.clear_provider_circuits("sqlite-provider")

    with pytest.raises(ValueError):
        provider_resilience.call_provider_with_resilience(
            "sqlite-provider",
            lambda: (_ for _ in ()).throw(ValueError("boom")),
        )

    provider_resilience._CIRCUITS.clear()

    with pytest.raises(provider_resilience.ProviderCircuitOpenError):
        provider_resilience.call_provider_with_resilience("sqlite-provider", lambda: "ok")


def test_yfinance_timeout_and_403_open_circuit_after_three_failures(monkeypatch):
    provider_resilience.clear_provider_circuits()
    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("PROVIDER_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("PROVIDER_RETRY_JITTER_SECONDS", "0")
    monkeypatch.setenv("PROVIDER_CIRCUIT_BREAKER_THRESHOLD", "3")
    monkeypatch.setenv("PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "60")

    def blocked():
        raise TimeoutError("yfinance timeout and HTTP 403 blocked")

    for _ in range(3):
        result = source_audit.audited_fetch("market_data", "yfinance", blocked, default={})
        assert result["audit"]["status"] == AUDIT_STATUS_ERROR

    state = provider_resilience.provider_circuit_state("yfinance")
    assert state["open"] is True
    assert state["failures"] == 3
    assert "timeout" in state["last_error"].lower()

    skipped = source_audit.audited_fetch("market_data", "yfinance", lambda: {"ok": True}, default={})
    assert skipped["audit"]["status"] == AUDIT_STATUS_UNAVAILABLE
    assert skipped["audit"]["error_kind"] == "ProviderCircuitOpenError"
    provider_resilience.clear_provider_circuits()
