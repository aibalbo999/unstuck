"""Secret-safe quota and model availability error helpers."""

from __future__ import annotations

import json
import re
from typing import Any


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
    raw = str(error)
    details = getattr(error, "details", None)
    code = getattr(error, "code", None)
    status = getattr(error, "status", None)
    message = getattr(error, "message", None)

    found: list[str] = []
    seen: set[str] = set()

    def add(label: str, value: Any):
        if value is None or value == "":
            return
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        text = f"{label}={value}"
        if text not in seen:
            seen.add(text)
            found.append(text)

    def walk(value: Any):
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in {"quotametric", "quotaid", "quotavalue", "retrydelay", "reason"}:
                    add(key, item)
                elif lowered == "quotadimensions" and isinstance(item, dict):
                    for dim_key in ("model", "location"):
                        if dim_key in item:
                            add(f"quotaDimensions.{dim_key}", item[dim_key])
                elif lowered == "metadata" and isinstance(item, dict):
                    for meta_key, meta_value in item.items():
                        meta_lowered = str(meta_key).lower()
                        if "quota" in meta_lowered and meta_lowered != "consumer":
                            add(f"metadata.{meta_key}", meta_value)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(details)

    signature = " ".join([raw, json.dumps(details, ensure_ascii=False) if details else ""]).lower()
    if "tokensperminute" in signature or "tokens_per_minute" in signature or "tpm" in signature:
        condition = "每分鐘 token 額度（TPM）"
    elif "requestsperminute" in signature or "requests_per_minute" in signature or "rpm" in signature:
        condition = "每分鐘請求額度（RPM）"
    elif "requestsperday" in signature or "requests_per_day" in signature or "perday" in signature:
        condition = "每日請求額度（RPD）"
    elif "free_tier" in signature or "free-tier" in signature or "freetier" in signature:
        condition = "免費層/專案配額"
    else:
        condition = "Google API 配額或速率限制（未提供細項）"

    summary_parts = []
    if code or status:
        summary_parts.append(" ".join(str(x) for x in (code, status) if x))
    if message:
        summary_parts.append(str(message))
    summary_parts.append(condition)
    summary_parts.extend(found[:6])

    return "；".join(summary_parts)


def is_missing_model_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return "404" in normalized or "not found" in normalized
