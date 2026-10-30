"""Issuer legal names from bounded TWSE/TPEx public company rosters.

This is an identity anchor for exact-employer searches. A matched company
profile is never evidence that the issuer currently has any open jobs.
"""

from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import math
import re
import time
from zoneinfo import ZoneInfo

from external_http_client import sync_get
from shared_provider_cache import shared_fetch


PROVIDER = "TWSE/TPEx official company profile OpenAPI"
URLS = {
    ".TW": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
    ".TWO": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
}
FIELDS = {
    ".TW": ("公司代號", "公司名稱", "公司簡稱", "出表日期"),
    ".TWO": ("SecuritiesCompanyCode", "CompanyName", "CompanyAbbreviation", "Date"),
}
MAX_BYTES = 2_500_000
MAX_ROWS = 2_000
_TICKER = re.compile(r"^(\d{4,6})(\.TWO|\.TW)$")
_STOCK_ID = re.compile(r"\d{4,6}")
_LEGAL_SUFFIX = ("股份有限公司", "有限公司")


def _known_short_name_reconciliation(ticker, expected, current, legal_name, ubn):
    """One observed SDK/official-label mismatch, bound to the current issuer row.

    Do not strip board suffixes or change saved/global company aliases. The
    dated market roster must still independently satisfy all anchor checks.
    """
    if (ticker, expected, current, legal_name, ubn) == (
            "7740.TW", "熙特爾", "熙特爾-創", "熙特爾新能源股份有限公司", "55118186"):
        return {"policy": "seetel-current-twse-name-v1",
                "requested_short_name": expected, "current_short_name": current}
    return None


def _receipt_short_name_matches(evidence, ticker, expected):
    current = evidence.get("official_short_name")
    if "short_name_reconciliation" not in evidence:
        return current == expected
    marker = evidence.get("short_name_reconciliation")
    if not isinstance(marker, dict):
        return False
    known = _known_short_name_reconciliation(
        ticker, marker.get("requested_short_name"), current,
        evidence.get("legal_name"), evidence.get("official_ubn"))
    return bool(known and marker == known and expected in (
        marker["requested_short_name"], current))


def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def parse_roster(raw: bytes, suffix: str) -> dict:
    """Normalize one complete official market roster, rejecting duplicate codes."""
    if suffix not in FIELDS or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("official company roster response size or market invalid")
    try:
        rows = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("official company roster JSON invalid") from exc
    if not isinstance(rows, list) or not 0 < len(rows) <= MAX_ROWS:
        raise ValueError("official company roster shape invalid")
    code_field, name_field, short_field, date_field = FIELDS[suffix]
    entries = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("official company roster row invalid")
        code = str(row.get(code_field) or "").strip()
        if not _STOCK_ID.fullmatch(code):
            continue
        if code in entries:
            raise ValueError("duplicate official company roster code")
        entries[code] = {
            "legal_name": str(row.get(name_field) or "").strip(),
            "short_name": str(row.get(short_field) or "").strip(),
            "published_roc": str(row.get(date_field) or "").strip(),
            "official_ubn": str(row.get("營利事業統一編號" if suffix == ".TW" else "UnifiedBusinessNo.") or "").strip(),
        }
    if not entries:
        raise ValueError("official company roster has no issuers")
    return {"entries": entries, "source_url": URLS[suffix],
            "response_sha256": sha256(raw).hexdigest()}


def select_legal_name(roster: dict, ticker: str, expected_short_name: str, *, today: date | None = None) -> dict | None:
    """Require market/code/name identity and a recent filing; label drift is explicit."""
    match = _TICKER.fullmatch(str(ticker or "").strip().upper())
    if not match or not isinstance(roster, dict) or roster.get("source_url") != URLS[match[2]]:
        return None
    entries = roster.get("entries")
    row = entries.get(match[1]) if isinstance(entries, dict) else None
    if not isinstance(row, dict):
        return None
    legal_name = str(row.get("legal_name") or "").strip()
    short_name = str(row.get("short_name") or "").strip()
    published = str(row.get("published_roc") or "").strip()
    official_ubn = str(row.get("official_ubn") or "").strip()
    expected = str(expected_short_name or "").strip()
    reconciliation = _known_short_name_reconciliation(
        match[1] + match[2], expected, short_name, legal_name, official_ubn)
    if (not short_name or (short_name != expected and not reconciliation)
            or not 4 <= len(legal_name) <= 100 or not legal_name.endswith(_LEGAL_SUFFIX)
            or not re.fullmatch(r"\d{7}", published)):
        return None
    try:
        published_on = date(int(published[:3]) + 1911, int(published[3:5]), int(published[5:]))
    except ValueError:
        return None
    age = ((today or _today()) - published_on).days
    if not 0 <= age <= 14:
        return None
    return {"ticker": match[1] + match[2], "legal_name": legal_name,
            "official_short_name": short_name, "as_of": published_on.isoformat(),
            "official_ubn": official_ubn if re.fullmatch(r"\d{8}", official_ubn) and int(official_ubn) > 0 else None,
            "source_url": roster["source_url"], "response_sha256": roster.get("response_sha256"),
            **({"short_name_reconciliation": reconciliation} if reconciliation else {})}


