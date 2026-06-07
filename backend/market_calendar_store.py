"""File-backed market calendar store for freshness decisions."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

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
            if isinstance(loaded, dict):
                return normalize_calendar(loaded, market=market, year=year)
        except (OSError, json.JSONDecodeError):
            pass
    return normalize_calendar(BUILTIN_MARKET_CALENDARS.get((market, year), {}), market=market, year=year)


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
