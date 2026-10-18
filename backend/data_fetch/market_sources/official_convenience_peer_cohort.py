"""A narrowly verified convenience-store peer lead from public issuer and TPEx pages.

TPEx industry-chain membership has no publication date. It is therefore a
candidate-search receipt, never current whole-business valuation comparability.
"""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import re

from bs4 import BeautifulSoup

from external_http_client import sync_get
from shared_provider_cache import shared_fetch


PROVIDER = "TPEx industry chain and issuer profiles"
CHAIN_URLS = {
    code: f"https://ic.tpex.org.tw/company_chain.php?stk_code={code}"
    for code in ("2912", "5903")
}
PROFILE_URLS = {
    "2912": "https://ir.7-11.com.tw/tw/companyprofile.php",
    "5903": "https://www.family.com.tw/web_enterprise/page/information.aspx",
}
IDENTITIES = {
    "2912": ("統一超", "twse"),
    "5903": ("全家", "tpex"),
}
_MAX_PAGE_BYTES = 150_000


def _page(raw: bytes) -> BeautifulSoup:
    if not isinstance(raw, bytes) or not 100 <= len(raw) <= _MAX_PAGE_BYTES:
        raise ValueError("official profile size invalid")
    return BeautifulSoup(raw.decode("utf-8", errors="strict"), "html.parser")


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _chain_verified(raw: bytes, code: str, name: str) -> bool:
    page = _page(raw)
    if len([h for h in page.find_all("h3") if h.get_text(" ", strip=True) == "個體公司所屬產業鏈"]) != 1:
        return False
    headings = [h for h in page.find_all("h4") if _compact(h.get_text(" ", strip=True))
                == f"{code}{name}所屬產業鏈如下:"]
    if len(headings) != 1:
        return False
    chain = headings[0].find_next_sibling("h4")
    if chain is None or _compact(chain.get_text(" ", strip=True)) != "►貿易百貨>零售通路":
        return False
    links = chain.find_all("a", href="introduce.php?ic=V000")
    return len(links) == 1 and links[0].get_text(" ", strip=True) == "貿易百貨"


def _table_value(page: BeautifulSoup, label: str) -> str | None:
    values = []
    for row in page.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) == 2 and _compact(cells[0].get_text(" ", strip=True)) == label:
            values.append(cells[1].get_text(" ", strip=True))
    return values[0] if len(values) == 1 else None


def _profiles_verified(pages: dict[str, bytes]) -> bool:
    eleven, family = (_page(pages[code]) for code in ("2912", "5903"))
    business = _table_value(eleven, "主要業務")
    return (
        _table_value(eleven, "公司名稱") == "統一超商股份有限公司"
        and bool(business and "超級商店之經營" in business)
        and _table_value(family, "公司全名") == "全家便利商店股份有限公司"
        and _table_value(family, "公司代號") == "5903"
    )


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
    latest_rows = [row for day, row in matching if day == latest]
    name, market = IDENTITIES[code]
    if (not 0 <= (today - latest).days <= 7 or len(latest_rows) != 1
            or latest_rows[0].get("stock_name") != name
            or str(latest_rows[0].get("type") or "").lower() != market):
        return None
    return latest


def _fetch_pages() -> dict:
    chain, profiles = {}, {}
    for code in IDENTITIES:
        chain[code] = sync_get(CHAIN_URLS[code], headers={"User-Agent": "stock-agent/1.0"},
                               timeout=8, provider=PROVIDER).content
        profiles[code] = sync_get(PROFILE_URLS[code], headers={"User-Agent": "stock-agent/1.0"},
                                  timeout=8, provider=PROVIDER).content
    if (not all(_chain_verified(chain[code], code, IDENTITIES[code][0]) for code in IDENTITIES)
            or not _profiles_verified(profiles)):
        raise ValueError("official convenience identity or business evidence changed")
    return {
        "chain_response_sha256": {code: sha256(raw).hexdigest() for code, raw in chain.items()},
        "profile_response_sha256": {code: sha256(raw).hexdigest() for code, raw in profiles.items()},
    }


def get_official_convenience_candidates(ticker: str, master_rows: list[dict], *, today: date) -> dict:
    """Return the documented lead only after fresh exact stock identities and pages."""
    if ticker != "2912.TW":
        return {"candidates": [], "status": "not_applicable"}
    issuer_day = _current_master_day(master_rows, "2912", today=today)
    peer_day = _current_master_day(master_rows, "5903", today=today)
    if issuer_day is None or peer_day is None:
        return {"candidates": [], "status": "current_master_identity_unverified"}
    try:
        evidence, meta = shared_fetch(
            "official-convenience-peer-cohort:v1", _fetch_pages,
            freshness_seconds=24 * 60 * 60, use_cache=True, lock_wait_seconds=10,
        )
    except Exception:
        return {"candidates": [], "status": "official_pages_unavailable"}
    if (meta.get("stale") or not isinstance(evidence, dict)
            or any(not isinstance(evidence.get(kind), dict)
                   or set(evidence[kind]) != set(IDENTITIES)
                   or any(not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                          for digest in evidence[kind].values())
                   for kind in ("chain_response_sha256", "profile_response_sha256"))):
        return {"candidates": [], "status": "official_pages_unavailable"}
    candidate = {
        "name": "全家", "ticker": "5903.TWO",
        "identity_status": "current_exchange_master_and_official_profiles",
        "comparison_status": "official_convenience_candidate",
        "business_comparability_verified_current": False,
        "relationship_basis": "same_official_retail_chain_and_issuer_convenience_profiles",
        "issuer_master_observed_at": issuer_day.isoformat(),
        "master_observed_at": peer_day.isoformat(),
        "chain_urls": dict(CHAIN_URLS), "profile_urls": dict(PROFILE_URLS),
        "chain_response_sha256": evidence["chain_response_sha256"],
        "profile_response_sha256": evidence["profile_response_sha256"],
        "official_page_acquired_at_epoch": meta.get("fetched_at_epoch"),
    }
    return {"candidates": [candidate], "status": "success", "cache_hit": bool(meta.get("cache_hit"))}
