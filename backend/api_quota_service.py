"""Operator-facing API quota and reset-time summaries."""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

from config import API_KEYS, FMP_API_KEY, GOOGLE_CSE_ID, GOOGLE_SEARCH_API_KEY, RPD_LIMITS
from job_store import query_events


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


def _event_payload(event: dict) -> dict:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    return payload if isinstance(payload, dict) else {}


def _llm_usage_since(since_utc: datetime) -> dict:
    since_ts = since_utc.timestamp()
    events = query_events(limit=1000)
    calls = 0
    quota_errors = 0
    recent_quota = []
    models: dict[str, int] = {}
    for event in events:
        if float(event.get("created_at") or 0) < since_ts:
            continue
        payload = _event_payload(event)
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        model_id = str(metadata.get("model_id") or "unknown")
        phase = str(event.get("phase") or payload.get("phase") or "")
        message = str(payload.get("message") or "")
        if phase == "llm_model_call":
            calls += 1
            models[model_id] = models.get(model_id, 0) + 1
        if (
            phase == "llm_model_error"
            and (
                metadata.get("error_category") == "quota"
                or "429" in message
                or "quota" in message.lower()
                or "rate" in message.lower()
            )
        ):
            quota_errors += 1
            if len(recent_quota) < 5:
                recent_quota.append({
                    "at": event.get("created_at"),
                    "model_id": model_id,
                    "message": message[:180],
                })
    return {
        "observed_calls_since_reset": calls,
        "observed_model_calls": models,
        "observed_quota_errors_since_reset": quota_errors,
        "recent_quota_events": recent_quota,
    }


def _provider_attempts(providers: list[dict], provider_names: set[str]) -> dict:
    attempts = 0
    errors = 0
    latest = []
    for item in providers:
        provider = str(item.get("provider") or "")
        if provider not in provider_names:
            continue
        window = (item.get("windows") or {}).get("last_24h") or {}
        attempts += int(window.get("attempts") or item.get("attempts") or 0)
        errors += int(window.get("error_count") or item.get("error_count") or 0)
        latest.append({
            "source": item.get("source"),
            "provider": provider,
            "last_status": item.get("last_status"),
            "alert_level": item.get("alert_level"),
            "success_rate": item.get("success_rate"),
        })
    return {"observed_24h_attempts": attempts, "observed_24h_errors": errors, "providers": latest[:6]}


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
        "key_count": key_count,
        "daily_limit": daily_limit,
        "next_reset_at": _fmt_dt(next_reset_source),
        "next_reset_taipei": _fmt_dt(next_reset_taipei),
        "reset_label": reset_label,
        "usage": usage,
        "notes": notes,
    }


def build_api_quota_payload(provider_summary_fetcher) -> dict:
    """Build a compact quota dashboard from local observations."""
    pacific_next, pacific_tw = _next_reset_at(dt_time(0, 0), PACIFIC)
    pacific_prev_utc = _previous_reset_at(dt_time(0, 0), PACIFIC)
    fmp_next, fmp_tw = _next_reset_at(dt_time(15, 0), EST_FIXED)

    try:
        providers = provider_summary_fetcher(100)
    except Exception:
        providers = []

    gemini_usage = _llm_usage_since(pacific_prev_utc)
    google_usage = _provider_attempts(providers, {"Google Search"})
    fmp_usage = _provider_attempts(providers, {"FMP quote", "FMP news", "FMP news retry"})

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
                    "本機用量為 job event 估算；實際額度請以 AI Studio / Google Cloud 為準。",
                ],
            ),
            _quota_row(
                service="Google Custom Search",
                configured=bool(GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID),
                key_count=1 if GOOGLE_SEARCH_API_KEY else 0,
                next_reset_source=pacific_next,
                next_reset_taipei=pacific_tw,
                reset_label="每日 quota：Pacific Time 00:00",
                daily_limit={"default_free_queries_per_day": 100},
                usage=google_usage,
                notes=["Custom Search 免費每日 100 queries；實際付費上限以 Google Cloud Console 為準。"],
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
