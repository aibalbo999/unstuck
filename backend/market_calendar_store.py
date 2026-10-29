"""File-backed market calendar store for freshness decisions."""

from __future__ import annotations

import json
import hashlib
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from config import MARKET_CALENDAR_DIR


BUILTIN_MARKET_CALENDARS = {
    ("us", 2026): {
        "market": "us",
        "year": 2026,
        "timezone": "America/New_York",
        "open": "09:30",
        "close": "16:00",
        "holidays": [
            "2026-01-01",
            "2026-01-19",
            "2026-02-16",
            "2026-04-03",
            "2026-05-25",
            "2026-06-19",
            "2026-07-03",
            "2026-09-07",
            "2026-11-26",
            "2026-12-25",
        ],
        "early_closes": {
            "2026-11-27": "13:00",
            "2026-12-24": "13:00",
        },
    },
    ("tw", 2026): {
        "market": "tw",
        "year": 2026,
        "timezone": "Asia/Taipei",
        "open": "09:00",
        "close": "13:30",
        "holidays": [
            "2026-01-01",
            "2026-02-12",
            "2026-02-13",
            "2026-02-16",
            "2026-02-17",
            "2026-02-18",
            "2026-02-19",
            "2026-02-20",
            "2026-02-27",
            "2026-04-03",
            "2026-04-06",
            "2026-05-01",
            "2026-06-19",
            "2026-09-25",
            "2026-09-28",
            "2026-10-09",
            "2026-10-26",
            "2026-12-25",
        ],
        "early_closes": {},
    },
}

# Annual schedules do not contain later emergency closures. Keep an explicit
# dated exception with its announcement; a missing quote/index row is never
# converted into a holiday. These references establish calendar scope only,
# not a security's OHLC, publication finality or historical point-in-time proof.
BUILTIN_SESSION_EXCEPTIONS = {
    ("tw", 2026): {
        "2026-07-10": {
            "state": "closed",
            "reason": "official_emergency_closure",
            "published_date": "2026-07-09",
            "source_url": "https://www.twse.com.tw/staticFiles/news/news/tsecnews/8a8216d69ef76943019f46cb86ae0110.pdf",
            "title": "臺灣證券交易所集中交易市場115年7月10日休市一天",
            "scope": "TWSE full-day closure",
            "exchanges": ["TWSE"],
        },
        "2026-10-23": {
            "state": "closed",
            "reason": "official_emergency_closure",
            "published_date": "2026-10-22",
            "source_url": "https://www.twse.com.tw/staticFiles/news/news/tsecnews/8a8216d6a0fa351b01a1638507940202.pdf",
            "title": "臺灣證券交易所集中交易市場115年10月23日休市一天",
            "scope": "TWSE full-day closure",
            "exchanges": ["TWSE"],
        },
    },
}

CALENDAR_REFERENCE_URLS = {
    ("tw", 2026): "https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html",
}


def calendar_path(market: str, year: int, calendar_dir: Optional[str] = None) -> Path:
    root = Path(calendar_dir or MARKET_CALENDAR_DIR)
    return root / f"{market}_{int(year)}.json"


def load_market_calendar(market: str, year: int, calendar_dir: Optional[str] = None) -> dict:
    market = str(market or "").lower()
    year = int(year)
    path = calendar_path(market, year, calendar_dir)
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("market") == market and loaded.get("year") == year and _complete_calendar(loaded):
                return _with_provenance(loaded, market=market, year=year, source="local_file")
        except (OSError, json.JSONDecodeError):
            pass
    seed = BUILTIN_MARKET_CALENDARS.get((market, year), {})
    return _with_provenance(seed, market=market, year=year, source="builtin" if seed else "missing")


def _complete_calendar(calendar: dict) -> bool:
    required = ('timezone', 'open', 'close', 'holidays', 'early_closes')
    if not all(key in calendar for key in required):
        return False
    holidays, early = calendar['holidays'], calendar['early_closes']
    if not isinstance(holidays, list) or not isinstance(early, dict):
        return False
    if not isinstance(calendar.get('session_exceptions', {}), dict) or not isinstance(calendar.get('quarantined_dates', []), list):
        return False
    try:
        from datetime import time
        from zoneinfo import ZoneInfo
        ZoneInfo(calendar['timezone'])
        for value in [calendar['open'], calendar['close'], *early.values()]:
            time.fromisoformat(value)
        return all(date.fromisoformat(day).year == calendar['year'] for day in [*holidays, *early])
    except (ValueError, TypeError, KeyError):
        return False


def _with_provenance(calendar: dict, *, market: str, year: int, source: str) -> dict:
    result = normalize_calendar(calendar, market=market, year=year)
    # A previously saved annual file must not erase a later known closure.
    exceptions = dict(result.get("session_exceptions") or {})
    exceptions.update(BUILTIN_SESSION_EXCEPTIONS.get((market, year), {}))
    result["session_exceptions"] = exceptions
    result["holidays"] = sorted(set(result["holidays"]) | {
        day for day, entry in exceptions.items()
        if _valid_exception(day, entry, market) and entry["state"] == "closed"
    })
    result["calendar_reference_url"] = CALENDAR_REFERENCE_URLS.get((market, year))
    result["verification_scope"] = "schedule_and_recorded_exceptions; not independent daily-price verification"
    result["official_price_verified"] = False
    result["historical_point_in_time_verified"] = False
    result.update(source=source, coverage_status="unknown" if source == "missing" else "available",
                  valid_year=year if source != "missing" else None,
                  calendar_version=hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest() if calendar else None)
    return result


