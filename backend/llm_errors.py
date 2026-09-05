"""Secret-safe quota and model availability error helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from llm_quota_details import describe_quota_details, extract_quota_details


def is_quota_or_rate_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    return (
        bool(re.search(r"\b429\b", normalized))
        or "quota" in compact
        or "resourceexhausted" in compact
        or "ratelimit" in compact
        or "retryafter" in compact
        or "requestsperminute" in compact
        or "tokensperminute" in compact
        or "requestsperday" in compact
        or bool(re.search(r"\brate\s+limit(?:ed|ing|s)?\b", normalized))
        or bool(re.search(r"\btoo\s+many\s+requests\b", normalized))
    )


def is_requests_per_day_error(error: Any) -> bool:
    """Return True only for explicit per-day request quota exhaustion."""
    if any(item["kind"] == "rpd" for item in extract_quota_details(error)["violations"]):
        return True
    details = getattr(error, "details", None)
    raw = " ".join([str(error), json.dumps(details, ensure_ascii=False) if details else ""])
    normalized = raw.lower()
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    snake = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")

    explicit_rpd_markers = (
        "requestsperday" in compact
        or "generaterequestsperday" in compact
        or "requests_per_day" in snake
        or "request_per_day" in snake
        or "per_day" in snake
    )
    if not explicit_rpd_markers:
        return False

    rpm_or_tpm_markers = (
        "requestsperminute" in compact
        or "tokensperminute" in compact
        or "requests_per_minute" in snake
        or "tokens_per_minute" in snake
        or bool(re.search(r"\b[rt]pm\b", normalized))
    )
    return not rpm_or_tpm_markers


def is_auth_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    return (
        bool(re.search(r"\b401\b", normalized))
        or "unauthenticated" in normalized
        or "apikeynotvalid" in compact
        or "invalidapikey" in compact
        or "api_key_invalid" in normalized
        or (
            "boundserviceaccount" in compact
            and ("deletedordisabled" in compact or "mustbeactive" in compact)
        )
    )


def retry_delay_seconds(error: Any, default: float = 60) -> float:
    parsed = extract_quota_details(error)["retry_delay_seconds"]
    if parsed is not None:
        return parsed
    details = getattr(error, "details", None)
    raw = " ".join([str(error), json.dumps(details, ensure_ascii=False) if details else ""])
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", raw, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r"retry(?:_|-)?after['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)", raw, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return default


def describe_quota_or_rate_error(error: Any) -> str:
    """Return a concise, secret-safe description of a Google quota/rate error."""
    return describe_quota_details(error)


def is_missing_model_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return "404" in normalized or "not found" in normalized
