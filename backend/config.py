# ============================================================
# config.py - 系統配置：模型、速率限制、輸出目錄
# ============================================================

import os
import json
import re
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_ROUTES_FILE = BASE_DIR / "model_routes.json"


def _load_local_env():
    """Load backend/.env for local runs without adding a dependency."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (key not in os.environ or _is_placeholder_key(os.environ[key])):
            os.environ[key] = value


def _split_keys(raw: str) -> list[str]:
    return [key.strip() for key in raw.replace("\n", ",").split(",") if key.strip()]


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return str(default or "").strip()
    return raw.strip()


def _json_env_dict(name: str) -> dict:
    raw = os.getenv(name, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _load_model_routes() -> dict:
    routes_path = Path(_env_str("MODEL_ROUTES_FILE", str(DEFAULT_MODEL_ROUTES_FILE))).expanduser()
    if not routes_path.exists():
        return {}
    try:
        parsed = json.loads(routes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _route_section(section_name: str) -> dict:
    section = MODEL_ROUTES.get(section_name, {})
    return section if isinstance(section, dict) else {}


def _route_str(name: str, default: str = "") -> str:
    return str(MODEL_ROUTES.get(name, default) or "").strip()


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


def _is_placeholder_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        marker in lowered
        for marker in [
            "replace_with",
            "your_key",
            "example",
            "placeholder",
        ]
    )


def _load_api_keys() -> list[str]:
    _load_local_env()

    keys = []
    for env_name in ("GEMINI_API_KEYS", "GOOGLE_API_KEYS"):
        keys.extend(_split_keys(os.getenv(env_name, "")))

    for i in range(1, 11):
        key = os.getenv(f"GOOGLE_API_KEY_{i}") or os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append(key.strip())

    # Preserve order while removing duplicates and ignoring unedited examples.
    return [key for key in dict.fromkeys(keys) if not _is_placeholder_key(key)]


# API keys must come from environment variables or backend/.env.
# See backend/.env.example for local setup. Keep the same list object so modules
# importing API_KEYS see refreshes made after the server starts.
API_KEYS = []


def refresh_api_keys() -> list[str]:
    API_KEYS[:] = _load_api_keys()
    return API_KEYS


def has_api_keys() -> bool:
    return bool(refresh_api_keys())


API_KEY_SETUP_MESSAGE = (
    "未設定 Gemini API key。請設定 GEMINI_API_KEYS / GOOGLE_API_KEYS，"
    "或在 backend/.env 放入 GEMINI_API_KEYS=key1,key2，然後重新啟動系統。"
)


refresh_api_keys()

MODEL_ROUTES = _load_model_routes()

DEFAULT_ANALYSIS_MODEL = _env_str("DEFAULT_ANALYSIS_MODEL", _route_str("default_analysis_model"))
DEFAULT_DECISION_MODEL = _env_str("DEFAULT_DECISION_MODEL", _route_str("default_decision_model"))
CONTEXT_DIGEST_MODEL = _env_str("CONTEXT_DIGEST_MODEL", _route_str("context_digest_model", DEFAULT_ANALYSIS_MODEL))
AUDIT_MODEL = _env_str("AUDIT_MODEL", _route_str("audit_model", DEFAULT_DECISION_MODEL))

if not DEFAULT_ANALYSIS_MODEL or not DEFAULT_DECISION_MODEL:
    raise RuntimeError(
        "缺少模型路由設定。請設定 backend/model_routes.json、MODEL_ROUTES_FILE，"
        "或在 backend/.env 提供 DEFAULT_ANALYSIS_MODEL / DEFAULT_DECISION_MODEL。"
    )


def _load_agent_models() -> dict[int, str]:
    route_agents = _route_section("agents")
    models = {}
    for agent_num in range(1, 7):
        configured = route_agents.get(str(agent_num), DEFAULT_ANALYSIS_MODEL)
        models[agent_num] = str(configured or DEFAULT_ANALYSIS_MODEL).strip()
    models[7] = str(route_agents.get("7", DEFAULT_DECISION_MODEL) or DEFAULT_DECISION_MODEL).strip()

    for raw_key, value in _json_env_dict("AGENT_MODELS_JSON").items():
        try:
            agent_num = int(raw_key)
        except (TypeError, ValueError):
            continue
        if 1 <= agent_num <= 7 and str(value).strip():
            models[agent_num] = str(value).strip()

    for agent_num in range(1, 8):
        override = os.getenv(f"AGENT_MODEL_{agent_num}", "").strip()
        if override:
            models[agent_num] = override

    return models


def _load_model_limits(json_env_name: str, default_env_name: str, builtins: dict[str, int], default_limit: int) -> dict[str, int]:
    limits = {"*": _env_int(default_env_name, default_limit)}
    limits.update(builtins)
    for model, value in _json_env_dict(json_env_name).items():
        try:
            limits[str(model)] = int(value)
        except (TypeError, ValueError):
            continue

    configured_models = {*AGENT_MODELS.values(), CONTEXT_DIGEST_MODEL, AUDIT_MODEL}
    for model in configured_models:
        suffix = _model_env_suffix(model)
        override = os.getenv(f"{json_env_name.removesuffix('_JSON')}_{suffix}", "").strip()
        if override:
            try:
                limits[model] = int(override)
            except ValueError:
                pass
    return limits


AGENT_MODELS = _load_agent_models()

# Per-key dynamic limits used by llm_client.KeyRotator. Override in backend/.env.
ROUTE_RPM_LIMITS = _route_limit_defaults("rpm_limits")
ROUTE_TPM_LIMITS = _route_limit_defaults("tpm_limits")
ROUTE_RPD_LIMITS = _route_limit_defaults("rpd_limits")
DEFAULT_MODEL_RPM_LIMITS = dict(ROUTE_RPM_LIMITS)
DEFAULT_MODEL_RPM_LIMITS[DEFAULT_ANALYSIS_MODEL] = _env_int(
    "DEFAULT_ANALYSIS_RPM_LIMIT",
    DEFAULT_MODEL_RPM_LIMITS.get(DEFAULT_ANALYSIS_MODEL, 30),
)
DEFAULT_MODEL_RPM_LIMITS[DEFAULT_DECISION_MODEL] = _env_int(
    "DEFAULT_DECISION_RPM_LIMIT",
    DEFAULT_MODEL_RPM_LIMITS.get(DEFAULT_DECISION_MODEL, 5),
)
RPM_LIMITS = _load_model_limits(
    "RPM_LIMITS_JSON",
    "DEFAULT_RPM_LIMIT",
    DEFAULT_MODEL_RPM_LIMITS,
    5,
)
TPM_LIMITS = _load_model_limits("TPM_LIMITS_JSON", "DEFAULT_TPM_LIMIT", ROUTE_TPM_LIMITS, 0)
RPD_LIMITS = _load_model_limits("RPD_LIMITS_JSON", "DEFAULT_RPD_LIMIT", ROUTE_RPD_LIMITS, 0)


def format_model_routes(agent_models: Optional[dict[int, str]] = None) -> str:
    models = agent_models or AGENT_MODELS
    analysis_models = [models.get(agent_num, "N/A") for agent_num in range(1, 7)]
    unique_analysis_models = list(dict.fromkeys(analysis_models))
    if len(unique_analysis_models) == 1:
        parts = [f"Agent 1-6: {unique_analysis_models[0]}"]
    else:
        parts = [", ".join(f"A{agent_num}: {models.get(agent_num, 'N/A')}" for agent_num in range(1, 7))]

    decision_model = models.get(7, "N/A")
    if AUDIT_MODEL == decision_model:
        parts.append(f"Agent 7/稽核: {decision_model}")
    else:
        parts.append(f"Agent 7: {decision_model}")
        parts.append(f"稽核: {AUDIT_MODEL}")

    if CONTEXT_DIGEST_MODEL and CONTEXT_DIGEST_MODEL not in unique_analysis_models:
        parts.append(f"提煉摘要: {CONTEXT_DIGEST_MODEL}")
    return "；".join(parts)

# Optional legacy pacing. Dynamic RPM/TPM buckets are authoritative by default.
INTER_AGENT_DELAY = _env_float("INTER_AGENT_DELAY", 0.0)

# 輸出目錄
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))

# 本地持久化快取
CACHE_DIR = Path(os.getenv("CACHE_DIR", str(BASE_DIR / "cache")))
CACHE_DB_PATH = os.getenv("CACHE_DB_PATH", str(CACHE_DIR / "stock_agent_cache.sqlite3"))
FINANCIAL_DATA_CACHE_SECONDS = int(os.getenv("FINANCIAL_DATA_CACHE_SECONDS", str(24 * 60 * 60)))

# 可選外部資料備援來源
FMP_API_KEY = os.getenv("FMP_API_KEY", "").strip()
FMP_BASE_URL = os.getenv("FMP_BASE_URL", "https://financialmodelingprep.com/stable").rstrip("/")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "").strip()
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "").strip()
CATALYST_LOOKBACK_DAYS = int(os.getenv("CATALYST_LOOKBACK_DAYS", "30"))
INSTITUTIONAL_LOOKBACK_DAYS = int(os.getenv("INSTITUTIONAL_LOOKBACK_DAYS", "30"))

# 報告生命週期
REPORT_RETENTION_DAYS = int(os.getenv("REPORT_RETENTION_DAYS", "30"))
REPORT_CLEANUP_INTERVAL_SECONDS = int(os.getenv("REPORT_CLEANUP_INTERVAL_SECONDS", str(24 * 60 * 60)))

# 本地分析任務佇列 worker 數
ANALYSIS_WORKER_COUNT = int(os.getenv("ANALYSIS_WORKER_COUNT", "2"))
TASK_QUEUE_BACKEND = os.getenv("TASK_QUEUE_BACKEND", "local").strip().lower()
TASK_QUEUE_NAME = os.getenv("TASK_QUEUE_NAME", "stock-analysis")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TASK_DB_PATH = os.getenv("TASK_DB_PATH", str(CACHE_DIR / "analysis_jobs.sqlite3"))
ANALYSIS_JOB_STALE_SECONDS = int(os.getenv("ANALYSIS_JOB_STALE_SECONDS", str(6 * 60 * 60)))