def _fetch_roster(url: str, suffix: str) -> dict:
    response = sync_get(url, headers={"User-Agent": "stock-agent/1.0"}, timeout=8, provider=PROVIDER)
    raw = response.content
    roster = parse_roster(raw, suffix)
    # Existing metadata remains usable if supplemental archival is unavailable.
    # Consumers requiring complete originals must independently fail closed.
    import httpx
    if (type(response) is httpx.Response and response.url == url
            and response.status_code == 200 and not getattr(response, 'from_cache', False)):
        from official_response_evidence import archive_response
        try:
            archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200)
        except (OSError, ValueError):
            pass
    return roster


def read_cached_listed_roster_bytes() -> tuple[bytes, dict] | None:
    """Read an already acquired full master, never synthesize it from fields.

    The profile cache owns its original 24-hour expiry. The digest-addressed
    archive only supplies identical complete payload bytes; it does not prove
    new HTTP, renew acquisition time, or replace the issuer/domain checks.
    """
    from cache_store import get_cache_json
    from official_response_evidence import read_response
    from runtime_paths import current_runtime_paths

    key = "shared_provider:v1:" + sha256(b"official-company-roster:v2:.TW").hexdigest()
    try:
        cached = get_cache_json(key)
        if not isinstance(cached, dict) or cached.get("error_kind"):
            return None
        stamp, until = cached.get("fetched_at_epoch"), cached.get("fresh_until_epoch")
        now = time.time()
        if (type(stamp) not in (int, float) or type(until) not in (int, float)
                or not math.isfinite(stamp) or not math.isfinite(until)
                or not 0 < stamp <= now or not 0 <= now - stamp <= 86400
                or not now < until or not 0 < until - stamp <= 86401):
            return None
        roster = cached.get("value")
        if (not isinstance(roster, dict) or roster.get("source_url") != URLS[".TW"]
                or not isinstance(roster.get("entries"), dict) or len(roster["entries"]) < 800):
            return None
        digest = roster.get("response_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            return None
        path = current_runtime_paths().cache_dir / "official-response-evidence" / (digest + ".gz")
        raw = read_response({"raw_response_sha256": digest, "raw_response_path": str(path)})
        if parse_roster(raw, ".TW") != roster:
            return None
        return raw, {"cache_hit": True, "stale": False, "fetched_at_epoch": stamp,
                     "cache_source": "official-company-roster:v2:.TW", "source_url": URLS[".TW"],
                     "source_payload_sha256": digest, "source_payload_bytes": len(raw),
                     "evidence_kind": "cached_complete_source_payload_verified_by_digest",
                     "http_status_observed": False}
    except Exception:
        # A missing/corrupt/expired auxiliary receipt must not enable a weaker
        # identity route or prevent the original bounded transport from running.
        return None


def verified_legal_name_from_evidence(evidence: dict | None, ticker: str, expected_short_name: str) -> str:
    """Recheck a saved issuer anchor before counting exact-employer postings."""
    match = _TICKER.fullmatch(str(ticker or "").strip().upper())
    if not match or not isinstance(evidence, dict):
        return ""
    name = str(evidence.get("legal_name") or "").strip()
    digest = str(evidence.get("response_sha256") or "")
    stamp = evidence.get("fetched_at_epoch")
    if (evidence.get("ticker") != match[1] + match[2]
            or evidence.get("source_url") != URLS[match[2]]
            or not _receipt_short_name_matches(evidence, match[1] + match[2],
                                              str(expected_short_name or "").strip())
            or not 4 <= len(name) <= 100 or not name.endswith(_LEGAL_SUFFIX)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or isinstance(stamp, bool) or not isinstance(stamp, (int, float))
            or not math.isfinite(stamp) or not 0 < stamp <= time.time() + 300
            or evidence.get("stale") is True):
        return ""
    try:
        published_on = date.fromisoformat(str(evidence.get("as_of") or ""))
        fetched_on = datetime.fromtimestamp(stamp, ZoneInfo("Asia/Taipei")).date()
    except (ValueError, OverflowError):
        return ""
    return name if 0 <= (fetched_on - published_on).days <= 14 else ""


def verified_official_ubn_from_evidence(evidence: dict | None, ticker: str, expected_short_name: str) -> str:
    """Accept an issuer tax ID only alongside a current, matching official name receipt."""
    if not verified_legal_name_from_evidence(evidence, ticker, expected_short_name):
        return ""
    ubn = str(evidence.get("official_ubn") or "").strip()
    return ubn if re.fullmatch(r"\d{8}", ubn) and int(ubn) > 0 else ""


def get_official_legal_name(ticker: str, expected_short_name: str) -> dict | None:
    match = _TICKER.fullmatch(str(ticker or "").strip().upper())
    if not match or not str(expected_short_name or "").strip():
        return None
    suffix = match[2]
    roster, meta = shared_fetch(
        "official-company-roster:v2:" + suffix,
        lambda: _fetch_roster(URLS[suffix], suffix),
        freshness_seconds=24 * 60 * 60, use_cache=True, lock_wait_seconds=10,
    )
    if meta.get("stale") or not isinstance(roster, dict):
        return None
    selected = select_legal_name(roster, match[1] + suffix, expected_short_name)
    return {**selected, "cache_hit": bool(meta.get("cache_hit")),
            "fetched_at_epoch": meta.get("fetched_at_epoch")} if selected else None
