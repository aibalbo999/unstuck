"""Cathay Financial Holdings' dated IR event links; no presentation redistribution."""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import os
import re
import time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from external_http_client import sync_get
from search_provider_runtime import SourceResponseError, error_details, observe_http_response, record_observation
from shared_provider_cache import shared_fetch


PROVIDER = "Cathay Financial Holdings official IR"
INDEX_URL = "https://www.cathayholdings.com/holdings/ir"
PARSER_VERSION = "cathay-ir-event-metadata-v1"
MAX_BYTES = 1_000_000
COVERAGE_NOTE = "僅取得公司官方法說活動日期與簡報、直播連結；未讀取或轉供簡報、影音及逐字稿。"
_EVENT = re.compile(r"/holdings/ir/events_and_announcements/events/event_info\?EventID=[A-Za-z0-9_-]+")
_PDF = re.compile(r"/holdings/-/media/[0-9a-f]{32}\.pdf\?sc_lang=zh-tw")
_VIDEO = re.compile(r"https://www\.zucast\.com/webcast/[A-Za-z0-9_-]+")
_DATE = re.compile(r"^(\d{4}/\d{2}/\d{2})\s+(.+)$")


def supports_cathay(ticker: str) -> bool:
    return str(ticker or "").strip().upper() in {"2882", "2882.TW"}


def parse_index(raw: bytes, *, today: date | None = None) -> dict | None:
    """Select one completed Chinese quarterly event and its same-issuer links."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Cathay IR page size invalid")
    soup = BeautifulSoup(raw, "html.parser")
    visible = soup.get_text(" ", strip=True)
    if "國泰金融控股" not in visible or not re.search(r"(?<!\d)2882(?!\d)", visible):
        return None
    today = today or datetime.now(ZoneInfo("Asia/Taipei")).date()
    rows = []
    for item in soup.select("[list001item]"):
        event = item.find("a", href=_EVENT)
        block = event.select_one(".d-lg-flex") if event else None
        match = _DATE.fullmatch(block.get_text(" ", strip=True)) if block else None
        if not match or "法人說明會" not in match[2] or "中文" not in match[2]:
            continue
        try:
            event_date = date.fromisoformat(match[1].replace("/", "-"))
        except ValueError:
            continue
        if event_date > today:
            continue
        pdf = item.find("a", id="lnk_FileButtonLink", href=_PDF)
        if pdf is None:
            continue
        video = item.find("a", id="lnk_VideoButtonLink", href=_VIDEO)
        rows.append({"date": event_date.isoformat(), "title": match[2],
                     "event_url": urljoin(INDEX_URL, event["href"]),
                     "presentation_url": urljoin(INDEX_URL, pdf["href"]),
                     "webcast_url": video["href"] if video else ""})
    if not rows:
        return None
    latest = max(row["date"] for row in rows)
    selected = [row for row in rows if row["date"] == latest]
    if len(selected) != 1:
        raise ValueError("ambiguous latest Cathay IR event")
    return selected[0]


def _fetch() -> dict:
    started = time.monotonic()
    details = {"actual_provider": PROVIDER, "parser_version": PARSER_VERSION,
               "source_url": INDEX_URL, "http_request_sent": False}
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
        raise SourceResponseError("test_network_disabled")
    response = None
    observe_http_response(None)
    try:
        response = sync_get(INDEX_URL, timeout=(4, 9), provider=PROVIDER)
        observe_http_response(response)
        raw = response.content
        details.update(http_request_sent=True, http_status=response.status_code,
                       response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
        if response.headers.get("content-type", "").split(";")[0].lower() != "text/html":
            raise ValueError("unexpected Cathay IR content type")
        selected = parse_index(raw)
    except Exception as exc:
        received = response or getattr(exc, "response", None)
        if received is not None:
            observe_http_response(received)
        details.update(http_request_sent=received is not None, **error_details(exc))
        record_observation(PROVIDER, started, outcome="failure", source="earnings_call",
                           details=details, sent=details["http_request_sent"])
        error = SourceResponseError(details["error_kind"], status_code=details.get("http_status"))
        error.diagnostic.update(details)
        raise error from exc
    details.update(outcome="results" if selected else "valid_empty",
                   coverage_status="metadata_only", record_count=1 if selected else 0,
                   fetched_at_epoch=time.time())
    record_observation(PROVIDER, started, outcome=details["outcome"],
                       count=details["record_count"], source="earnings_call", details=details)
    if not selected:
        return {"context": {}, "diagnostic": details}
    materials = [{"url": selected["presentation_url"], "kind": "presentation_link",
                  "content_retrieved": False, "transcript_available": False}]
    if selected["webcast_url"]:
        materials.append({"url": selected["webcast_url"], "kind": "official_webcast_link",
                          "content_retrieved": False, "transcript_available": False})
    context = {"ticker": "2882.TW", "date": selected["date"], "period": selected["date"],
               "title": selected["title"], "summary": "", "transcript_excerpt": "",
               "transcript_available": False, "source": PROVIDER, "source_url": INDEX_URL,
               "event_url": selected["event_url"], "materials": materials,
               "coverage_status": "metadata_only", "coverage_notes": [COVERAGE_NOTE],
               "fetched_at_epoch": details["fetched_at_epoch"]}
    return {"context": context, "diagnostic": details}


def fetch_cathay_conference_context(ticker: str, *, diagnostics: dict | None = None) -> dict:
    if not supports_cathay(ticker):
        return {}
    captured = {}
    def fetch():
        try:
            return _fetch()
        except SourceResponseError as exc:
            captured.update(exc.diagnostic)
            raise
    value, meta = shared_fetch(PARSER_VERSION + ":2882", fetch, freshness_seconds=86400,
                               result_ttl=lambda row: 86400 if row["context"] else 300,
                               lock_wait_seconds=0)
    if meta.get("error_kind"):
        details = {**meta, **captured, "actual_provider": PROVIDER}
        error = SourceResponseError(details.get("error_kind") or "provider_error",
                                    status_code=details.get("http_status"))
        error.diagnostic.update(details)
        raise error
    details = {**value["diagnostic"], **meta, "actual_provider": PROVIDER,
               "coverage_status": "partial"}
    if meta.get("cache_hit"):
        details.update(http_request_sent=False, event_kind="cache_hit")
    if diagnostics is not None:
        diagnostics.update(details)
    return dict(value["context"])
