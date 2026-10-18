"""Latest exchange-published PE and PB observations for Taiwan peer stocks."""

from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import os
import re
from zoneinfo import ZoneInfo

from external_http_client import sync_get
from shared_provider_cache import shared_fetch


PROVIDER = "TWSE/TPEx official peer valuation OpenAPI"
URLS = {
    ".TW": "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
    ".TWO": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
}
FIELDS = {
    ".TW": ("Code", "Name", "Date", "PEratio", "PBratio"),
    ".TWO": ("SecuritiesCompanyCode", "CompanyName", "Date", "PriceEarningRatio", "PriceBookRatio"),
}
TICKER = re.compile(r"^([1-9]\d{3,5})(\.TWO|\.TW)$")
MAX_BYTES = 1_000_000
MAX_ROWS = 2_000


def parse_roster(raw: bytes, suffix: str) -> dict:
    if suffix not in FIELDS or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("official peer valuation response size or market invalid")
    try:
        rows = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("official peer valuation JSON invalid") from exc
    if not isinstance(rows, list) or not 0 < len(rows) <= MAX_ROWS:
        raise ValueError("official peer valuation roster shape invalid")
    code_key, name_key, date_key, pe_key, pb_key = FIELDS[suffix]
    entries = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("official peer valuation row invalid")
        code = str(row.get(code_key) or "").strip()
        if not re.fullmatch(r"[1-9]\d{3,5}", code):
            continue
        if code in entries:
            raise ValueError("duplicate official peer valuation code")
        entries[code] = {"name": str(row.get(name_key) or "").strip(),
                         "date_roc": str(row.get(date_key) or "").strip(),
                         "pe": row.get(pe_key), "pb": row.get(pb_key)}
    if not entries:
        raise ValueError("official peer valuation roster has no stocks")
    return {"source_url": URLS[suffix], "response_sha256": sha256(raw).hexdigest(),
            "entries": entries}


def _ratio(raw):
    if isinstance(raw, bool):
        return None
    text = str(raw or "").replace(",", "").strip()
    if not re.fullmatch(r"\d{1,8}(?:\.\d{1,6})?", text):
        return None
    value = float(text)
    return round(value, 4) if 0 < value < 1_000_000 else None


def select_valuation(roster: dict, ticker: str, *, today: date | None = None) -> dict | None:
    match = TICKER.fullmatch(str(ticker or "").strip().upper())
    if not match or not isinstance(roster, dict) or roster.get("source_url") != URLS[match[2]]:
        return None
    entries = roster.get("entries")
    row = entries.get(match[1]) if isinstance(entries, dict) else None
    if not isinstance(row, dict) or not str(row.get("name") or "").strip():
        return None
    stamp = str(row.get("date_roc") or "")
    if not re.fullmatch(r"\d{7}", stamp):
        return None
    try:
        observed = date(int(stamp[:3]) + 1911, int(stamp[3:5]), int(stamp[5:]))
    except ValueError:
        return None
    current = today or datetime.now(ZoneInfo("Asia/Taipei")).date()
    if not 0 <= (current - observed).days <= 7:
        return None
    metrics = {field: number for field, raw in (("pe_ttm", row.get("pe")), ("pb", row.get("pb")))
               if (number := _ratio(raw)) is not None}
    return {"metrics": metrics, "status": "success" if metrics else "metrics_missing",
            "source": PROVIDER, "source_url": roster["source_url"],
            "response_sha256": roster.get("response_sha256"),
            "observed_at": observed.isoformat(), "official_company_name": row["name"],
            "metric_basis": {"pe_ttm": "exchange_reported_price_earnings_ratio",
                             "pb": "exchange_reported_price_book_ratio"},
            "observation_policy": "within_7_calendar_days; not latest-session guarantee"}


def _fetch_roster(suffix: str) -> dict:
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
        raise ValueError("network disabled for isolated tests")
    response = sync_get(URLS[suffix], headers={"User-Agent": "stock-agent/1.0"},
                        timeout=8, provider=PROVIDER)
    return parse_roster(response.content, suffix)


def fetch_official_peer_valuation(ticker: str, *, today: date | None = None) -> dict:
    match = TICKER.fullmatch(str(ticker or "").strip().upper())
    if not match:
        return {"metrics": {}, "status": "not_applicable", "source": PROVIDER}
    suffix = match[2]
    current = today or datetime.now(ZoneInfo("Asia/Taipei")).date()
    roster, meta = shared_fetch(
        "official-peer-valuation:v1:" + current.isoformat() + ":" + suffix,
        lambda: _fetch_roster(suffix), freshness_seconds=30 * 60,
        use_cache=True, lock_wait_seconds=10,
    )
    if meta.get("stale") or not isinstance(roster, dict):
        return {"metrics": {}, "status": "unavailable", "source": PROVIDER,
                "error_kind": meta.get("error_kind"), "cache_hit": bool(meta.get("cache_hit"))}
    result = select_valuation(roster, match[1] + suffix, today=current)
    if result is None:
        return {"metrics": {}, "status": "valid_empty", "source": PROVIDER,
                "cache_hit": bool(meta.get("cache_hit"))}
    return {**result, "cache_hit": bool(meta.get("cache_hit")),
            "fetched_at_epoch": meta.get("fetched_at_epoch")}
