"""Daily market screener for upstream watchlist discovery."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import requests

from config import FINMIND_API_TOKEN
from data_fetch.market_sources.taiwan import DataLoader
from external_http_client import log_http_warning
import watchlist_service
import watchlist_store


TAIPEI = watchlist_store.TAIPEI
AUTO_SCREENER_TAG = "Auto-Screener"
DAILY_SCREENER_SOURCE = "daily_screener"
DAILY_SCREENER_PIPELINE = "v4"
SCREENER_META_KEY = "daily_market_screener:last_run_date"
DEFAULT_BIAS_THRESHOLD_PCT = 8.0
DEFAULT_VOLUME_SPIKE_RATIO = 2.5
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
        return _build_finmind_loader(self.data_loader_cls)

    def fetch_institutional_frame(self, scan_date: date) -> pd.DataFrame:
        loader = self._loader()
        return loader.taiwan_stock_institutional_investors(
            start_date=(scan_date - timedelta(days=14)).isoformat(),
            end_date=scan_date.isoformat(),
        )

    def fetch_daily_frame(self, scan_date: date) -> pd.DataFrame:
        loader = self._loader()
        return loader.taiwan_stock_daily(
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
            _clean_tw_stock_id(row.get("Code") or row.get("證券代號")): _safe_float(row.get("MonthlyAveragePrice") or row.get("月平均價"))
            for row in self._json_get(TWSE_STOCK_DAY_AVG_ALL_URL)
            if isinstance(row, dict)
        }
        records = []
        for row in day_rows:
            if not isinstance(row, dict):
                continue
            stock_id = _clean_tw_stock_id(row.get("Code") or row.get("證券代號"))
            if not _is_common_tw_stock_id(stock_id):
                continue
            record_date = _twse_date_to_iso(row.get("Date")) or scan_date.isoformat()
            records.append({
                "date": record_date,
                "stock_id": stock_id,
                "company_name": _clean_company_name(row.get("Name") or row.get("證券名稱")),
                "close": _safe_float(row.get("ClosingPrice") or row.get("收盤價")),
                "Trading_Volume": _safe_float(row.get("TradeVolume") or row.get("成交股數")),
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
        record_date = _twse_date_to_iso(payload.get("date")) or scan_date.isoformat()
        records = []
        for row in payload.get("data") or []:
            if not isinstance(row, list) or len(row) < 5:
                continue
            stock_id = _clean_tw_stock_id(row[1])
            if not _is_common_tw_stock_id(stock_id):
                continue
            records.append({
                "date": record_date,
                "stock_id": stock_id,
                "company_name": _clean_company_name(row[2] if len(row) > 2 else ""),
                "name": investor_name,
                "buy": _safe_float(row[3]),
                "sell": _safe_float(row[4]),
            })
        return records


TwseOpenApiScreenerDataSource = TwseFreeScreenerDataSource


def run_daily_market_screener(
    *,
    now: datetime | None = None,
    force: bool = False,
    data_loader_cls=DataLoader,
    data_source=None,
    data_sources: list | None = None,
    top_n: int = 10,
) -> dict:
    now = _taipei_now(now)
    run_date = now.date().isoformat()
    if not force and screener_already_ran(run_date):
        return {
            "success": True,
            "market": "TW",
            "screen_date": run_date,
            "candidates": [],
            "warnings": [],
            "imported": [],
            "imported_count": 0,
            "errors": [],
            "candidate_count": 0,
            "skipped": [{"reason": "already_ran", "run_date": run_date}],
        }
    scan = scan_taiwan_market(
        scan_date=now.date(),
        data_loader_cls=data_loader_cls,
        data_source=data_source,
        data_sources=data_sources,
        top_n=top_n,
    )
    imported = import_candidates_to_watchlist(scan.get("candidates") or [])
    return {
        **scan,
        **imported,
        "success": bool(scan.get("success")) and not imported.get("errors"),
        "candidate_count": len(scan.get("candidates") or []),
    }


def scan_taiwan_market(
    *,
    scan_date: date | None = None,
    data_loader_cls=DataLoader,
    data_source=None,
    data_sources: list | None = None,
    top_n: int = 10,
) -> dict:
    scan_date = scan_date or datetime.now(TAIPEI).date()
    warnings = []
    sources = _resolve_data_sources(data_loader_cls=data_loader_cls, data_source=data_source, data_sources=data_sources)
    institutional, institutional_provider = _first_available_frame(
        sources,
        "institutional trades",
        lambda source: source.fetch_institutional_frame(scan_date),
        warnings,
    )
    daily, daily_provider = _first_available_frame(
        sources,
        "daily prices",
        lambda source: source.fetch_daily_frame(scan_date),
        warnings,
    )

    candidates = []
    candidates.extend(_institutional_candidates(institutional, scan_date=scan_date, top_n=top_n))
    candidates.extend(_technical_candidates(daily, scan_date=scan_date, top_n=top_n))
    merged = _merge_candidates(candidates)
    providers = _unique([institutional_provider, daily_provider])
    data_source_names = _unique([_provider_name(source) for source in sources])
    return {
        "success": bool(merged) or not warnings,
        "market": "TW",
        "screen_date": scan_date.isoformat(),
        "candidates": merged,
        "candidate_count": len(merged),
        "providers": providers,
        "data_sources": data_source_names,
        "warnings": warnings,
    }


def import_candidates_to_watchlist(candidates: list[dict]) -> dict:
    imported = []
    errors = []
    for candidate in _merge_candidates(candidates):
        ticker = str(candidate.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        categories = candidate.get("categories") if isinstance(candidate.get("categories"), list) else [candidate.get("category")]
        categories = [str(category) for category in categories if category]
        tags = [AUTO_SCREENER_TAG, *categories]
        trigger = {
            "key": "daily_screener",
            "type": DAILY_SCREENER_SOURCE,
            "company_name": str(candidate.get("company_name") or ""),
            "category": candidate.get("category") or "",
            "categories": categories,
            "screen_date": str(candidate.get("screen_date") or ""),
            "reason": str(candidate.get("reason") or ""),
            "score": candidate.get("score"),
            "metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
        }
        try:
            watchlist_service.upsert_watchlist_item({
                "ticker": ticker,
                "pipeline": DAILY_SCREENER_PIPELINE,
                "enabled": True,
                "schedule_slots": ["post_market"],
                "tags": tags,
                "trigger_source": DAILY_SCREENER_SOURCE,
                "triggers": [trigger],
            })
            imported.append({"ticker": ticker, "pipeline": DAILY_SCREENER_PIPELINE, "trigger": trigger})
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)[:240]})
    return {"imported": imported, "imported_count": len(imported), "errors": errors}


def list_auto_screener_watchlist(output_dir: str | None = None) -> dict:
    payload = watchlist_service.list_watchlist_with_report_alerts(output_dir or "")
    items = [
        item for item in payload.get("items", [])
        if item.get("trigger_source") == DAILY_SCREENER_SOURCE or AUTO_SCREENER_TAG in (item.get("tags") or [])
    ]
    category_counts: dict[str, int] = {}
    for item in items:
        for tag in item.get("tags") or []:
            if tag != AUTO_SCREENER_TAG:
                category_counts[tag] = category_counts.get(tag, 0) + 1
    return {**payload, "items": items, "category_counts": category_counts, "auto_screener_count": len(items)}


def screener_already_ran(run_date: str | date) -> bool:
    run_date_text = _date_text(run_date)
    with watchlist_store._connect() as conn:
        return watchlist_store._meta_value(conn, SCREENER_META_KEY) == run_date_text


def mark_screener_ran(run_date: str | date) -> None:
    run_date_text = _date_text(run_date)
    with watchlist_store._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        watchlist_store._set_meta(conn, SCREENER_META_KEY, run_date_text)
        watchlist_store._touch_store(conn)


def _build_finmind_loader(data_loader_cls):
    loader = data_loader_cls()
    if FINMIND_API_TOKEN and hasattr(loader, "login_by_token"):
        loader.login_by_token(api_token=FINMIND_API_TOKEN)
    return loader


def _resolve_data_sources(*, data_loader_cls=DataLoader, data_source=None, data_sources: list | None = None) -> list:
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


def _first_available_frame(sources: list, operation: str, fetcher, warnings: list[dict]) -> tuple[pd.DataFrame, str]:
    for source in sources:
        provider = _provider_name(source)
        try:
            value = fetcher(source)
        except Exception as exc:
            warning = log_http_warning(provider, operation, exc)
            warnings.append(warning)
            continue
        frame = value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()
        if not frame.empty:
            return frame, provider
    return pd.DataFrame(), ""


def _institutional_candidates(df: pd.DataFrame, *, scan_date: date, top_n: int) -> list[dict]:
    if df.empty or not {"date", "stock_id", "name", "buy", "sell"} <= set(df.columns):
        return []
    latest, latest_date = _latest_rows(df, scan_date)
    if latest.empty:
        return []
    latest = latest.copy()
    latest["stock_id"] = latest["stock_id"].map(str)
    latest["net_buy"] = latest["buy"].map(_safe_float) - latest["sell"].map(_safe_float)
    latest["category"] = latest["name"].map(_institutional_category)
    latest = latest[latest["stock_id"].map(_is_common_tw_stock_id) & latest["category"].isin({"foreign", "investment_trust"})]
    if latest.empty:
        return []
    company_names = _company_names_by_stock_id(latest)
    pivot = latest.groupby(["stock_id", "category"])["net_buy"].sum().unstack(fill_value=0)
    for column in ("foreign", "investment_trust"):
        if column not in pivot:
            pivot[column] = 0.0
    pivot["score"] = pivot["foreign"] + pivot["investment_trust"]
    selected = pivot[(pivot["foreign"] > 0) & (pivot["investment_trust"] > 0)].sort_values("score", ascending=False).head(top_n)
    candidates = []
    for stock_id, row in selected.iterrows():
        foreign = float(row["foreign"])
        trust = float(row["investment_trust"])
        candidates.append({
            "ticker": _tw_ticker(stock_id),
            "company_name": company_names.get(str(stock_id), ""),
            "category": "institutional_accumulation",
            "categories": ["institutional_accumulation"],
            "screen_date": latest_date,
            "score": round(float(row["score"]) / 1000, 2),
            "reason": f"外資買超 {foreign / 1000:.0f} 張、投信買超 {trust / 1000:.0f} 張",
            "metrics": {
                "foreign_net_buy_shares": int(foreign),
                "investment_trust_net_buy_shares": int(trust),
                "total_net_buy_shares": int(row["score"]),
            },
        })
    return candidates


def _technical_candidates(df: pd.DataFrame, *, scan_date: date, top_n: int) -> list[dict]:
    volume_column = _volume_column(df)
    average_column = _monthly_average_column(df)
    if df.empty or not {"date", "stock_id", "close"} <= set(df.columns):
        return []
    latest, latest_date = _latest_rows(df, scan_date)
    if latest.empty:
        return []
    latest_stock_ids = set(latest["stock_id"].map(str))
    working = df[df["stock_id"].map(str).isin(latest_stock_ids)].copy()
    working["_date"] = pd.to_datetime(working["date"], errors="coerce")
    working["_close"] = working["close"].map(_safe_float)
    if volume_column is not None:
        working["_volume"] = working[volume_column].map(_safe_float)
    records = []
    for stock_id, rows in working.groupby(working["stock_id"].map(str)):
        if not _is_common_tw_stock_id(stock_id):
            continue
        required_subset = ["_date", "_close"]
        if volume_column is not None:
            required_subset.append("_volume")
        rows = rows.dropna(subset=required_subset).sort_values("_date")
        rows = rows[rows["_date"].dt.date <= scan_date]
        if len(rows) < 20 and average_column is None:
            continue
        latest_row = rows.iloc[-1]
        if latest_row["_date"].date().isoformat() != latest_date:
            continue
        ma20 = _safe_float(latest_row.get(average_column)) if average_column else float(rows["_close"].tail(20).mean())
        if ma20 <= 0:
            continue
        close = float(latest_row["_close"])
        if close <= 0:
            continue
        latest_volume = float(latest_row["_volume"]) if "_volume" in latest_row else 0.0
        previous_volume = rows["_volume"].iloc[:-1].tail(20) if "_volume" in rows else pd.Series(dtype=float)
        average_volume = float(previous_volume.mean()) if not previous_volume.empty else 0.0
        bias_pct = ((close / ma20) - 1) * 100
        volume_ratio = latest_volume / average_volume if average_volume > 0 else 0.0
        if abs(bias_pct) < DEFAULT_BIAS_THRESHOLD_PCT and volume_ratio < DEFAULT_VOLUME_SPIKE_RATIO:
            continue
        score = abs(bias_pct) + max(volume_ratio - 1, 0) * 5
        reason_parts = [f"乖離率 {bias_pct:.1f}%"]
        if volume_ratio > 0:
            reason_parts.append(f"成交量放大 {volume_ratio:.1f}x")
        records.append({
            "ticker": _tw_ticker(stock_id),
            "company_name": _clean_company_name(latest_row.get("company_name")),
            "category": "technical_heat",
            "categories": ["technical_heat"],
            "screen_date": latest_date,
            "score": round(score, 2),
            "reason": "，".join(reason_parts),
            "metrics": {
                "close": round(close, 4),
                "ma20": round(ma20, 4),
                "bias_pct": round(bias_pct, 4),
                "latest_volume": int(latest_volume),
                "average_volume_20d": int(average_volume),
                "volume_ratio": round(volume_ratio, 4),
            },
        })
    return sorted(records, key=lambda item: float(item.get("score") or 0), reverse=True)[:top_n]


def _merge_candidates(candidates: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for candidate in candidates:
        ticker = str(candidate.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        existing = merged.get(ticker)
        if existing is None:
            merged[ticker] = {**candidate, "ticker": ticker}
            continue
        categories = list(dict.fromkeys([*(existing.get("categories") or []), *(candidate.get("categories") or [candidate.get("category")])]))
        reasons = [existing.get("reason"), candidate.get("reason")]
        existing["categories"] = [category for category in categories if category]
        existing["reason"] = "；".join(str(reason) for reason in reasons if reason)
        existing["score"] = max(float(existing.get("score") or 0), float(candidate.get("score") or 0))
        if not existing.get("company_name") and candidate.get("company_name"):
            existing["company_name"] = candidate.get("company_name")
        existing["metrics"] = {**(existing.get("metrics") or {}), **(candidate.get("metrics") or {})}
    return sorted(merged.values(), key=lambda item: (str(item.get("screen_date") or ""), float(item.get("score") or 0)), reverse=True)


def _latest_rows(df: pd.DataFrame, scan_date: date) -> tuple[pd.DataFrame, str]:
    working = df.copy()
    working["_date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["_date"])
    working = working[working["_date"].dt.date <= scan_date]
    if working.empty:
        return working, scan_date.isoformat()
    latest_date = working["_date"].max().date()
    return working[working["_date"].dt.date == latest_date], latest_date.isoformat()


def _volume_column(df: pd.DataFrame) -> str | None:
    for name in ("Trading_Volume", "trading_volume", "volume"):
        if name in df.columns:
            return name
    return None


def _monthly_average_column(df: pd.DataFrame) -> str | None:
    for name in ("monthly_average_close", "MonthlyAveragePrice", "monthly_average_price"):
        if name in df.columns:
            return name
    return None


def _company_names_by_stock_id(df: pd.DataFrame) -> dict[str, str]:
    if "company_name" not in df.columns:
        return {}
    result = {}
    for stock_id, rows in df.groupby(df["stock_id"].map(str)):
        for value in rows["company_name"]:
            company_name = _clean_company_name(value)
            if company_name:
                result[str(stock_id)] = company_name
                break
    return result


def _institutional_category(name: Any) -> str:
    text = str(name or "")
    if "Foreign" in text or "外資" in text:
        return "foreign"
    if "Investment_Trust" in text or "投信" in text:
        return "investment_trust"
    return "dealer"


def _safe_float(value: Any) -> float:
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


def _is_common_tw_stock_id(stock_id: Any) -> bool:
    text = str(stock_id or "").strip()
    return len(text) == 4 and text.isdigit()


def _clean_tw_stock_id(stock_id: Any) -> str:
    return "".join(ch for ch in str(stock_id or "").strip() if ch.isdigit())


def _clean_company_name(value: Any) -> str:
    return " ".join(str(value or "").split())


def _tw_ticker(stock_id: Any) -> str:
    text = str(stock_id or "").strip().upper()
    return text if "." in text else f"{text}.TW"


def _twse_date_to_iso(value: Any) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(text) == 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) != 7:
        return ""
    year = int(text[:3]) + 1911
    return f"{year:04d}-{text[3:5]}-{text[5:7]}"


def _provider_name(source: Any) -> str:
    return str(getattr(source, "provider_name", None) or source.__class__.__name__).strip()


def _unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _taipei_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(TAIPEI)
    if now.tzinfo is None:
        return now.replace(tzinfo=TAIPEI)
    return now.astimezone(TAIPEI)


def _date_text(value: str | date) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)
