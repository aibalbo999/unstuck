"""Exact issuer postings from Cathay Financial Holdings' public career site.

The listed issuer links to this recruiting host from its own career page. The
site's company selector uses C0 for the holding company; other codes are group
subsidiaries and cannot be attributed to 2882. No login or browser token is
used. A listing without individually open postings is unknown, not zero jobs.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import os
import re
import time
from uuid import uuid4

from bounded_curl_process import collect_capped_process


PROVIDER = "Cathay Financial Holdings official careers"
CAREER_URL = "https://recruit.cathayholdings.com/iMatch/job/search"
API_URL = "https://recruit.cathayholdings.com/api/job/EZM-C-JOBLISTQ001"
LEGAL_NAME = "國泰金融控股股份有限公司"
TICKER = "2882.TW"
MAX_BYTES = 1_000_000
MAX_ROWS = 1_000
MAX_POSTINGS = 10
JOB_ID = re.compile(r"I\d{8}")
DIGEST = re.compile(r"[0-9a-f]{64}")


def _sequence() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + uuid4().hex[:4]


def _request(sequence: str) -> bytes:
    return json.dumps({
        "MWHEADER": {"TXNSEQ": sequence, "MSGID": "EZM-C-JOBLISTQ001",
                     "SOURCECHANNEL": "HRD-LX-FND-01"},
        "TRANRQ": {"LOCATION_PARENT_ID": None, "LOCATION_ID_LIST": [],
                   "COMPANY_LIST": ["C0"], "JOB_TYPE": None,
                   "EMPLOYMENT_TYPE": None, "WORKED_YEARS_CONDITION": None,
                   "EDU_DEGREE_CONDITION": None, "KEYWORD": ""},
    }, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _download(request: bytes) -> bytes:
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
        raise RuntimeError("network disabled for tests")
    if not isinstance(request, bytes) or len(request) > 2048:
        raise ValueError("invalid career request")
    # The host's certificate is accepted by the system curl trust store but
    # rejected by the project's Python/OpenSSL chain validator. Keep TLS
    # verification enabled and never copy browser credentials into this call.
    argv = ["/usr/bin/curl", "--disable", "--silent", "--show-error", "--fail-with-body",
            "--max-time", "12", "--connect-timeout", "4", "--max-filesize", str(MAX_BYTES),
            "--proto", "=https", "--max-redirs", "0", "--retry", "0",
            "-H", "Content-Type: application/json", "-H", "Accept: application/json",
            "-H", "Referer: " + CAREER_URL, "--data-binary", request.decode("ascii"), API_URL]
    parts, rc, error = collect_capped_process(argv, time.monotonic() + 13,
                                               body_limit=MAX_BYTES)
    if error or rc != 0 or not 0 < len(parts["body"]) <= MAX_BYTES:
        raise RuntimeError(error or "career HTTP response unavailable")
    return parts["body"]


def parse_career_listing(raw: bytes, sequence: str, *, fetched_at_epoch: float) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("career response size invalid")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("career response shape invalid")
    header = payload.get("MWHEADER")
    result = payload.get("TRANRS")
    if (not isinstance(header, dict) or header.get("MSGID") != "EZM-C-JOBLISTQ001"
            or header.get("TXNSEQ") != sequence or header.get("RETURNCODE") != "0000"
            or not isinstance(result, dict)):
        raise ValueError("career response identity or result invalid")
    rows = result.get("JOB_LIST")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("career job list incomplete or oversized")
    seen: dict[str, dict] = {}
    rejected = 0
    for row in rows:
        if not isinstance(row, dict):
            rejected += 1
            continue
        number = row.get("APPL_FORM_NO")
        title = str(row.get("JOB_TITLE") or "").strip()
        if (not isinstance(number, str) or not JOB_ID.fullmatch(number)
                or not 1 <= len(title) <= 200
                or row.get("COMPANY_NAME") != "COMPANY_SIMPLE_C0"
                or row.get("COMPANY_LIST") != ["C0"]
                or row.get("IS_OPEN") != "Y" or row.get("CAN_SUBMIT") != "Y"
                or "職缺總覽" in title or "請勿在此頁投遞" in str(row.get("JOB_DESCRIPTION") or "")):
            rejected += 1
            continue
        job = {"title": title, "url": f"https://recruit.cathayholdings.com/iMatch/job/info/{number}",
               "job_no": number, "employer": LEGAL_NAME, "company_code": "C0",
               "is_open": True, "can_submit": True}
        if number in seen:
            if seen[number] != job:
                raise ValueError("conflicting official career job identity")
            rejected += 1
            continue
        seen[number] = job
    if not seen:
        return {"status": "unavailable", "ticker": TICKER, "company_name": LEGAL_NAME,
                "job_count": None, "current_open_job_count": None, "job_postings": [],
                "reason_code": "no_verified_open_issuer_postings", "rejected_count": rejected,
                "source": PROVIDER, "source_url": API_URL}
    return {"status": "success", "ticker": TICKER, "company_name": LEGAL_NAME,
            "job_count": None, "current_open_job_count": len(seen),
            "job_postings": list(seen.values())[:MAX_POSTINGS],
            "evidence_kind": "official_company_job_postings",
            "query_scope": "exact_issuer_current_open_postings", "source": PROVIDER,
            "source_url": API_URL, "listing_url": CAREER_URL,
            "response_sha256": sha256(raw).hexdigest(), "response_bytes": len(raw),
            "fetched_at_epoch": fetched_at_epoch,
            "rejected_count": rejected, "raw_count": len(rows),
            "coverage_status": "current_open_posting_sample",
            "message": "只計入官方招募站金控公司別 C0 的開放中職缺；不含集團子公司，也不推定刊登日期。"}


def fetch_official_cathay_jobs(ticker: str) -> dict:
    if ticker != TICKER:
        return {"status": "unavailable", "reason_code": "issuer_not_supported", "job_count": None}
    sequence = _sequence()
    try:
        raw = _download(_request(sequence))
        return parse_career_listing(raw, sequence, fetched_at_epoch=time.time())
    except (RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {"status": "unavailable", "ticker": TICKER, "company_name": LEGAL_NAME,
                "job_count": None, "current_open_job_count": None, "job_postings": [],
                "source": PROVIDER, "source_url": API_URL, "reason_code": "official_career_unverified"}


def verified_official_job_count(value: dict, ticker: str, legal_name: str, *, now: float | None = None) -> int:
    """Count only source-shaped, fresh individual records for the exact issuer."""
    now = time.time() if now is None else now
    if not isinstance(value, dict) or value.get("status") != "success":
        return 0
    fetched = value.get("fetched_at_epoch")
    rows = value.get("job_postings")
    total = value.get("current_open_job_count")
    if (ticker != TICKER or legal_name != LEGAL_NAME or value.get("ticker") != TICKER
            or value.get("company_name") != LEGAL_NAME or value.get("source") != PROVIDER
            or value.get("source_url") != API_URL or value.get("listing_url") != CAREER_URL
            or value.get("evidence_kind") != "official_company_job_postings"
            or value.get("query_scope") != "exact_issuer_current_open_postings"
            or value.get("job_count") is not None
            or not DIGEST.fullmatch(str(value.get("response_sha256") or ""))
            or type(fetched) not in (int, float) or not 0 <= now - fetched <= 86400
            or type(total) is not int or total <= 0
            or not isinstance(rows, list) or not 0 < len(rows) <= MAX_POSTINGS
            or total < len(rows)):
        return 0
    ids = set()
    for row in rows:
        if not isinstance(row, dict):
            return 0
        number = row.get("job_no")
        if (not isinstance(number, str) or not JOB_ID.fullmatch(number) or number in ids
                or not isinstance(row.get("title"), str) or not row["title"].strip()
                or row.get("employer") != LEGAL_NAME or row.get("company_code") != "C0"
                or row.get("is_open") is not True or row.get("can_submit") is not True
                or row.get("url") != f"https://recruit.cathayholdings.com/iMatch/job/info/{number}"):
            return 0
        ids.add(number)
    return len(ids)
