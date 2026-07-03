"""FRED macro indicator fetcher for macro strategy agents."""

from __future__ import annotations

import os
import time
from datetime import date, timedelta
from typing import Any

from external_http_client import sync_get


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_CACHE_TTL_SECONDS = 15 * 60
_CACHE: dict[str, Any] = {"expires_at": 0.0, "value": None}


def fetch_key_macro_indicators(
    *,
    api_key: str | None = None,
    session: Any | None = None,
    use_cache: bool = True,
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    timeout: float = 15,
) -> dict[str, Any]:
    """Fetch DGS10, CPI YoY, and VIX from FRED and return agent-ready context."""
    key = api_key or os.getenv("FRED_API_KEY")
    if not key:
        return {
            "status": "not_configured",
            "source": "FRED",
            "message": "FRED_API_KEY 未設定，略過總經資料抓取。",
        }

    now = time.time()
    if use_cache and _CACHE.get("value") is not None and now < float(_CACHE.get("expires_at") or 0):
        return _CACHE["value"]

    try:
        dgs10 = _latest_observation(session, key, "DGS10", timeout=timeout)
        cpi = _cpi_yoy_observation(session, key, timeout=timeout)
        vix = _latest_observation(session, key, "VIXCLS", timeout=timeout)
        result = {
            "status": "success",
            "source": "FRED",
            "source_url": "https://fred.stlouisfed.org/",
            "indicators": {
                "us_10y_yield": {
                    "series_id": "DGS10",
                    "label": "美國10年期公債殖利率",
                    "value": dgs10["value"],
                    "unit": "%",
                    "date": dgs10["date"],
                },
                "us_cpi_yoy": {
                    "series_id": "CPIAUCSL",
                    "label": "美國 CPI 年增率",
                    "value": cpi["value"],
                    "unit": "%",
                    "date": cpi["date"],
                },
                "vix": {
                    "series_id": "VIXCLS",
                    "label": "VIX 恐慌指數",
                    "value": vix["value"],
                    "unit": "index",
                    "date": vix["date"],
                },
            },
        }
        result["summary_text"] = _format_macro_summary(result)
        if use_cache:
            _CACHE["value"] = result
            _CACHE["expires_at"] = now + max(0, int(cache_ttl_seconds))
        return result
    except Exception as exc:
        return {
            "status": "unavailable",
            "source": "FRED",
            "message": f"FRED 總經資料抓取失敗：{exc}",
        }


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
    prior = _same_month_prior_year(valid, latest["date"]) or valid[0]
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
    except ValueError:
        return None
    return {"date": str(observation.get("date") or ""), "value": number}


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
    dgs10 = indicators.get("us_10y_yield", {})
    cpi = indicators.get("us_cpi_yoy", {})
    vix = indicators.get("vix", {})
    return (
        f"FRED 最新總經：美國10年期公債殖利率 {float(dgs10.get('value')):.2f}%"
        f"（{dgs10.get('date')}），CPI年增率 {float(cpi.get('value')):.2f}%"
        f"（{cpi.get('date')}），VIX {float(vix.get('value')):.2f}"
        f"（{vix.get('date')}）。"
    )
