"""External data provider and API-key settings."""

from __future__ import annotations

import os

from .env import is_placeholder_key, load_local_env, split_keys


def _load_api_keys() -> list[str]:
    load_local_env()
    keys = []
    for env_name in ("GEMINI_API_KEYS", "GOOGLE_API_KEYS"):
        keys.extend(split_keys(os.getenv(env_name, "")))

    for i in range(1, 11):
        key = os.getenv(f"GOOGLE_API_KEY_{i}") or os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append(key.strip())

    return [key for key in dict.fromkeys(keys) if not is_placeholder_key(key)]


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

FMP_API_KEY = os.getenv("FMP_API_KEY", "").strip()
FMP_BASE_URL = os.getenv("FMP_BASE_URL", "https://financialmodelingprep.com/stable").rstrip("/")
FINMIND_API_TOKEN = os.getenv("FINMIND_API_TOKEN", "").strip()
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "").strip()
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "").strip()
GOOGLE_SEARCH_REFERER = os.getenv("GOOGLE_SEARCH_REFERER", "").strip()
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "").strip()
BING_SEARCH_ENDPOINT = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()
WEB_SEARCH_PROVIDER_ORDER = os.getenv("WEB_SEARCH_PROVIDER_ORDER", "tavily,serpapi,google_news_rss,gdelt,yahoo_rss,brave").strip()
CATALYST_LOOKBACK_DAYS = int(os.getenv("CATALYST_LOOKBACK_DAYS", "30"))
INSTITUTIONAL_LOOKBACK_DAYS = int(os.getenv("INSTITUTIONAL_LOOKBACK_DAYS", "30"))
WACC_COST_OF_EQUITY_DEFAULT_PCT = float(os.getenv("WACC_COST_OF_EQUITY_PCT", "10.0"))
WACC_COST_OF_DEBT_DEFAULT_PCT = float(os.getenv("WACC_COST_OF_DEBT_PCT", "3.0"))
WACC_TAX_RATE_DEFAULT_PCT = float(os.getenv("WACC_TAX_RATE_PCT", "20.0"))


__all__ = [name for name in globals() if name.isupper() or name in {"has_api_keys", "refresh_api_keys"}]
