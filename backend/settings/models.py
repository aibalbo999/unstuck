"""Model routing, context, RAG, and rate-limit settings."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from agent_catalog import AGENT_NAMES
from pipeline_modes import get_pipeline_agents

from .env import DEFAULT_MODEL_ROUTES_FILE, env_bool, env_int, env_list, env_str, json_env_dict


def _load_model_routes() -> dict:
    routes_path = Path(env_str("MODEL_ROUTES_FILE", str(DEFAULT_MODEL_ROUTES_FILE))).expanduser()
    if not routes_path.exists():
        return {}
    try:
        parsed = json.loads(routes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


MODEL_ROUTES = _load_model_routes()


def _route_section(section_name: str) -> dict:
    section = MODEL_ROUTES.get(section_name, {})
    return section if isinstance(section, dict) else {}


def _route_str(name: str, default: str = "") -> str:
    return str(MODEL_ROUTES.get(name, default) or "").strip()


def _route_list(name: str, default: Optional[list[str]] = None) -> list[str]:
    value = MODEL_ROUTES.get(name, default or [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(default or [])


def _route_limit_defaults(section_name: str) -> dict[str, int]:
    limits = {}
    for model, value in _route_section(section_name).items():
        try:
            limits[str(model)] = int(value)
        except (TypeError, ValueError):
            continue
    return limits


def _model_env_suffix(model: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", model.upper()).strip("_")


DEFAULT_ANALYSIS_MODEL = env_str("DEFAULT_ANALYSIS_MODEL", _route_str("default_analysis_model"))
DEFAULT_DECISION_MODEL = env_str("DEFAULT_DECISION_MODEL", _route_str("default_decision_model"))
CONTEXT_DIGEST_MODEL = env_str("CONTEXT_DIGEST_MODEL", _route_str("context_digest_model", DEFAULT_ANALYSIS_MODEL))
TEAR_SHEET_MODEL = env_str("TEAR_SHEET_MODEL", _route_str("tear_sheet_model", CONTEXT_DIGEST_MODEL))
AUDIT_MODEL = env_str("AUDIT_MODEL", _route_str("audit_model", DEFAULT_DECISION_MODEL))
AUDIT_FALLBACK_MODELS = env_list("AUDIT_FALLBACK_MODELS", _route_list("audit_fallback_models"))
EMBEDDING_MODEL = env_str("EMBEDDING_MODEL", _route_str("embedding_model", "gemini-embedding-2"))
REPORT_COVER_MODEL = env_str("REPORT_COVER_MODEL", _route_str("report_cover_model", "imagen-4.0-generate-001"))
REPORT_COVER_FALLBACK_MODELS = env_list("REPORT_COVER_FALLBACK_MODELS", _route_list("report_cover_fallback_models"))
ENABLE_REPORT_COVER = env_bool("ENABLE_REPORT_COVER", env_bool("REPORT_COVER_ENABLED", True))
REPORT_COVER_IMAGE_SIZE = env_str("REPORT_COVER_IMAGE_SIZE", _route_str("report_cover_image_size", "1K"))
REPORT_COVER_ASPECT_RATIO = env_str("REPORT_COVER_ASPECT_RATIO", _route_str("report_cover_aspect_ratio", "16:9"))

RAG_ENABLED = env_bool("RAG_ENABLED", env_bool("ENABLE_RAG", True))
RAG_CHUNK_SIZE = env_int("RAG_CHUNK_SIZE", 1600)
RAG_CHUNK_OVERLAP = env_int("RAG_CHUNK_OVERLAP", 220)
RAG_MIN_SOURCE_CHARS = env_int("RAG_MIN_SOURCE_CHARS", 280)
RAG_MAX_INDEX_CHUNKS = env_int("RAG_MAX_INDEX_CHUNKS", 48)
RAG_MAX_CHUNKS_PER_AGENT = env_int("RAG_MAX_CHUNKS_PER_AGENT", 5)
RAG_MAX_CONTEXT_CHARS = env_int("RAG_MAX_CONTEXT_CHARS", 5200)
RAG_LARGE_CONTEXT_CHARS = env_int("RAG_LARGE_CONTEXT_CHARS", 16000)
RAG_LARGE_CONTEXT_CHUNKS = env_int("RAG_LARGE_CONTEXT_CHUNKS", 8)
RAG_EMBEDDING_CACHE_SECONDS = env_int("RAG_EMBEDDING_CACHE_SECONDS", 30 * 24 * 60 * 60)
PRIMARY_PROMPT_CONTEXT_TOTAL_CHAR_BUDGET = env_int("PRIMARY_PROMPT_CONTEXT_TOTAL_CHAR_BUDGET", 4500)
PRIMARY_PROMPT_RAG_CONTEXT_CHARS = env_int("PRIMARY_PROMPT_RAG_CONTEXT_CHARS", 1800)

CONTEXT_TOTAL_CHAR_BUDGET = env_int("CONTEXT_TOTAL_CHAR_BUDGET", 11000)
CONTEXT_PER_AGENT_CHAR_BUDGET = env_int("CONTEXT_PER_AGENT_CHAR_BUDGET", 2200)
LARGE_CONTEXT_MODEL_PATTERN = env_str("LARGE_CONTEXT_MODEL_PATTERN", r"(gemini|flash)")
LARGE_CONTEXT_TOTAL_CHAR_BUDGET = env_int("LARGE_CONTEXT_TOTAL_CHAR_BUDGET", 28000)
LARGE_CONTEXT_PER_AGENT_CHAR_BUDGET = env_int("LARGE_CONTEXT_PER_AGENT_CHAR_BUDGET", 5200)
BLIND_CONTEXT_AGENTS = {int(agent_num) for agent_num in env_list("BLIND_CONTEXT_AGENTS", ["13"]) if str(agent_num).strip().isdigit()}

if not DEFAULT_ANALYSIS_MODEL or not DEFAULT_DECISION_MODEL:
    raise RuntimeError(
        "缺少模型路由設定。請設定 backend/model_routes.json、MODEL_ROUTES_FILE，"
        "或在 backend/.env 提供 DEFAULT_ANALYSIS_MODEL / DEFAULT_DECISION_MODEL。"
    )


def _load_agent_models() -> dict[int, str]:
    route_agents = _route_section("agents")
    models = {}
    decision_agents = {7, 16, 19}
    for agent_num in sorted(AGENT_NAMES):
        default_model = DEFAULT_DECISION_MODEL if agent_num in decision_agents else DEFAULT_ANALYSIS_MODEL
        configured = route_agents.get(str(agent_num), default_model)
        models[agent_num] = str(configured or default_model).strip()

    for raw_key, value in json_env_dict("AGENT_MODELS_JSON").items():
        try:
            agent_num = int(raw_key)
        except (TypeError, ValueError):
            continue
        if agent_num in AGENT_NAMES and str(value).strip():
            models[agent_num] = str(value).strip()

    for agent_num in sorted(AGENT_NAMES):
        override = os.getenv(f"AGENT_MODEL_{agent_num}", "").strip()
        if override:
            models[agent_num] = override

    return models


def _load_agent_fallbacks() -> dict[int, list[str]]:
    route_fallbacks = _route_section("agent_fallbacks")
    default_analysis_fallbacks = env_list("DEFAULT_ANALYSIS_FALLBACK_MODELS", _route_list("analysis_fallback_models"))
    models: dict[int, list[str]] = {}
    decision_agents = {7, 16, 19}
    for agent_num in sorted(AGENT_NAMES):
        configured = route_fallbacks.get(str(agent_num), [] if agent_num in decision_agents else default_analysis_fallbacks)
        if isinstance(configured, list):
            models[agent_num] = [str(model).strip() for model in configured if str(model).strip()]
        elif isinstance(configured, str):
            models[agent_num] = [model.strip() for model in configured.split(",") if model.strip()]
        else:
            models[agent_num] = []

    for raw_key, value in json_env_dict("AGENT_FALLBACK_MODELS_JSON").items():
        try:
            agent_num = int(raw_key)
        except (TypeError, ValueError):
            continue
        if agent_num not in AGENT_NAMES:
            continue
        if isinstance(value, list):
            models[agent_num] = [str(model).strip() for model in value if str(model).strip()]
        elif isinstance(value, str):
            models[agent_num] = [model.strip() for model in value.split(",") if model.strip()]

    for agent_num in sorted(AGENT_NAMES):
        models[agent_num] = env_list(f"AGENT_FALLBACK_MODELS_{agent_num}", models.get(agent_num, []))
    return models


AGENT_MODELS = _load_agent_models()
AGENT_FALLBACK_MODELS = _load_agent_fallbacks()


def is_large_context_model(model_id: str) -> bool:
    """Return True for models configured to receive a larger prompt budget."""
    pattern = str(LARGE_CONTEXT_MODEL_PATTERN or "").strip()
    if not pattern:
        return False
    try:
        return bool(re.search(pattern, str(model_id or ""), re.IGNORECASE))
    except re.error:
        return False


def get_agent_context_budgets(agent_num: int) -> tuple[int, int]:
    """Return total/per-upstream-agent context character budgets."""
    model_id = AGENT_MODELS.get(int(agent_num), "")
    if is_large_context_model(model_id):
        return LARGE_CONTEXT_TOTAL_CHAR_BUDGET, LARGE_CONTEXT_PER_AGENT_CHAR_BUDGET
    return CONTEXT_TOTAL_CHAR_BUDGET, CONTEXT_PER_AGENT_CHAR_BUDGET


def get_agent_rag_budget(agent_num: int) -> tuple[int, int]:
    """Return RAG max chars/top-k budget for the agent's primary model."""
    model_id = AGENT_MODELS.get(int(agent_num), "")
    if is_large_context_model(model_id):
        return RAG_LARGE_CONTEXT_CHARS, RAG_LARGE_CONTEXT_CHUNKS
    return RAG_MAX_CONTEXT_CHARS, RAG_MAX_CHUNKS_PER_AGENT


