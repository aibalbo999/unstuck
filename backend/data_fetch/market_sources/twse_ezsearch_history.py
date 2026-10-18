"""Bounded issuer/date search of the public TWSE announcement index."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import json
import re
from urllib.parse import parse_qs, urlsplit

from external_http_client import sync_post
from .twse_company_history import TAIPEI, _detail_identity, _roc_day, _text


INDEX_URL = "https://mopsov.twse.com.tw/mops/web/ezsearch_query"
MAX_INDEX_BYTES = 2_000_000
MAX_INDEX_ROWS = 1_000
MAX_CANDIDATES = 30


def _roc_string(day: datetime) -> str:
    return f"{day.year - 1911:03d}/{day.month:02d}/{day.day:02d}"


def fetch_ezsearch_candidates(stock_id: str, *, now: datetime, post=None) -> tuple[list[tuple], dict]:
    """Return exact-company M announcements; only a complete index may close the window."""
    if not re.fullmatch(r"[1-9]\d{3,5}", stock_id):
        raise ValueError("invalid listed company ID")
    now = now.astimezone(TAIPEI)
    lower = now - timedelta(days=30)
    post = post or sync_post
    diagnostic = {"index_url": INDEX_URL, "coverage_status": "partial",
                  "status": "unavailable", "rejected_reason_counts": {},
                  "index_limit": MAX_INDEX_ROWS, "candidate_limit": MAX_CANDIDATES}
    form = {"step": "00", "RADIO_CM": "2", "TYPEK": "", "CO_MARKET": "",
            "CO_ID": stock_id, "PRO_ITEM": "", "SUBJECT": "",
            "SDATE": _roc_string(lower), "EDATE": _roc_string(now), "lang": "TW", "AN": ""}
    try:
        response = post(INDEX_URL, data=form, headers={"Referer": "https://mopsov.twse.com.tw/mops/web/ezsearch"},
                        timeout=(5, 15), provider="TWSE EZSearch company history")
        response.raise_for_status()
        if len(response.content) > MAX_INDEX_BYTES:
            raise ValueError("oversized TWSE company search response")
        payload = json.loads(response.content.decode("utf-8-sig").strip())
        rows = payload.get("data") if isinstance(payload, dict) and payload.get("status") == "success" else None
        if not isinstance(rows, list) or len(rows) >= MAX_INDEX_ROWS:
            raise ValueError("TWSE company search incomplete or invalid")
    except Exception as exc:
        diagnostic.update(status="error", error_kind=getattr(exc, "error_kind", type(exc).__name__),
                          http_status=getattr(getattr(exc, "response", None), "status_code", None))
        return [], diagnostic
    rejected = Counter()
    candidates = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            rejected["invalid_row"] += 1
            continue
        if str(row.get("COMPANY_ID")) != stock_id:
            rejected["issuer_mismatch"] += 1
            continue
        if row.get("TYPEK") != "上市":
            rejected["market_mismatch"] += 1
            continue
        if not re.fullmatch(r"M\d{2}", str(row.get("AN_CODE") or "")):
            continue
        try:
            day = _roc_day(row.get("CDATE"))
            clock = str(row.get("CTIME") or "").strip()
            if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", clock):
                raise ValueError("invalid announcement time")
            published = datetime.fromisoformat(f"{day.date().isoformat()}T{clock}").replace(tzinfo=TAIPEI)
        except (ValueError, TypeError):
            rejected["invalid_publication_time"] += 1
            continue
        if not lower <= published <= now:
            rejected["outside_window"] += 1
            continue
        link = str(row.get("HYPERLINK") or "").strip()
        if (not _detail_identity(link, stock_id, published)
                or parse_qs(urlsplit(link).query)["SPOKE_TIME"][0].zfill(6) != published.strftime("%H%M%S")):
            rejected["invalid_detail_url"] += 1
            continue
        company = _text(row.get("COMPANY_NAME"))
        title = _text(row.get("SUBJECT"))
        if not company or not title:
            rejected["missing_subject_or_company"] += 1
            continue
        if link in seen:
            rejected["duplicate_detail"] += 1
            continue
        seen.add(link)
        candidates.append((published, title, company, link))
    hard_rejections = sum(count for reason, count in rejected.items() if reason != "outside_window")
    complete = not hard_rejections and len(candidates) <= MAX_CANDIDATES
    diagnostic.update(status="success" if complete else "degraded_enrichment",
                      coverage_status="window_complete" if complete else "partial",
                      index_count=len(rows), candidate_count=len(candidates),
                      rejected_reason_counts=dict(rejected))
    return candidates[:MAX_CANDIDATES], diagnostic
