"""Provider error classification helpers for agent retry policy."""

from __future__ import annotations

import re

from llm_client import is_auth_error, is_missing_model_error, is_quota_or_rate_error
from llm_rate_limits import AllKeysRpdDisabledError


def _is_server_5xx_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return bool(re.search(r"\b5\d{2}\b", normalized)) or any(
        marker in normalized
        for marker in [
            "internal server",
            "service unavailable",
            "server error",
            "backend error",
            "overloaded",
            "high demand",
        ]
    )


def _is_invalid_argument_error(error_msg: str) -> bool:
    """Return True for permanent 400 INVALID_ARGUMENT provider contract errors."""
    normalized = (error_msg or "").lower()
    return "400" in normalized and "invalid_argument" in normalized


def _is_transient_provider_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return any(
        marker in normalized
        for marker in [
            "503",
            "500",
            "unavailable",
            "deadline",
            "timeout",
            "temporarily",
            "connection",
        ]
    )


def _key_slot(api_key: str | None, rotator) -> tuple[int | None, int | None]:
    keys = list(getattr(rotator, "keys", []) or [])
    if not api_key or not keys:
        return None, len(keys) or None
    try:
        return keys.index(api_key) + 1, len(keys)
    except ValueError:
        return None, len(keys)


def _agent_error_category(exc: Exception) -> str:
    error_msg = str(exc)
    if isinstance(exc, AllKeysRpdDisabledError):
        return "quota"
    if is_auth_error(error_msg):
        return "auth"
    if is_quota_or_rate_error(error_msg):
        return "quota"
    if is_missing_model_error(error_msg):
        return "missing_model"
    if _is_invalid_argument_error(error_msg):
        return "schema_error"
    if _is_server_5xx_error(error_msg):
        return "server_5xx"
    if _is_transient_provider_error(error_msg):
        return "timeout" if "timeout" in error_msg.lower() or "deadline" in error_msg.lower() else "provider"
    return "provider"
