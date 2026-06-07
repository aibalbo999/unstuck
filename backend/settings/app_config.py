"""Compatibility aggregator for grouped application settings."""

from __future__ import annotations

from .models import *  # noqa: F401,F403
from .providers import *  # noqa: F401,F403
from .runtime_limits import *  # noqa: F401,F403
from .security import *  # noqa: F401,F403
from .storage import *  # noqa: F401,F403


def validate_runtime_settings() -> list[str]:
    """Return startup configuration warnings without exposing secrets."""
    warnings = []
    if not DEFAULT_ANALYSIS_MODEL or not DEFAULT_DECISION_MODEL:
        warnings.append("DEFAULT_ANALYSIS_MODEL / DEFAULT_DECISION_MODEL 未設定。")
    if DATA_SNAPSHOT_MAX_BYTES <= 0:
        warnings.append("DATA_SNAPSHOT_MAX_BYTES 必須大於 0。")
    if ANALYSIS_WORKER_COUNT <= 0:
        warnings.append("ANALYSIS_WORKER_COUNT 必須大於 0。")
    if LLM_AGENT_CALL_TIMEOUT_SECONDS < 0:
        warnings.append("LLM_AGENT_CALL_TIMEOUT_SECONDS 不可為負數。")
    if not ALLOWED_ORIGINS:
        warnings.append("ALLOWED_ORIGINS 為空，瀏覽器前端可能無法呼叫 API。")
    invalid_freshness = [
        source for source, seconds in SOURCE_FRESHNESS_MAX_AGE_SECONDS.items()
        if int(seconds) <= 0
    ]
    if invalid_freshness:
        warnings.append("SOURCE_FRESHNESS_*_SECONDS 必須大於 0：" + ", ".join(sorted(invalid_freshness)))
    return warnings


__all__ = [name for name in globals() if name.isupper() or name in {"has_api_keys", "refresh_api_keys", "validate_runtime_settings"} or name.startswith(("format_", "get_", "is_"))]
