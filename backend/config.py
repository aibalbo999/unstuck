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
        if key and key not in os.environ:
            os.environ[key] = value


def _split_keys(raw: str) -> list[str]:
    return [key.strip() for key in raw.replace("\n", ",").split(",") if key.strip()]


def _load_api_keys() -> list[str]:
    _load_local_env()

    keys = []
    for env_name in ("GEMINI_API_KEYS", "GOOGLE_API_KEYS"):
        keys.extend(_split_keys(os.getenv(env_name, "")))

    for i in range(1, 11):
        key = os.getenv(f"GOOGLE_API_KEY_{i}") or os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append(key.strip())

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(keys))


# API keys must come from environment variables or backend/.env.
# See backend/.env.example for local setup.
API_KEYS = _load_api_keys()

# 各 Agent 的模型分配
# gemini-3.5-flash：複雜推理分析（商業、估值、辯論、決策）
# gemma-4-31b-it：資料處理分析（財務、護城河、成長）
AGENT_MODELS = {
    1: "gemini-3.5-flash",   # 商業模式與整體分析（需深度推理）
    2: "gemma-4-31b-it",     # 五年財務數據分析（資料密集）
    3: "gemma-4-31b-it",     # 競爭護城河評估（結構化評分）
    4: "gemini-3.5-flash",   # 估值分析（複雜金融建模）
    5: "gemma-4-31b-it",     # 未來成長潛力（市場分析）
    6: "gemini-3.5-flash",   # 多空辯論（創意對話生成）
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
