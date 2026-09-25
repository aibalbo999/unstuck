"""Dated Taiwan peer identities and exact-stock valuation recovery.

No financial statement arithmetic is inferred here. FinMind TaiwanStockPER
preserves the exchanges' reported ratios; zero/negative PER is not a valid PE.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from functools import lru_cache
from math import isfinite
import re
from zoneinfo import ZoneInfo

from source_observation_freshness import parse_observation_date


NON_SPECIFIC_CATEGORIES = {"上市股票", "上櫃股票", "興櫃股票", "電子工業", "其他", "其他業"}
NON_EQUITY_CATEGORIES = {"ETF", "ETN", "指數", "受益證券", "認購權證", "認售權證", "存託憑證", "大盤"}
MASTER_MAX_AGE_DAYS = 7


def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


@lru_cache(maxsize=1)
def _master_for_day(day: date) -> list[dict]:
    from .identity import load_taiwan_stock_info_records

    # The legacy loader otherwise keeps historical membership for the lifetime
    # of a worker. Refresh once per day, sharing the result within this process.
    load_taiwan_stock_info_records.cache_clear()
    return load_taiwan_stock_info_records()


def load_peer_stock_master() -> list[dict]:
    return _master_for_day(_today())


def _current_rows(rows: list[dict], today: date, master_day: date | None = None) -> tuple[list[dict], str | None]:
    dated = [(parse_observation_date(row.get("date")), row) for row in rows]
    dates = [day for day, _ in dated if day is not None and day <= today]
    if not dates:
        return [], "undated_master_row"
    latest = max(dates)
    if (today - latest).days > MASTER_MAX_AGE_DAYS:
        return [], "stale_master_row"
    if master_day is not None and latest < master_day:
        return [], "historical_master_row"
    current = [row for day, row in dated if day == latest]
    markets = {str(row.get("type", "")).lower() for row in current}
    if len(markets) != 1 or not markets <= {"twse", "tpex"}:
        return [], "unsupported_or_ambiguous_market"
    return current, None


def resolve_legacy_peer_candidates(ticker: str, identity: dict, rows: list[dict], *, today: date) -> tuple[list[dict], dict]:
    grouped = defaultdict(list)
    for row in rows:
        if isinstance(row, dict):
            grouped[str(row.get("stock_id", "")).strip()].append(row)
    master_day = max((day for row in rows if isinstance(row, dict)
                      if (day := parse_observation_date(row.get("date"))) is not None and day <= today), default=None)
    target_id = ticker.split(".")[0]
    target_rows, target_error = _current_rows(grouped.get(target_id, []), today, master_day)
    audit = {"selection_status": "selected", "selection_rejected_reason_counts": {},
             "selection_basis": "current_master_industry; business_and_size_comparability_unverified"}
    if target_error:
        return [], {**audit, "selection_status": "target_" + target_error}
    categories = {str(r.get("industry_category", "")) for r in target_rows} - NON_SPECIFIC_CATEGORIES - NON_EQUITY_CATEGORIES - {""}
    if not categories:
        return [], {**audit, "selection_status": "broad_industry_only"}
    audit["current_industry_categories"] = sorted(categories)
    ordered_ids = [str(p.get("stock_id", "")) for p in identity.get("same_industry_peers", []) if isinstance(p, dict)]
    # Existing cached identities can predate newly listed peers. The same
    # current category is required for both legacy and newly discovered rows.
    ordered_ids.extend(s for s in sorted(grouped) if any(r.get("industry_category") in categories for r in grouped[s]))
    seen = set()
    rejected = Counter()
    candidates = []
    for stock_id in ordered_ids:
        if stock_id == target_id or stock_id in seen:
            continue
        seen.add(stock_id)
        if not re.fullmatch(r"[1-9]\d{3}", stock_id):
            rejected["not_ordinary_equity_code"] += 1
            continue
        current, error = _current_rows(grouped.get(stock_id, []), today, master_day)
        if error:
            rejected[error] += 1
            continue
        peer_categories = {str(r.get("industry_category", "")) for r in current}
        if peer_categories & NON_EQUITY_CATEGORIES or not peer_categories & categories:
            rejected["current_industry_mismatch"] += 1
            continue
        row = current[0]
        suffix = ".TW" if row["type"].lower() == "twse" else ".TWO"
        candidates.append({"name": row["stock_name"], "ticker": stock_id + suffix,
                           "identity_status": "verified_master", "master_observed_at": row["date"],
                           "comparison_status": "industry_candidate_only",
                           "industry_categories": sorted(peer_categories)})
    audit.update(selection_rejected_reason_counts=dict(rejected), candidate_count=len(candidates))
    if not candidates:
        audit["selection_status"] = "no_eligible_current_peers"
    return candidates, audit


def finite_number(value, *, positive=False):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or (positive and number <= 0):
        return None
    return number


def industry_comparability(target: str, candidate: str) -> str:
    """A coarse exchange industry is insufficient when finer data disagrees."""
    def normalized(value):
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value).casefold())
    left, right = normalized(target), normalized(candidate)
    if not left or not right:
        return "industry_candidate_only"
    if left == right:
        return "business_industry_matched"
    families = ({"medicaldevices", "medicalinstrumentssupplies"},
                {"banksregional", "banksdiversified"})
    if any(left in family and right in family for family in families):
        return "business_industry_matched"
    return "business_industry_mismatch"


def select_peer_valuation_observation(rows: list[dict], ticker: str, *, today: date) -> dict:
    stock_id = ticker.split(".")[0]
    valid = []
    rejected = 0
    for row in rows:
        day = parse_observation_date(row.get("date"))
        if (str(row.get("stock_id", "")).strip() != stock_id or day is None
                or not 0 <= (today - day).days <= 7):
            rejected += 1
            continue
        valid.append((day, row))
    result = {"metrics": {}, "status": "valid_empty", "source": "FinMind TaiwanStockPER",
              "rejected_row_count": rejected, "observation_policy": "within_7_calendar_days; not latest-session guarantee"}
    if not valid:
        return result
    latest = max(day for day, _ in valid)
    latest_rows = [row for day, row in valid if day == latest]
    normalized = [{field: round(number, 4) for source, field in (("PER", "pe_ttm"), ("PBR", "pb"))
                   if (number := finite_number(row.get(source), positive=True)) is not None}
                  for row in latest_rows]
    if any(row != normalized[0] for row in normalized[1:]):
        return {**result, "status": "conflicting_observations", "observed_at": latest.isoformat()}
    return {**result, "metrics": normalized[0], "observed_at": latest.isoformat(),
            "status": "success" if normalized[0] else "metrics_missing",
            "metric_basis": {"pe_ttm": "exchange_reported_price_to_latest_four_quarters_earnings",
                             "pb": "exchange_reported_price_to_book"}}


def fetch_peer_valuation_fallback(ticker: str, *, today: date | None = None) -> dict:
    from cache_store import get_cache_json, set_cache_json
    from .taiwan import DataLoader

    today = today or _today()
    if DataLoader is None or not re.fullmatch(r"[1-9]\d{3}\.TW[O]?", ticker):
        return {"metrics": {}, "status": "not_applicable"}
    cache_key = f"peer_valuation:v1:{ticker}:{today.isoformat()}"
    cached = get_cache_json(cache_key)
    if isinstance(cached, dict):
        return {**cached, "cache_hit": True}
    try:
        frame = DataLoader().taiwan_stock_per_pbr(stock_id=ticker.split(".")[0],
                                                start_date=(today - timedelta(days=10)).isoformat(),
                                                end_date=today.isoformat(), timeout=8)
        result = select_peer_valuation_observation(frame.to_dict("records") if frame is not None else [], ticker, today=today)
    except Exception as exc:
        result = {"metrics": {}, "status": "download_failed", "error_kind": type(exc).__name__}
    set_cache_json(cache_key, result, 1800 if result.get("metrics") else 300)
    return {**result, "cache_hit": False}
