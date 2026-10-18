"""Listed brokerage candidates joined through two current TWSE public rosters.

The broker's exchange code is not its listed stock code. Only the registered
business number links the datasets; a same-business peer remains a candidate
until its finer industry and numeric fields are checked separately.
"""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import re

from external_http_client import sync_get
from shared_provider_cache import shared_fetch


BROKER_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap18"
LISTED_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
PROVIDER = "TWSE official broker and listed-company OpenAPI"
_UBID = re.compile(r"\d{8}")
_STOCK_ID = re.compile(r"[1-9]\d{3}")
_BROKER_KIND = "經紀、自營、承銷"


def _roc_day(value: object) -> date | None:
    stamp = str(value or "").strip()
    if not re.fullmatch(r"\d{7}", stamp):
        return None
    try:
        return date(int(stamp[:3]) + 1911, int(stamp[3:5]), int(stamp[5:]))
    except ValueError:
        return None


def _json_rows(raw: bytes, *, max_bytes: int, max_rows: int) -> list[dict]:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= max_bytes:
        raise ValueError("official roster response size invalid")
    try:
        rows = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("official roster JSON invalid") from exc
    if not isinstance(rows, list) or not 0 < len(rows) <= max_rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("official roster rows invalid")
    return rows


def parse_official_rosters(broker_raw: bytes, listed_raw: bytes) -> dict:
    """Retain only identity/business fields and raw-response fingerprints."""
    brokers = _json_rows(broker_raw, max_bytes=250_000, max_rows=200)
    listed = _json_rows(listed_raw, max_bytes=2_500_000, max_rows=2_000)
    by_ubid = {}
    for row in brokers:
        ubid = str(row.get("營利事業統一編號") or "").strip()
        if not _UBID.fullmatch(ubid) or ubid == "00000000":
            continue
        if ubid in by_ubid:
            raise ValueError("duplicate broker business number")
        by_ubid[ubid] = {
            "business_kind": str(row.get("業務種類") or "").strip(),
            "published_roc": str(row.get("出表日期") or "").strip(),
        }
    companies = {}
    seen_ubids = set()
    for row in listed:
        code = str(row.get("公司代號") or "").strip()
        ubid = str(row.get("營利事業統一編號") or "").strip()
        if not _STOCK_ID.fullmatch(code) or not _UBID.fullmatch(ubid) or ubid == "00000000":
            continue
        if code in companies or ubid in seen_ubids:
            raise ValueError("duplicate listed company identity")
        seen_ubids.add(ubid)
        companies[code] = {
            "short_name": str(row.get("公司簡稱") or "").strip(),
            "ubid": ubid,
            "published_roc": str(row.get("出表日期") or "").strip(),
        }
    if not by_ubid or not companies:
        raise ValueError("official rosters lack usable identities")
    return {
        "brokers_by_ubid": by_ubid, "listed_by_code": companies,
        "broker_source_url": BROKER_URL, "listed_source_url": LISTED_URL,
        "broker_response_sha256": sha256(broker_raw).hexdigest(),
        "listed_response_sha256": sha256(listed_raw).hexdigest(),
        "broker_row_count": len(brokers), "listed_row_count": len(listed),
    }


def select_broker_candidates(ticker: str, rosters: dict, master_rows: list[dict], *, today: date) -> list[dict]:
    """Require exact UBID, same broker business, and a current stock identity."""
    target_code = str(ticker or "").removesuffix(".TW")
    if (ticker != target_code + ".TW" or not _STOCK_ID.fullmatch(target_code)
            or not isinstance(rosters, dict)
            or rosters.get("broker_source_url") != BROKER_URL
            or rosters.get("listed_source_url") != LISTED_URL):
        return []
    companies = rosters.get("listed_by_code")
    brokers = rosters.get("brokers_by_ubid")
    if not isinstance(companies, dict) or not isinstance(brokers, dict):
        return []
    dated_master = []
    for row in master_rows:
        if not isinstance(row, dict):
            continue
        try:
            observed = date.fromisoformat(str(row.get("date") or ""))
        except ValueError:
            continue
        if observed <= today:
            dated_master.append((observed, row))
    if not dated_master:
        return []
    master_day = max(day for day, _ in dated_master)
    if not 0 <= (today - master_day).days <= 7:
        return []
    current_by_code = {}
    for day, row in dated_master:
        if day == master_day:
            current_by_code.setdefault(str(row.get("stock_id") or "").strip(), []).append(row)

    def eligible(code: str) -> tuple[dict, dict] | None:
        company = companies.get(code)
        rows = current_by_code.get(code, [])
        if not isinstance(company, dict) or len(rows) != 1 or rows[0].get("type") != "twse":
            return None
        if rows[0].get("stock_name") != company.get("short_name"):
            return None
        broker = brokers.get(company.get("ubid"))
        if not isinstance(broker, dict):
            return None
        company_day = _roc_day(company.get("published_roc"))
        broker_day = _roc_day(broker.get("published_roc"))
        if (company_day is None or broker_day is None
                or not 0 <= (today - company_day).days <= 14
                or not 0 <= (today - broker_day).days <= 14):
            return None
        return company, broker

    target = eligible(target_code)
    if target is None or target[1]["business_kind"] != _BROKER_KIND:
        return []
    candidates = []
    for code in sorted(companies):
        if code == target_code:
            continue
        matched = eligible(code)
        if matched is None or matched[1]["business_kind"] != target[1]["business_kind"]:
            continue
        company, broker = matched
        candidates.append({
            "name": company["short_name"], "ticker": code + ".TW",
            "identity_status": "official_ubid_and_current_master",
            "comparison_status": "industry_candidate_only",
            "issuer_registered_business_number": target[0]["ubid"],
            "peer_registered_business_number": company["ubid"],
            "broker_business_kind": broker["business_kind"],
            "master_observed_at": master_day.isoformat(),
            "broker_observed_at": _roc_day(broker["published_roc"]).isoformat(),
            "company_observed_at": _roc_day(company["published_roc"]).isoformat(),
            "broker_source_url": BROKER_URL, "listed_source_url": LISTED_URL,
            "broker_response_sha256": rosters.get("broker_response_sha256"),
            "listed_response_sha256": rosters.get("listed_response_sha256"),
        })
    return candidates[:5]


def _fetch_official_rosters() -> dict:
    broker_raw = sync_get(BROKER_URL, headers={"User-Agent": "stock-agent/1.0"},
                          timeout=8, provider=PROVIDER).content
    listed_raw = sync_get(LISTED_URL, headers={"User-Agent": "stock-agent/1.0"},
                          timeout=8, provider=PROVIDER).content
    rosters = parse_official_rosters(broker_raw, listed_raw)
    if rosters["broker_row_count"] < 40 or rosters["listed_row_count"] < 800:
        raise ValueError("official roster response appears incomplete")
    return rosters


def get_official_broker_candidates(ticker: str, master_rows: list[dict], *, today: date) -> dict:
    rosters, meta = shared_fetch(
        "official-broker-cohort:v1", _fetch_official_rosters,
        freshness_seconds=24 * 60 * 60, use_cache=True, lock_wait_seconds=10,
    )
    if meta.get("stale") or not isinstance(rosters, dict):
        return {"candidates": [], "status": "stale_or_unavailable"}
    candidates = select_broker_candidates(ticker, rosters, master_rows, today=today)
    return {"candidates": candidates, "status": "success" if candidates else "no_verified_broker_peer",
            "cache_hit": bool(meta.get("cache_hit"))}
