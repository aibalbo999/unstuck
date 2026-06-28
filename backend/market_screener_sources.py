"""Data source adapters for the Taiwan market screener."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import requests

from config import FINMIND_API_TOKEN
from data_fetch.market_sources.taiwan import DataLoader
from external_http_client import log_http_warning
from market_screener_utils import (
    clean_company_name,
    clean_tw_stock_id,
    is_common_tw_stock_id,
    provider_name,
    safe_float,
    twse_date_to_iso,
)


TWSE_FOREIGN_INVESTOR_URL = "https://www.twse.com.tw/rwd/zh/fund/TWT38U"
TWSE_INVESTMENT_TRUST_URL = "https://www.twse.com.tw/rwd/zh/fund/TWT44U"
TWSE_STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_STOCK_DAY_AVG_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL"
HTTP_TIMEOUT_SECONDS = 15
HTTP_HEADERS = {
    "User-Agent": "stock-agent/1.0 Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
}


class FinMindScreenerDataSource:
    provider_name = "FinMind"

    def __init__(self, data_loader_cls=DataLoader):
        self.data_loader_cls = data_loader_cls

    def _loader(self):
        return build_finmind_loader(self.data_loader_cls)

    def fetch_institutional_frame(self, scan_date: date) -> pd.DataFrame:
        return self._loader().taiwan_stock_institutional_investors(
            start_date=(scan_date - timedelta(days=14)).isoformat(),
            end_date=scan_date.isoformat(),
        )

    def fetch_daily_frame(self, scan_date: date) -> pd.DataFrame:
        return self._loader().taiwan_stock_daily(
            start_date=(scan_date - timedelta(days=90)).isoformat(),
            end_date=scan_date.isoformat(),
        )


class TwseFreeScreenerDataSource:
    provider_name = "TWSE Free API"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch_institutional_frame(self, scan_date: date) -> pd.DataFrame:
        records = []
        foreign_payload = self._twse_rwd_payload(TWSE_FOREIGN_INVESTOR_URL, scan_date)
        trust_payload = self._twse_rwd_payload(TWSE_INVESTMENT_TRUST_URL, scan_date)
        records.extend(self._institutional_records_from_payload(foreign_payload, "Foreign_Investor", scan_date))
        records.extend(self._institutional_records_from_payload(trust_payload, "Investment_Trust", scan_date))
        return pd.DataFrame(records)

    def fetch_daily_frame(self, scan_date: date) -> pd.DataFrame:
        day_rows = self._json_get(TWSE_STOCK_DAY_ALL_URL)
        avg_by_code = {
            clean_tw_stock_id(row.get("Code") or row.get("證券代號")): safe_float(row.get("MonthlyAveragePrice") or row.get("月平均價"))
            for row in self._json_get(TWSE_STOCK_DAY_AVG_ALL_URL)
            if isinstance(row, dict)
        }
        records = []
        for row in day_rows:
            if not isinstance(row, dict):
                continue
            stock_id = clean_tw_stock_id(row.get("Code") or row.get("證券代號"))
            if not is_common_tw_stock_id(stock_id):
                continue
            records.append({
                "date": twse_date_to_iso(row.get("Date")) or scan_date.isoformat(),
                "stock_id": stock_id,
                "company_name": clean_company_name(row.get("Name") or row.get("證券名稱")),
                "close": safe_float(row.get("ClosingPrice") or row.get("收盤價")),
                "Trading_Volume": safe_float(row.get("TradeVolume") or row.get("成交股數")),
                "monthly_average_close": avg_by_code.get(stock_id),
            })
        return pd.DataFrame(records)

    def _json_get(self, url: str) -> list[dict]:
        response = self.session.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json() or []
        return payload if isinstance(payload, list) else []

    def _twse_rwd_payload(self, url: str, scan_date: date) -> dict:
        for offset in range(10):
            query_date = scan_date - timedelta(days=offset)
            response = self.session.get(
                url,
                params={"response": "json", "date": query_date.strftime("%Y%m%d")},
                headers=HTTP_HEADERS,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json() or {}
            if isinstance(payload, dict) and payload.get("data"):
                return payload
        return {}

    def _institutional_records_from_payload(self, payload: dict, investor_name: str, scan_date: date) -> list[dict]:
        if not isinstance(payload, dict):
            return []
        record_date = twse_date_to_iso(payload.get("date")) or scan_date.isoformat()
        records = []
        for row in payload.get("data") or []:
            if not isinstance(row, list) or len(row) < 5:
                continue
            stock_id = clean_tw_stock_id(row[1])
            if is_common_tw_stock_id(stock_id):
                records.append({
                    "date": record_date,
                    "stock_id": stock_id,
                    "company_name": clean_company_name(row[2] if len(row) > 2 else ""),
                    "name": investor_name,
                    "buy": safe_float(row[3]),
                    "sell": safe_float(row[4]),
                })
        return records


TwseOpenApiScreenerDataSource = TwseFreeScreenerDataSource


def build_finmind_loader(data_loader_cls):
    loader = data_loader_cls()
    if FINMIND_API_TOKEN and hasattr(loader, "login_by_token"):
        loader.login_by_token(api_token=FINMIND_API_TOKEN)
    return loader


def resolve_data_sources(*, data_loader_cls=DataLoader, data_source=None, data_sources: list | None = None) -> list:
    if data_source is not None:
        return [data_source]
    if data_sources:
        return list(data_sources)
    if data_loader_cls is not DataLoader and data_loader_cls is not None:
        return [FinMindScreenerDataSource(data_loader_cls)]
    sources = [TwseFreeScreenerDataSource()]
    if data_loader_cls is not None:
        sources.append(FinMindScreenerDataSource(data_loader_cls))
    return sources


def first_available_frame(sources: list, operation: str, fetcher, warnings: list[dict]) -> tuple[pd.DataFrame, str]:
    for source in sources:
        provider = provider_name(source)
        try:
            value = fetcher(source)
        except Exception as exc:
            warnings.append(log_http_warning(provider, operation, exc))
            continue
        frame = value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()
        if not frame.empty:
            return frame, provider
    return pd.DataFrame(), ""
