"""External data provider and API-key settings."""

from __future__ import annotations

import os

from .env import is_placeholder_key, load_local_env, split_keys


def _load_keys(env_names: tuple[str, ...], numbered_prefixes: tuple[str, ...]) -> list[str]:
    load_local_env()
    keys = _load_numbered_keys(numbered_prefixes)
    for env_name in env_names:
        keys.extend(split_keys(os.getenv(env_name, "")))

    return [key for key in dict.fromkeys(keys) if not is_placeholder_key(key)]


def _load_numbered_keys(prefixes: tuple[str, ...]) -> list[str]:
    indexes = set()
    for env_name in os.environ:
        for prefix in prefixes:
            marker = f"{prefix}_"
            if env_name.startswith(marker) and env_name[len(marker) :].isdigit():
                indexes.add(int(env_name[len(marker) :]))

    keys = []
    for index in sorted(indexes):
        raw = next((os.getenv(f"{prefix}_{index}", "") for prefix in prefixes if os.getenv(f"{prefix}_{index}")), "")
        keys.extend(split_keys(raw))
    return keys


def _load_api_keys() -> list[str]:
    return _load_keys(("GEMINI_API_KEYS", "GOOGLE_API_KEYS"), ("GOOGLE_API_KEY", "GEMINI_API_KEY"))


def _load_llm_api_keys_by_provider() -> dict[str, list[str]]:
    return {
        "google": _load_api_keys(),
        "openai": _load_keys(("OPENAI_API_KEYS", "OPENAI_API_KEY"), ("OPENAI_API_KEY",)),
        "anthropic": _load_keys(("ANTHROPIC_API_KEYS", "ANTHROPIC_API_KEY"), ("ANTHROPIC_API_KEY",)),
    }


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


API_KEYS = []
LLM_API_KEYS_BY_PROVIDER = {}


def refresh_api_keys() -> list[str]:
    provider_keys = _load_llm_api_keys_by_provider()
    API_KEYS[:] = provider_keys.get("google", [])
    LLM_API_KEYS_BY_PROVIDER.clear()
    LLM_API_KEYS_BY_PROVIDER.update(provider_keys)
    return API_KEYS


def has_api_keys() -> bool:
    refresh_api_keys()
    return any(LLM_API_KEYS_BY_PROVIDER.values())


API_KEY_SETUP_MESSAGE = (
    "未設定 LLM API key。請設定 GEMINI_API_KEY_1 / GOOGLE_API_KEY_1 等序號格式，"
    "或使用 legacy GEMINI_API_KEYS / GOOGLE_API_KEYS；跨供應商 fallback 可設定 "
    "OPENAI_API_KEYS / ANTHROPIC_API_KEYS。"
)


refresh_api_keys()

FMP_API_KEY = os.getenv("FMP_API_KEY", "").strip()
FMP_BASE_URL = os.getenv("FMP_BASE_URL", "https://financialmodelingprep.com/stable").rstrip("/")
FINMIND_API_TOKEN = os.getenv("FINMIND_API_TOKEN", "").strip()
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "").strip()
BING_SEARCH_ENDPOINT = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()
WEB_SEARCH_PROVIDER_ORDER = os.getenv("WEB_SEARCH_PROVIDER_ORDER", "tavily,serpapi,google_news_rss,gdelt,yahoo_rss,brave").strip()
CATALYST_LOOKBACK_DAYS = int(os.getenv("CATALYST_LOOKBACK_DAYS", "30"))
SEARCH_CATALYST_MAX_RESULTS = _env_int("SEARCH_CATALYST_MAX_RESULTS", 8)
SEARCH_PEER_DISCOVERY_MAX_RESULTS = _env_int("SEARCH_PEER_DISCOVERY_MAX_RESULTS", 8)
SEARCH_MIN_UNIQUE_SOURCES = _env_int("SEARCH_MIN_UNIQUE_SOURCES", 3)
SEARCH_PROVIDER_EXPANSION_MIN_RESULTS = _env_int("SEARCH_PROVIDER_EXPANSION_MIN_RESULTS", 3)
INSTITUTIONAL_LOOKBACK_DAYS = int(os.getenv("INSTITUTIONAL_LOOKBACK_DAYS", "30"))
WACC_COST_OF_EQUITY_DEFAULT_PCT = float(os.getenv("WACC_COST_OF_EQUITY_PCT", "10.0"))
WACC_COST_OF_DEBT_DEFAULT_PCT = float(os.getenv("WACC_COST_OF_DEBT_PCT", "3.0"))
WACC_TAX_RATE_DEFAULT_PCT = float(os.getenv("WACC_TAX_RATE_PCT", "20.0"))
WACC_EQUITY_RISK_PREMIUM_DEFAULT_PCT = float(os.getenv("WACC_EQUITY_RISK_PREMIUM_PCT", "5.5"))
WACC_CREDIT_SPREAD_DEFAULT_PCT = float(os.getenv("WACC_CREDIT_SPREAD_PCT", "1.5"))


__all__ = [name for name in globals() if name.isupper() or name in {"has_api_keys", "refresh_api_keys"}]
