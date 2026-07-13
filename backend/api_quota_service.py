"""Operator-facing API quota and reset-time summaries."""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from config import API_KEYS, FMP_API_KEY, RPD_LIMITS
from api_usage_store import summarize_llm_usage_since, summarize_provider_usage_since
from mapping_fields import safe_mapping_dict, safe_mapping_items, safe_sequence_items, safe_text
from notification_delivery_audit_context import safe_float, safe_int


TAIPEI = ZoneInfo("Asia/Taipei")
PACIFIC = ZoneInfo("America/Los_Angeles")
EST_FIXED = timezone(timedelta(hours=-5), "EST")


def _next_reset_at(reset_time: dt_time, tzinfo) -> tuple[datetime, datetime]:
    now = datetime.now(tzinfo)
    reset = datetime.combine(now.date(), reset_time, tzinfo=tzinfo)
    if now >= reset:
        reset = reset + timedelta(days=1)
    return reset, reset.astimezone(TAIPEI)


def _previous_reset_at(reset_time: dt_time, tzinfo) -> datetime:
    now = datetime.now(tzinfo)
    reset = datetime.combine(now.date(), reset_time, tzinfo=tzinfo)
    if now < reset:
        reset = reset - timedelta(days=1)
    return reset.astimezone(timezone.utc)


def _fmt_dt(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _llm_usage_since(since_utc: datetime) -> dict:
    return _usage_payload(summarize_llm_usage_since(since_utc))


def _provider_attempts(providers: list[dict], provider_names: set[str], since_utc: datetime) -> dict:
    usage = _usage_payload(summarize_provider_usage_since(since_utc, provider_names))
    latest = []
    for item in safe_sequence_items(providers):
        row = safe_mapping_dict(item) or {}
        provider = safe_text(row.get("provider")).strip()
        if provider not in provider_names:
            continue
        latest.append({
            "source": _text_or_unknown(row.get("source")),
            "provider": provider,
            "last_status": _text_or_unknown(row.get("last_status")),
            "alert_level": _text_or_unknown(row.get("alert_level")),
            "success_rate": _strict_optional_float(row.get("success_rate")),
        })
    return {**usage, "providers": latest[:6]}


def _quota_row(
    *,
    service: str,
    configured: bool,
    key_count: int,
    next_reset_source: datetime,
    next_reset_taipei: datetime,
    reset_label: str,
    daily_limit,
    usage: dict,
    notes: list[str],
) -> dict:
    return {
        "service": service,
        "configured": configured,
        "key_count": _strict_count(key_count),
        "daily_limit": _daily_limit_payload(daily_limit),
        "next_reset_at": _fmt_dt(next_reset_source),
        "next_reset_taipei": _fmt_dt(next_reset_taipei),
        "reset_label": reset_label,
        "usage": _usage_payload(usage),
        "notes": notes,
    }


def _daily_limit_payload(value: Any):
    if value is None:
        return None
    raw_limit = safe_mapping_dict(value)
    if raw_limit is not None:
        normalized = {}
        for raw_key, raw_value in safe_mapping_items(raw_limit):
            key = safe_text(raw_key).strip()
            if key:
                normalized[key] = _strict_count(raw_value)
        return normalized or None
    return _strict_count(value)


def _usage_payload(value: Any) -> dict:
    raw_usage = safe_mapping_dict(value) or {}
    normalized = {}
    count_fields = {
        "observed_calls_since_reset",
        "observed_quota_errors_since_reset",
        "observed_attempts_since_reset",
        "observed_errors_since_reset",
        "observed_24h_attempts",
        "observed_24h_errors",
    }
    for key, child in safe_mapping_items(raw_usage):
        if key in count_fields:
            normalized[key] = _strict_count(child)
        elif key == "observed_model_calls":
            normalized[key] = _count_map(child)
        else:
            normalized[key] = child
    return normalized


def _count_map(value: Any) -> dict[str, int]:
    normalized = {}
    for raw_key, raw_count in safe_mapping_items(safe_mapping_dict(value) or {}):
        key = safe_text(raw_key).strip()
        if key:
            normalized[key] = _strict_count(raw_count)
    return normalized


def _text_or_unknown(value: Any) -> str:
    return safe_text(value).strip() or "unknown"


def _strict_count(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return max(safe_int(value), 0)


def _strict_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0.0
    return safe_float(value)


def build_api_quota_payload(provider_summary_fetcher) -> dict:
    """Build a compact quota dashboard from local observations."""
    pacific_next, pacific_tw = _next_reset_at(dt_time(0, 0), PACIFIC)
    pacific_prev_utc = _previous_reset_at(dt_time(0, 0), PACIFIC)
    fmp_next, fmp_tw = _next_reset_at(dt_time(15, 0), EST_FIXED)
    fmp_prev_utc = _previous_reset_at(dt_time(15, 0), EST_FIXED)

    try:
        providers = provider_summary_fetcher(100)
    except Exception:
        providers = []

    gemini_usage = _llm_usage_since(pacific_prev_utc)
    fmp_usage = _provider_attempts(providers, {"FMP quote", "FMP stable quote", "FMP news", "FMP news retry"}, fmp_prev_utc)

    return {
        "generated_at": _fmt_dt(datetime.now(TAIPEI)),
        "timezone": "Asia/Taipei",
        "services": [
            _quota_row(
                service="Gemini / Google AI",
                configured=bool(API_KEYS),
                key_count=len(API_KEYS),
                next_reset_source=pacific_next,
                next_reset_taipei=pacific_tw,
                reset_label="RPD 每日額度：Pacific Time 00:00",
                daily_limit=RPD_LIMITS or None,
                usage=gemini_usage,
                notes=[
                    "Gemini RPD 依 Google project 計算，不是依單支 API key 分開計算。",
                    "本機用量來自 api_usage_events ledger；實際額度請以 AI Studio / Google Cloud 為準。",
                ],
            ),
            _quota_row(
                service="Financial Modeling Prep",
                configured=bool(FMP_API_KEY),
                key_count=1 if FMP_API_KEY else 0,
                next_reset_source=fmp_next,
                next_reset_taipei=fmp_tw,
                reset_label="每日 API calls：3 PM EST",
                daily_limit={"basic_free_calls_per_day": 250},
                usage=fmp_usage,
                notes=["FMP FAQ 使用 EST 字樣；若其系統依美東夏令時間運作，台灣時間可能提早 1 小時。"],
            ),
        ],
    }
