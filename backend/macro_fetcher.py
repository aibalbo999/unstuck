"""FRED macro indicator fetcher for macro strategy agents."""

from __future__ import annotations

import os
import time
import math
import hashlib
from datetime import date, timedelta
from typing import Any

from external_http_client import sync_get


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_CACHE_TTL_SECONDS = 15 * 60


def fetch_key_macro_indicators(
    *,
    api_key: str | None = None,
    session: Any | None = None,
    use_cache: bool = True,
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    timeout: float = 15,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    """Fetch DGS10, CPI YoY, and VIX from FRED and return agent-ready context."""
    key = api_key or os.getenv("FRED_API_KEY")
    if not key:
        return {
            "status": "not_configured",
            "source": "FRED",
            "message": "FRED_API_KEY 未設定，略過總經資料抓取。",
        }

    from shared_provider_cache import shared_fetch
    from source_observation_freshness import observation_recency

    evaluated_at = time.time() if now_epoch is None else now_epoch

    definitions = (
        ("us_10y_yield", "DGS10", "美國10年期公債殖利率", "%"),
        ("us_cpi_yoy", "CPIAUCSL", "CPI年增率", "%"),
        ("vix", "VIXCLS", "VIX", "index"),
    )
    indicators, components = {}, {}
    credential_scope = hashlib.sha256(key.encode()).hexdigest()[:16]
    for name, series, label, unit in definitions:
        def acquire(series=series):
            return (_cpi_yoy_observation(session, key, timeout=timeout) if series == "CPIAUCSL"
                    else _latest_observation(session, key, series, timeout=timeout))
        observation, meta = shared_fetch(
            f"FRED:{credential_scope}:{series}:v2", acquire,
            freshness_seconds=cache_ttl_seconds,
            retention_seconds=7 * 86400 if series == "CPIAUCSL" else 86400,
            use_cache=use_cache,
        )
        recency = observation_recency(observation.get("date") if observation else None,
                                      ticker="US", now_epoch=evaluated_at,
                                      max_age_days=90 if series == "CPIAUCSL" else 7)
        observation_status = recency["observation_status"]
        meta = {**meta, **recency, "stale": bool(meta.get("stale")) or bool(observation and observation_status != "recent")}
        component_status = ("unavailable" if not observation else "success" if not meta["stale"] else
                            observation_status if observation_status in {"unknown", "future"} else "stale")
        components[name] = {"series_id": series, "status": component_status, **meta,
                            "as_of": recency["observed_at"],
                            "reason_code": f"observation_{observation_status}" if observation_status != "recent" else
                                           "cache_expired" if meta["stale"] else "observation_recent"}
        if observation:
            indicators[name] = {"series_id": series, "label": label, "unit": unit,
                                **observation, **meta, "status": component_status}
    fresh_count = sum(item["status"] == "success" for item in components.values())
    status = ("success" if fresh_count == 3 else "partial" if fresh_count else
              "stale" if indicators else "unavailable")
    result = {
        "status": status, "source": "FRED", "actual_provider": "FRED",
        "source_url": "https://fred.stlouisfed.org/", "indicators": indicators,
        "component_statuses": components,
        "cache_hit": bool(indicators) and all(item.get("cache_hit") for item in components.values()),
        "stale": any(item.get("stale") for item in components.values()),
    }
    if status != "success":
        result["message"] = "FRED 部分指標不足或僅有過期備援；各指標保留原觀測日期。"
    result["summary_text"] = _format_macro_summary(result)
    return result


def _latest_observation(
    session: Any | None,
    api_key: str,
    series_id: str,
    *,
    timeout: float,
) -> dict[str, Any]:
    observations = _fred_observations(
        session,
        api_key,
        series_id,
        timeout=timeout,
        limit=10,
        sort_order="desc",
    )
    latest = _first_valid_observation(observations)
    if latest is None:
        raise ValueError(f"{series_id} 無有效觀測值")
    return latest


def _cpi_yoy_observation(session: Any | None, api_key: str, *, timeout: float) -> dict[str, Any]:
    start = (date.today() - timedelta(days=420)).isoformat()
    observations = _fred_observations(
        session,
        api_key,
        "CPIAUCSL",
        timeout=timeout,
        observation_start=start,
        sort_order="asc",
        limit=500,
    )
    valid = [item for item in (_parse_observation(obs) for obs in observations) if item is not None]
    if len(valid) < 2:
        raise ValueError("CPIAUCSL 無足夠觀測值計算年增率")
    latest = valid[-1]
    prior = _same_month_prior_year(valid, latest["date"])
    if prior is None:
        raise ValueError("CPIAUCSL 缺去年同月值，不能以其他月份代替年增率")
    if not prior["value"]:
        raise ValueError("CPIAUCSL 去年同期值為 0")
    yoy = (latest["value"] / prior["value"] - 1) * 100
    return {"date": latest["date"], "value": round(yoy, 4), "prior_date": prior["date"]}


def _fred_observations(
    session: Any | None,
    api_key: str,
    series_id: str,
    *,
    timeout: float,
    limit: int,
    sort_order: str,
    observation_start: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": sort_order,
        "limit": str(limit),
    }
    if observation_start:
        params["observation_start"] = observation_start
    response = _fred_get(session, params=params, timeout=timeout)
    payload = response.json()
    return payload.get("observations", []) if isinstance(payload, dict) else []


def _fred_get(session: Any | None, *, params: dict[str, str], timeout: float):
    if session is not None:
        response = session.get(FRED_OBSERVATIONS_URL, params=params, timeout=timeout)
        response.raise_for_status()
        return response
    return sync_get(FRED_OBSERVATIONS_URL, params=params, timeout=timeout, provider="FRED")


def _first_valid_observation(observations: list[dict[str, Any]]) -> dict[str, Any] | None:
    for observation in observations:
        parsed = _parse_observation(observation)
        if parsed is not None:
            return parsed
    return None


def _parse_observation(observation: dict[str, Any]) -> dict[str, Any] | None:
    value = observation.get("value")
    if value in (None, "", "."):
        return None
    try:
        number = float(str(value))
    except (ValueError, TypeError, OverflowError):
        return None
    observed_date = str(observation.get("date") or "")
    try:
        date.fromisoformat(observed_date)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return {"date": observed_date, "value": number}


def _same_month_prior_year(valid: list[dict[str, Any]], latest_date: str) -> dict[str, Any] | None:
    try:
        latest_year = int(latest_date[:4])
        latest_month = latest_date[5:7]
    except Exception:
        return None
    expected_prefix = f"{latest_year - 1:04d}-{latest_month}"
    for item in reversed(valid[:-1]):
        if str(item.get("date") or "").startswith(expected_prefix):
            return item
    return None


def _format_macro_summary(result: dict[str, Any]) -> str:
    indicators = result.get("indicators", {})
    parts = []
    for name, label in (("us_10y_yield", "美國10年期公債殖利率"), ("us_cpi_yoy", "CPI年增率"), ("vix", "VIX")):
        item = indicators.get(name)
        if not item:
            parts.append(f"{label} 資料不足")
            continue
        suffix = "%" if item.get("unit") == "%" else ""
        observation_status = item.get("observation_status")
        stale_note = ({"unknown": "；觀測日期未知，無法確認時效", "future": "；觀測日期在未來，不可作目前值",
                       "stale": "；觀測日期過舊，非目前值"}.get(observation_status, "；過期備援，非最新值")
                      if item.get("stale") else "")
        parts.append(f"{label} {float(item['value']):.2f}{suffix}（{item['date']}{stale_note}）")
    return "FRED 總經：" + "，".join(parts) + "。"
