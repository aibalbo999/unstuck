"""Shared helpers for Taiwan market screener modules."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

import watchlist_store


TAIPEI = watchlist_store.TAIPEI


def safe_float(value: Any) -> float:
    try:
        text = str(value if value is not None else "").strip()
        negative = text.startswith("(") and text.endswith(")")
        text = text.replace(",", "").replace("+", "").replace("(", "").replace(")", "")
        if text in {"", "-", "--"}:
            return 0.0
        number = float(text)
    except (TypeError, ValueError):
        return 0.0
    if negative:
        number = -number
    if pd.isna(number):
        return 0.0
    return number


def is_common_tw_stock_id(stock_id: Any) -> bool:
    text = str(stock_id or "").strip()
    return len(text) == 4 and text.isdigit()


def clean_tw_stock_id(stock_id: Any) -> str:
    return "".join(ch for ch in str(stock_id or "").strip() if ch.isdigit())


def clean_company_name(value: Any) -> str:
    return " ".join(str(value or "").split())


def tw_ticker(stock_id: Any) -> str:
    text = str(stock_id or "").strip().upper()
    return text if "." in text else f"{text}.TW"


def twse_date_to_iso(value: Any) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(text) == 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) != 7:
        return ""
    year = int(text[:3]) + 1911
    return f"{year:04d}-{text[3:5]}-{text[5:7]}"


def provider_name(source: Any) -> str:
    return str(getattr(source, "provider_name", None) or source.__class__.__name__).strip()


def unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def taipei_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(TAIPEI)
    if now.tzinfo is None:
        return now.replace(tzinfo=TAIPEI)
    return now.astimezone(TAIPEI)


def date_text(value: str | date) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)
