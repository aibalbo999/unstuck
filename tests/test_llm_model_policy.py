import sys
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agent_runtime.model_policy import (  # noqa: E402
    is_model_circuit_open,
    make_model_retry_stop,
    model_attempt_policy,
    record_model_failure,
    should_stop_retry,
    timeout_for_model_call,
)
from agent_runtime.retry_policy import (  # noqa: E402
    AgentAuthError,
    AgentConfigurationError,
    AgentRateLimitError,
    AgentServerError,
    AgentTransientError,
    _agent_error_category,
    _raise_agent_call_error,
)
from llm_rate_limits import AllKeysRpdDisabledError  # noqa: E402
from settings.models import is_large_context_model  # noqa: E402


def _retry_state(attempt, exc):
    return SimpleNamespace(attempt_number=attempt, outcome=SimpleNamespace(exception=lambda: exc))


def test_primary_policy_uses_configured_timeout_and_fast_transient_fallback():
    policy = model_attempt_policy(model_index=0, has_fallback=True, max_retries=3, key_count=6)

    assert timeout_for_model_call(model_index=0, has_fallback=True) == 360.0
    assert timeout_for_model_call(model_index=1, has_fallback=False) == 120.0
    assert should_stop_retry(_retry_state(1, AgentTransientError("LLM timeout after 360.0s")), policy) is True
    assert should_stop_retry(_retry_state(1, AgentRateLimitError("429", 1, 60)), policy) is False
    assert should_stop_retry(_retry_state(2, AgentRateLimitError("429", 1, 60)), policy) is False
    assert should_stop_retry(_retry_state(6, AgentRateLimitError("429", 1, 60)), policy) is True


def test_quota_policy_exhausts_all_keys_before_model_fails():
    primary_policy = model_attempt_policy(model_index=0, has_fallback=True, max_retries=3, key_count=8)
    fallback_policy = model_attempt_policy(model_index=1, has_fallback=False, max_retries=3, key_count=8)

    assert primary_policy.quota_attempts == 8
    assert fallback_policy.quota_attempts == 8
    assert should_stop_retry(_retry_state(7, AgentRateLimitError("429", 1, 60)), primary_policy) is False
    assert should_stop_retry(_retry_state(8, AgentRateLimitError("429", 1, 60)), primary_policy) is True


def test_stateful_retry_stop_does_not_let_5xx_consume_quota_key_budget():
    policy = model_attempt_policy(model_index=1, has_fallback=False, max_retries=3, key_count=6)
    stop = make_model_retry_stop(policy)

    assert stop(_retry_state(1, AgentServerError("503 UNAVAILABLE"))) is False
    for attempt, key_slot in enumerate([1, 2, 3, 4, 5], start=2):
        assert stop(_retry_state(attempt, AgentRateLimitError("429", 1, 60, key_slot=key_slot, key_count=6))) is False
    assert stop(_retry_state(7, AgentRateLimitError("429", 1, 60, key_slot=6, key_count=6))) is True


def test_stateful_retry_stop_keeps_trying_when_quota_slots_repeat():
    policy = model_attempt_policy(model_index=1, has_fallback=False, max_retries=3, key_count=6)
    stop = make_model_retry_stop(policy)

    for attempt, key_slot in enumerate([1, 2, 3, 4, 5, 1], start=1):
        assert stop(_retry_state(attempt, AgentRateLimitError("429", 1, 60, key_slot=key_slot, key_count=6))) is False
    assert stop(_retry_state(7, AgentRateLimitError("429", 1, 60, key_slot=6, key_count=6))) is True


def test_server_5xx_policy_keeps_retrying_longer_than_primary_timeout():
    policy = model_attempt_policy(model_index=0, has_fallback=True, max_retries=3, key_count=6)

    assert should_stop_retry(_retry_state(1, AgentServerError("503 UNAVAILABLE")), policy) is False
    assert should_stop_retry(_retry_state(5, AgentServerError("500 INTERNAL")), policy) is False
    assert should_stop_retry(_retry_state(6, AgentServerError("500 INTERNAL")), policy) is True


def test_503_is_classified_as_server_error_not_plain_transient():
    class FakeRotator:
        keys = ["k1"]

        def penalize(self, *_args, **_kwargs):
            raise AssertionError("5xx should not penalize API key as quota")

    try:
        _raise_agent_call_error(RuntimeError("503 UNAVAILABLE high demand"), None, "model", FakeRotator(), 1)
    except AgentServerError:
        pass
    else:
        raise AssertionError("503 should become AgentServerError")

    assert _agent_error_category(RuntimeError("503 UNAVAILABLE high demand")) == "server_5xx"


def test_rate_limit_error_records_key_slot_metadata():
    class FakeRotator:
        keys = ["key-a", "key-b", "key-c"]

        def penalize(self, *_args, **_kwargs):
            pass

    try:
        _raise_agent_call_error(RuntimeError("429 RESOURCE_EXHAUSTED"), "key-b", "model", FakeRotator(), 1)
    except AgentRateLimitError as exc:
        assert exc.key_slot == 2
        assert exc.key_count == 3
    else:
        raise AssertionError("429 should become AgentRateLimitError")


