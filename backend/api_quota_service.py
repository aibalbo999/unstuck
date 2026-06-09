"""Operator-facing API quota and reset-time summaries."""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

from config import API_KEYS, FMP_API_KEY, GOOGLE_CSE_ID, GOOGLE_SEARCH_API_KEY, RPD_LIMITS
from api_usage_store import summarize_llm_usage_since, summarize_provider_usage_since


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
    return summarize_llm_usage_since(since_utc)


def _provider_attempts(providers: list[dict], provider_names: set[str], since_utc: datetime) -> dict:
    usage = summarize_provider_usage_since(since_utc, provider_names)
    latest = []
    for item in providers:
        provider = str(item.get("provider") or "")
        if provider not in provider_names:
            continue
        latest.append({
            "source": item.get("source"),
            "provider": provider,
            "last_status": item.get("last_status"),
            "alert_level": item.get("alert_level"),
            "success_rate": item.get("success_rate"),
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
    fmp_prev_utc = _previous_reset_at(dt_time(15, 0), EST_FIXED)

    try:
        providers = provider_summary_fetcher(100)
    except Exception:
        providers = []

    gemini_usage = _llm_usage_since(pacific_prev_utc)
    google_usage = _provider_attempts(providers, {"Google Search"}, pacific_prev_utc)
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
