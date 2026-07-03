"""Official free Taiwan financial-data adapters."""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from external_http_client import sync_get, sync_post
from official_financials_mops_conference import MOPS_INVESTOR_CONFERENCE_URL, fetch_mops_investor_conference_events


LOGGER = logging.getLogger(__name__)
TWSE_INSTITUTIONAL_TRADES_URL = "https://openapi.twse.com.tw/v1/fund/TWT38U13"
MOPS_BALANCE_SHEET_URL = "https://mops.twse.com.tw/mops/web/ajax_t164sb03"
REQUEST_TIMEOUT = (5, 15)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}
BALANCE_ALIASES = {
    "total_assets": ("資產總計", "資產總額", "資產合計"),
    "total_liabilities": ("負債總計", "負債總額", "負債合計"),
    "total_equity": ("權益總計", "權益總額", "權益合計", "歸屬於母公司業主之權益合計"),
}


def fetch_twse_institutional_trades(
    ticker: str,
    date: str,
    *,
    session: Any | None = None,
) -> dict[str, Any] | None:
    """Fetch same-day institutional net trades from TWSE OpenAPI."""
    symbol = _twse_symbol(ticker)
    if symbol is None:
        return None
    try:
        response = _http_get(
            TWSE_INSTITUTIONAL_TRADES_URL,
            session=session,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            provider="TWSE OpenAPI",
        )
        rows = response.json() or []
    except Exception as exc:
        _warn("TWSE OpenAPI", "institutional trades", exc)
        return None
    for row in rows:
        if str(row.get("證券代號") or row.get("Code") or "").strip() != symbol:
            continue
        return {
            "ticker": symbol,
            "date": date,
            "foreign_net": _parse_number(row.get("外陸資買賣超股數(不含外資自營商)") or row.get("ForeignInvestorsNet")),
            "investment_trust_net": _parse_number(row.get("投信買賣超股數") or row.get("InvestmentTrustNet")),
            "dealer_net": _parse_number(row.get("自營商買賣超股數") or row.get("DealerNet")),
            "total_net": _parse_number(row.get("三大法人買賣超股數") or row.get("TotalNet")),
            "source": "TWSE OpenAPI",
        }
    return None


def fetch_mops_balance_sheet(
    ticker: str,
    year: int,
    season: int,
    *,
    session: Any | None = None,
) -> dict[str, Any] | None:
    """Fetch and normalize a MOPS balance sheet table."""
    symbol, typek = _mops_symbol_and_type(ticker)
    try:
        year_int = int(year)
        season_int = int(season)
    except (TypeError, ValueError):
        return None
    if symbol is None or season_int not in {1, 2, 3, 4}:
        return None
    data = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "queryName": "co_id",
        "inpuType": "co_id",
        "TYPEK": typek,
        "isnew": "false",
        "co_id": symbol,
        "year": str(year_int - 1911),
        "season": f"{season_int:02d}",
    }
    try:
        response = _http_post(
            MOPS_BALANCE_SHEET_URL,
            data=data,
            session=session,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            provider="MOPS",
        )
        frames = pd.read_html(response.text)
    except Exception as exc:
        _warn("MOPS", "balance sheet", exc)
        return None
    parsed = _parse_balance_frames(frames, year_int, season_int)
    if not parsed:
        return None
    raw_line_items = parsed["raw_line_items"]
    payload = {
        "ticker": symbol,
        "year": year_int,
        "season": season_int,
        "statement_scope": "consolidated",
        "unit": "thousand_twd",
        "source": "MOPS",
        "raw_line_items": raw_line_items,
    }
    for field, aliases in BALANCE_ALIASES.items():
        payload[field] = _first_alias_value(raw_line_items, aliases)
    return payload


def _http_get(
    url: str,
    *,
    session: Any | None,
    headers: dict[str, str],
    timeout: Any,
    provider: str,
):
    if session is not None:
        response = session.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    return sync_get(url, headers=headers, timeout=timeout, provider=provider)


def _http_post(
    url: str,
    *,
    data: dict[str, str],
    session: Any | None,
    headers: dict[str, str],
    timeout: Any,
    provider: str,
):
    if session is not None:
        response = session.post(url, data=data, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    return sync_post(url, data=data, headers=headers, timeout=timeout, provider=provider)


def _parse_balance_frames(frames: list[pd.DataFrame], year: int, season: int) -> dict[str, Any] | None:
    for frame in frames:
        rows = _frame_line_items(frame, year, season)
        if rows:
            return {"raw_line_items": rows}
    return None


def _frame_line_items(frame: pd.DataFrame, year: int, season: int) -> dict[str, int]:
    if frame is None or frame.empty:
        return {}
    work = frame.copy()
    work.columns = [_flatten_column(column) for column in work.columns]
    item_col = _find_item_column(work.columns)
    value_col = _find_value_column(work.columns, item_col, year, season)
    if item_col is None or value_col is None:
        return {}
    rows: dict[str, int] = {}
    for _, row in work.iterrows():
        item = _clean_label(row.get(item_col))
        value = _parse_number(row.get(value_col))
        if item and value is not None:
            rows[item] = value
    return rows


def _find_item_column(columns: list[str]) -> str | None:
    for column in columns:
        normalized = _clean_label(column)
        if any(key in normalized for key in ("會計項目", "項目", "account")):
            return column
    return columns[0] if columns else None


def _find_value_column(columns: list[str], item_col: str | None, year: int, season: int) -> str | None:
    period_tokens = (
        f"{year}年第{season}季",
        f"{year}Q{season}",
        f"{year} q{season}",
        "本期",
        "本季",
    )
    for column in columns:
        normalized = _clean_label(column)
        lowered = normalized.lower()
        if column != item_col and any(_clean_label(token).lower() in lowered for token in period_tokens):
            return column
    return None


def _flatten_column(column: Any) -> str:
    if isinstance(column, tuple):
        return " ".join(str(part) for part in column if str(part) != "nan")
    return str(column)


def _first_alias_value(rows: dict[str, int], aliases: tuple[str, ...]) -> int | None:
    normalized = {_normalize_key(alias) for alias in aliases}
    for key, value in rows.items():
        if _normalize_key(key) in normalized:
            return value
    return None


def _twse_symbol(ticker: Any) -> str | None:
    symbol, typek = _mops_symbol_and_type(ticker)
    return symbol if typek == "sii" else None


def _mops_symbol_and_type(ticker: Any) -> tuple[str | None, str | None]:
    raw = str(ticker or "").strip()
    if "." in raw:
        symbol, suffix = raw.split(".", 1)
        suffix = suffix.upper()
        if suffix == "TW":
            typek = "sii"
        elif suffix == "TWO":
            typek = "otc"
        else:
            return None, None
    else:
        symbol = raw
        typek = "sii"
    return (symbol, typek) if re.fullmatch(r"\d{4,6}", symbol) else (None, None)


def _parse_number(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan" or text in {"-", "--"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "").replace("，", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if negative:
        number = -abs(number)
    return int(round(number))


def _clean_label(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def _normalize_key(value: Any) -> str:
    return _clean_label(value).replace("　", "").lower()


def _warn(provider: str, operation: str, exc: BaseException | None = None) -> None:
    kind = exc.__class__.__name__ if exc else "Unavailable"
    LOGGER.warning("%s %s failed [%s]", provider, operation, kind)
