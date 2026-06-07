# ============================================================
# config.py - 系統配置：模型、速率限制、輸出目錄
# ============================================================

import os
import json
import re
from pathlib import Path
from typing import Optional

from agent_catalog import AGENT_NAMES
from pipeline_modes import get_pipeline_agents


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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return str(default or "").strip()
    return raw.strip()


def _env_list(name: str, default: Optional[list[str]] = None) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return list(default or [])
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in raw.split(",") if item.strip()]


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
TEAR_SHEET_MODEL = _env_str("TEAR_SHEET_MODEL", _route_str("tear_sheet_model", CONTEXT_DIGEST_MODEL))
AUDIT_MODEL = _env_str("AUDIT_MODEL", _route_str("audit_model", DEFAULT_DECISION_MODEL))
EMBEDDING_MODEL = _env_str("EMBEDDING_MODEL", _route_str("embedding_model", "gemini-embedding-2"))
REPORT_COVER_MODEL = _env_str("REPORT_COVER_MODEL", _route_str("report_cover_model", "imagen-4.0-generate-001"))
REPORT_COVER_FALLBACK_MODELS = _env_list(
    "REPORT_COVER_FALLBACK_MODELS",
    _route_list("report_cover_fallback_models"),
)
ENABLE_REPORT_COVER = _env_bool("ENABLE_REPORT_COVER", _env_bool("REPORT_COVER_ENABLED", True))
REPORT_COVER_IMAGE_SIZE = _env_str("REPORT_COVER_IMAGE_SIZE", _route_str("report_cover_image_size", "1K"))
REPORT_COVER_ASPECT_RATIO = _env_str("REPORT_COVER_ASPECT_RATIO", _route_str("report_cover_aspect_ratio", "16:9"))

RAG_ENABLED = _env_bool("RAG_ENABLED", _env_bool("ENABLE_RAG", True))
RAG_CHUNK_SIZE = _env_int("RAG_CHUNK_SIZE", 1600)
RAG_CHUNK_OVERLAP = _env_int("RAG_CHUNK_OVERLAP", 220)
RAG_MIN_SOURCE_CHARS = _env_int("RAG_MIN_SOURCE_CHARS", 280)
RAG_MAX_INDEX_CHUNKS = _env_int("RAG_MAX_INDEX_CHUNKS", 48)
RAG_MAX_CHUNKS_PER_AGENT = _env_int("RAG_MAX_CHUNKS_PER_AGENT", 5)
RAG_MAX_CONTEXT_CHARS = _env_int("RAG_MAX_CONTEXT_CHARS", 5200)
RAG_LARGE_CONTEXT_CHARS = _env_int("RAG_LARGE_CONTEXT_CHARS", 16000)
RAG_LARGE_CONTEXT_CHUNKS = _env_int("RAG_LARGE_CONTEXT_CHUNKS", 8)
RAG_EMBEDDING_CACHE_SECONDS = _env_int("RAG_EMBEDDING_CACHE_SECONDS", 30 * 24 * 60 * 60)

CONTEXT_TOTAL_CHAR_BUDGET = _env_int("CONTEXT_TOTAL_CHAR_BUDGET", 11000)
CONTEXT_PER_AGENT_CHAR_BUDGET = _env_int("CONTEXT_PER_AGENT_CHAR_BUDGET", 2200)
LARGE_CONTEXT_MODEL_PATTERN = _env_str("LARGE_CONTEXT_MODEL_PATTERN", r"(gemini|flash)")
LARGE_CONTEXT_TOTAL_CHAR_BUDGET = _env_int("LARGE_CONTEXT_TOTAL_CHAR_BUDGET", 28000)
LARGE_CONTEXT_PER_AGENT_CHAR_BUDGET = _env_int("LARGE_CONTEXT_PER_AGENT_CHAR_BUDGET", 5200)
BLIND_CONTEXT_AGENTS = {
    int(agent_num)
    for agent_num in _env_list("BLIND_CONTEXT_AGENTS", ["13"])
    if str(agent_num).strip().isdigit()
}

if not DEFAULT_ANALYSIS_MODEL or not DEFAULT_DECISION_MODEL:
    raise RuntimeError(
        "缺少模型路由設定。請設定 backend/model_routes.json、MODEL_ROUTES_FILE，"
        "或在 backend/.env 提供 DEFAULT_ANALYSIS_MODEL / DEFAULT_DECISION_MODEL。"
    )


