# RPD Key Model Disable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On explicit Gemini `RequestsPerDay` 429s, disable only the affected `API key + model` tuple until the next Pacific Time midnight.

**Architecture:** Reuse the current quota parser, shared Redis/local limiter, and `KeyRotator` boundaries. RPD state lives beside existing key/model cooldown state, keyed by hashed identity and checked before local RPM/TPM reservation.

**Tech Stack:** Python 3, pytest, Redis-compatible shared guard API, `zoneinfo.ZoneInfo("America/Los_Angeles")`.

---

## File Structure

- Modify `backend/llm_errors.py`: add `is_requests_per_day_error(error)` that inspects exception text and structured details.
- Modify `backend/llm_client.py`: re-export the new helper.
- Modify `backend/shared_runtime_guards.py`: add Pacific-midnight TTL calculation plus Redis/local RPD disable methods.
- Modify `backend/llm_rate_limits.py`: skip RPD-disabled key/model tuples and raise a classified error when all candidate keys are disabled.
- Modify `backend/agent_runtime/retry_policy.py`: call RPD disable on explicit RPD quota errors.
- Modify `tests/test_shared_runtime_guards.py`: cover RPD storage secrecy, local expiry, key/model isolation, and all-disabled rotator behavior.
- Modify `tests/test_llm_model_policy.py`: cover retry policy RPD disable behavior.
- Create `tests/test_llm_errors.py`: cover explicit RPD detection and false positives.

### Task 1: RPD Error Detection Tests

**Files:**
- Create: `tests/test_llm_errors.py`
- Modify: `backend/llm_errors.py`
- Modify: `backend/llm_client.py`

- [ ] **Step 1: Write the failing tests**

```python
from types import SimpleNamespace

from llm_errors import is_requests_per_day_error


def test_requests_per_day_error_detects_text_signature():
    error = RuntimeError("429 RESOURCE_EXHAUSTED quotaMetric=GenerateRequestsPerDayPerProject")
    assert is_requests_per_day_error(error) is True


def test_requests_per_day_error_detects_structured_quota_metric():
    error = SimpleNamespace(
        details=[
            {
                "violations": [
                    {
                        "quotaMetric": "generativelanguage.googleapis.com/generate_content_requests_per_day",
                        "quotaDimensions": {"model": "gemini-2.5-flash"},
                    }
                ]
            }
        ]
    )
    assert is_requests_per_day_error(error) is True


def test_requests_per_day_error_rejects_rpm_tpm_and_free_tier():
    assert is_requests_per_day_error(RuntimeError("429 RequestsPerMinute free_tier")) is False
    assert is_requests_per_day_error(RuntimeError("429 TokensPerMinute")) is False
    assert is_requests_per_day_error(RuntimeError("429 RESOURCE_EXHAUSTED free_tier")) is False
```

- [ ] **Step 2: Run red**

Run: `$(scripts/project_python.sh) -m pytest tests/test_llm_errors.py -q`

Expected: FAIL because `is_requests_per_day_error` does not exist.

- [ ] **Step 3: Implement minimal helper**

Add a recursive detail flattener and explicit RPD signature matching in `backend/llm_errors.py`; export it from `backend/llm_client.py`.

- [ ] **Step 4: Run green**

Run: `$(scripts/project_python.sh) -m pytest tests/test_llm_errors.py -q`

Expected: PASS.

### Task 2: Shared RPD Disable State Tests

**Files:**
- Modify: `tests/test_shared_runtime_guards.py`
- Modify: `backend/shared_runtime_guards.py`

- [ ] **Step 1: Write failing tests**

Add tests that call:

```python
wait = limiter.disable_rpd_until_reset("super-secret-api-key", "gemini-test", now=now)
assert wait > 0
assert limiter.rpd_disabled_wait("super-secret-api-key", "gemini-test", now=now) == wait
assert limiter.rpd_disabled_wait("super-secret-api-key", "other-model", now=now) == 0
```

Also assert Redis keys contain neither the API key nor the model ID.

- [ ] **Step 2: Run red**

Run: `$(scripts/project_python.sh) -m pytest tests/test_shared_runtime_guards.py -q`

Expected: FAIL because `disable_rpd_until_reset` and `rpd_disabled_wait` do not exist.

- [ ] **Step 3: Implement shared state**

Add local dictionary state in `LocalFixedWindowRateLimiter`, Redis `SET ... px=...` storage in `RedisFixedWindowRateLimiter`, and `seconds_until_next_pacific_midnight(now=None)`.

- [ ] **Step 4: Run green**

Run: `$(scripts/project_python.sh) -m pytest tests/test_shared_runtime_guards.py -q`

Expected: PASS.

### Task 3: KeyRotator Skip Tests

**Files:**
- Modify: `tests/test_shared_runtime_guards.py`
- Modify: `backend/llm_rate_limits.py`

- [ ] **Step 1: Write failing tests**

Add tests proving disabled `key + model` tuples are skipped, same key on another model remains usable, and all-disabled keys raise `AllKeysRpdDisabledError` with a positive retry wait.

- [ ] **Step 2: Run red**

Run: `$(scripts/project_python.sh) -m pytest tests/test_shared_runtime_guards.py::test_key_rotator_skips_rpd_disabled_key_for_that_model -q`

Expected: FAIL because the rotator does not check RPD disable state.

- [ ] **Step 3: Implement rotator behavior**

Add `AllKeysRpdDisabledError`, filter candidates with `rpd_disabled_wait`, and preserve existing reservation behavior for available keys.

- [ ] **Step 4: Run green**

Run: `$(scripts/project_python.sh) -m pytest tests/test_shared_runtime_guards.py -q`

Expected: PASS.

### Task 4: Retry Policy Wiring Tests

**Files:**
- Modify: `tests/test_llm_model_policy.py`
- Modify: `backend/agent_runtime/retry_policy.py`

- [ ] **Step 1: Write failing test**

Add a fake rotator whose `disable_rpd_until_reset()` records calls. Pass a structured `RequestsPerDay` error into `_raise_agent_call_error()` and assert RPD disable is called, while ordinary 429 still calls `penalize()`.

- [ ] **Step 2: Run red**

Run: `$(scripts/project_python.sh) -m pytest tests/test_llm_model_policy.py::test_rpd_429_disables_key_model_until_reset -q`

Expected: FAIL because retry policy only calls `penalize()`.

- [ ] **Step 3: Implement retry wiring**

Import `is_requests_per_day_error`; on explicit RPD call `rotator.disable_rpd_until_reset(api_key, model_id)` and use its returned wait for metadata. Keep non-RPD quota behavior unchanged.

- [ ] **Step 4: Run green**

Run: `$(scripts/project_python.sh) -m pytest tests/test_llm_model_policy.py -q`

Expected: PASS.

### Task 5: Final Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run focused tests**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_llm_errors.py \
  tests/test_shared_runtime_guards.py \
  tests/test_llm_model_policy.py \
  tests/test_llm_transport.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run syntax/diff checks**

Run:

```bash
git diff --check
git status -sb
```

Expected: no whitespace errors; only intended files plus pre-existing dirty files are modified.
