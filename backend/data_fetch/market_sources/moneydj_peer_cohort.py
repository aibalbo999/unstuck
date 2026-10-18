"""Dated MoneyDJ food-biotech cohort for the broad-classified 5314 issuer.

Membership is discovery evidence only. It does not establish business or
numeric comparability, and market-price columns are deliberately ignored.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import base64
import math
import os
import re
import time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import httpx

from .peer_recovery import load_peer_stock_master


POLICY = "moneydj-dated-food-biotech-cohort-v1"
PROVIDER = "MoneyDJ published food-biotech cohort"
URL = "https://www.moneydj.com/z/zh/zha/zh00.djhtm?A=C017108&B=6"
TARGET = "5314.TWO"
MAX_BYTES = 200_000
TITLE = "同業股價表現-生技醫療保健-食品生技-台股-MoneyDJ理財網"
LINK_RE = re.compile(r"javascript:Link2Stk\('AS([1-9]\d{3})'\);", re.I)
LABEL_RE = re.compile(r"^([1-9]\d{3})(.+)$")
DATE_RE = re.compile(r"\b(20\d{2})/(\d{2})/(\d{2})\b")


class CohortError(ValueError):
    pass


def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def _current_identity(code: str, rows: list[dict], today: date) -> tuple[str, str] | None:
    dated, all_days = [], []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            observed = date.fromisoformat(str(row.get("date") or ""))
        except ValueError:
            continue
        if 0 <= (today - observed).days <= 7:
            all_days.append(observed)
            if str(row.get("stock_id")) == code:
                dated.append((observed, row))
    if not dated or not all_days:
        return None
    latest = max(all_days)
    current = {(str(row.get("stock_name") or "").strip(), str(row.get("type") or "").lower())
               for day, row in dated if day == latest}
    if len(current) != 1:
        return None
    name, market = next(iter(current))
    return (name, market) if name and market in {"twse", "tpex"} else None


def parse_cohort_page(raw: bytes, ticker: str, master_rows: list[dict], *, today: date | None = None) -> dict:
    today = today or _today()
    if ticker != TARGET or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise CohortError("unsupported issuer or cohort response size")
    identity = _current_identity("5314", master_rows, today)
    if identity != ("世紀*", "tpex"):
        raise CohortError("current issuer identity is not verified")
    try:
        soup = BeautifulSoup(raw.decode("big5"), "html.parser")
    except UnicodeError as exc:
        raise CohortError("cohort encoding changed") from exc
    if not soup.title or soup.title.get_text(" ", strip=True) != TITLE:
        raise CohortError("published cohort title changed")
    table = soup.find("table", id="oMainTable")
    if table is None:
        raise CohortError("published cohort table is missing")
    parsed = {}
    for row in table.find_all("tr"):
        links = [a for a in row.find_all("a", href=True) if LINK_RE.fullmatch(str(a["href"]))]
        if len(links) != 1:
            continue
        link = links[0]
        match = LINK_RE.fullmatch(str(link["href"]))
        label = LABEL_RE.fullmatch(link.get_text(" ", strip=True))
        dates = DATE_RE.findall(row.get_text(" ", strip=True))
        if not match or not label or not dates or match.group(1) != label.group(1) or len(dates) != 1:
            raise CohortError("cohort row identity or date is ambiguous")
        try:
            observed = date(*map(int, dates[0]))
        except ValueError as exc:
            raise CohortError("cohort row date is invalid") from exc
        if not 0 <= (today - observed).days <= 7:
            raise CohortError("cohort observation is stale or future-dated")
        code, name = match.group(1), label.group(2).strip()
        if code in parsed:
            raise CohortError("duplicate cohort stock code")
        parsed[code] = (name, observed)
    if "5314" not in parsed or parsed["5314"][0] != identity[0]:
        raise CohortError("issuer is absent from the dated publisher cohort")
    issuer_day = parsed["5314"][1]
    digest = sha256(raw).hexdigest()
    candidates = []
    for code in sorted(parsed):
        if code == "5314":
            continue
        name, observed = parsed[code]
        current = _current_identity(code, master_rows, today)
        if current is None:
            continue
        if current[0] != name:
            raise CohortError("published candidate name disagrees with current stock master")
        market = ".TW" if current[1] == "twse" else ".TWO"
        candidates.append({
            "title": f"MoneyDJ 食品生技同頁名單：世紀*、{name}",
            "source": "MoneyDJ 理財網", "source_type": "published_industry_peer_cohort",
            "link": URL, "selection_policy": POLICY,
            "relationship_kind": "publisher_listed_industry_candidate",
            "relationship_basis": "dated_same_publisher_cohort_and_current_stock_master",
            "industry_category": "食品生技", "observed_at": observed.isoformat(),
            "issuer_observed_at": issuer_day.isoformat(), "response_sha256": digest,
            "numeric_comparability_verified": False, "business_comparability_verified": False,
            "issuer": {"ticker": TARGET, "official_name": identity[0]},
            "counterparty": {"ticker": code + market, "official_name": name},
        })
    if not candidates:
        raise CohortError("published cohort has no current verified candidates")
    return {"records": candidates[:5], "source_url": URL,
            "observed_at": issuer_day.isoformat(), "response_sha256": digest,
            "raw_html_base64": base64.b64encode(raw).decode("ascii"),
            "raw_count": len(parsed) - 1, "usable_count": len(candidates[:5]),
            "candidate_order_policy": "stock_code_only_not_similarity_rank"}


def is_moneydj_peer_record(record: dict, ticker: str, *, today: date | None = None) -> bool:
    if not isinstance(record, dict) or ticker != TARGET:
        return False
    today = today or _today()
    issuer, peer = record.get("issuer"), record.get("counterparty")
    if not isinstance(issuer, dict) or not isinstance(peer, dict):
        return False
    try:
        observed = date.fromisoformat(str(record.get("observed_at") or ""))
        issuer_day = date.fromisoformat(str(record.get("issuer_observed_at") or ""))
    except ValueError:
        return False
    return bool(
        issuer == {"ticker": TARGET, "official_name": "世紀*"}
        and re.fullmatch(r"[1-9]\d{3}\.TW(?:O)?", str(peer.get("ticker") or ""))
        and peer.get("ticker") != TARGET and peer.get("official_name")
        and record.get("source_type") == "published_industry_peer_cohort"
        and record.get("selection_policy") == POLICY
        and record.get("relationship_kind") == "publisher_listed_industry_candidate"
        and record.get("relationship_basis") == "dated_same_publisher_cohort_and_current_stock_master"
        and record.get("industry_category") == "食品生技" and record.get("link") == URL
        and record.get("business_comparability_verified") is False
        and record.get("numeric_comparability_verified") is False
        and re.fullmatch(r"[0-9a-f]{64}", str(record.get("response_sha256") or ""))
        and 0 <= (today - observed).days <= 7 and 0 <= (today - issuer_day).days <= 7
    )


def fetch_published_cohort(ticker: str, *, today: date | None = None,
                           master_rows: list[dict] | None = None,
                           client: httpx.Client | None = None, diagnostics: dict | None = None) -> dict:
    diagnostics=diagnostics if diagnostics is not None else {}
    diagnostics["http_request_sent"]=False
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1" and client is None:
        raise CohortError("network is disabled for tests")
    today = today or _today()
    rows = master_rows if master_rows is not None else load_peer_stock_master()
    if ticker != TARGET or _current_identity("5314", rows, today) != ("世紀*", "tpex"):
        raise CohortError("current issuer identity is not verified")
    if client is None:
        from search_provider_runtime import SourceResponseError, cooldown_state, remember_failure, scope_key
        from .moneydj_cohort_transport import download_html
        key=scope_key(PROVIDER,endpoint="published-food-biotech")
        if cooldown_state(key):
            raise SourceResponseError("cooldown")
        deadline=time.monotonic()+8
        try:
            raw=download_html(deadline=deadline,diagnostics=diagnostics)
            result=parse_cohort_page(raw,ticker,rows,today=today)
            if time.monotonic()>=deadline:
                raise SourceResponseError("timeout")
            return result
        except Exception as exc:
            remember_failure(key,exc)
            raise
    # Explicit client injection is retained for isolated parser/HTTP tests.
    chunks, size = [], 0
    diagnostics["http_request_sent"]=True
    with client.stream("GET", URL) as response:
        if response.status_code != 200:
            raise CohortError(f"MoneyDJ cohort HTTP {response.status_code}")
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_BYTES:
                raise CohortError("published cohort exceeds size limit")
            chunks.append(chunk)
    return parse_cohort_page(b"".join(chunks), ticker, rows, today=today)


def acquire_published_cohort(ticker, master_rows, *, today):
    """Discovery and numeric leads share one receipt, rechecked against its bytes."""
    from shared_provider_cache import shared_fetch
    diagnostics={"http_request_sent":False}
    value,meta=shared_fetch(
        f"moneydj-published-food-biotech:v2:{ticker}:{today.isoformat()}",
        lambda:fetch_published_cohort(ticker,today=today,master_rows=master_rows,diagnostics=diagnostics),
        freshness_seconds=4*3600,retention_seconds=4*3600,
        result_ttl=lambda result:4*3600 if result.get("records") else 900,
        error_retry_seconds=300,lock_wait_seconds=1)
    meta={**meta,"http_request_sent":diagnostics["http_request_sent"]}
    try:
        epoch=meta.get("fetched_at_epoch")
        if (meta.get("stale") or meta.get("error_kind") or type(epoch) not in (int,float)
                or not math.isfinite(float(epoch)) or not 0<=time.time()-epoch<=4*3600
                or not isinstance(value,dict)):
            raise CohortError("cohort receipt is not fresh")
        encoded=value.get("raw_html_base64")
        if not isinstance(encoded,str) or not 0<len(encoded)<=4*((MAX_BYTES+2)//3):
            raise CohortError("cohort receipt has no bounded original bytes")
        raw=base64.b64decode(encoded,validate=True)
        if value.get("source_url")!=URL or sha256(raw).hexdigest()!=value.get("response_sha256"):
            raise CohortError("cohort receipt hash mismatch")
        parsed=parse_cohort_page(raw,ticker,master_rows,today=today)
        # Parsed cache fields are not authority: reconstruct them from the
        # retained bytes and current master, keeping independent valid peers.
        return parsed,meta
    except (ValueError,TypeError,OverflowError):
        return {},{**meta,"error_kind":meta.get("error_kind") or "cohort_receipt_validation_failed"}


def cohort_source_audit(value, meta, *, started_at_epoch):
    """The caller that acquired the page owns its actual/cache/local observation."""
    from source_audit import build_source_audit_entry
    rows=value.get("records",[])
    stale,cache_hit=bool(meta.get("stale")),bool(meta.get("cache_hit"))
    sent=meta.get("http_request_sent") is True
    if meta.get("error_kind"):
        status="degraded_enrichment" if stale and rows else "error"
    elif cache_hit:
        status="skipped_fresh_cache" if rows else "unavailable"
    else:
        status="success" if rows else "unavailable"
    audit=build_source_audit_entry("peer_discovery",PROVIDER,status,
        fetched_at_epoch=meta.get("fetched_at_epoch"),started_at_epoch=started_at_epoch,
        finished_at_epoch=time.time(),record_count=len(rows),cache_hit=cache_hit,stale=stale,
        error_kind=str(meta.get("error_kind") or ""),
        message="取得當期食品生技研究候選；整體業務與財期可比性未驗證。" if rows else "未取得可核對的食品生技研究候選。")
    audit.update(selection_policy=POLICY,source_url=URL,observed_at=value.get("observed_at"),
                 response_sha256=value.get("response_sha256"),raw_count=value.get("raw_count",0),
                 usable_count=len(rows),candidate_order_policy=value.get("candidate_order_policy"),
                 http_request_sent=sent,event_kind="http_request" if sent else "cache_hit" if cache_hit else "local_block")
    return audit
