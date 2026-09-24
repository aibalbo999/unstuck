"""Secret-free policy snapshot from the same functions used for agent calls.

An API snapshot describes its own process, not a worker. Worker model events
carry a digest of their process policy so operators can compare actual callers.
Temporary per-call overrides remain visible in each model event's model_id.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
import time

import config
from agent_catalog import AGENT_NAMES
from agent_runtime.generation_config import (
    GENERATION_POLICY_VERSION, build_generation_config, generation_event_metadata,
    google_safe_agent_system_instruction,
)
from agent_runtime.model_policy import timeout_for_model_call
from agent_runtime.prompt_budget import get_agent_context_input_token_limit, get_agent_prompt_token_budget
from agent_runtime.prompt_config import ANALYSIS_PROMPTS, PROMPT_CONFIG
from agent_runtime.prompt_routing_policy import AGENT_HISTORY_YEARS, ROUTED_EXTERNAL_CONTEXT_KEYS
from agent_runtime.quality_retry import quality_retry_model_sequence
from agent_runtime.routing import (
    get_agent_function_tools, get_agent_model_sequence, get_audit_model_sequence,
    get_audit_rewrite_model_sequence, get_context_digest_model_sequence,
)
from llm_provider_routes import provider_for_model
from generation_settings_safety import safe_generation_settings
from pipeline_modes import PIPELINE_DEFINITIONS
from structured_output_models import get_structured_response_schema


SETTINGS_SCHEMA_VERSION = 1
_RUNTIME_FIELDS = (
    "LLM_AGENT_CALL_TIMEOUT_SECONDS", "PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS",
    "FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS", "LLM_KEY_ADMISSION_TIMEOUT_SECONDS",
    "PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS", "PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS",
    "LLM_SERVER_ERROR_MAX_ATTEMPTS", "LLM_ROUTE_SERVER_ERROR_MAX_ATTEMPTS",
    "LLM_QUOTA_MAX_ATTEMPTS_PER_MODEL", "LLM_SERVER_ERROR_RETRY_MAX_WAIT_SECONDS",
    "LLM_SERVER_ERROR_MODEL_COOLDOWN_SECONDS", "LLM_MODEL_CIRCUIT_THRESHOLD",
    "LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS", "MAX_PER_JOB_REPAIR_ATTEMPTS",
    "AGENT_STEP_CACHE_ENABLED", "AGENT_STEP_CACHE_SECONDS", "LLM_SEMANTIC_CACHE_ENABLED",
    "LLM_SEMANTIC_CACHE_SECONDS", "LLM_CONGESTION_GUARD_ENABLED",
    "LLM_PROVIDER_QUOTA_AUTHORITATIVE", "GEMMA_EVIDENCE_BATCHING_ENABLED",
    "GEMMA_STATE_REFERENCE_COMPACTION_ENABLED", "RAG_ENABLED", "RAG_CHUNK_SIZE",
    "RAG_CHUNK_OVERLAP", "RAG_MAX_INDEX_CHUNKS", "RAG_MIN_SOURCE_CHARS",
    "RAG_EMBEDDING_CACHE_SECONDS", "PRIMARY_PROMPT_CONTEXT_TOTAL_CHAR_BUDGET",
    "PRIMARY_PROMPT_RAG_CONTEXT_CHARS", "PROMPT_CONTEXT_RESPONSE_TOKEN_BUDGET",
    "PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS",
)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _limit(mapping: dict, model: str) -> int:
    return int(mapping.get(model, mapping.get("*", 0)))


def _schema_digest(schema) -> str | None:
    if schema is None:
        return None
    if hasattr(schema, "model_json_schema"):
        schema = schema.model_json_schema()
    return _digest(schema)


def _candidate(agent: int, model: str, index: int, route_length: int) -> dict:
    from agent_runtime.llm_waiting import key_admission_timeout

    timeout = timeout_for_model_call(index, route_length > 1)
    return {
        "model_id": model,
        "provider": provider_for_model(model),
        "generation_config": generation_event_metadata(agent, model),
        "system_instruction_sha256": _digest(google_safe_agent_system_instruction(agent, model)),
        "context_window_tokens": config.get_model_context_token_limit(model),
        "configured_context_input_ceiling_tokens": get_agent_context_input_token_limit(agent, model),
        "local_input_limit_tokens": _limit(config.MODEL_INPUT_TOKEN_LIMITS, model),
        "local_rpm_limit": _limit(config.RPM_LIMITS, model),
        "local_tpm_limit": _limit(config.TPM_LIMITS, model),
        "rpd_reference": _limit(config.RPD_LIMITS, model),
        "supplementary_context_budget_tokens": get_agent_prompt_token_budget(agent, model_id=model),
        "provider_timeout_seconds": timeout,
        "key_admission_timeout_seconds": key_admission_timeout(timeout),
    }


def _agent_settings(agent: int) -> dict:
    route = get_agent_model_sequence(agent)
    generation = build_generation_config(agent)
    tools = get_agent_function_tools(agent) if getattr(generation, "tools", None) else []
    schema = get_structured_response_schema(agent)
    native_schema = getattr(generation, "response_schema", None)
    total, per_agent = config.get_agent_context_budgets(agent)
    rag_chars, rag_chunks = config.get_agent_rag_budget(agent)
    return {
        "agent_num": agent, "name": AGENT_NAMES[agent],
        "pipeline_ids": [name for name, mode in PIPELINE_DEFINITIONS.items() if agent in mode["agents"]],
        "configured_primary_model": config.AGENT_MODELS[agent],
        "configured_fallback_models": list(config.AGENT_FALLBACK_MODELS.get(agent, [])),
        "effective_model_sequence": route,
        "effective_audit_rewrite_sequence": get_audit_rewrite_model_sequence(agent),
        "effective_quality_rewrite_sequence": quality_retry_model_sequence(agent, {}),
        "critical_lite_fallback_enabled": bool(config.CRITICAL_LITE_FALLBACK_AGENTS.get(agent)),
        "audit_rewrite_lite_fallback_enabled": bool(config.AUDIT_REWRITE_LITE_FALLBACK_AGENTS.get(agent)),
        "candidates": [_candidate(agent, model, index, len(route)) for index, model in enumerate(route)],
        "output_contract": {
            "schema_name": schema.__name__ if schema else None,
            "native_schema_enabled": native_schema is not None,
            "schema_sha256": _schema_digest(native_schema),
            "response_mime_type": getattr(generation, "response_mime_type", None),
            "effective_tools": [tool.__name__ for tool in tools],
            "maximum_tool_remote_calls": getattr(getattr(generation, "automatic_function_calling", None),
                                                  "maximum_remote_calls", None),
        },
        "context": {
            "upstream_total_chars": total, "upstream_per_agent_chars": per_agent,
            "upstream_and_rag_character_budget_basis": "configured_primary_model",
            "rag_max_chars": rag_chars, "rag_max_chunks": rag_chunks,
            "rag_budget_is_supplementary_not_full_request_admission": True,
            "blind_to_upstream_analysis": agent in config.BLIND_CONTEXT_AGENTS,
            "history_years": AGENT_HISTORY_YEARS.get(agent),
            "external_context_fields": sorted(key for key, roles in ROUTED_EXTERNAL_CONTEXT_KEYS.items() if agent in roles),
        },
        "analysis_template_sha256": _digest(ANALYSIS_PROMPTS.get(agent, "")),
    }


def _auxiliary_roles() -> dict:
    from context_digest_runtime import _build_digest_generation_config
    from context_digest_tasks import CONTEXT_DIGEST_TARGET_AGENTS
    from tear_sheet_tasks import _build_tear_sheet_generation_config
    from agent_runtime.repair_reflection import _build_reflection_generation_config
    from agent_runtime import gemma_evidence_runtime as batches
    from gemma_evidence_batches import MODEL, TRIGGER_MODEL, ROLES

    def generation(factory):
        value = factory()
        safe = safe_generation_settings(value.model_dump(exclude_none=True))
        thinking = getattr(value, "thinking_config", None)
        if thinking and thinking.thinking_level is not None:
            safe["thinking_level"] = str(thinking.thinking_level.value).lower()
        return safe

    return {
        "chief_editor": {"execution_kind": "deterministic", "model_sequence": []},
        "context_digest": {"model_sequence": get_context_digest_model_sequence(),
                           "target_agents": sorted(CONTEXT_DIGEST_TARGET_AGENTS),
                           "generation_config": generation(_build_digest_generation_config)},
        "tear_sheet": {"model_sequence": [config.TEAR_SHEET_MODEL],
                       "generation_config": generation(_build_tear_sheet_generation_config)},
        "audit_reflection": {"model_sequence": get_audit_model_sequence(),
                             "generation_config": generation(_build_reflection_generation_config),
                             "deterministic_fallback_enabled": True},
        "embedding": {"model_sequence": [config.EMBEDDING_MODEL]},
        "gemma_evidence_batching": {"enabled": config.GEMMA_EVIDENCE_BATCHING_ENABLED,
                                   "model_sequence": [MODEL], "trigger_model": TRIGGER_MODEL,
                                   "target_agents": sorted(ROLES),
                                   "generation_config": generation(batches.config),
                                   "provider_timeout_seconds": batches.TIMEOUT,
                                   "transient_max_attempts": batches.TRANSIENT_MAX_ATTEMPTS},
    }


def _build_policy() -> dict:
    return {
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "generation_policy_version": GENERATION_POLICY_VERSION,
        "model_routes_file_sha256": config.MODEL_ROUTES_FILE_SHA256,
        "prompt_fingerprint": PROMPT_CONFIG["prompt_fingerprint"],
        "prompt_version": PROMPT_CONFIG["prompt_version"],
        "agents": [_agent_settings(agent) for agent in sorted(AGENT_NAMES)],
        "auxiliary_roles": _auxiliary_roles(),
        "local_model_limits": {
            "rpm": dict(config.RPM_LIMITS), "tpm": dict(config.TPM_LIMITS),
            "rpd_reference": dict(config.RPD_LIMITS),
            "input_tokens": dict(config.MODEL_INPUT_TOKEN_LIMITS),
            "context_tokens": dict(config.MODEL_CONTEXT_TOKEN_LIMITS),
        },
        "runtime_policy": {name: getattr(config, name) for name in _RUNTIME_FIELDS if hasattr(config, name)},
        "quota_scope": {
            "project_mapping_status": "unknown",
            "independent_project_count": None,
            "configured_key_count_does_not_establish_project_count": True,
            "local_limits_are_not_provider_entitlements": True,
        },
    }


@lru_cache(maxsize=1)
def process_settings_sha256() -> str:
    """Cache import-time policy identity; settings changes require process restart."""
    return _digest(_build_policy())


def build_agent_settings_payload() -> dict:
    policy = _build_policy()
    providers = {provider_for_model(model) for agent in AGENT_NAMES for model in get_agent_model_sequence(agent)}
    providers.update({"google", "openai", "anthropic"})
    keys = config.LLM_API_KEYS_BY_PROVIDER
    return {
        **policy,
        "effective_settings_sha256": _digest(policy),
        "identity_scope": "configured_routes_generation_prompts_context_and_runtime_policy",
        # Credentials may refresh without reloading the policy. Counts are live
        # readiness observations, not identity inputs or independent quotas.
        "provider_readiness": [{
            "provider": provider, "configured_credential_count": len(keys.get(provider, [])),
            "credentials_loaded": bool(keys.get(provider)), "live_health_verified": False,
        } for provider in sorted(providers)],
        "generated_at": time.time(),
        "snapshot_scope": "api_process",
        "process_id": os.getpid(),
        "worker_settings_verified": False,
        "worker_verification_method": "Compare effective_settings_sha256 on persisted worker llm_provider_request events.",
        "call_override_note": "Configured routes exclude temporary audit/quality overrides; actual model_id and generation_config are recorded per call.",
    }
