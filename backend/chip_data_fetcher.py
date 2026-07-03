"""Taiwan chip data fetchers for TDCC shareholder distribution and TWSE margin data."""

from __future__ import annotations

import io
import re
import ssl
from datetime import date, datetime
from typing import Any

import pandas as pd

from external_http_client import sync_get

TDCC_SHAREHOLDER_DISTRIBUTION_CSV_URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
TWSE_MARGIN_BALANCE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"
TWSE_BORROWED_SHORT_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U?response=json"
DEFAULT_HEADERS = {
    "User-Agent": "stock-agent/1.0 (+https://github.com/) Mozilla/5.0",
    "Accept": "application/json,text/csv,text/plain,*/*",
}

RETAIL_LT_50_LOTS_LEVELS = set(range(1, 9))
MAJOR_GT_1000_LOTS_LEVELS = {15}


def _build_compatible_tls_context() -> ssl.SSLContext:
    """Keep certificate verification while tolerating legacy public-site chains."""
    context = ssl.create_default_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


def fetch_tdcc_shareholder_distribution(
    ticker: str,
    date: str | date | datetime | None = None,
    *,
    session: Any | None = None,
    timeout: float = 20,
) -> dict[str, Any]:
    """Fetch TDCC shareholder distribution and compute major/retail holding ratios."""
    code = _normalize_taiwan_stock_code(ticker)
    try:
        response = _http_get(
            TDCC_SHAREHOLDER_DISTRIBUTION_CSV_URL,
            session=session,
            timeout=timeout,
            provider="TDCC OpenData",
            verify=_build_compatible_tls_context(),
        )
        df = _read_tdcc_csv(response.text)
        if df.empty:
            return _unavailable("TDCC OpenData 未回傳股權分散資料。", ticker=code, source="TDCC OpenData")

        df = _normalize_tdcc_distribution_frame(df)
        rows = df[df["證券代號"].astype(str).str.strip() == code]
        target_date = _normalize_date_token(date)
        if target_date:
            rows = rows[rows["資料日期"].astype(str).str.strip() == target_date]
        elif not rows.empty:
            latest_date = rows["資料日期"].astype(str).max()
            rows = rows[rows["資料日期"].astype(str) == latest_date]
            target_date = latest_date

        if rows.empty:
            date_part = f"、日期 {target_date}" if target_date else ""
            return _unavailable(f"TDCC OpenData 找不到 {code}{date_part} 的股權分散資料。", ticker=code, source="TDCC OpenData")

        rows = rows.copy()
        rows["持股分級"] = pd.to_numeric(rows["持股分級"], errors="coerce").astype("Int64")
        rows["占集保庫存數比例%"] = rows["占集保庫存數比例%"].map(_parse_float)
        major_pct = rows.loc[rows["持股分級"].isin(MAJOR_GT_1000_LOTS_LEVELS), "占集保庫存數比例%"].sum()
        retail_pct = rows.loc[rows["持股分級"].isin(RETAIL_LT_50_LOTS_LEVELS), "占集保庫存數比例%"].sum()

        return {
            "status": "success",
            "ticker": code,
            "as_of_date": str(target_date or rows["資料日期"].astype(str).max()),
            "major_holders_gt_1000_lots_pct": round(float(major_pct), 4),
            "retail_holders_lt_50_lots_pct": round(float(retail_pct), 4),
            "row_count": int(len(rows)),
            "source": "TDCC OpenData",
            "source_url": TDCC_SHAREHOLDER_DISTRIBUTION_CSV_URL,
        }
    except Exception as exc:
        return _unavailable(f"TDCC 股權分散資料抓取失敗：{exc}", ticker=code, source="TDCC OpenData")


