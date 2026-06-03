# ============================================================
# config.py - 系統配置：模型、速率限制、輸出目錄
# ============================================================

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


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

# 各 Agent 的模型分配
# Agent 1-6 與提煉摘要：統一使用 gemma-4-31b-it
# Agent 7（最終投資決策）與最終稽核/修復：使用 gemini-3.5-flash
CONTEXT_DIGEST_MODEL = "gemma-4-31b-it"
AUDIT_MODEL = "gemini-3.5-flash"
AGENT_MODELS = {
    1: "gemma-4-31b-it",     # 商業模式與整體分析
    2: "gemma-4-31b-it",     # 五年財務數據分析
    3: "gemma-4-31b-it",     # 競爭護城河評估
    4: "gemma-4-31b-it",     # 估值分析
    5: "gemma-4-31b-it",     # 未來成長潛力
    6: "gemma-4-31b-it",     # 多空辯論
    7: "gemini-3.5-flash",   # 最終投資決策（綜合判斷）
}

# 速率限制（每個 API Key）
RPM_LIMITS = {
    "gemini-3.5-flash": 5,    # 每分鐘 5 次
    "gemma-4-31b-it": 30,     # 每分鐘 30 次
}

RPD_LIMITS = {
    "gemini-3.5-flash": 25,   # 每天 25 次
    "gemma-4-31b-it": 14400,  # 每天 14400 次
}

# Agent 呼叫之間的最小延遲（秒）
INTER_AGENT_DELAY = 13  # 保守設定，避免超過 RPM

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
