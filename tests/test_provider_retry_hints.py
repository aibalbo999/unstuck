"""Provider retry hints cool only the rejected key/model; unknown 429 is not RPD."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from agent_runtime.retry_error_classification import provider_status_code
from agent_runtime.retry_policy import AgentRateLimitError, _raise_agent_call_error
from llm_errors import extract_quota_details, is_requests_per_day_error, retry_delay_seconds


class ProviderError(RuntimeError):
    code = 429

    def __init__(self, *, headers=None, delay=None):
        super().__init__('429 RESOURCE_EXHAUSTED')
        self.response = SimpleNamespace(headers=headers or {})
        self.details = [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': delay}] if delay else []


class Rotator:
    keys = ['key-a', 'key-b']

    def __init__(self):
        self.penalties = []
        self.disabled = []

    def penalize(self, *args):
        self.penalties.append(args)

    def disable_rpd_until_reset(self, *args):
        self.disabled.append(args)
        return 43200


@pytest.mark.parametrize(('headers', 'delay', 'expected'), [
    ({'Retry-After': '75'}, None, 75),
    ({'retry-after': '90'}, '28s', 90),
    ({'Retry-After': '15'}, '28s', 28),
    ({'Retry-After': '10'}, '90.123456789s', 90.123456789),
    ({'Retry-After': '0'}, None, 0),
    ({'Retry-After': '1.5'}, None, 1.5),
])
def test_maximum_provider_hint_controls_rejected_key_cooldown(headers, delay, expected):
    error = ProviderError(headers=headers, delay=delay)
    assert retry_delay_seconds(error, default=60) == expected
    assert extract_quota_details(error)['retry_delay_seconds'] == expected
    rotator = Rotator()
    with pytest.raises(AgentRateLimitError) as caught:
        _raise_agent_call_error(error, 'key-a', 'model', rotator, 1)
    assert rotator.penalties == [('key-a', 'model', expected)]
    assert caught.value.retry_wait_seconds == 1  # Healthy keys are still available.
    assert rotator.disabled == []


def test_http_date_retry_after(monkeypatch):
    import llm_quota_details
    monkeypatch.setattr(llm_quota_details.time, 'time', lambda: datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc).timestamp())
    error = ProviderError(headers={'Retry-After': 'Sat, 19 Sep 2026 15:01:30 GMT'})
    assert retry_delay_seconds(error) == 90


@pytest.mark.parametrize('value', ['-1', 'nan', 'inf', 'malformed', '', '1e500'])
def test_invalid_header_uses_conservative_unknown_cooldown(value):
    error = ProviderError(headers={'Retry-After': value})
    assert retry_delay_seconds(error, default=60) == 60
    rotator = Rotator()
    with pytest.raises(AgentRateLimitError) as caught:
        _raise_agent_call_error(error, 'key-a', 'model', rotator, 1)
    assert caught.value.key_cooldown_seconds == 60
    assert rotator.disabled == []


def test_unknown_429_keeps_http_status_and_unknown_reason_without_rpd():
    error = ProviderError()
    rotator = Rotator()
    with pytest.raises(AgentRateLimitError) as caught:
        _raise_agent_call_error(error, 'key-a', 'model', rotator, 1)
    wrapped = caught.value
    assert wrapped.key_cooldown_seconds == 60
    assert wrapped.retry_wait_seconds == 1
    assert wrapped.reason_code == 'provider_quota_or_rate_unknown'
    assert provider_status_code(wrapped) == 429
    assert wrapped.__cause__ is error
    assert is_requests_per_day_error(error) is False
    assert rotator.disabled == []
    assert wrapped.all_keys_exhausted is False


def test_single_key_waits_full_unknown_cooldown():
    rotator = Rotator()
    rotator.keys = ['key-a']
    with pytest.raises(AgentRateLimitError) as caught:
        _raise_agent_call_error(ProviderError(), 'key-a', 'model', rotator, 1)
    assert caught.value.retry_wait_seconds == 60


def test_unknown_429_stops_after_four_keys_without_claiming_all_sixteen_exhausted(monkeypatch):
    from agent_runtime import model_policy
    monkeypatch.setattr(model_policy, 'LLM_QUOTA_MAX_ATTEMPTS_PER_MODEL', 4)
    policy = model_policy.model_attempt_policy(0, True, 3, 16)
    stop = model_policy.make_model_retry_stop(policy, eligible_key_slots=lambda: set(range(1, 17)))
    rotator = Rotator()
    rotator.keys = [f'key-{i}' for i in range(16)]
    for attempt in range(1, 5):
        with pytest.raises(AgentRateLimitError) as caught:
            _raise_agent_call_error(ProviderError(), rotator.keys[attempt - 1], 'model', rotator, 1)
        error = caught.value
        state = SimpleNamespace(attempt_number=attempt, outcome=SimpleNamespace(exception=lambda: error))
        assert stop(state) is (attempt == 4)
        assert error.all_keys_exhausted is False
    assert rotator.disabled == []


def test_wrapped_unknown_429_remains_quota_in_events():
    from agent_runtime.retry_error_classification import _agent_error_category
    from agent_runtime.retry_policy import _key_error_metadata
    with pytest.raises(AgentRateLimitError) as caught:
        _raise_agent_call_error(ProviderError(), 'key-a', 'model', Rotator(), 1)
    assert _agent_error_category(caught.value) == 'quota'
    assert _key_error_metadata(caught.value)['provider_status_code'] == 429
    assert _key_error_metadata(caught.value)['reason_code'] == 'provider_quota_or_rate_unknown'


def test_unknown_429_real_rotator_shares_only_affected_pair_cooldown(monkeypatch):
    from llm_rate_limits import KeyRotator
    from shared_runtime_local_guards import LocalFixedWindowRateLimiter
    shared = LocalFixedWindowRateLimiter()
    clock = [1000.0]
    monkeypatch.setattr('shared_runtime_local_guards.time.time', lambda: clock[0])
    monkeypatch.setattr('llm_rate_limits.create_shared_llm_limiter', lambda: shared)
    rotator = KeyRotator(['key-a', 'key-b'])
    with pytest.raises(AgentRateLimitError):
        _raise_agent_call_error(ProviderError(), 'key-a', 'model', rotator, 1)
    peer = KeyRotator(['key-a', 'key-b'])
    assert peer._shared_limiter.reserve('key-a', 'model', rpm_limit=100) == 60
    assert peer._shared_limiter.reserve('key-b', 'model', rpm_limit=100) == 0
    assert peer._shared_limiter.reserve('key-a', 'other-model', rpm_limit=100) == 0
    assert peer._shared_limiter.rpd_disabled_wait('key-a', 'model') == 0
    clock[0] += 61
    assert peer._shared_limiter.reserve('key-a', 'model', rpm_limit=100) == 0
