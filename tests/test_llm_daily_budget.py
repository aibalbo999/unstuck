import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone

import pytest

from llm_daily_budget import DailyBudgetStore, DailyBudgetBlockedError


NOW = datetime(2026, 9, 5, 18, tzinfo=timezone.utc).timestamp()
STORES = []


@pytest.fixture(autouse=True)
def close_test_budget_connections():
    yield
    for store in STORES:
        store.close_current_thread()
    STORES.clear()


def store_at(path, now=NOW):
    store = DailyBudgetStore(path_getter=lambda: path, clock=lambda: now)
    STORES.append(store)
    return store


def test_default_budget_stores_share_path_aware_connection_resource():
    assert DailyBudgetStore()._resource is DailyBudgetStore()._resource


def test_budget_persists_and_is_scoped_to_key_model(tmp_path):
    path = tmp_path / 'budget.sqlite3'
    store = store_at(path)
    assert store.reserve('secret-a', 'flash', 1, ['secret-a', 'secret-b'])
    assert not store_at(path).reserve('secret-a', 'flash', 1, ['secret-a', 'secret-b'])
    assert store.reserve('secret-b', 'flash', 1, ['secret-a', 'secret-b'])
    assert store.reserve('secret-a', 'lite', 1, ['secret-a', 'secret-b'])
    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute('SELECT * FROM llm_daily_budgets').fetchall()
    assert 'secret-' not in repr(rows)


def test_atomic_budget_across_independent_connections(tmp_path):
    path = tmp_path / 'budget.sqlite3'
    store_at(path).remaining(['a'], 'm', 7)
    def reserve(_):
        store = store_at(path)
        try:
            return store.reserve('a', 'm', 7, ['a'])
        finally:
            store.close_current_thread()
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(30))) == 7


def test_tool_loop_reserves_its_maximum_request_count_atomically(tmp_path):
    store = store_at(tmp_path / 'budget.sqlite3')
    assert store.reserve('a', 'm', 16, ['a'], request_units=6)
    assert store.reserve('a', 'm', 16, ['a'], request_units=6)
    assert not store.reserve('a', 'm', 16, ['a'], request_units=6)
    assert store.remaining(['a'], 'm', 16) == {'a': 4}


def test_rotator_chooses_project_that_fits_entire_tool_loop(rotator, monkeypatch):
    monkeypatch.setattr('llm_rate_limits.RPD_LIMITS', {'m': 6})
    assert rotator._daily_budget.reserve('a', 'm', 6, ['a', 'b'])
    assert rotator.get_key('m', request_units=6) == 'b'
    with pytest.raises(DailyBudgetBlockedError):
        rotator.get_key('m', request_units=6)


@pytest.mark.parametrize('before,after', [
    ('2026-09-06T06:59:59+00:00', '2026-09-06T07:00:00+00:00'),
    ('2026-12-06T07:59:59+00:00', '2026-12-06T08:00:00+00:00'),
])
def test_pacific_midnight_resets_with_dst(tmp_path, before, after):
    path = tmp_path / 'budget.sqlite3'
    assert store_at(path, datetime.fromisoformat(before).timestamp()).reserve('a', 'm', 1, ['a'])
    assert store_at(path, datetime.fromisoformat(after).timestamp()).reserve('a', 'm', 1, ['a'])


def test_seed_request_events_once_including_diagnostics_not_results_or_local_blocks(tmp_path):
    path = tmp_path / 'budget.sqlite3'
    import api_usage_store
    conn = api_usage_store._connect_for_path(path)
    rows = [('llm_provider_request', {'key_slot': 1}),
            ('llm_model_response', {'key_slot': 1}),
            ('llm_model_error', {'error_kind': 'InputCapacityExceededError'}),
            ('llm_provider_request', {}),
            ('diagnostic_model_smoke', {'key_slot': 1}),
            ('diagnostic_model_smoke_result', {'key_slot': 1}),
            ('diagnostic_count_tokens', {'key_slot': 1})]
    with conn:
        for operation, metadata in rows:
            conn.execute('INSERT INTO api_usage_events(service,provider,operation,model_id,status,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)',
                         ('gemini', 'google', operation, 'm', 'success', json.dumps(metadata), NOW - 1))
    conn.close()
    store = store_at(path)
    assert store.remaining(['a', 'b'], 'm', 4) == {'a': 1, 'b': 3}
    assert store.reserve('a', 'm', 4, ['a', 'b'])
    assert store_at(path).remaining(['a', 'b'], 'm', 4) == {'a': 0, 'b': 3}


