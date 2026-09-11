import asyncio
import json
import sqlite3
from types import SimpleNamespace

import pytest
import rq

from llm_daily_budget import DailyBudgetStore, AllKeysRpdDisabledError
import llm_rate_limits as limits
import analysis_job_retry as retry
from agent_runtime.deferred import AgentDeferredError, unavailable_model
from agent_runtime.retry_policy import AgentTransientError


@pytest.mark.parametrize('async_mode', [False, True])
def test_local_daily_estimate_does_not_block_but_provider_feedback_does(monkeypatch, tmp_path, async_mode):
    monkeypatch.setattr(limits, 'LLM_PROVIDER_QUOTA_AUTHORITATIVE', True, raising=False)
    monkeypatch.setattr(limits, 'RPD_LIMITS', {'m': 1})
    monkeypatch.setattr(limits, 'RPM_LIMITS', {'*': 1000})
    monkeypatch.setattr(limits, 'TPM_LIMITS', {})
    monkeypatch.setattr(limits, 'MODEL_INPUT_TOKEN_LIMITS', {})
    monkeypatch.setattr(limits, 'create_shared_llm_limiter', lambda: None)
    monkeypatch.setattr(limits, 'emit_log', lambda _: None)
    rotator = limits.KeyRotator(['a', 'b'])
    rotator._daily_budget = DailyBudgetStore(path_getter=lambda: tmp_path/'budget.db')
    async def get(): return await rotator.async_get_key('m')
    call = (lambda: asyncio.run(get())) if async_mode else (lambda: rotator.get_key('m'))
    assert [call() for _ in range(4)] == ['a', 'b', 'a', 'b']
    assert rotator.eligible_key_slots('m') == {1, 2}
    assert rotator.model_retry_wait('m') == 0
    with sqlite3.connect(tmp_path/'budget.db') as c:
        assert c.execute('select sum(used) from llm_daily_budgets').fetchone()[0] == 4
    rotator.disable_rpd_until_reset('a', 'm')
    assert call() == 'b'
    rotator.disable_rpd_until_reset('b', 'm')
    with pytest.raises(AllKeysRpdDisabledError): call()
    route = unavailable_model({}, rotator, 'm')
    assert route['provider_quota_confirmed'] is True
    assert rotator.eligible_key_slots('other-model') == {1, 2}
    rotator._daily_budget.close_current_thread()


def test_observed_tool_reservations_still_settle_exact_unused_units(tmp_path):
    store = DailyBudgetStore(path_getter=lambda: tmp_path/'budget.db')
    receipts = [store.reserve_with_receipt('a','m',1,['a'],request_units=6,enforce_limit=False) for _ in range(3)]
    assert all(receipts)
    for receipt in receipts:store.settle_reservation(receipt,accounted_units=2)
    with sqlite3.connect(tmp_path/'budget.db') as c:
        assert c.execute('select used from llm_daily_budgets').fetchone()[0] == 6
    store.close_current_thread()


@pytest.mark.parametrize('kind', ['transient', 'quota'])
def test_availability_retries_outlive_original_queue_attempt_budget(monkeypatch, kind):
    monkeypatch.setattr(retry, 'LLM_PROVIDER_QUOTA_AUTHORITATIVE', True, raising=False)
    saved = []
    job = SimpleNamespace(id='analysis:test', retries_left=0, retry_intervals=[60,300,900], meta={}, save=lambda:saved.append(True))
    monkeypatch.setattr(rq,'get_current_job',lambda:job)
    error = AgentTransientError('503') if kind == 'transient' else AgentDeferredError(4,[{'model_id':'m','provider_quota_confirmed':True,'reason_code':'provider_daily_quota_exhausted','retry_wait_seconds':18000}])
    waits = []
    for _ in range(12):
        result = retry.prepare_analysis_retry('test',error)
        assert result['retry_scheduled'] is True
        assert result['retry_budget_exhausted'] is False
        assert job.retries_left >= 1
        waits.append(result['retry_after_seconds'])
        job.retries_left = 0  # RQ consumes one after handling the exception
    assert waits == sorted(waits)
    assert 300 <= waits[0] <= waits[-1]
    assert waits[-1] <= (18000 if kind == 'quota' else 1800)
    assert len(saved)==12


def test_permanent_error_does_not_gain_infinite_retries(monkeypatch):
    monkeypatch.setattr(retry,'LLM_PROVIDER_QUOTA_AUTHORITATIVE',True,raising=False)
    job=SimpleNamespace(id='analysis:test',retries_left=0,retry_intervals=[60],save=lambda:None)
    monkeypatch.setattr(rq,'get_current_job',lambda:job)
    assert not retry.prepare_analysis_retry('test',ValueError('bad schema'))['retry_scheduled']


def test_real_rq_retry_schedules_again_after_last_retry_is_consumed(monkeypatch):
    from rq.job import Job
    from unittest.mock import Mock
    from datetime import datetime, timezone
    monkeypatch.setattr(retry,'LLM_PROVIDER_QUOTA_AUTHORITATIVE',True)
    job=Job(id='analysis:test',connection=Mock())
    job.retries_left=0;job.retry_intervals=[60,300,900];job.meta={}
    monkeypatch.setattr(job,'save',lambda:None)
    monkeypatch.setattr(rq,'get_current_job',lambda:job)
    scheduled=[]
    queue=SimpleNamespace(schedule_job=lambda j,at,pipeline:scheduled.append((j.id,at,j.retries_left)))
    for _ in range(5):
        result=retry.prepare_analysis_retry('test',AgentTransientError('timeout'))
        assert result['retry_scheduled']
        job.retry(queue,Mock())  # actual RQ decrement and schedule code
        assert job.get_status(refresh=False)=='scheduled'
        assert job.retries_left==0
        assert scheduled[-1][1]>datetime.now(timezone.utc)
    assert len(scheduled)==5


def test_generic_cooldown_is_not_reported_as_provider_daily_exhaustion(monkeypatch):
    rotator=SimpleNamespace(eligible_key_slots=lambda _:set(),model_circuit_wait=lambda _:60,provider_quota_exhausted=lambda _:False)
    route=unavailable_model({},rotator,'m')
    assert route['provider_quota_confirmed'] is False
    assert route['reason_code']=='model_cooldown'
