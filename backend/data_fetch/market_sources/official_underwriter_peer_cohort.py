"""Dated public underwriting peer samples with current stock-identity checks.

An underwriter's comparison is a useful candidate lead, not proof that whole-
company operations or every financial metric remain comparable today.
"""
from __future__ import annotations

from datetime import date


_ISSUER = ("3587", "閎康", "tpex", "其他電子類")
_DOCUMENTED = (
    ("6830", "汎銓", "twse", "其他電子業", 2025,
     "https://www.cathaysec.com.tw/RiskManage/4A80A899-F884-4399-8AC4-03BB77ACDFA0.pdf"),
    ("3289", "宜特", "tpex", "其他電子類", 2022,
     "https://www.kgi.com.tw/zh-tw/-/media/files/kgis/3_2_6_ipo/competitive-bidding/6830-3.pdf"),
)


def _current_identity(rows: list[dict], identity: tuple[str, str, str, str], today: date) -> date | None:
    code, name, market, category = identity
    matching = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("stock_id") or "").strip() != code:
            continue
        try:
            observed = date.fromisoformat(str(row.get("date") or ""))
        except ValueError:
            return None
        if not 0 <= (today - observed).days <= 7:
            return None
        if str(row.get("stock_name") or "").strip() != name or str(row.get("type") or "").lower() != market:
            return None
        matching.append((observed, row))
    if not matching or not any(row.get("industry_category") == category for _, row in matching):
        return None
    return max(observed for observed, _ in matching)


def documented_peer_candidates(ticker: str, master_rows: list[dict], *, today: date) -> list[dict]:
    """Return only dated historical comparators with current exact identities."""
    issuer_master_day = _current_identity(master_rows, _ISSUER, today) if ticker == "3587.TWO" else None
    if issuer_master_day is None:
        return []
    candidates = []
    for code, name, market, category, published_year, url in _DOCUMENTED:
        peer_master_day = _current_identity(master_rows, (code, name, market, category), today)
        if peer_master_day is None:
            continue
        candidates.append({
            "name": name, "ticker": code + (".TW" if market == "twse" else ".TWO"),
            "identity_status": "current_exchange_master",
            "comparison_status": "underwriter_documented_candidate",
            "relationship_basis": "dated_public_underwriter_comparison_sample",
            "business_comparability_verified_current": False,
            "underwriter_document_url": url, "underwriter_document_year": published_year,
            "issuer_master_observed_at": issuer_master_day.isoformat(),
            "master_observed_at": peer_master_day.isoformat(),
        })
    return candidates
