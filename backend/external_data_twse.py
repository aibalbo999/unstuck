"""TWSE / MOPS official-data adapter for Taiwan equities."""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Optional

from config import FINMIND_API_TOKEN

try:
    from data_fetch.market_sources.taiwan import DataLoader
except Exception:  # pragma: no cover - optional FinMind dependency
    DataLoader = None


logger = logging.getLogger(__name__)

REVENUE_ALIASES = ("Revenue", "OperatingRevenue", "營業收入", "營業收入合計")
GROSS_PROFIT_ALIASES = ("GrossProfit", "GrossProfitLoss", "營業毛利", "營業毛利（毛損）")
OPERATING_INCOME_ALIASES = ("OperatingIncome", "OperatingIncomeLoss", "營業利益", "營業利益（損失）")
NET_INCOME_ALIASES = ("IncomeAfterTaxes", "ProfitLoss", "NetIncome", "本期淨利", "本期淨利（淨損）")
OCF_ALIASES = ("NetCashInflowFromOperatingActivities", "CashFlowsFromUsedInOperatingActivities", "營業活動之淨現金流入")
CAPEX_ALIASES = ("PurchaseOfPropertyPlantAndEquipment", "AcquisitionOfPropertyPlantAndEquipment", "取得不動產、廠房及設備")
TOTAL_DEBT_ALIASES = ("TotalLiabilities", "TotalDebt", "Liabilities", "負債總計")
DEBT_COMPONENT_ALIASES = (
    "ShortTermBorrowings",
    "LongTermBorrowings",
    "BondsPayable",
    "CurrentPortionOfLongTermDebt",
    "短期借款",
    "長期借款",
    "應付公司債",
)
FINANCIAL_FIELDS = (
    "revenue_ttm_raw",
    "net_income_ttm_raw",
    "free_cash_flow_raw",
    "gross_margin_raw",
    "operating_margin_raw",
    "profit_margin_raw",
    "total_debt_raw",
)


def fetch_twse_official_data(ticker: str) -> Optional[dict[str, Any]]:
    """Fetch last-four-quarter official Taiwan financial data."""
    symbol = ticker.split(".")[0]
    if not symbol.isdigit():
        logger.info("Ticker %s does not appear to be a TWSE symbol.", ticker)
        return None

    payload = _fetch_finmind_with_retry(symbol)
    if payload:
        return payload
    return _fetch_twse_openapi_fallback(symbol)


def _fetch_finmind_with_retry(symbol: str) -> Optional[dict[str, Any]]:
    if DataLoader is None:
        logger.warning("FinMind DataLoader is unavailable; trying TWSE OpenAPI fallback.")
        return None

    for attempt in range(1, 4):
        try:
            payload = _fetch_finmind_payload(symbol)
            if payload:
                return payload
            return None
        except Exception as exc:
            logger.warning("FinMind TWSE official fetch failed for %s (attempt %s/3): %s", symbol, attempt, exc)
            if attempt < 3:
                time.sleep(2)
    return None


def _fetch_finmind_payload(symbol: str) -> Optional[dict[str, Any]]:
    loader = DataLoader()
    _login_finmind(loader)
    start_date = (datetime.now() - timedelta(days=560)).strftime("%Y-%m-%d")
    income = _call_loader(loader, ("taiwan_stock_income_statement", "taiwan_stock_financial_statement"), symbol, start_date)
    balance = _call_loader(loader, ("taiwan_stock_balance_sheet",), symbol, start_date)
    cash_flow = _call_loader(loader, ("taiwan_stock_cash_flows_statement", "taiwan_stock_cash_flows"), symbol, start_date)
    return _build_payload(_frame_rows(income), _frame_rows(balance), _frame_rows(cash_flow), "FinMind_TWSE")


def _login_finmind(loader: Any) -> None:
    if not FINMIND_API_TOKEN or not hasattr(loader, "login_by_token"):
        return
    try:
        loader.login_by_token(api_token=FINMIND_API_TOKEN)
    except TypeError:
        loader.login_by_token(FINMIND_API_TOKEN)


def _call_loader(loader: Any, method_names: tuple[str, ...], symbol: str, start_date: str) -> Any:
    for method_name in method_names:
        method = getattr(loader, method_name, None)
        if method is None:
            continue
        try:
            return method(stock_id=symbol, start_date=start_date)
        except TypeError:
            return method(symbol, start_date)
    return None


