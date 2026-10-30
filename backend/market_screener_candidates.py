"""Candidate construction and quality enrichment for market screener."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from market_screener_candidate_query import filter_candidates, paginate_candidates, sort_candidates
from market_screener_utils import clean_company_name, is_common_tw_stock_id, safe_float, tw_ticker
from quality_funnel import evaluate_quality_funnel


DEFAULT_BIAS_THRESHOLD_PCT = 8.0
DEFAULT_VOLUME_SPIKE_RATIO = 2.5


def build_screener_candidates(institutional: pd.DataFrame, daily: pd.DataFrame, *, scan_date: date, top_n: int) -> list[dict]:
    from screener_signal_dimensions import separate_signals
    institution = institutional_candidates(institutional, scan_date=scan_date, top_n=max(top_n, len(institutional)))
    latest, _ = latest_rows(daily, scan_date) if not daily.empty and "date" in daily else (pd.DataFrame(), "")
    volume_key = volume_column_name(daily)
    for row in institution:
        match = latest[latest["stock_id"].map(str) == row["ticker"].split(".")[0]] if not latest.empty else pd.DataFrame()
        if not match.empty and str(match.iloc[-1]["date"])[:10] == row["screen_date"] and volume_key:
            row["metrics"]["latest_volume"] = _optional_observation_number(match.iloc[-1].get(volume_key))
            row["metrics"]["flow_observation_date"] = row["screen_date"]
            row["metrics"]["volume_observation_date"] = str(match.iloc[-1]["date"])[:10]
            row["metrics"]["price_observation_date"] = str(match.iloc[-1]["date"])[:10]
            row["metrics"]["close"] = _optional_observation_number(match.iloc[-1].get("close"))
            _copy_source_observation_metrics(match.iloc[-1], row["metrics"])
    institution = [separate_signals(row) for row in institution]
    institution.sort(key=lambda row: (row["metrics"]["normalized_flow_pct"] is None,
                                     -(row["metrics"]["normalized_flow_pct"] or 0), row["ticker"]))
    technical = technical_candidates(daily, scan_date=scan_date, top_n=top_n)
    return [separate_signals(row) for row in attach_quality_funnel(merge_candidates(institution[:top_n] + technical))]


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
    latest = latest[latest["stock_id"].map(is_common_tw_stock_id) & latest["category"].isin({"foreign", "investment_trust", "dealer"})]
    if latest.empty:
        return []
    company_names = company_names_by_stock_id(latest)
    pivot = latest.groupby(["stock_id", "category"])["net_buy"].sum().unstack()
    for column in ("foreign", "investment_trust", "dealer"):
        if column not in pivot:
            pivot[column] = float("nan")
    pivot["score"] = pivot["foreign"] + pivot["investment_trust"]
    selected = pivot[(pivot["foreign"] > 0) & (pivot["investment_trust"] > 0)].sort_values("score", ascending=False).head(top_n)
    candidates = []
    for stock_id, row in selected.iterrows():
        foreign = float(row["foreign"])
        trust = float(row["investment_trust"])
        dealer = float(row["dealer"]) if pd.notna(row["dealer"]) else None
        candidates.append({
            "ticker": tw_ticker(stock_id),
            "company_name": company_names.get(str(stock_id), ""),
            "category": "institutional_accumulation",
            "categories": ["institutional_accumulation"],
            "screen_date": latest_date,
            "score": round(float(row["score"]) / 1000, 2),
            "reason": f"外資買超 {foreign / 1000:.0f} 張、投信買超 {trust / 1000:.0f} 張；自營商" + (f" {dealer / 1000:.0f} 張" if dealer is not None else "未知"),
            "metrics": {
                "foreign_net_buy_shares": int(foreign),
                "investment_trust_net_buy_shares": int(trust),
                "dealer_net_buy_shares": int(dealer) if dealer is not None else None,
                "total_net_buy_shares": int(foreign + trust + dealer) if dealer is not None else None,
                "foreign_trust_net_buy_shares": int(foreign + trust),
                "flow_observation_date": latest_date,
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
    working["_close"] = working["close"].map(_optional_observation_number)
    if volume_column is not None:
        working["_volume"] = working[volume_column].map(_optional_observation_number)
    records = []
    for stock_id, rows in working.groupby(working["stock_id"].map(str)):
        record = technical_candidate_record(stock_id, rows, scan_date, latest_date, volume_column, average_column)
        if record:
            records.append(record)
    return sorted(records, key=lambda item: float(item.get("score") or 0), reverse=True)[:top_n]


def technical_candidate_record(stock_id: str, rows: pd.DataFrame, scan_date: date, latest_date: str, volume_column: str | None, average_column: str | None) -> dict:
    if not is_common_tw_stock_id(stock_id):
        return {}
    required_subset = ["_date", "_close"]
    rows = rows.dropna(subset=required_subset).sort_values("_date")
    rows = rows[rows["_date"].dt.date <= scan_date]
    rows = rows[rows["_close"] > 0]
    if rows.empty or (len(rows) < 20 and average_column is None):
        return {}
    latest_row = rows.iloc[-1]
    if latest_row["_date"].date().isoformat() != latest_date:
        return {}
    ma20 = safe_float(latest_row.get(average_column)) if average_column else float(rows["_close"].tail(20).mean())
    close = float(latest_row["_close"])
    if ma20 <= 0 or close <= 0:
        return {}
    latest_volume = _optional_observation_number(latest_row.get("_volume"))
    if latest_volume is not None and latest_volume < 0:latest_volume=None
    previous_volume = rows["_volume"].iloc[:-1].tail(20) if "_volume" in rows else pd.Series(dtype=float)
    average_volume = float(previous_volume.mean()) if len(previous_volume) >= 20 and previous_volume.notna().all() and (previous_volume >= 0).all() else None
    bias_pct = ((close / ma20) - 1) * 100
    volume_ratio = latest_volume / average_volume if latest_volume is not None and average_volume and average_volume > 0 else None
    if abs(bias_pct) < DEFAULT_BIAS_THRESHOLD_PCT and (volume_ratio or 0) < DEFAULT_VOLUME_SPIKE_RATIO:
        return {}
    score = abs(bias_pct) + max((volume_ratio or 0) - 1, 0) * 5
    reason_parts = [f"乖離率 {bias_pct:.1f}%"]
    if volume_ratio is not None and volume_ratio > 0:
        reason_parts.append(f"成交量放大 {volume_ratio:.1f}x")
    metrics = {
        "close": round(close, 4),
        "ma20": round(ma20, 4) if average_column is None else None,
        "reference_average_price": round(ma20, 4),
        "bias_reference_basis": "provider_monthly_average;not_verified_rolling_20_sessions" if average_column else "observed_last_20_closes;session_coverage_unverified",
        "bias_pct": round(bias_pct, 4),
        "latest_volume": int(latest_volume) if volume_column and latest_volume is not None else None,
        "average_volume_20d": int(average_volume) if average_volume is not None else None,
        "volume_ratio": round(volume_ratio, 4) if volume_ratio is not None else None,
        "volume_ratio_policy": "latest / previous 20 observed volumes;all 20 must be finite nonnegative;missing stays unknown",
        "price_observation_date": latest_date,
        "volume_observation_date": latest_date if volume_column else None,
    }
    _copy_optional_latest_metrics(latest_row, metrics)
    _copy_source_observation_metrics(latest_row, metrics)
    return {
        "ticker": tw_ticker(stock_id),
        "company_name": clean_company_name(latest_row.get("company_name")),
        "category": "technical_heat",
        "categories": ["technical_heat"],
        "screen_date": latest_date,
        "score": round(score, 2),
        "reason": "，".join(reason_parts),
        "metrics": metrics,
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
            quality_funnel = evaluate_quality_funnel(
                metrics,
                sector=candidate.get("sector") or metrics.get("sector"),
                industry=candidate.get("industry") or metrics.get("industry"),
            )
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


def _copy_optional_latest_metrics(row: pd.Series, metrics: dict) -> None:
    aliases = {
        "rsi_14": ("rsi_14", "rsi", "RSI"),
        "macd": ("macd", "MACD"),
        "macd_signal": ("macd_signal", "MACD_signal", "signal"),
        "macd_histogram": ("macd_histogram", "MACD_histogram", "histogram"),
        "revenue_growth_yoy_pct": ("revenue_growth_yoy_pct", "monthly_revenue_growth_yoy_pct", "revenue_yoy_pct"),
    }
    for metric_name, source_names in aliases.items():
        for source_name in source_names:
            if source_name not in row or pd.isna(row.get(source_name)):
                continue
            metrics[metric_name] = round(safe_float(row.get(source_name)), 4)
            break


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


def _copy_source_observation_metrics(row, metrics):
    for key in ("price_source_url","volume_source_url","latest_volume_unit","price_response_sha256","response_hash_kind","monthly_average_observation_date"):
        value=row.get(key)
        if isinstance(value,str) and value.strip():metrics[key]=value


def _optional_observation_number(value):
    from screener_twse_daily import numeric
    return numeric(value)