def _load_agent_models() -> dict[int, str]:
    route_agents = _route_section("agents")
    models = {}
    decision_agents = {7, 16}
    for agent_num in sorted(AGENT_NAMES):
        default_model = DEFAULT_DECISION_MODEL if agent_num in decision_agents else DEFAULT_ANALYSIS_MODEL
        configured = route_agents.get(str(agent_num), default_model)
        models[agent_num] = str(configured or default_model).strip()

    for raw_key, value in _json_env_dict("AGENT_MODELS_JSON").items():
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
    default_analysis_fallbacks = _env_list(
        "DEFAULT_ANALYSIS_FALLBACK_MODELS",
        _route_list("analysis_fallback_models"),
    )
    models: dict[int, list[str]] = {}
    decision_agents = {7, 16}
    for agent_num in sorted(AGENT_NAMES):
        configured = route_fallbacks.get(str(agent_num), [] if agent_num in decision_agents else default_analysis_fallbacks)
        if isinstance(configured, list):
            models[agent_num] = [str(model).strip() for model in configured if str(model).strip()]
        elif isinstance(configured, str):
            models[agent_num] = [model.strip() for model in configured.split(",") if model.strip()]
        else:
            models[agent_num] = []

    for raw_key, value in _json_env_dict("AGENT_FALLBACK_MODELS_JSON").items():
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
        override = _env_list(f"AGENT_FALLBACK_MODELS_{agent_num}", models.get(agent_num, []))
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

    configured_models = {
        *AGENT_MODELS.values(),
        CONTEXT_DIGEST_MODEL,
        TEAR_SHEET_MODEL,
        AUDIT_MODEL,
        EMBEDDING_MODEL,
        REPORT_COVER_MODEL,
        *REPORT_COVER_FALLBACK_MODELS,
    }
    for fallback_models in AGENT_FALLBACK_MODELS.values():
        configured_models.update(fallback_models)
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
    if AUDIT_MODEL == decision_model:
        parts.append(f"Agent {decision_agent}/稽核: {decision_model}")
    else:
        parts.append(f"Agent {decision_agent}: {decision_model}")
        parts.append(f"稽核: {AUDIT_MODEL}")

    if CONTEXT_DIGEST_MODEL and CONTEXT_DIGEST_MODEL not in unique_analysis_models:
        parts.append(f"提煉摘要: {CONTEXT_DIGEST_MODEL}")
    if TEAR_SHEET_MODEL and TEAR_SHEET_MODEL != CONTEXT_DIGEST_MODEL:
        parts.append(f"一頁式摘要: {TEAR_SHEET_MODEL}")
    fallback_models = list(dict.fromkeys(model for models_for_agent in AGENT_FALLBACK_MODELS.values() for model in models_for_agent))
    if fallback_models:
        parts.append("備援: " + ", ".join(fallback_models))
    return "；".join(parts)

# Optional legacy pacing. Dynamic RPM/TPM buckets are authoritative by default.
INTER_AGENT_DELAY = _env_float("INTER_AGENT_DELAY", 0.0)

# 輸出目錄
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))

# CORS 白名單。若確定只做本機同源服務，可保留預設；雲端部署請用環境變數覆寫。
ALLOWED_ORIGINS = _env_list(
    "ALLOWED_ORIGINS",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)
MUTATION_API_TOKEN = _env_str("MUTATION_API_TOKEN", _env_str("ADMIN_API_TOKEN", ""))

# 本地持久化快取
CACHE_DIR = Path(os.getenv("CACHE_DIR", str(BASE_DIR / "cache")))
CACHE_DB_PATH = os.getenv("CACHE_DB_PATH", str(CACHE_DIR / "stock_agent_cache.sqlite3"))
DATA_SNAPSHOT_MAX_BYTES = _env_int("DATA_SNAPSHOT_MAX_BYTES", 2 * 1024 * 1024)
FINANCIAL_DATA_CACHE_SECONDS = int(os.getenv("FINANCIAL_DATA_CACHE_SECONDS", str(24 * 60 * 60)))
FINANCIAL_DATA_MARKET_CACHE_SECONDS = _env_int("FINANCIAL_DATA_MARKET_CACHE_SECONDS", 15 * 60)
FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS = _env_int(
    "FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS",
    FINANCIAL_DATA_CACHE_SECONDS,
)


def _load_source_freshness_seconds() -> dict[str, int]:
    defaults = {
        "market_data": FINANCIAL_DATA_MARKET_CACHE_SECONDS,
        "financial_statements": FINANCIAL_DATA_CACHE_SECONDS,
        "monthly_revenue": 24 * 60 * 60,
        "recent_catalysts": 30 * 60,
        "institutional_trading": 6 * 60 * 60,
        "dynamic_peer_metrics": 24 * 60 * 60,
        "peer_discovery": 24 * 60 * 60,
        "pe_river_chart": 24 * 60 * 60,
    }
    for key in list(defaults):
        env_name = f"SOURCE_FRESHNESS_{key.upper()}_SECONDS"
        defaults[key] = _env_int(env_name, defaults[key])
    for key, value in _json_env_dict("SOURCE_FRESHNESS_SECONDS_JSON").items():
        try:
            defaults[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return defaults


SOURCE_FRESHNESS_MAX_AGE_SECONDS = _load_source_freshness_seconds()

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
