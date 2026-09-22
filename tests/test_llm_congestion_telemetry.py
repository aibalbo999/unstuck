"""Transition observations cannot change admission or disclose credentials."""
import asyncio
import hashlib
import json

import pytest

import config
import llm_congestion as guard
from llm_congestion_store import CongestionStore
from provider_correlation import correlation_scope


class Busy(RuntimeError):
    status_code = 503
    headers = {"Retry-After": "90", "Authorization": "private-header"}


@pytest.fixture
def rig(monkeypatch):
    now, events = [1000.0], []
    monkeypatch.setattr(config, "LLM_CONGESTION_GUARD_ENABLED", True)
    monkeypatch.setattr(guard, "_store", CongestionStore(clock=lambda: now[0], jitter=lambda: 0))
    monkeypatch.setattr("api_usage_store.record_api_usage", lambda **event: events.append(event))
    return now, events


def fail():
    with pytest.raises(Busy):
        with guard.provider_attempt_scope("gemini-fixture", "private-key", record_outcome=False):
            with guard.provider_attempt_scope("gemini-fixture", "private-key"):
                raise Busy("private-error")


def test_nested_request_records_one_admission_and_outcome_then_probe_recovery(rig):
    now, events = rig
    with correlation_scope(replace=True, job_id="job-fixture", ticker="2305.TW"):
        fail()
    assert len(events) == 2
    admission, failure = [event["metadata"] for event in events]
    assert admission["outcome"] == "admitted" and admission["probe"] is False
    assert failure["outcome"] == "provider_503"
    assert failure["admission_generation"] == 0 and failure["generation"] == 1
    assert failure["retry_wait_seconds"] == 90
    assert failure["retry_not_before"] >= failure["observed_at"] + 90
    assert failure["job_id"] == "job-fixture"
    assert failure["attempt_id"] == admission["attempt_id"]
    with pytest.raises(guard.ProviderCongestionError):
        with guard.provider_attempt_scope("gemini-fixture", "other-private-key"):
            pytest.fail("blocked request reached provider")
    assert events[-1]["metadata"]["outcome"] == "blocked"
    now[0] += 91
    with guard.provider_attempt_scope("gemini-fixture", "other-private-key"):
        pass
    assert events[-2]["metadata"]["probe"] is True
    assert events[-1]["metadata"]["outcome"] == "success"
    assert events[-1]["metadata"]["generation"] == 2
    assert events[-1]["metadata"]["retry_not_before"] is None
    assert guard.congestion_wait("gemini-fixture") == 0
    assert all(event["operation"] == "llm_congestion_transition" and event["units"] == 0 for event in events)
    serialized = json.dumps(events)
    for secret in ("private-key", "private-header", "private-error", hashlib.sha256(b"private-key").hexdigest()):
        assert secret not in serialized


def test_cache_only_probe_is_release_never_provider_success_and_peek_is_silent(rig):
    now, events = rig
    fail()
    now[0] += 91
    start = len(events)
    with guard.provider_attempt_scope("gemini-fixture", "cache-key", record_outcome=False):
        pass
    assert [x["metadata"]["outcome"] for x in events[start:]] == ["admitted", "released_without_outcome"]
    assert guard.congestion_wait("gemini-fixture") == 30
    assert len(events) == start + 2


def test_failed_telemetry_preserves_original_exception_and_guard(rig, monkeypatch):
    attempts = []
    def broken(**kwargs):
        attempts.append(kwargs)
        raise RuntimeError("ledger unavailable")
    monkeypatch.setattr("api_usage_store.record_api_usage", broken)
    fail()
    assert len(attempts) == 2
    assert guard.congestion_wait("gemini-fixture") == 90


def test_rpd_is_not_logged_as_unknown_rate_limit_congestion(rig):
    class Rpd(RuntimeError):
        status_code = 429
    with pytest.raises(Rpd):
        with guard.provider_attempt_scope("gemini-fixture", "private-key"):
            raise Rpd("RequestsPerDay exhausted")
    assert rig[1][-1]["metadata"]["outcome"] == "provider_rpd"
    assert guard.congestion_wait("gemini-fixture") == 0


def test_late_success_is_distinct_from_atomic_probe_recovery(rig):
    now, events = rig
    with guard.provider_attempt_scope('gemini-fixture', 'first-key'):
        fail()  # Another already-admitted request opens generation 1.
    late = events[-1]['metadata']
    assert late['outcome'] == 'success'
    assert late.get('transition') == 'unchanged'
    assert guard.congestion_wait('gemini-fixture') == 90
    now[0] += 91
    with guard.provider_attempt_scope('gemini-fixture', 'recovery-key'):
        pass
    assert events[-1]['metadata']['transition'] == 'recovered'


def test_concurrent_jobs_have_separate_attempt_identity_and_correlation(rig):
    async def run(job):
        with correlation_scope(replace=True, job_id=job):
            with guard.provider_attempt_scope("gemini-fixture", job + "-secret"):
                await asyncio.sleep(0)
    async def all_jobs():
        await asyncio.gather(run("job-a"), run("job-b"))
    asyncio.run(all_jobs())
    grouped = {}
    for event in rig[1]:
        metadata = event['metadata']
        grouped.setdefault(metadata['attempt_id'], []).append(metadata)
    assert len(grouped) == 2
    for pair in grouped.values():
        assert len(pair) == 2 and pair[0]['job_id'] == pair[1]['job_id']
        assert [item['outcome'] for item in pair] == ['admitted', 'success']


def test_persisted_telemetry_does_not_inflate_request_or_error_totals(monkeypatch):
    import api_usage_store as usage
    monkeypatch.setattr(config, 'LLM_CONGESTION_GUARD_ENABLED', True)
    monkeypatch.setattr(guard, '_store', CongestionStore(jitter=lambda: 0))
    with correlation_scope(replace=True, job_id='persisted-job'):
        with guard.provider_attempt_scope('gemini-fixture', 'private-key'):
            pass
    # The project runner points this connection at its isolated operational DB.
    rows = usage._connect().execute("SELECT * FROM api_usage_events WHERE operation='llm_congestion_transition'").fetchall()
    assert len(rows) == 2
    assert {json.loads(row['metadata_json'])['outcome'] for row in rows} == {'admitted', 'success'}
    assert all(row['units'] == 0 and row['status'] == 'observed' for row in rows)
    summary = usage.summarize_llm_usage_since(0)
    assert summary['observed_calls_since_reset'] == 0
    assert summary['observed_quota_errors_since_reset'] == 0
