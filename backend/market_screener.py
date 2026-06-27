"""Daily market screener for upstream watchlist discovery."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

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


def run_daily_market_screener(
    *,
    now: datetime | None = None,
    force: bool = False,
    data_loader_cls=DataLoader,
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
    scan = scan_taiwan_market(scan_date=now.date(), data_loader_cls=data_loader_cls, top_n=top_n)
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
    top_n: int = 10,
) -> dict:
    scan_date = scan_date or datetime.now(TAIPEI).date()
    if data_loader_cls is None:
        return {
            "success": False,
            "market": "TW",
            "screen_date": scan_date.isoformat(),
            "candidates": [],
            "warnings": [{"provider": "FinMind", "message": "FinMind DataLoader unavailable"}],
        }

    warnings = []
    loader = _build_finmind_loader(data_loader_cls)
    institutional = _safe_fetch_frame(
        "FinMind",
        "TaiwanStockInstitutionalInvestorsBuySell",
        lambda: loader.taiwan_stock_institutional_investors(
            start_date=(scan_date - timedelta(days=14)).isoformat(),
            end_date=scan_date.isoformat(),
        ),
        warnings,
    )
    daily = _safe_fetch_frame(
        "FinMind",
        "TaiwanStockPrice",
        lambda: loader.taiwan_stock_daily(
            start_date=(scan_date - timedelta(days=90)).isoformat(),
            end_date=scan_date.isoformat(),
        ),
        warnings,
    )

    candidates = []
    candidates.extend(_institutional_candidates(institutional, scan_date=scan_date, top_n=top_n))
    candidates.extend(_technical_candidates(daily, scan_date=scan_date, top_n=top_n))
    merged = _merge_candidates(candidates)
    return {
        "success": bool(merged) or not warnings,
        "market": "TW",
        "screen_date": scan_date.isoformat(),
        "candidates": merged,
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


def _safe_fetch_frame(provider: str, operation: str, fetcher, warnings: list[dict]) -> pd.DataFrame:
    try:
        value = fetcher()
    except Exception as exc:
        warning = log_http_warning(provider, operation, exc)
        warnings.append(warning)
        return pd.DataFrame()
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


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
    if df.empty or volume_column is None or not {"date", "stock_id", "close"} <= set(df.columns):
        return []
    latest, latest_date = _latest_rows(df, scan_date)
    if latest.empty:
        return []
    latest_stock_ids = set(latest["stock_id"].map(str))
    working = df[df["stock_id"].map(str).isin(latest_stock_ids)].copy()
    working["_date"] = pd.to_datetime(working["date"], errors="coerce")
    working["_close"] = working["close"].map(_safe_float)
    working["_volume"] = working[volume_column].map(_safe_float)
    records = []
    for stock_id, rows in working.groupby(working["stock_id"].map(str)):
        if not _is_common_tw_stock_id(stock_id):
            continue
        rows = rows.dropna(subset=["_date", "_close", "_volume"]).sort_values("_date")
        rows = rows[rows["_date"].dt.date <= scan_date]
        if len(rows) < 20:
            continue
        latest_row = rows.iloc[-1]
        if latest_row["_date"].date().isoformat() != latest_date:
            continue
        ma20 = float(rows["_close"].tail(20).mean())
        if ma20 <= 0:
            continue
        previous_volume = rows["_volume"].iloc[:-1].tail(20)
        average_volume = float(previous_volume.mean()) if not previous_volume.empty else 0.0
        close = float(latest_row["_close"])
        latest_volume = float(latest_row["_volume"])
        bias_pct = ((close / ma20) - 1) * 100
        volume_ratio = latest_volume / average_volume if average_volume > 0 else 0.0
        if abs(bias_pct) < DEFAULT_BIAS_THRESHOLD_PCT and volume_ratio < DEFAULT_VOLUME_SPIKE_RATIO:
            continue
        score = abs(bias_pct) + max(volume_ratio - 1, 0) * 5
        records.append({
            "ticker": _tw_ticker(stock_id),
            "category": "technical_heat",
            "categories": ["technical_heat"],
            "screen_date": latest_date,
            "score": round(score, 2),
            "reason": f"乖離率 {bias_pct:.1f}%，成交量放大 {volume_ratio:.1f}x",
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


def _institutional_category(name: Any) -> str:
    text = str(name or "")
    if "Foreign" in text or "外資" in text:
        return "foreign"
    if "Investment_Trust" in text or "投信" in text:
        return "investment_trust"
    return "dealer"


def _safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(number):
        return 0.0
    return number


def _is_common_tw_stock_id(stock_id: Any) -> bool:
    text = str(stock_id or "").strip()
    return len(text) == 4 and text.isdigit()


def _tw_ticker(stock_id: Any) -> str:
    text = str(stock_id or "").strip().upper()
    return text if "." in text else f"{text}.TW"


def _taipei_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(TAIPEI)
    if now.tzinfo is None:
        return now.replace(tzinfo=TAIPEI)
    return now.astimezone(TAIPEI)


def _date_text(value: str | date) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)