def test_rpd_429_disables_key_model_until_reset():
    class FakeRpdError(RuntimeError):
        details = [
            {
                "violations": [
                    {
                        "quotaMetric": "generativelanguage.googleapis.com/generate_content_requests_per_day",
                        "quotaDimensions": {"model": "gemini-2.5-flash"},
                    }
                ]
            }
        ]

    class FakeRotator:
        keys = ["key-a", "key-b"]

        def __init__(self):
            self.disabled = []
            self.penalties = []

        def disable_rpd_until_reset(self, key, model):
            self.disabled.append((key, model))
            return 43200

        def penalize(self, key, model, wait_seconds):
            self.penalties.append((key, model, wait_seconds))

    rotator = FakeRotator()

    try:
        _raise_agent_call_error(FakeRpdError("429 RESOURCE_EXHAUSTED"), "key-b", "gemini-2.5-flash", rotator, 1)
    except AgentRateLimitError as exc:
        assert exc.key_slot == 2
        assert exc.key_count == 2
        assert exc.key_cooldown_seconds == 43200
    else:
        raise AssertionError("RPD 429 should become AgentRateLimitError")

    assert rotator.disabled == [("key-b", "gemini-2.5-flash")]
    assert rotator.penalties == []


def test_non_rpd_429_keeps_short_key_penalty():
    class FakeRotator:
        keys = ["key-a", "key-b"]

        def __init__(self):
            self.disabled = []
            self.penalties = []

        def disable_rpd_until_reset(self, key, model):
            self.disabled.append((key, model))
            return 43200

        def penalize(self, key, model, wait_seconds):
            self.penalties.append((key, model, wait_seconds))

    rotator = FakeRotator()

    try:
        _raise_agent_call_error(RuntimeError("429 RESOURCE_EXHAUSTED RequestsPerMinute"), "key-b", "gemini-2.5-flash", rotator, 7)
    except AgentRateLimitError as exc:
        assert exc.key_cooldown_seconds == 7
    else:
        raise AssertionError("429 should become AgentRateLimitError")

    assert rotator.disabled == []
    assert rotator.penalties == [("key-b", "gemini-2.5-flash", 7)]


def test_all_keys_rpd_disabled_is_classified_as_rate_limit():
    class FakeRotator:
        keys = ["key-a", "key-b"]

    error = AllKeysRpdDisabledError("gemini-2.5-flash", 1800)

    try:
        _raise_agent_call_error(error, None, "gemini-2.5-flash", FakeRotator(), 1)
    except AgentRateLimitError as exc:
        assert exc.retry_wait_seconds == 1800
        assert exc.key_cooldown_seconds == 1800
        assert exc.key_slot is None
        assert exc.key_count == 2
    else:
        raise AssertionError("all-disabled RPD should become AgentRateLimitError")

    assert _agent_error_category(error) == "quota"


def test_auth_error_is_classified_separately_from_quota_and_records_key_slot():
    class FakeRotator:
        keys = ["key-a", "key-b", "key-c"]

        def penalize(self, *_args, **_kwargs):
            pass

    error = RuntimeError(
        "google.genai.models.generate_content failed: 401 UNAUTHENTICATED. "
        "The bound service account is deleted or disabled. "
        "The service account bound to the API key must be active."
    )
    try:
        _raise_agent_call_error(error, "key-b", "gemini-2.5-flash", FakeRotator(), 1)
    except AgentAuthError as exc:
        assert exc.key_slot == 2
        assert exc.key_count == 3
    else:
        raise AssertionError("401 service-account errors should become AgentAuthError")

    assert _agent_error_category(error) == "auth"


def test_auth_retry_stop_exhausts_all_keys_before_model_fails():
    policy = model_attempt_policy(model_index=1, has_fallback=False, max_retries=3, key_count=3)
    stop = make_model_retry_stop(policy)

    for attempt, key_slot in enumerate([1, 2], start=1):
        assert stop(_retry_state(attempt, AgentAuthError("401", 1, key_slot=key_slot, key_count=3))) is False
    assert stop(_retry_state(3, AgentAuthError("401", 1, key_slot=3, key_count=3))) is True


def test_invalid_argument_config_error_is_not_reported_as_missing_model():
    class FakeRotator:
        keys = ["key-a"]

        def penalize(self, *_args, **_kwargs):
            raise AssertionError("schema/config errors should not penalize API keys")

    error = RuntimeError(
        "400 INVALID_ARGUMENT. Function calling with a response mime type: "
        "'application/json' is unsupported."
    )
    try:
        _raise_agent_call_error(error, "key-a", "gemini-2.5-flash", FakeRotator(), 1)
    except AgentConfigurationError as exc:
        assert "[schema_error]" in str(exc)
    else:
        raise AssertionError("400 INVALID_ARGUMENT should become AgentConfigurationError")

    assert _agent_error_category(error) == "schema_error"


def test_model_circuit_opens_after_repeated_failures():
    context = {}

    first = record_model_failure(context, "gemma-4-31b-it", AgentTransientError("timeout"))
    second = record_model_failure(context, "gemma-4-31b-it", AgentTransientError("500"))

    assert first["failures"] == 1
    assert second["failures"] == 2
    assert second["opened_until"] > time.time()
    assert is_model_circuit_open(context, "gemma-4-31b-it") is True


def test_gemma_receives_large_context_budget_by_default():
    assert is_large_context_model("gemma-4-31b-it") is True
    assert is_large_context_model("gemini-3.5-flash") is True