def _frame_rows(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if getattr(frame, "empty", False):
        return []
    if hasattr(frame, "to_dict"):
        return [row for row in frame.to_dict("records") if isinstance(row, dict)]
    if isinstance(frame, list):
        return [row for row in frame if isinstance(row, dict)]
    return []


def _build_payload(
    income_rows: list[dict[str, Any]],
    balance_rows: list[dict[str, Any]],
    cash_flow_rows: list[dict[str, Any]],
    source: str,
) -> Optional[dict[str, Any]]:
    dates = _recent_dates(income_rows, limit=4)
    revenue = _sum_metric(income_rows, dates, REVENUE_ALIASES)
    gross_profit = _sum_metric(income_rows, dates, GROSS_PROFIT_ALIASES)
    operating_income = _sum_metric(income_rows, dates, OPERATING_INCOME_ALIASES)
    net_income = _sum_metric(income_rows, dates, NET_INCOME_ALIASES)
    ocf = _sum_metric(cash_flow_rows, dates, OCF_ALIASES)
    capex = _sum_metric(cash_flow_rows, dates, CAPEX_ALIASES)
    free_cash_flow = None
    if ocf is not None and capex is not None:
        free_cash_flow = ocf - abs(capex) if capex > 0 else ocf + capex

    payload = {
        "revenue_ttm_raw": _round_or_none(revenue),
        "net_income_ttm_raw": _round_or_none(net_income),
        "free_cash_flow_raw": _round_or_none(free_cash_flow),
        "gross_margin_raw": _ratio(gross_profit, revenue),
        "operating_margin_raw": _ratio(operating_income, revenue),
        "profit_margin_raw": _ratio(net_income, revenue),
        "total_debt_raw": _round_or_none(_latest_debt(balance_rows)),
        "source": source,
        "fetch_date": _today_iso(),
    }
    return payload if _has_any_financial_value(payload) else None


def _recent_dates(rows: list[dict[str, Any]], limit: int = 4) -> list[str]:
    dates = sorted({_date_key(row) for row in rows if _date_key(row)})
    return dates[-limit:]


def _date_key(row: dict[str, Any]) -> str:
    return str(row.get("date") or row.get("Date") or row.get("財報年月") or "")[:10]


def _normalize_key(value: Any) -> str:
    return str(value or "").replace(" ", "").replace("_", "").lower()


def _value_for_date(rows: list[dict[str, Any]], date_key: str, aliases: tuple[str, ...]) -> Optional[float]:
    values = _values_for_date(rows, date_key, aliases)
    return values[0] if values else None


def _values_for_date(rows: list[dict[str, Any]], date_key: str, aliases: tuple[str, ...]) -> list[float]:
    alias_keys = {_normalize_key(alias) for alias in aliases}
    values: list[float] = []
    for row in rows:
        if _date_key(row) != date_key:
            continue
        row_type = _normalize_key(row.get("type") or row.get("metric") or row.get("name"))
        if row_type in alias_keys:
            value = _safe_float(row.get("value"))
            if value is not None:
                values.append(value)
                continue
        for key, raw_value in row.items():
            if _normalize_key(key) in alias_keys:
                value = _safe_float(raw_value)
                if value is not None:
                    values.append(value)
    return values


def _sum_metric(rows: list[dict[str, Any]], dates: list[str], aliases: tuple[str, ...]) -> Optional[float]:
    total = 0.0
    found = False
    for date_key in dates:
        value = _value_for_date(rows, date_key, aliases)
        if value is None:
            continue
        total += value
        found = True
    return total if found else None


def _latest_debt(rows: list[dict[str, Any]]) -> Optional[float]:
    for date_key in reversed(_recent_dates(rows, limit=12)):
        total = _value_for_date(rows, date_key, TOTAL_DEBT_ALIASES)
        if total is not None:
            return total
        components = _values_for_date(rows, date_key, DEBT_COMPONENT_ALIASES)
        if components:
            return sum(components)
    return None


def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator, 6)


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("NT$", "").replace("$", "").strip()
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None


def _round_or_none(value: Optional[float]) -> Optional[float]:
    return round(value, 4) if value is not None else None


def _has_any_financial_value(payload: dict[str, Any]) -> bool:
    return any(payload.get(field) is not None for field in FINANCIAL_FIELDS)


def _today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _fetch_twse_openapi_fallback(symbol: str) -> Optional[dict[str, Any]]:
    urls = [
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_O",
    ]
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                records = json.loads(response.read().decode("utf-8"))
            rows = [row for row in records if str(row.get("公司代號") or row.get("Code") or "") == symbol]
            payload = _build_payload(rows, rows, rows, "TWSE_OpenAPI")
            if payload:
                return payload
        except Exception as exc:
            logger.warning("TWSE OpenAPI fallback failed for %s via %s: %s", symbol, url, exc)
    return None
