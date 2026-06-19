"""Peer discovery and peer metric source helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite, log
from typing import Any

import yfinance as yf

from .common import _run_named_fetches


@dataclass(frozen=True)
class CompanyProfile:
    ticker: str
    name: str
    gics_code: str | None
    market: str
    market_cap_twd: float | None
    revenue_twd: float | None
    business_tags: set[str]
    product_keywords: set[str]
    segment_revenue_tags: set[str]


GLOBAL_PEER_HINTS = [
    (["半導體", "Semiconductor", "晶圓", "foundry"], [("Intel", "INTC"), ("Samsung Electronics", "005930.KS"), ("UMC", "2303.TW"), ("SMIC", "0981.HK")]),
    (["記憶體", "Memory", "DRAM", "NAND"], [("Micron", "MU"), ("SK hynix", "000660.KS"), ("Samsung Electronics", "005930.KS")]),
    (["面板", "Display", "LCD", "OLED"], [("AUO", "2409.TW"), ("Innolux", "3481.TW"), ("LG Display", "LPL"), ("BOE", "000725.SZ")]),
    (["航運", "Shipping", "Marine"], [("Evergreen Marine", "2603.TW"), ("Yang Ming", "2609.TW"), ("Wan Hai", "2615.TW"), ("Maersk", "MAERSK-B.CO")]),
]


def _gics_distance(left: str | None, right: str | None) -> int:
    if not left or not right:
        return 99
    if left == right:
        return 0
    if left[:6] == right[:6]:
        return 1
    if left[:4] == right[:4]:
        return 2
    if left[:2] == right[:2]:
        return 3
    return 99


def _overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    normalized_left = {item.strip().casefold() for item in left if item.strip()}
    normalized_right = {item.strip().casefold() for item in right if item.strip()}
    if not normalized_left or not normalized_right:
        return 0.0
    return len(normalized_left & normalized_right) / len(normalized_left | normalized_right)


def _ratio_in_band(value: float | None, target: float | None, low: float, high: float) -> bool:
    if not value or not target or target <= 0:
        return False
    ratio = value / target
    return low <= ratio <= high


def _peer_score(target: CompanyProfile, candidate: CompanyProfile) -> float:
    gics_distance = _gics_distance(target.gics_code, candidate.gics_code)
    if gics_distance > 2:
        return -1
    if not _ratio_in_band(candidate.market_cap_twd, target.market_cap_twd, 0.2, 5.0):
        return -1
    if (
        target.revenue_twd
        and candidate.revenue_twd
        and not _ratio_in_band(candidate.revenue_twd, target.revenue_twd, 0.2, 5.0)
    ):
        return -1

    business_score = max(
        _overlap_score(target.business_tags, candidate.business_tags),
        _overlap_score(target.product_keywords, candidate.product_keywords),
        _overlap_score(target.segment_revenue_tags, candidate.segment_revenue_tags),
    )
    if any((target.business_tags, target.product_keywords, target.segment_revenue_tags)) and business_score == 0:
        return -1

    market_cap_ratio = candidate.market_cap_twd / target.market_cap_twd
    market_cap_score = 1 - min(abs(log(market_cap_ratio)), log(5)) / log(5)
    revenue_score = 0.0
    if _ratio_in_band(candidate.revenue_twd, target.revenue_twd, 0.2, 5.0):
        revenue_ratio = candidate.revenue_twd / target.revenue_twd
        revenue_score = 1 - min(abs(log(revenue_ratio)), log(5)) / log(5)
    gics_score = {0: 1.0, 1: 0.85, 2: 0.65}.get(gics_distance, 0.0)
    return round(
        0.30 * gics_score
        + 0.25 * market_cap_score
        + 0.20 * revenue_score
        + 0.25 * business_score,
        4,
    )


def rank_peer_candidates(target: CompanyProfile, candidates: list[CompanyProfile]) -> list[dict]:
    rows = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized_ticker = candidate.ticker.upper()
        if normalized_ticker == target.ticker.upper() or normalized_ticker in seen:
            continue
        seen.add(normalized_ticker)
        score = _peer_score(target, candidate)
        if score < 0:
            continue
        rows.append({
            "ticker": candidate.ticker,
            "name": candidate.name,
            "market": candidate.market,
            "score": score,
            "market_cap_ratio": (
                round(candidate.market_cap_twd / target.market_cap_twd, 3)
                if candidate.market_cap_twd and target.market_cap_twd
                else None
            ),
            "revenue_ratio": (
                round(candidate.revenue_twd / target.revenue_twd, 3)
                if candidate.revenue_twd and target.revenue_twd
                else None
            ),
            "business_overlap": round(_overlap_score(target.business_tags, candidate.business_tags), 4),
            "product_overlap": round(_overlap_score(target.product_keywords, candidate.product_keywords), 4),
            "segment_overlap": round(
                _overlap_score(target.segment_revenue_tags, candidate.segment_revenue_tags),
                4,
            ),
        })
    return sorted(rows, key=lambda row: (-row["score"], row["ticker"]))


def select_peer_profiles(
    target: CompanyProfile,
    universe: list[CompanyProfile],
    *,
    min_peers: int = 5,
) -> dict:
    target_market = target.market.casefold()
    local_ranked = rank_peer_candidates(
        target,
        [candidate for candidate in universe if candidate.market.casefold() == target_market],
    )
    selected = [row for row in local_ranked if row["score"] >= 0.55]
    expansion_used = False
    if len(selected) < min_peers:
        global_ranked = rank_peer_candidates(
            target,
            [candidate for candidate in universe if candidate.market.casefold() != target_market],
        )
        selected.extend(row for row in global_ranked if row["score"] >= 0.55)
        expansion_used = True
    return {
        "selected_peers": sorted(selected, key=lambda row: (-row["score"], row["ticker"]))[:min_peers],
        "expansion_used": expansion_used,
        "selection_policy": {
            "gics_distance_max": 2,
            "market_cap_band": "0.2x-5.0x",
            "revenue_band_preferred": "0.2x-5.0x",
            "revenue_band_required_when_available": True,
            "business_overlap_required_when_target_tags_available": True,
            "minimum_score": 0.55,
        },
    }


def _optional_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number > 0 else None


def _string_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value.strip()} if value.strip() else set()
    if isinstance(value, (list, tuple, set, frozenset)):
        return {str(item).strip() for item in value if str(item).strip()}
    return set()


def _company_profile_from_mapping(payload: Mapping[str, Any]) -> CompanyProfile | None:
    ticker = str(payload.get("ticker") or "").strip()
    name = str(payload.get("name") or payload.get("company_name") or ticker).strip()
    market = str(payload.get("market") or "").strip()
    if not ticker or not market:
        return None
    return CompanyProfile(
        ticker=ticker,
        name=name,
        gics_code=str(payload.get("gics_code") or "").strip() or None,
        market=market,
        market_cap_twd=_optional_float(payload.get("market_cap_twd")),
        revenue_twd=_optional_float(payload.get("revenue_twd")),
        business_tags=_string_set(payload.get("business_tags")),
        product_keywords=_string_set(payload.get("product_keywords")),
        segment_revenue_tags=_string_set(payload.get("segment_revenue_tags")),
    )


def _ranked_profiles_from_identity(identity: dict) -> tuple[list[tuple[str, str]], dict[str, dict], dict] | None:
    target_payload = identity.get("company_profile")
    peer_payloads = identity.get("peer_profiles")
    if not isinstance(target_payload, Mapping) or not isinstance(peer_payloads, list):
        return None

    target = _company_profile_from_mapping(target_payload)
    candidates = [
        profile
        for payload in peer_payloads
        if isinstance(payload, Mapping)
        if (profile := _company_profile_from_mapping(payload)) is not None
    ]
    if target is None or not candidates:
        return None

    try:
        min_peers = max(int(identity.get("peer_selection_min_peers", 5)), 1)
    except (TypeError, ValueError):
        min_peers = 5
    selection = select_peer_profiles(target, candidates, min_peers=min_peers)
    selected_rows = selection["selected_peers"]
    if not selected_rows:
        return None

    rows_by_ticker = {row["ticker"].upper(): row for row in selected_rows}
    policy = {
        **selection["selection_policy"],
        "expansion_used": selection["expansion_used"],
    }
    peers = [(row["name"], row["ticker"]) for row in selected_rows]
    return peers, rows_by_ticker, policy


def infer_global_peer_tickers(ticker: str, company_name: str, sector: str, industry: str) -> list[tuple[str, str]]:
    signature = f"{company_name} {sector} {industry}"
    peers = []
    for keywords, candidates in GLOBAL_PEER_HINTS:
        if any(keyword.lower() in signature.lower() for keyword in keywords):
            peers.extend(candidates)
    return [(name, symbol) for name, symbol in peers if symbol.upper() != ticker.upper()][:5]


def fetch_dynamic_peer_metrics(ticker: str, company_name: str, sector: str, industry: str, identity: dict) -> list[dict]:
    ranked_profiles = _ranked_profiles_from_identity(identity)
    selection_rows: dict[str, dict] = {}
    selection_policy: dict | None = None
    if ranked_profiles is not None:
        peers, selection_rows, selection_policy = ranked_profiles
    else:
        peers = []
        for peer in (identity.get("same_industry_peers", []) or [])[:3]:
            stock_id = peer.get("stock_id")
            if stock_id:
                peers.append((peer.get("stock_name", stock_id), f"{stock_id}.TW"))
        peers.extend(infer_global_peer_tickers(ticker, company_name, sector, industry))

    seen = set()
    unique_peers = []
    for name, symbol in peers:
        if symbol in seen:
            continue
        seen.add(symbol)
        unique_peers.append((name, symbol))
        if len(unique_peers) >= 5:
            break

    def fetch_peer(name: str, symbol: str) -> dict:
        try:
            info = yf.Ticker(symbol).info
        except Exception:
            info = {}
        selection = selection_rows.get(symbol.upper())
        record = {
            "name": name,
            "ticker": symbol,
            "source": (
                "profile-ranked peer + yfinance metrics"
                if selection is not None
                else "FinMind industry peer + yfinance metrics"
                if symbol.endswith(".TW")
                else "global peer heuristic + yfinance metrics"
            ),
            "gross_margin_pct": round(float(info.get("grossMargins")) * 100, 2) if isinstance(info.get("grossMargins"), (int, float)) else None,
            "operating_margin_pct": round(float(info.get("operatingMargins")) * 100, 2) if isinstance(info.get("operatingMargins"), (int, float)) else None,
            "profit_margin_pct": round(float(info.get("profitMargins")) * 100, 2) if isinstance(info.get("profitMargins"), (int, float)) else None,
            "pe_ttm": round(float(info.get("trailingPE")), 2) if isinstance(info.get("trailingPE"), (int, float)) else None,
            "pb": round(float(info.get("priceToBook")), 2) if isinstance(info.get("priceToBook"), (int, float)) else None,
        }
        if selection is not None and selection_policy is not None:
            record.update({
                "selection_score": selection["score"],
                "market_cap_ratio": selection["market_cap_ratio"],
                "revenue_ratio": selection["revenue_ratio"],
                "business_overlap": selection["business_overlap"],
                "product_overlap": selection["product_overlap"],
                "segment_overlap": selection["segment_overlap"],
                "selection_policy": selection_policy,
            })
        return record

    fetches = {
        symbol: (fetch_peer, (name, symbol), None, f"{symbol} 同業指標獲取失敗")
        for name, symbol in unique_peers
    }
    results = _run_named_fetches(fetches, max_workers=5)
    return [record for record in results.values() if record]
