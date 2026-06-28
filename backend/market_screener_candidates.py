"""Candidate construction and quality enrichment for market screener."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from market_screener_utils import clean_company_name, is_common_tw_stock_id, safe_float, tw_ticker
from quality_funnel import evaluate_quality_funnel


DEFAULT_BIAS_THRESHOLD_PCT = 8.0
DEFAULT_VOLUME_SPIKE_RATIO = 2.5


def build_screener_candidates(institutional: pd.DataFrame, daily: pd.DataFrame, *, scan_date: date, top_n: int) -> list[dict]:
    candidates = []
    candidates.extend(institutional_candidates(institutional, scan_date=scan_date, top_n=top_n))
    candidates.extend(technical_candidates(daily, scan_date=scan_date, top_n=top_n))
    return attach_quality_funnel(merge_candidates(candidates))


def institutional_candidates(df: pd.DataFrame, *, scan_date: date, top_n: int) -> list[dict]:
    if df.empty or not {"date", "stock_id", "name", "buy", "sell"} <= set(df.columns):
        return []
    latest, latest_date = latest_rows(df, scan_date)
    if latest.empty:
        return []
    latest = latest.copy()
    latest["stock_id"] = latest["stock_id"].map(str)
    latest["net_buy"] = latest["buy"].map(safe_float) - latest["sell"].map(safe_float)
    latest["category"] = latest["name"].map(institutional_category)
    latest = latest[latest["stock_id"].map(is_common_tw_stock_id) & latest["category"].isin({"foreign", "investment_trust"})]
    if latest.empty:
        return []
    company_names = company_names_by_stock_id(latest)
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
            "ticker": tw_ticker(stock_id),
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


def technical_candidates(df: pd.DataFrame, *, scan_date: date, top_n: int) -> list[dict]:
    volume_column = volume_column_name(df)
    average_column = monthly_average_column(df)
    if df.empty or not {"date", "stock_id", "close"} <= set(df.columns):
        return []
    latest, latest_date = latest_rows(df, scan_date)
    if latest.empty:
        return []
    working = df[df["stock_id"].map(str).isin(set(latest["stock_id"].map(str)))].copy()
    working["_date"] = pd.to_datetime(working["date"], errors="coerce")
    working["_close"] = working["close"].map(safe_float)
    if volume_column is not None:
        working["_volume"] = working[volume_column].map(safe_float)
    records = []
    for stock_id, rows in working.groupby(working["stock_id"].map(str)):
        record = technical_candidate_record(stock_id, rows, scan_date, latest_date, volume_column, average_column)
        if record:
            records.append(record)
    return sorted(records, key=lambda item: float(item.get("score") or 0), reverse=True)[:top_n]


def technical_candidate_record(stock_id: str, rows: pd.DataFrame, scan_date: date, latest_date: str, volume_column: str | None, average_column: str | None) -> dict:
    if not is_common_tw_stock_id(stock_id):
        return {}
    required_subset = ["_date", "_close"] + (["_volume"] if volume_column is not None else [])
    rows = rows.dropna(subset=required_subset).sort_values("_date")
    rows = rows[rows["_date"].dt.date <= scan_date]
    if len(rows) < 20 and average_column is None:
        return {}
    latest_row = rows.iloc[-1]
    if latest_row["_date"].date().isoformat() != latest_date:
        return {}
    ma20 = safe_float(latest_row.get(average_column)) if average_column else float(rows["_close"].tail(20).mean())
    close = float(latest_row["_close"])
    if ma20 <= 0 or close <= 0:
        return {}
    latest_volume = float(latest_row["_volume"]) if "_volume" in latest_row else 0.0
    previous_volume = rows["_volume"].iloc[:-1].tail(20) if "_volume" in rows else pd.Series(dtype=float)
    average_volume = float(previous_volume.mean()) if not previous_volume.empty else 0.0
    bias_pct = ((close / ma20) - 1) * 100
    volume_ratio = latest_volume / average_volume if average_volume > 0 else 0.0
    if abs(bias_pct) < DEFAULT_BIAS_THRESHOLD_PCT and volume_ratio < DEFAULT_VOLUME_SPIKE_RATIO:
        return {}
    score = abs(bias_pct) + max(volume_ratio - 1, 0) * 5
    reason_parts = [f"乖離率 {bias_pct:.1f}%"]
    if volume_ratio > 0:
        reason_parts.append(f"成交量放大 {volume_ratio:.1f}x")
    return {
        "ticker": tw_ticker(stock_id),
        "company_name": clean_company_name(latest_row.get("company_name")),
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
    }


def merge_candidates(candidates: list[dict]) -> list[dict]:
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


def attach_quality_funnel(candidates: list[dict]) -> list[dict]:
    enriched = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        quality_funnel = candidate.get("quality_funnel")
        if not isinstance(quality_funnel, dict) or not quality_funnel.get("outcome"):
            metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
            quality_funnel = evaluate_quality_funnel(metrics)
        enriched.append({**candidate, "quality_funnel": quality_funnel})
    return enriched


def latest_rows(df: pd.DataFrame, scan_date: date) -> tuple[pd.DataFrame, str]:
    working = df.copy()
    working["_date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["_date"])
    working = working[working["_date"].dt.date <= scan_date]
    if working.empty:
        return working, scan_date.isoformat()
    latest_date = working["_date"].max().date()
    return working[working["_date"].dt.date == latest_date], latest_date.isoformat()


def volume_column_name(df: pd.DataFrame) -> str | None:
    for name in ("Trading_Volume", "trading_volume", "volume"):
        if name in df.columns:
            return name
    return None


def monthly_average_column(df: pd.DataFrame) -> str | None:
    for name in ("monthly_average_close", "MonthlyAveragePrice", "monthly_average_price"):
        if name in df.columns:
            return name
    return None


def company_names_by_stock_id(df: pd.DataFrame) -> dict[str, str]:
    if "company_name" not in df.columns:
        return {}
    result = {}
    for stock_id, rows in df.groupby(df["stock_id"].map(str)):
        for value in rows["company_name"]:
            company_name = clean_company_name(value)
            if company_name:
                result[str(stock_id)] = company_name
                break
    return result


def institutional_category(name: Any) -> str:
    text = str(name or "")
    if "Foreign" in text or "外資" in text:
        return "foreign"
    if "Investment_Trust" in text or "投信" in text:
        return "investment_trust"
    return "dealer"
