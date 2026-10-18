"""Official steel-wire industry-chain leads with current stock identities.

The TPEx chain page is undated; segment membership is a discovery receipt,
not current whole-company financial or valuation comparability.
"""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import re

from bs4 import BeautifulSoup

from external_http_client import sync_get
from shared_provider_cache import shared_fetch


PROVIDER = "TPEx industry chain steel-wire candidates"
ISSUER_URL = "https://ic.tpex.org.tw/company_chain.php?stk_code=1605"
SEGMENT_URL = "https://ic.tpex.org.tw/introduce.php?ic=Q000"
IDENTITIES = {
    "1605": ("華新", "twse"),
    "2024": ("志聯", "twse"),
    "2033": ("佳大", "twse"),
    "5016": ("松和", "tpex"),
}
PEER_CODES = ("2024", "2033", "5016")


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _page(raw: bytes) -> BeautifulSoup:
    if not isinstance(raw, bytes) or not 100 <= len(raw) <= 250_000:
        raise ValueError("official chain page size invalid")
    return BeautifulSoup(raw.decode("utf-8", errors="strict"), "html.parser")


def _issuer_has_segment(raw: bytes) -> bool:
    page = _page(raw)
    if len([h for h in page.find_all("h3") if h.get_text(" ", strip=True) == "個體公司所屬產業鏈"]) != 1:
        return False
    if len([h for h in page.find_all("h4") if _compact(h.get_text(" ", strip=True))
            == "1605華新所屬產業鏈如下:"]) != 1:
        return False
    for heading in page.find_all("h4"):
        if _compact(heading.get_text(" ", strip=True)) != "►鋼鐵>鋼線鋼纜":
            continue
        links = heading.find_all("a", href="introduce.php?ic=Q000")
        if len(links) == 1 and links[0].get_text(" ", strip=True) == "鋼鐵":
            return True
    return False


def _segment_has_exact_cohort(raw: bytes) -> bool:
    page = _page(raw)
    groups = page.select('div#companyList_QJ00[title="鋼線鋼纜"]')
    if not 1 <= len(groups) <= 2 or not any(
            node.get_text(" ", strip=True) == "鋼線鋼纜"
            for group in groups for node in group.find_all("b")):
        return False
    for group in groups:
        by_code = {}
        for link in group.find_all("a", href=True):
            match = re.fullmatch(r"company_basic\.php\?stk_code=([1-9]\d{3})", link["href"])
            if not match:
                continue
            code = match.group(1)
            by_code.setdefault(code, []).append((link.get_text(" ", strip=True), link.get("title")))
        if not all(by_code.get(code) == [(name, name)] for code, (name, _) in IDENTITIES.items()):
            return False
    return True


def _current_master_day(rows: list[dict], code: str, *, today: date) -> date | None:
    matching = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("stock_id") or "").strip() != code:
            continue
        try:
            observed = date.fromisoformat(str(row.get("date") or ""))
        except ValueError:
            return None
        if observed <= today:
            matching.append((observed, row))
    if not matching:
        return None
    latest = max(day for day, _ in matching)
    current = [row for day, row in matching if day == latest]
    name, market = IDENTITIES[code]
    if (not 0 <= (today - latest).days <= 7 or len(current) != 1
            or current[0].get("stock_name") != name
            or str(current[0].get("type") or "").lower() != market):
        return None
    return latest


def _fetch_pages() -> dict:
    issuer = sync_get(ISSUER_URL, headers={"User-Agent": "stock-agent/1.0"},
                      timeout=8, provider=PROVIDER).content
    segment = sync_get(SEGMENT_URL, headers={"User-Agent": "stock-agent/1.0"},
                       timeout=8, provider=PROVIDER).content
    if not _issuer_has_segment(issuer) or not _segment_has_exact_cohort(segment):
        raise ValueError("official steel-wire chain membership changed")
    return {"issuer_response_sha256": sha256(issuer).hexdigest(),
            "segment_response_sha256": sha256(segment).hexdigest()}


def get_official_steel_wire_candidates(ticker: str, master_rows: list[dict], *, today: date) -> dict:
    if ticker != "1605.TW":
        return {"candidates": [], "status": "not_applicable"}
    master_days = {code: _current_master_day(master_rows, code, today=today) for code in IDENTITIES}
    if any(day is None for day in master_days.values()):
        return {"candidates": [], "status": "current_master_identity_unverified"}
    try:
        evidence, meta = shared_fetch(
            "official-steel-wire-peer-cohort:v1", _fetch_pages,
            freshness_seconds=24 * 60 * 60, use_cache=True, lock_wait_seconds=10,
        )
    except Exception:
        return {"candidates": [], "status": "official_pages_unavailable"}
    if (meta.get("stale") or not isinstance(evidence, dict)
            or any(not isinstance(evidence.get(key), str)
                   or not re.fullmatch(r"[0-9a-f]{64}", evidence[key])
                   for key in ("issuer_response_sha256", "segment_response_sha256"))):
        return {"candidates": [], "status": "official_pages_unavailable"}
    candidates = []
    for code in PEER_CODES:
        name, market = IDENTITIES[code]
        candidates.append({
            "name": name, "ticker": code + (".TW" if market == "twse" else ".TWO"),
            "identity_status": "current_exchange_master_and_official_chain",
            "comparison_status": "official_segment_candidate",
            "business_comparability_verified_current": False,
            "relationship_basis": "same_undated_tpex_steel_wire_segment",
            "issuer_master_observed_at": master_days["1605"].isoformat(),
            "master_observed_at": master_days[code].isoformat(),
            "issuer_source_url": ISSUER_URL, "segment_source_url": SEGMENT_URL,
            **evidence,
            "official_page_acquired_at_epoch": meta.get("fetched_at_epoch"),
        })
    return {"candidates": candidates, "status": "success", "cache_hit": bool(meta.get("cache_hit"))}