def _valid_exception(day, entry, market):
    if (not isinstance(entry, dict) or not isinstance(entry.get("state"), str)
            or entry["state"] not in {"open", "closed"}
            or not isinstance(entry.get("source_url"), str)
            or not isinstance(entry.get("reason"), str)):
        return False
    exchanges = entry.get("exchanges", ["TWSE"])
    if not isinstance(exchanges, list) or not exchanges or any(not isinstance(value, str) for value in exchanges):
        return False
    try:
        event_day = date.fromisoformat(day)
        published = date.fromisoformat(entry.get("published_date", ""))
        url = urlsplit(entry.get("source_url", ""))
    except (TypeError, ValueError):
        return False
    hosts = {"tw": {"www.twse.com.tw", "www.tpex.org.tw", "wwwc.twse.com.tw"},
             "us": {"www.nyse.com", "www.nasdaq.com", "www.nasdaqtrader.com"}}
    return (published <= event_day and url.scheme == "https"
            and url.hostname in hosts.get(market, set()) and bool(entry.get("reason")))


def session_day_status(day, *, market="tw", calendar=None, exchange=None):
    """Classify one date without fetching, imputing, or trusting volume size."""
    try:
        day = date.fromisoformat(day) if isinstance(day, str) else day
        if not isinstance(day, date):
            raise ValueError("missing date")
    except (TypeError, ValueError):
        return {"state": "unknown", "reason": "invalid_session_date", "date": None}
    calendar = load_market_calendar(market, day.year) if calendar is None else calendar
    if not isinstance(calendar, dict):
        return {"date": day.isoformat(), "state": "unknown", "reason": "calendar_coverage_unknown"}
    provenance = {key: calendar.get(key) for key in
                  ("source", "coverage_status", "valid_year", "calendar_version", "calendar_reference_url")}
    result = {"date": day.isoformat(), "market": market, "calendar": provenance}
    if calendar.get("coverage_status") != "available" or calendar.get("year") != day.year:
        return {**result, "state": "unknown", "reason": "calendar_coverage_unknown"}
    if day.isoformat() in calendar.get("quarantined_dates", []):
        return {**result, "state": "unknown", "reason": "session_date_quarantined"}
    exception = (calendar.get("session_exceptions") or {}).get(day.isoformat())
    if exception is not None:
        if not _valid_exception(day.isoformat(), exception, market):
            return {**result, "state": "unknown", "reason": "session_exception_evidence_missing"}
        exchange = exchange or ("TWSE" if market == "tw" else None)
        if exchange and exchange not in exception.get("exchanges", ["TWSE"]):
            return {**result, "state": "unknown", "reason": "closure_evidence_scope_unverified",
                    "exception_evidence": dict(exception)}
        return {**result, "state": exception["state"], "reason": exception["reason"],
                "exception_evidence": dict(exception)}
    if day.weekday() >= 5:
        return {**result, "state": "closed", "reason": "weekend"}
    if day.isoformat() in calendar.get("holidays", []):
        return {**result, "state": "closed", "reason": "scheduled_holiday"}
    return {**result, "state": "open", "reason": "scheduled_session"}


def normalize_calendar(calendar: dict, *, market: str, year: int) -> dict:
    normalized = dict(calendar or {})
    normalized.setdefault("market", market)
    normalized.setdefault("year", year)
    normalized.setdefault("timezone", "Asia/Taipei" if market == "tw" else "America/New_York")
    normalized.setdefault("open", "09:00" if market == "tw" else "09:30")
    normalized.setdefault("close", "13:30" if market == "tw" else "16:00")
    normalized["holidays"] = sorted(str(item) for item in normalized.get("holidays", []) if _is_iso_date(item))
    early_closes = normalized.get("early_closes", {})
    normalized["early_closes"] = {
        str(day): str(close_time)
        for day, close_time in (early_closes.items() if isinstance(early_closes, dict) else [])
        if _is_iso_date(day) and str(close_time).strip()
    }
    return normalized


def write_market_calendar(calendar: dict, calendar_dir: Optional[str] = None, overwrite: bool = False) -> dict:
    normalized = normalize_calendar(calendar, market=str(calendar.get("market") or ""), year=int(calendar.get("year")))
    path = calendar_path(normalized["market"], normalized["year"], calendar_dir)
    if path.exists() and not overwrite:
        return {"path": str(path), "written": False, "reason": "exists"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"path": str(path), "written": True, "reason": "written"}


def update_market_calendars(
    *,
    years: list[int] | None = None,
    markets: list[str] | None = None,
    calendar_dir: Optional[str] = None,
    overwrite: bool = False,
) -> dict:
    selected_markets = [str(market).lower() for market in (markets or ["us", "tw"])]
    selected_years = [int(year) for year in (years or sorted({year for _market, year in BUILTIN_MARKET_CALENDARS}))]
    results = []
    for market in selected_markets:
        for year in selected_years:
            seed = BUILTIN_MARKET_CALENDARS.get((market, year))
            if not seed:
                results.append({"market": market, "year": year, "written": False, "reason": "no_builtin_seed"})
                continue
            result = write_market_calendar(seed, calendar_dir=calendar_dir, overwrite=overwrite)
            result.update({"market": market, "year": year})
            results.append(result)
    return {
        "updated": sum(1 for item in results if item.get("written")),
        "skipped": sum(1 for item in results if not item.get("written")),
        "results": results,
    }


def _is_iso_date(value) -> bool:
    try:
        date.fromisoformat(str(value))
        return True
    except ValueError:
        return False