def fetch_twse_margin_short_sales(
    ticker: str,
    *,
    session: Any | None = None,
    timeout: float = 15,
) -> dict[str, Any]:
    """Fetch latest TWSE margin/short and borrowed-short balances for one listed ticker."""
    code = _normalize_taiwan_stock_code(ticker)
    try:
        margin_response = _http_get(
            TWSE_MARGIN_BALANCE_URL,
            session=session,
            timeout=timeout,
            provider="TWSE OpenAPI MI_MARGN",
        )
        margin_rows = margin_response.json()
        margin_record = _find_twse_margin_record(margin_rows, code)
        if not margin_record:
            return _unavailable(f"TWSE OpenAPI 找不到 {code} 的融資融券資料。", ticker=code, source="TWSE OpenAPI MI_MARGN")

        result = {
            "status": "success",
            "ticker": code,
            "company_name": str(margin_record.get("股票名稱") or margin_record.get("Name") or ""),
            "margin_purchase": _parse_int(margin_record.get("融資買進")),
            "margin_sale": _parse_int(margin_record.get("融資賣出")),
            "margin_cash_repayment": _parse_int(margin_record.get("融資現金償還")),
            "margin_previous_balance": _parse_int(margin_record.get("融資前日餘額")),
            "margin_balance": _parse_int(margin_record.get("融資今日餘額")),
            "short_purchase": _parse_int(margin_record.get("融券買進")),
            "short_sale": _parse_int(margin_record.get("融券賣出")),
            "short_cash_repayment": _parse_int(margin_record.get("融券現券償還")),
            "short_previous_balance": _parse_int(margin_record.get("融券前日餘額")),
            "short_balance": _parse_int(margin_record.get("融券今日餘額")),
            "offset": _parse_int(margin_record.get("資券互抵")),
            "source": "TWSE OpenAPI MI_MARGN",
            "source_url": TWSE_MARGIN_BALANCE_URL,
        }
        result.update(_fetch_borrowed_short_sales(session, code, timeout=timeout))
        return result
    except Exception as exc:
        return _unavailable(f"TWSE 融資融券資料抓取失敗：{exc}", ticker=code, source="TWSE OpenAPI MI_MARGN")


def _fetch_borrowed_short_sales(session: Any | None, code: str, *, timeout: float) -> dict[str, Any]:
    try:
        response = _http_get(
            TWSE_BORROWED_SHORT_URL,
            session=session,
            timeout=timeout,
            provider="TWSE TWT93U",
        )
        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        for row in payload.get("data") or []:
            if not row or str(row[0]).strip() != code:
                continue
            return {
                "as_of_date": str(payload.get("date") or ""),
                "borrowed_short_sale_today": _parse_int(_at(row, 9)),
                "borrowed_short_return_today": _parse_int(_at(row, 10)),
                "borrowed_short_sale_balance": _parse_int(_at(row, 12)),
                "borrowed_short_source": "TWSE TWT93U",
                "borrowed_short_source_url": TWSE_BORROWED_SHORT_URL,
            }
    except Exception:
        return {}
    return {}


def _http_get(
    url: str,
    *,
    session: Any | None,
    timeout: float,
    provider: str,
    verify: ssl.SSLContext | None = None,
):
    if session is not None:
        response = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response
    return sync_get(url, headers=DEFAULT_HEADERS, timeout=timeout, provider=provider, verify=verify)


def _read_tdcc_csv(text: str) -> pd.DataFrame:
    if not text:
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(text.lstrip("\ufeff")), dtype=str)


def _normalize_tdcc_distribution_frame(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [str(column).lstrip("\ufeff").strip() for column in normalized.columns]
    for required in ("資料日期", "證券代號", "持股分級", "占集保庫存數比例%"):
        if required not in normalized.columns:
            normalized[required] = ""
    normalized["證券代號"] = normalized["證券代號"].astype(str).str.strip()
    normalized["資料日期"] = normalized["資料日期"].astype(str).str.strip()
    return normalized


def _find_twse_margin_record(rows: Any, code: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_code = str(row.get("股票代號") or row.get("Code") or "").strip()
        if row_code == code:
            return row
    return None


def _normalize_taiwan_stock_code(ticker: str) -> str:
    raw = str(ticker or "").strip().upper()
    raw = raw.split(".", 1)[0]
    match = re.search(r"\d{4,6}[A-Z]?", raw)
    return match.group(0) if match else raw


def _normalize_date_token(value: str | date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 8:
        return digits
    return digits or None


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _at(row: list[Any], index: int) -> Any:
    return row[index] if index < len(row) else None


def _unavailable(message: str, *, ticker: str, source: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "ticker": ticker,
        "message": message,
        "source": source,
    }
