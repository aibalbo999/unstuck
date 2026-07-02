"""Free local symbol suggestions and watchlist import parsing."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from pipeline_modes import normalize_pipeline_id


SCHEMA_VERSION = "symbol_tools.v1"
DEFAULT_UNIVERSE = [
    ("2330.TW", "台積電", "TW", "Semiconductors"),
    ("2308.TW", "台達電", "TW", "Electronics"),
    ("2454.TW", "聯發科", "TW", "Semiconductors"),
    ("2317.TW", "鴻海", "TW", "Electronics"),
    ("2881.TW", "富邦金", "TW", "Financials"),
    ("AAPL", "Apple Inc.", "US", "Technology"),
    ("MSFT", "Microsoft", "US", "Technology"),
    ("NVDA", "NVIDIA", "US", "Semiconductors"),
    ("TSLA", "Tesla", "US", "Consumer Discretionary"),
    ("QQQ", "Invesco QQQ Trust", "US", "ETF"),
    ("SPY", "SPDR S&P 500 ETF", "US", "ETF"),
]


def suggest_symbols(
    query: str,
    *,
    universe: list[dict[str, Any]] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    query = str(query or "").strip()
    rows = universe or _default_universe()
    normalized_query = _normalize_symbol(query)
    scored = []
    for row in rows:
        score = _match_score(query, normalized_query, row)
        if score > 0:
            scored.append((score, row))
    items = [
        {**row, "cost_tier": "free", "source": "local_symbol_universe"}
        for _, row in sorted(scored, key=lambda item: (-item[0], item[1]["ticker"]))[:max(1, limit)]
    ]
    return {"schema_version": SCHEMA_VERSION, "query": query, "items": items}


def parse_watchlist_import(text: str, *, default_pipeline: str = "v1") -> dict[str, Any]:
    text = str(text or "").strip()
    rows = _csv_rows(text) if _has_header(text) else _plain_rows(text)
    items = []
    errors = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        item = _import_item(row, default_pipeline)
        if not item["ticker"]:
            errors.append({"row": index, "error": "ticker is required"})
            continue
        key = (item["ticker"], item["pipeline"])
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    return {"schema_version": SCHEMA_VERSION, "items": items, "errors": errors}


def _default_universe() -> list[dict[str, Any]]:
    return [
        {"ticker": ticker, "name": name, "market": market, "sector": sector}
        for ticker, name, market, sector in DEFAULT_UNIVERSE
    ]


def _normalize_symbol(value: str) -> str:
    value = str(value or "").strip().upper()
    if re.fullmatch(r"\d{4}", value):
        return f"{value}.TW"
    return value


def _match_score(raw_query: str, normalized_query: str, row: dict[str, Any]) -> int:
    haystack = " ".join(str(row.get(key) or "") for key in ("ticker", "name", "market", "sector")).upper()
    if not raw_query:
        return 1
    raw = raw_query.upper()
    ticker = str(row.get("ticker") or "").upper()
    if ticker == normalized_query:
        return 100
    if ticker.startswith(normalized_query) or ticker.split(".", 1)[0].startswith(raw):
        return 80
    if raw in haystack:
        return 50
    return 0


def _has_header(text: str) -> bool:
    first = next((line for line in text.splitlines() if line.strip()), "")
    headers = {part.strip().lower() for part in first.split(",")}
    return bool(headers & {"ticker", "symbol", "代號", "股票代號"})


def _csv_rows(text: str) -> list[dict[str, Any]]:
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _plain_rows(text: str) -> list[dict[str, Any]]:
    rows = []
    for line in text.splitlines():
        parts = [part for part in re.split(r"[\s,]+", line.strip()) if part]
        if parts:
            rows.append({"ticker": parts[0], "pipeline": parts[1] if len(parts) > 1 else ""})
    return rows


def _import_item(row: dict[str, Any], default_pipeline: str) -> dict[str, Any]:
    ticker = _normalize_symbol(_first(row, "ticker", "symbol", "代號", "股票代號"))
    pipeline = normalize_pipeline_id(_first(row, "pipeline", "pipeline_id", "模式") or default_pipeline)
    return {
        "ticker": ticker,
        "pipeline": pipeline,
        "enabled": _bool(_first(row, "enabled", "啟用"), default=True),
        "schedule_slots": _slots(_first(row, "schedule_slots", "schedule", "排程")),
        "tags": _split(_first(row, "tags", "tag", "標籤")),
        "trigger_source": str(_first(row, "trigger_source", "source", "來源") or "manual_import").strip(),
    }


def _first(row: dict[str, Any], *keys: str) -> str:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _split(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[|;，、]+", str(value or "")) if part.strip()]


def _slots(value: str) -> list[str]:
    aliases = {"盤前": "pre_market", "pre": "pre_market", "盤後": "post_market", "post": "post_market"}
    slots = []
    for part in _split(value) or ["post_market"]:
        slot = aliases.get(part.lower(), aliases.get(part, part.lower()))
        if slot in {"pre_market", "post_market"} and slot not in slots:
            slots.append(slot)
    return slots or ["post_market"]


def _bool(value: str, *, default: bool) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return default
    return text not in {"0", "false", "no", "n", "停用", "否"}


__all__ = ["SCHEMA_VERSION", "parse_watchlist_import", "suggest_symbols"]
