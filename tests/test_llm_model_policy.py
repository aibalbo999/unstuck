import sys
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agent_runtime.model_policy import (  # noqa: E402
    is_model_circuit_open,
    model_attempt_policy,
    record_model_failure,
    should_stop_retry,
    timeout_for_model_call,
)
from agent_runtime.retry_policy import AgentRateLimitError, AgentTransientError  # noqa: E402


def _retry_state(attempt, exc):
    return SimpleNamespace(attempt_number=attempt, outcome=SimpleNamespace(exception=lambda: exc))


def test_primary_policy_uses_short_timeout_and_fast_transient_fallback():
    policy = model_attempt_policy(model_index=0, has_fallback=True, max_retries=3, key_count=6)

    assert timeout_for_model_call(model_index=0, has_fallback=True) == 1.0
    assert timeout_for_model_call(model_index=1, has_fallback=False) == 120.0
    assert should_stop_retry(_retry_state(1, AgentTransientError("500 INTERNAL")), policy) is True
    assert should_stop_retry(_retry_state(1, AgentRateLimitError("429", 1, 60)), policy) is False
    assert should_stop_retry(_retry_state(2, AgentRateLimitError("429", 1, 60)), policy) is True


def test_model_circuit_opens_after_repeated_failures():
    context = {}

    first = record_model_failure(context, "gemma-4-31b-it", AgentTransientError("timeout"))
    second = record_model_failure(context, "gemma-4-31b-it", AgentTransientError("500"))

    assert first["failures"] == 1
    assert second["failures"] == 2
    assert second["opened_until"] > time.time()
    assert is_model_circuit_open(context, "gemma-4-31b-it") is True
