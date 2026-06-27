import asyncio
import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_security_settings_fail_fast_without_mutation_token_in_server_mode(monkeypatch):
    import settings.security as security

    monkeypatch.setenv("DEPLOYMENT_MODE", "server")
    monkeypatch.setenv("MUTATION_API_TOKEN", "")
    monkeypatch.setenv("ADMIN_API_TOKEN", "legacy-token-must-not-bypass-production-check")

    with pytest.raises(ValueError, match="MUTATION_API_TOKEN must be set in production."):
        importlib.reload(security)

    monkeypatch.setenv("DEPLOYMENT_MODE", "local")
    importlib.reload(security)


def test_output_sanitizer_exposes_strict_payload_and_guardrail_hook():
    from pydantic import ValidationError

    from output_sanitizer import (
        SanitizedOutputPayload,
        SecureOutputSanitizer,
        SecurityViolationError,
        validate_prompt_input,
    )

    with pytest.raises(ValidationError):
        SanitizedOutputPayload(content=123)

    stages = []

    async def guardrail(_text, *, stage):
        stages.append(stage)
        return {"allowed": False, "reason": "external policy blocked"}

    sanitizer = SecureOutputSanitizer(guardrail=guardrail)

    with pytest.raises(SecurityViolationError, match="external policy blocked"):
        asyncio.run(sanitizer.sanitize("正常研究報告內容"))

    assert stages == ["output"]

    async def allow_guardrail(_text, *, stage):
        stages.append(stage)
        return {"allowed": True}

    assert asyncio.run(validate_prompt_input("外部新聞內容", allow_guardrail)) == "外部新聞內容"
    assert stages[-1] == "input"


def test_redis_rate_limiter_falls_back_to_local_bucket_when_redis_fails():
    from shared_runtime_guards import RedisFixedWindowRateLimiter

    class FailingRedis:
        def eval(self, *args):
            raise ConnectionError("redis down")

    limiter = RedisFixedWindowRateLimiter(FailingRedis(), namespace="test")

    assert limiter.reserve("key-a", "model-a", rpm_limit=1, tpm_limit=0, estimated_tokens=1) == 0
    assert limiter.reserve("key-a", "model-a", rpm_limit=1, tpm_limit=0, estimated_tokens=1) > 0


def test_shared_guard_factories_keep_local_protection_when_redis_connect_fails(monkeypatch):
    import shared_runtime_guards as guards

    monkeypatch.setattr(guards, "shared_guard_enabled", lambda _name: True)
    monkeypatch.setattr(guards, "create_redis_client", lambda _name: None)

    assert guards.create_shared_llm_limiter() is not None
    assert guards.create_shared_provider_circuit_store() is not None


def test_redis_provider_circuit_store_falls_back_to_local_circuit_when_redis_fails():
    from shared_runtime_guards import RedisProviderCircuitStore

    class FailingRedis:
        def hincrby(self, *args):
            raise ConnectionError("redis down")

        def hgetall(self, *args):
            raise ConnectionError("redis down")

    store = RedisProviderCircuitStore(FailingRedis(), namespace="test")
    store.record_failure("provider-a", "boom", threshold=1, cooldown_seconds=60)

    state = store.state("provider-a")

    assert state["open"] is True
    assert state["failures"] == 1


def test_main_uses_analysis_pipeline_runner_without_whole_pipeline_backoff():
    import main

    source = Path(main.__file__).read_text(encoding="utf-8")

    assert isinstance(main.PIPELINE_RUNNER, main.AnalysisPipelineRunner)
    assert "await PIPELINE_RUNNER.run_async(analysis_req)" in source
    assert not hasattr(main, "run_analysis_pipeline_with_backoff")
    assert "13 秒延遲" not in source


def test_agent_system_prompts_use_functional_personas_without_institution_names():
    agents = json.loads((ROOT / "backend" / "prompts" / "agents.json").read_text(encoding="utf-8"))
    system_prompts = "\n".join(agents["system_prompts"].values())
    forbidden = [
        "Goldman Sachs",
        "Morgan Stanley",
        "BlackRock",
        "JPMorgan",
        "Fidelity",
        "Bridgewater",
        "Citadel",
        "Point72",
        "Muddy Waters",
        "Morningstar",
        "華爾街",
        "高盛",
        "摩根士丹利",
        "貝萊德",
        "富達",
        "渾水",
    ]

    assert all(name not in system_prompts for name in forbidden)
    assert "禁止輸出機構名稱、角色扮演問候語或 meta-talk" in system_prompts
    assert "逐項驗證中間算術" in system_prompts
