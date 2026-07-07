from __future__ import annotations

from typing import Any

from .utils import _int, _label, _number, _percent_change, _profile_text, _text


def _identity(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_name": _text(data.get("company_name")) or _text(data.get("ticker")),
        "sector": _text(data.get("sector")),
        "industry": _text(data.get("industry")),
        "country": _text(data.get("country")),
    }

def _company_profile(data: dict[str, Any]) -> dict[str, Any]:
    summary = _profile_text(
        data.get("company_summary"),
        data.get("business_summary"),
        data.get("long_business_summary"),
        data.get("longBusinessSummary"),
    )
    website = _profile_text(data.get("website"))
    sector = _profile_text(data.get("sector"))
    industry = _profile_text(data.get("industry"))
    country = _profile_text(data.get("country"))
    exchange = _profile_text(data.get("exchange"), data.get("full_exchange_name"))
    currency = _profile_text(data.get("currency"))
    financial_currency = _profile_text(data.get("financial_currency"))
    employees = _int(data.get("employees"))

    facts = []
    sector_industry = " / ".join(item for item in (sector, industry) if item)
    if sector_industry:
        facts.append({"label": "產業", "value": sector_industry})
    market = " · ".join(item for item in (country, exchange) if item)
    if market:
        facts.append({"label": "市場", "value": market})
    currency_label = currency or financial_currency
    if currency_label and financial_currency and financial_currency != currency_label:
        currency_label = f"{currency_label} / 財報 {financial_currency}"
    if currency_label:
        facts.append({"label": "幣別", "value": currency_label})
    if employees:
        facts.append({"label": "員工", "value": f"{employees:,}"})

    if not summary and not website and not facts:
        return {
            "status": "insufficient_data",
            "label": "公司檔案不足",
            "summary": "",
            "website": "",
            "facts": [],
        }
    return {
        "status": "available",
        "label": "公司檔案",
        "summary": summary,
        "website": website,
        "facts": facts[:6],
    }

def _quote(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "price": _number(data.get("current_price")),
        "price_label": _label(data.get("current_price_fmt"), data.get("current_price")),
        "market_cap": _number(data.get("market_cap_raw")),
        "market_cap_label": _label(data.get("market_cap_fmt"), data.get("market_cap_raw")),
        "beta": _number(data.get("beta")),
        "volume": _number(data.get("volume"), data.get("avg_volume"), data.get("average_volume")),
        "open": _number(data.get("open")),
        "previous_close": _number(data.get("previous_close")),
        "day_range": {
            "low": _number(data.get("day_low")),
            "high": _number(data.get("day_high")),
        },
        "range_52w": {
            "high": _number(data.get("week_52_high")),
            "low": _number(data.get("week_52_low")),
        },
        "as_of": _text(data.get("cache_generated_at") or data.get("fetch_date")),
    }

def _market_session(data: dict[str, Any], *, current_price: float | None) -> dict[str, Any]:
    previous_close = _number(data.get("previous_close"))
    open_price = _number(data.get("open"))
    day_low = _number(data.get("day_low"))
    day_high = _number(data.get("day_high"))
    volume = _number(data.get("volume"))
    avg_volume = _number(data.get("avg_volume"), data.get("average_volume"))
    change = round(current_price - previous_close, 2) if current_price is not None and previous_close is not None else None
    day_span = day_high - day_low if day_high is not None and day_low is not None else None
    return {
        "current_price": current_price,
        "previous_close": previous_close,
        "open": open_price,
        "change": change,
        "change_pct": _percent_change(current_price, previous_close),
        "direction": _market_direction(change),
        "day_range": {"low": day_low, "high": day_high},
        "day_position_pct": round(((current_price - day_low) / day_span) * 100, 2)
        if current_price is not None and day_low is not None and day_span and day_span > 0
        else None,
        "volume": volume,
        "avg_volume": avg_volume,
        "volume_vs_avg_pct": _percent_change(volume, avg_volume),
        "as_of": _text(data.get("cache_generated_at") or data.get("fetch_date")),
    }

def _market_direction(change: float | None) -> str:
    if change is None:
        return "flat"
    if change > 0:
        return "up"
    if change < 0:
        return "down"
    return "flat"