def test_unavailable_database_fails_closed_without_leaking_path(tmp_path):
    store = store_at(tmp_path)
    with pytest.raises(DailyBudgetBlockedError) as error:
        store.remaining(['secret'], 'm', 2)
    assert error.value.reason == 'budget_store_unavailable'
    assert 'secret' not in str(error.value)
    assert str(tmp_path) not in str(error.value)


@pytest.fixture
def rotator(monkeypatch, tmp_path):
    import llm_rate_limits as limits
    monkeypatch.setattr(limits, 'RPD_LIMITS', {'m': 1})
    monkeypatch.setattr(limits, 'RPM_LIMITS', {'*': 1000})
    monkeypatch.setattr(limits, 'TPM_LIMITS', {})
    monkeypatch.setattr(limits, 'MODEL_INPUT_TOKEN_LIMITS', {})
    monkeypatch.setattr(limits, 'create_shared_llm_limiter', lambda: None)
    r = limits.KeyRotator(['a', 'b'])
    r._daily_budget = store_at(tmp_path / 'budget.sqlite3')
    return r


@pytest.mark.parametrize('async_mode', [False, True])
def test_rotator_blocks_after_each_project_budget_without_sleep(rotator, monkeypatch, async_mode):
    monkeypatch.setattr('llm_rate_limits.time.sleep', lambda _: pytest.fail('daily exhaustion must not sleep'))
    async def invoke():
        return await rotator.async_get_key('m', 10)
    get = (lambda: asyncio.run(invoke())) if async_mode else (lambda: rotator.get_key('m', 10))
    assert {get(), get()} == {'a', 'b'}
    with pytest.raises(DailyBudgetBlockedError):
        get()
    assert rotator.eligible_key_slots('m') == set()
    assert rotator.model_retry_wait('m') > 0


def test_minute_wait_does_not_consume_daily_budget(rotator, monkeypatch):
    waits = iter([1, 1, 0, 0])
    monkeypatch.setattr(rotator, '_wait_for_key', lambda *args: next(waits))
    monkeypatch.setattr('llm_rate_limits.time.sleep', lambda _: None)
    assert rotator.get_key('m') == 'a'
    assert rotator._daily_budget.remaining(['a', 'b'], 'm', 1) == {'a': 0, 'b': 1}


def test_capacity_rejection_never_reserves_daily_budget(rotator, monkeypatch):
    from llm_input_capacity import InputCapacityExceededError
    monkeypatch.setattr('llm_rate_limits.MODEL_INPUT_TOKEN_LIMITS', {'m': 5})
    with pytest.raises(InputCapacityExceededError):
        rotator.get_key('m', 6)
    assert rotator._daily_budget.remaining(['a', 'b'], 'm', 1) == {'a': 1, 'b': 1}


def test_local_budget_error_is_preflight_not_provider_quota(rotator):
    from agent_runtime.retry_policy import _raise_agent_call_error, AgentRateLimitError
    from agent_runtime.retry_error_classification import _agent_error_category
    from llm_daily_usage import LOCAL_BLOCK_KINDS
    exc = DailyBudgetBlockedError('m', 100, 'daily_budget_exhausted')
    assert _agent_error_category(exc) == 'local_daily_budget'
    assert type(exc).__name__ in LOCAL_BLOCK_KINDS
    with pytest.raises(AgentRateLimitError) as error:
        _raise_agent_call_error(exc, None, 'm', rotator, 60)
    assert error.value.preflight_blocked
    assert error.value.all_keys_exhausted


def test_store_unavailable_defers_instead_of_configuration_failure(rotator, monkeypatch, tmp_path):
    from agent_runtime.deferred import unavailable_model
    rotator._daily_budget = store_at(tmp_path)
    result = unavailable_model({}, rotator, 'm')
    assert result['retry_wait_seconds'] == 60


def test_tool_guard_contract_error_is_local_and_not_retried(rotator):
    from llm_tool_rate_guard import ToolRequestGuardError
    from llm_daily_usage import LOCAL_BLOCK_KINDS
    from agent_runtime.retry_policy import _raise_agent_call_error, AgentConfigurationError
    from agent_runtime.retry_error_classification import _agent_error_category
    exc = ToolRequestGuardError('Tool request budget exhausted')
    assert _agent_error_category(exc) == 'local_tool_guard'
    assert type(exc).__name__ in LOCAL_BLOCK_KINDS
    with pytest.raises(AgentConfigurationError):
        _raise_agent_call_error(exc, None, 'm', rotator, 60)