def _load_model_limits(json_env_name: str, default_env_name: str, builtins: dict[str, int], default_limit: int) -> dict[str, int]:
    limits = {"*": env_int(default_env_name, default_limit)}
    limits.update(builtins)
    for model, value in json_env_dict(json_env_name).items():
        try:
            limits[str(model)] = int(value)
        except (TypeError, ValueError):
            continue

    configured_models = {
        *AGENT_MODELS.values(),
        CONTEXT_DIGEST_MODEL,
        TEAR_SHEET_MODEL,
        AUDIT_MODEL,
        *AUDIT_FALLBACK_MODELS,
        EMBEDDING_MODEL,
        REPORT_COVER_MODEL,
        *REPORT_COVER_FALLBACK_MODELS,
    }
    for fallback_models in AGENT_FALLBACK_MODELS.values():
        configured_models.update(fallback_models)
    for model in configured_models:
        override = os.getenv(f"{json_env_name.removesuffix('_JSON')}_{_model_env_suffix(model)}", "").strip()
        if override:
            try:
                limits[model] = int(override)
            except ValueError:
                pass
    return limits


ROUTE_RPM_LIMITS = _route_limit_defaults("rpm_limits")
ROUTE_TPM_LIMITS = _route_limit_defaults("tpm_limits")
ROUTE_RPD_LIMITS = _route_limit_defaults("rpd_limits")
DEFAULT_MODEL_RPM_LIMITS = dict(ROUTE_RPM_LIMITS)
DEFAULT_MODEL_RPM_LIMITS[DEFAULT_ANALYSIS_MODEL] = env_int(
    "DEFAULT_ANALYSIS_RPM_LIMIT",
    DEFAULT_MODEL_RPM_LIMITS.get(DEFAULT_ANALYSIS_MODEL, 30),
)
DEFAULT_MODEL_RPM_LIMITS[DEFAULT_DECISION_MODEL] = env_int(
    "DEFAULT_DECISION_RPM_LIMIT",
    DEFAULT_MODEL_RPM_LIMITS.get(DEFAULT_DECISION_MODEL, 5),
)
RPM_LIMITS = _load_model_limits("RPM_LIMITS_JSON", "DEFAULT_RPM_LIMIT", DEFAULT_MODEL_RPM_LIMITS, 5)
TPM_LIMITS = _load_model_limits("TPM_LIMITS_JSON", "DEFAULT_TPM_LIMIT", ROUTE_TPM_LIMITS, 0)
RPD_LIMITS = _load_model_limits("RPD_LIMITS_JSON", "DEFAULT_RPD_LIMIT", ROUTE_RPD_LIMITS, 0)


