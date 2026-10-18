"""Bounded public SGX issuer statements for one exchange-anchored Taiwan TDR.

Research candidate: deliberately absent from the formal provider plan because
the native anonymous date query returned 401. Do not copy website credentials.
SGX is the publishing venue; it does not approve the company's assertions.
Original-share identifiers never become a TDR price, share count or currency.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import re
import time
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from news_record_utils import clean_text
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .issuer_news_transport import IssuerNewsHttp, ROSTER_URL
from .official_company_legal_name import parse_roster, select_legal_name

POLICY = "sgx-issuer-announcement-v1"
SG = ZoneInfo("Asia/Singapore")
UTC = timezone.utc
TICKER = "9103.TW"
SHORT = "美德醫療-DR"
LEGAL = "美德向邦醫療國際股份有限公司"
ENGLISH = "MEDTECS INTERNATIONAL CORPORATION LIMITED"
ISSUER = "MEDTECS INTERNATIONAL CORP LTD"
ISIN, STOCK = "BMG5958R1043", "546"
API = "https://api.sgx.com/announcements/v1.1/company"
ARTICLE = re.compile(r"https://links\.sgx\.com/1\.0\.0/corporate-announcements/([A-Z0-9]{16})/([0-9a-f]{64})\Z")


def query_url(now):
    local = now.astimezone(SG).replace(hour=0, minute=0, second=0, microsecond=0)
    return API + "?" + urlencode({
        "periodstart": (local - timedelta(days=30)).astimezone(UTC).strftime("%Y%m%d_%H%M%S"),
        "periodend": (local + timedelta(days=1, seconds=-1)).astimezone(UTC).strftime("%Y%m%d_%H%M%S"),
        "value": ISSUER, "exactsearch": "true", "pagestart": "0", "pagesize": "20",
    }, quote_via=quote)


def url_contract(url):
    if url == ROSTER_URL:
        return 2_500_000, {"application/json", "text/json"}
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.fragment or parts.username or parts.password or parts.port:
        raise SourceResponseError("transport_url_invalid")
    if parts.netloc == "api.sgx.com" and parts.path == "/announcements/v1.1/company":
        params = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
        required = {"periodstart", "periodend", "value", "exactsearch", "pagestart", "pagesize"}
        if set(params) == required and all(len(v) == 1 for v in params.values()):
            start = datetime.strptime(params["periodstart"][0], "%Y%m%d_%H%M%S")
            end = datetime.strptime(params["periodend"][0], "%Y%m%d_%H%M%S")
            if (params["value"] == [ISSUER] and params["exactsearch"] == ["true"]
                    and params["pagestart"] == ["0"] and params["pagesize"] == ["20"]
                    and timedelta(0) < end - start <= timedelta(days=31)):
                return 100_000, {"application/json", "text/json"}
    if ARTICLE.fullmatch(url):
        return 100_000, {"text/html", "application/xhtml+xml"}
    if parts.netloc == "links.sgx.com" and parts.path.startswith("/FileOpen/"):
        name = unquote(parts.path[len("/FileOpen/"):])
        if (1 <= len(name) <= 300 and re.fullmatch(r"[^/\\?#\x00-\x1f]+\.ashx", name)
                and ".." not in name and re.fullmatch(r"App=Announcement&FileID=[1-9][0-9]{4,8}", parts.query)):
            return 1_000_000, {"application/pdf", "application/octet-stream"}
    raise SourceResponseError("transport_url_invalid")


class SgxNewsHttp(IssuerNewsHttp):
    route_contract = staticmethod(url_contract)


def _identity(raw, today):
    anchor = select_legal_name(parse_roster(raw, ".TW"), TICKER, SHORT, today=today)
    rows = [r for r in json.loads(raw) if str(r.get("公司代號")) == "9103"]
    if not anchor or len(rows) != 1:
        raise ValueError("tdr_identity_unverified")
    row = rows[0]
    if (anchor["legal_name"] != LEGAL or str(row.get("英文簡稱") or "").strip() != "MEDTECS"
            or str(row.get("網址") or "").strip() not in {"www.medtecs.com", "https://www.medtecs.com"}
            or not str(row.get("外國企業註冊地國") or "").strip().startswith("BM ")):
        raise ValueError("tdr_identity_unverified")
    return {"ticker": TICKER, "official_name": SHORT, "legal_name": LEGAL,
            "english_alias": "MEDTECS", "registered_country": "BM",
            "master_observed_on": anchor["as_of"], "master_source_url": ROSTER_URL,
            "master_response_sha256": sha256(raw).hexdigest(),
            "original_share_issuer": ISSUER, "original_share_isin": ISIN, "original_share_code": STOCK}


def _milliseconds(value):
    if type(value) is not int or not 946684800000 <= value <= 4102444800000:
        raise ValueError("announcement_time_invalid")
    return datetime.fromtimestamp(value / 1000, UTC)


def _candidate(item):
    if not isinstance(item, dict) or item.get("issuer_name") != ISSUER or item.get("security_name") != ISSUER:
        raise ValueError("sgx_issuer_unverified")
    issuers = item.get("issuers")
    if (not isinstance(issuers, list) or len(issuers) != 1
            or any(issuers[0].get(k) != v for k, v in {
                "issuer_name": ISSUER, "security_name": ISSUER, "isin_code": ISIN, "stock_code": STOCK}.items())):
        raise ValueError("sgx_security_unverified")
    match = ARTICLE.fullmatch(str(item.get("url") or ""))
    title, reference = item.get("title"), item.get("ref_id")
    if (not match or match[1] != item.get("id") or item.get("sub") != "ANNC18" or item.get("cat") != "ANNC"
            or not isinstance(title, str) or not title.startswith("General Announcement::")
            or not 1 <= len(title.split("::", 1)[1]) <= 300
            or not re.fullmatch(r"SG[0-9]{6}OTHR[A-Z0-9]{4}", str(reference or ""))):
        raise ValueError("sgx_announcement_shape_invalid")
    submitted = _milliseconds(item.get("submission_date_time"))
    published = _milliseconds(item.get("broadcast_date_time"))
    if (submitted > published or published - submitted > timedelta(days=1)
            or item.get("submission_date") != submitted.astimezone(SG).strftime("%Y%m%d")
            or reference[2:8] != submitted.astimezone(SG).strftime("%y%m%d")):
        raise ValueError("announcement_time_mismatch")
    return published


def _canonical_attachment(attachment, item):
    parts = urlsplit(attachment)
    prefix = f"/1.0.0/corporate-announcements/{item['id']}/"
    if (parts.scheme != "https" or parts.netloc != "links.sgx.com" or parts.query or parts.fragment
            or not parts.path.startswith(prefix)):
        raise ValueError("sgx_attachment_binding_invalid")
    name = unquote(parts.path[len(prefix):])
    match = re.fullmatch(r"([1-9][0-9]{4,8})_([^/\\?#\x00-\x1f]+)\.pdf", name)
    if not match or ".." in name:
        raise ValueError("sgx_attachment_binding_invalid")
    url = "https://links.sgx.com/FileOpen/" + quote(match[2], safe="-_.()~") + ".ashx?App=Announcement&FileID=" + match[1]
    url_contract(url)
    return url


def _original(raw, item, published):
    soup = BeautifulSoup(raw, "html.parser")
    fields = {}
    for label in soup.select("dt"):
        value = label.find_next_sibling("dd")
        name = clean_text(label)
        if value is None or name in fields:
            raise ValueError("sgx_detail_fields_invalid")
        fields[name] = clean_text(value)
    expected = {"Issuer/ Manager": ISSUER, "Securities": f"{ISSUER} - {ISIN} - {STOCK}",
                "Status": "New", "Announcement Title": "General Announcement",
                "Announcement Reference": item["ref_id"],
                "Announcement Sub Title": item["title"].split("::", 1)[1],
                "Date &Time of Broadcast": published.astimezone(SG).strftime("%d-%b-%Y %H:%M:%S")}
    if any(fields.get(k) != v for k, v in expected.items()):
        raise ValueError("sgx_index_original_mismatch")
    attachments = soup.select("a.announcement-attachment[href]")
    if len(attachments) != 1:
        raise ValueError("sgx_attachment_coverage_unverified")
    path = f"/1.0.0/corporate-announcements/{item['id']}/"
    href = attachments[0]["href"]
    if not isinstance(href, str) or not href.startswith(path):
        raise ValueError("sgx_attachment_binding_invalid")
    # This fixed public FileOpen mapping was verified against the publisher's
    # actual 302 Location. Do not follow arbitrary redirects or copy sessions.
    attachment = "https://links.sgx.com" + href
    return _canonical_attachment(attachment, item), attachment


def _pdf_text(raw, published, subtitle, remaining):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1_000_000 or not raw.startswith(b"%PDF-"):
        raise ValueError("sgx_pdf_invalid")
    result = extract_pdf_pages(raw, timeout_seconds=min(5., remaining))
    if result["coverage_status"] != "complete" or not 1 <= result["page_count"] <= 8:
        raise ValueError("sgx_pdf_coverage_incomplete")
    body = clean_text("\n".join(p["text"] for p in result["pages"]))
    normalized = " ".join(body.split()).casefold()
    day = published.astimezone(SG).date()
    signed = f"{day.day} {day.strftime('%B %Y')}"
    signed_dates = re.findall(r"BY ORDER OF THE BOARD[\s\S]{0,250}?\b(\d{1,2} [A-Z][a-z]+ 20\d{2})\b", body)
    if (not 100 <= len(body) <= 12000 or ENGLISH.casefold() not in normalized
            or " ".join(subtitle.split()).casefold() not in normalized
            or signed_dates != [signed]):
        raise ValueError("sgx_pdf_identity_date_title_unverified")
    return body, result


_CONTENT_FIELDS = ("ticker", "title", "date", "text", "summary", "source", "source_type", "link",
                   "source_document_url", "original_attachment_url", "source_role", "event_assessment",
                   "content_coverage", "content_truncated", "publication_date_precision", "publication_date_original")


def _digest(record):
    return sha256(json.dumps({k: record.get(k) for k in _CONTENT_FIELDS}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def verified_sgx_issuer_news(record, data, *, today=None):
    try:
        receipt = record.get("sgx_issuer_receipt")
        if not isinstance(receipt, dict) or data.get("ticker") != TICKER:
            return None
        expected = {"policy": POLICY, "ticker": TICKER, "official_name": SHORT, "legal_name": LEGAL,
                    "english_alias": "MEDTECS", "registered_country": "BM", "master_source_url": ROSTER_URL,
                    "original_share_issuer": ISSUER, "original_share_isin": ISIN, "original_share_code": STOCK}
        if any(receipt.get(k) != v for k, v in expected.items()):
            return None
        identity = data.get("company_identity") or {}
        if not isinstance(identity, dict) or identity.get("official_name") not in (None, "", SHORT):
            return None
        if identity.get("legal_name") not in (None, "", LEGAL):
            return None
        forbidden = identity.get("forbidden_aliases", [])
        if not isinstance(forbidden, (list, tuple)) or any(clean_text(x).strip().strip("*").casefold() == "medtecs" for x in forbidden):
            return None
        current = today or datetime.now(SG).date()
        if not 0 <= (current - date.fromisoformat(receipt["master_observed_on"])).days <= 14:
            return None
        if (record.get("ticker") != TICKER or record.get("source_type") != "foreign_exchange_issuer_announcement"
                or record.get("source") != "美德醫療官方公告（SGX）" or record.get("source_role") != "issuer_statement"
                or record.get("event_assessment") != "not_assessed" or record.get("content_coverage") != "text_available"
                or record.get("content_truncated") is not False or record.get("publication_date_precision") != "second"
                or receipt.get("parsed_content_sha256") != _digest(record)):
            return None
        if not all(re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(k) or "")) for k in (
                "master_response_sha256", "index_response_sha256", "article_response_sha256", "pdf_response_sha256")):
            return None
        item = receipt["index_identity"]
        stamp = _candidate(item)
        if record.get("date") != stamp.isoformat() or record.get("link") != item["url"] or record.get("title") != item["title"]:
            return None
        if _canonical_attachment(record["original_attachment_url"], item) != record["source_document_url"]:
            return None
        if receipt.get("pdf_extraction_sha256") != receipt["pdf_response_sha256"] or receipt.get("pdf_coverage_status") != "complete":
            return None
        if type(receipt.get("pdf_page_count")) is not int or not 1 <= receipt["pdf_page_count"] <= 8:
            return None
        original = record["publication_date_original"]
        if original != {"broadcast_epoch_ms": item["broadcast_date_time"], "timezone": "Asia/Singapore",
                        "signed_on": stamp.astimezone(SG).date().isoformat()}:
            return None
        body = record.get("text")
        if not isinstance(body, str) or not 100 <= len(body) <= 12000 or ENGLISH not in " ".join(body.split()):
            return None
        return "MEDTECS"
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, SourceResponseError):
        return None


def fetch_sgx_issuer_news(ticker, *, now=None, http=None):
    now = now or datetime.now(UTC)
    if ticker != TICKER:
        return [], {"status": "not_applicable", "event_kind": "local_block", "http_request_sent": False, "record_count": 0}
    deadline = time.monotonic() + 20
    http = http or SgxNewsHttp(deadline)
    records, excluded = [], Counter()
    audit = {"selection_policy": POLICY, "coverage_status": "partial", "window_complete": False}
    try:
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("reference_time_unverified")
        identity = _identity(http.get(ROSTER_URL), now.astimezone(SG).date())
        index = http.get(query_url(now))
        payload = json.loads(index)
        if not isinstance(payload, dict) or payload.get("meta", {}).get("code") != "200":
            raise ValueError("sgx_index_invalid")
        rows = payload.get("data")
        if not isinstance(rows, list) or len(rows) > 20:
            raise ValueError("sgx_index_invalid")
        audit["raw_count"] = len(rows)
        selected, seen = [], set()
        for item in rows:
            try:
                stamp = _candidate(item)
                if stamp > now or now - stamp > timedelta(days=30):
                    excluded["outside_window"] += 1
                elif item["id"] in seen:
                    excluded["duplicate"] += 1
                else:
                    seen.add(item["id"]); selected.append((stamp, item))
            except (ValueError, TypeError, AttributeError):
                excluded["issuer_or_announcement_unverified"] += 1
        for stamp, item in sorted(selected, key=lambda p: p[0], reverse=True)[:3]:
            if time.monotonic() >= deadline:
                raise SourceResponseError("timeout")
            raw = http.get(item["url"])
            document, attachment = _original(raw, item, stamp)
            pdf = http.get(document)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SourceResponseError("timeout")
            body, extracted = _pdf_text(pdf, stamp, item["title"].split("::", 1)[1], remaining)
            if time.monotonic() >= deadline:
                raise SourceResponseError("timeout")
            record = {"ticker": TICKER, "title": item["title"], "date": stamp.isoformat(), "text": body, "summary": body[:280],
                      "source": "美德醫療官方公告（SGX）", "source_type": "foreign_exchange_issuer_announcement",
                      "link": item["url"], "source_document_url": document, "original_attachment_url": attachment,
                      "source_role": "issuer_statement", "event_assessment": "not_assessed",
                      "content_coverage": "text_available", "content_truncated": False, "publication_date_precision": "second",
                      "publication_date_original": {"broadcast_epoch_ms": item["broadcast_date_time"], "timezone": "Asia/Singapore",
                                                    "signed_on": stamp.astimezone(SG).date().isoformat()}}
            record["sgx_issuer_receipt"] = {**identity, "policy": POLICY, "index_identity": item,
                "index_response_sha256": sha256(index).hexdigest(), "article_response_sha256": sha256(raw).hexdigest(),
                "pdf_response_sha256": sha256(pdf).hexdigest(), "pdf_extraction_sha256": extracted["content_sha256"],
                "pdf_page_count": extracted["page_count"], "pdf_coverage_status": extracted["coverage_status"],
                "parsed_content_sha256": _digest(record)}
            if not verified_sgx_issuer_news(record, {"ticker": TICKER}, today=now.astimezone(SG).date()):
                raise ValueError("saved_sgx_receipt_unverified")
            records.append(record)
        audit["status"] = "degraded_enrichment" if excluded and not records else "success" if records else "unavailable"
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, SourceResponseError, SourcePdfError) as exc:
        audit.update(status="degraded_enrichment" if records else "error", error_kind=getattr(exc, "error_kind", "parse_error"), error_message=str(exc)[:150])
    components = getattr(http, "components", [])
    sent = getattr(http, "http_request_count", 0)
    cached = bool(components) and all(c.get("cache_hit") for c in components)
    if audit.get("status") == "success" and cached and not sent:
        audit["status"] = "skipped_fresh_cache"
    epochs = [c["fetched_at_epoch"] for c in components if type(c.get("fetched_at_epoch")) in (int, float)]
    audit.update(record_count=len(records), usable_count=len(records), excluded_reason_counts=dict(excluded),
                 http_request_count=sent, http_request_sent=bool(sent), cache_hit=cached, stale=False,
                 event_kind="http_request" if sent else "cache_hit" if cached else "local_block",
                 fetched_at_epoch=min(epochs) if epochs else None, parser_version=POLICY, component_receipts=components)
    return records, audit
