"""Notification delivery failure reason buckets."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text


def failure_reason_bucket(error: Any) -> str:
    value = safe_text(error).strip().lower()
    if not value:
        return "unknown"
    if any(marker in value for marker in ("429", "rate limit", "too many requests")):
        return "rate_limited"
    if any(marker in value for marker in ("timeout", "timed out", "deadline")):
        return "timeout"
    if any(marker in value for marker in ("401", "403", "unauthorized", "forbidden", "auth", "token", "credential")):
        return "auth"
    if any(marker in value for marker in ("missing", "not configured", "configuration", "config", "env", "webhook url")):
        return "configuration"
    if any(marker in value for marker in ("dns", "network", "connection", "refused", "reset")):
        return "network"
    return "other"