def format_model_routes(agent_models: Optional[dict[int, str]] = None, pipeline_id: str = "v1") -> str:
    models = agent_models or AGENT_MODELS
    agent_nums = list(get_pipeline_agents(pipeline_id))
    decision_agent = agent_nums[-1]
    analysis_agents = agent_nums[:-1]
    analysis_models = [models.get(agent_num, "N/A") for agent_num in analysis_agents]
    unique_analysis_models = list(dict.fromkeys(analysis_models))
    if len(unique_analysis_models) == 1 and analysis_agents:
        parts = [f"Agent {analysis_agents[0]}-{analysis_agents[-1]}: {unique_analysis_models[0]}"]
    else:
        parts = [", ".join(f"A{agent_num}: {models.get(agent_num, 'N/A')}" for agent_num in analysis_agents)]

    decision_model = models.get(decision_agent, "N/A")
    audit_models = list(dict.fromkeys([AUDIT_MODEL, *AUDIT_FALLBACK_MODELS]))
    audit_label = " → ".join(audit_models)
    if AUDIT_MODEL == decision_model and not AUDIT_FALLBACK_MODELS:
        parts.append(f"Agent {decision_agent}/稽核: {decision_model}")
    else:
        parts.append(f"Agent {decision_agent}: {decision_model}")
        parts.append(f"稽核: {audit_label}")

    if CONTEXT_DIGEST_MODEL and CONTEXT_DIGEST_MODEL not in unique_analysis_models:
        parts.append(f"提煉摘要: {CONTEXT_DIGEST_MODEL}")
    if TEAR_SHEET_MODEL and TEAR_SHEET_MODEL != CONTEXT_DIGEST_MODEL:
        parts.append(f"一頁式摘要: {TEAR_SHEET_MODEL}")
    fallback_models = list(dict.fromkeys(model for models_for_agent in AGENT_FALLBACK_MODELS.values() for model in models_for_agent))
    if fallback_models:
        parts.append("備援: " + ", ".join(fallback_models))
    return "；".join(parts)


__all__ = [name for name in globals() if name.isupper() or name.startswith(("format_", "get_", "is_"))]
