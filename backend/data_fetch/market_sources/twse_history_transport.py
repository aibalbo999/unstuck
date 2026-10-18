"""Hard-deadline, capped ordinary HTTPS for official company-history endpoints."""
from __future__ import annotations

import json
import hashlib
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit

import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                     remember_failure, scope_key)

PROVIDER = "TWSE company announcement history"
IIH_URL = "https://wwwc.twse.com.tw/rwd/zh/IIH/company/events"
IIH_EN_URL = "https://wwwc.twse.com.tw/rwd/en/IIH/company/events"
EZ_URL = "https://mopsov.twse.com.tw/mops/web/ezsearch_query"
JSON_URL = "https://mops.twse.com.tw/mops/api/t05st01"
TDR_DETAIL_URL = "https://mops.twse.com.tw/mops/api/t59sb01_detail"
ORDINARY_DETAIL_URL = "https://mops.twse.com.tw/mops/api/t05st01_detail"
ORDINARY_DETAIL_CODES = frozenset({"1216", "2442", "2838", "2845", "6550", "6924"})
TDR_PDF = re.compile(r"https://mopsov\.twse\.com\.tw/nas/t59/t59sa01/9103_\d{8}\d{2}_FIM\.pdf\Z")
TDR_MASTER_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_INFOHUB_API_URL = "https://info.tpex.org.tw/api/stkInfo"
PROXY_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def _mops_conference_notice_url(url):
    try:
        parsed = urlsplit(url)
        query_text = parsed.query[1:] if parsed.query.startswith("&") else parsed.query
        pairs = parse_qsl(query_text, keep_blank_values=False, strict_parsing=True)
    except (TypeError, ValueError):
        return False
    query = dict(pairs)
    return bool(
        parsed.scheme == "https" and parsed.hostname == "emops.twse.com.tw"
        and parsed.port in (None, 443) and not parsed.username and not parsed.password
        and parsed.path == "/server-java/t05sr01_1_e" and not parsed.fragment
        and len(query) == len(pairs) and set(query) <= {"isNew", "seq_no", "spoke_time", "spoke_date", "co_id"}
        and {"seq_no", "spoke_time", "spoke_date", "co_id"} <= set(query)
        and query.get("isNew", "Y") == "Y"
        and re.fullmatch(r"\d{1,6}", query.get("seq_no", "")) is not None
        and re.fullmatch(r"\d{6}", query.get("spoke_time", "")) is not None
        and re.fullmatch(r"\d{8}", query.get("spoke_date", "")) is not None
        and re.fullmatch(r"\d{4,6}", query.get("co_id", "")) is not None
    )


def _mops_conference_month_url(url):
    """Accept only IIH-published, issuer- and month-bound MOPS event pages."""
    try:
        parsed = urlsplit(url)
        query_text = parsed.query[1:] if parsed.query.startswith('&') else parsed.query
        pairs = parse_qsl(query_text, keep_blank_values=False, strict_parsing=True)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    query = dict(pairs)
    month = query.get("LPSHOW_DATE_MM", "")
    return bool(
        parsed.scheme == "https" and parsed.hostname == "emops.twse.com.tw"
        and port in (None, 443) and not parsed.username and not parsed.password
        and parsed.path == "/server-java/t100sb07_1_e" and not parsed.fragment
        and len(query) == len(pairs)
        and set(query) == {"TYPEK", "step", "code", "LPSHOW_DATE_YY", "LPSHOW_DATE_MM"}
        and query.get("TYPEK") == "all" and query.get("step") == "show"
        and re.fullmatch(r"\d{4,6}", query.get("code", "")) is not None
        and re.fullmatch(r"20\d{2}", query.get("LPSHOW_DATE_YY", "")) is not None
        and re.fullmatch(r"0[1-9]|1[0-2]", month) is not None
    )


def _mops_english_announcement_url(url):
    try:
        parsed = urlsplit(url)
        query_text = parsed.query[1:] if parsed.query.startswith('&') else parsed.query
        pairs = parse_qsl(query_text, keep_blank_values=False, strict_parsing=True)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    query = dict(pairs)
    stamp = query.get('spoke_time', '').zfill(6)
    return bool(
        parsed.scheme == 'https' and parsed.hostname == 'emops.twse.com.tw'
        and port in (None, 443) and not parsed.username and not parsed.password
        and parsed.path == '/server-java/t05sr01_1_e' and not parsed.fragment
        and len(query) == len(pairs)
        and set(query) == {'isNew', 'seq_no', 'spoke_time', 'spoke_date', 'co_id'}
        and query.get('isNew') == 'Y'
        and re.fullmatch(r'[1-9]\d{3,5}', query.get('co_id', '')) is not None
        and re.fullmatch(r'\d{8}', query.get('spoke_date', '')) is not None
        and re.fullmatch(r'\d{1,6}', query.get('spoke_time', '')) is not None
        and int(stamp[:2]) < 24 and int(stamp[2:4]) < 60 and int(stamp[4:]) < 60
        and re.fullmatch(r'[1-9]\d{0,5}', query.get('seq_no', '')) is not None
    )


def _tpex_infohub_api_url(url):
    """Accept only the public InfoHub company query for one exact TPEx code."""
    try:
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=False, strict_parsing=True)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    query = dict(pairs)
    return bool(
        parsed.scheme == "https" and parsed.hostname == "info.tpex.org.tw"
        and port in (None, 443) and not parsed.username and not parsed.password
        and parsed.path == "/api/stkInfo" and not parsed.fragment
        and len(query) == len(pairs) and set(query) == {"query", "lang"}
        and re.fullmatch(r"[1-9]\d{3,5}", query.get("query", "")) is not None
        and query.get("lang") == "en-us"
    )


def _headers(raw):
    status, headers = None, {}
    for line in raw.replace(b"\r\n", b"\n").splitlines(keepends=True):
        if not line.endswith(b"\n"):
            continue
        if line.startswith(b"HTTP/"):
            match = re.match(rb"HTTP/\S+ +([2-5]\d{2})(?: |$)", line)
            if match:
                status, headers = int(match[1]), {}
        elif status:
            key, sep, value = line.partition(b":")
            name = key.decode("ascii", "ignore").lower()
            if sep and name in {"content-type", "content-encoding", "retry-after"}:
                headers[name] = value.decode("latin-1").strip()
    return status, headers


class BoundedHistoryHttp:
    def __init__(self, deadline, *, provider=PROVIDER):
        self.deadline = deadline
        self.provider = provider
        self.http_request_count = 0
        self.request_observations = []

    def get(self, url, *, params=None, **kwargs):
        return self._request("GET", url, params=params)

    def post(self, url, *, data=None, json=None, **kwargs):
        return self._request("POST", url, data=data, payload=json)

    def _request(self, method, url, *, params=None, data=None, payload=None):
        from .twse_announcement_progress import request_fingerprint, _detail_url
        start, count = time.monotonic(), self.http_request_count
        target = url + ("?" + urlencode(params) if params else "")
        known = url in {IIH_URL, IIH_EN_URL, EZ_URL, JSON_URL, TDR_DETAIL_URL, ORDINARY_DETAIL_URL, TDR_MASTER_URL}
        safe_url = (url if known or _tpex_infohub_api_url(url) else target if (_detail_url(url) or _mops_english_announcement_url(url) or _mops_conference_notice_url(target)
                    or _mops_conference_month_url(target) or TDR_PDF.fullmatch(url))
                    and len(target) <= 2048 else None)
        observation = {"url": safe_url, "method": method,
                       "request_fingerprint": request_fingerprint(method, url, params=params, data=data, payload=payload),
                       "status": "error", "error_kind": None, "http_status": None,
                       "http_status_observed": False, "response_complete": False,
                       "response_bytes": 0, "response_sha256": None}
        try:
            response = self._request_native(method, url, params=params, data=data, payload=payload,
                                            observation=observation)
            observation["status"] = "success"
            return response
        except Exception as exc:
            observation["error_kind"] = getattr(exc, "error_kind", type(exc).__name__)
            raise
        finally:
            observation.update(http_request_count=self.http_request_count-count,
                               http_request_sent=self.http_request_count > count,
                               elapsed_seconds=max(0., time.monotonic()-start),
                               remaining_seconds=max(0., self.deadline-time.monotonic()))
            self.request_observations.append(observation)

    def _request_native(self, method, url, *, params=None, data=None, payload=None, observation):
        parsed = urlsplit(url)
        detail = (method == "GET" and parsed.scheme == "https" and parsed.netloc == "mopsov.twse.com.tw"
                  and parsed.path == "/mops/web/ajax_t05sr01_1" and not parsed.fragment)
        english_detail = method == "GET" and _mops_english_announcement_url(url)
        conference_notice = method == "GET" and _mops_conference_notice_url(url)
        conference_month = method == "GET" and _mops_conference_month_url(url)
        tpex_infohub = method == "POST" and _tpex_infohub_api_url(url) and data in (None, {}) and payload is None
        tdr_detail = (method == "POST" and url == TDR_DETAIL_URL and isinstance(payload, dict)
                      and set(payload) == {"marketKind", "companyId", "serialNumber", "enterDate"}
                      and payload.get("marketKind") == "sii" and payload.get("companyId") == "9103"
                      and isinstance(payload.get("serialNumber"), str)
                      and re.fullmatch(r"[1-9]\d?", payload["serialNumber"]) is not None
                      and isinstance(payload.get("enterDate"), str)
                      and re.fullmatch(r"\d{7}", payload["enterDate"]) is not None)
        tdr_pdf = method == "GET" and TDR_PDF.fullmatch(url) is not None and params is None
        ordinary_detail = (method == "POST" and url == ORDINARY_DETAIL_URL and isinstance(payload, dict)
                           and set(payload) == {"marketKind", "companyId", "serialNumber", "enterDate"}
                           and payload.get("marketKind") == "sii" and isinstance(payload.get("companyId"), str)
                           and payload["companyId"] in ORDINARY_DETAIL_CODES
                           and isinstance(payload.get("serialNumber"), str)
                           and re.fullmatch(r"[1-9]\d{0,5}", payload["serialNumber"]) is not None
                           and isinstance(payload.get("enterDate"), str)
                           and re.fullmatch(r"\d{7}", payload["enterDate"]) is not None)
        tdr_master = method == "GET" and url == TDR_MASTER_URL and params is None
        if not (method == "GET" and url in {IIH_URL, IIH_EN_URL} or method == "POST" and url in {EZ_URL, JSON_URL} or detail or english_detail or conference_notice or conference_month or tpex_infohub or tdr_detail or ordinary_detail or tdr_pdf or tdr_master):
            raise SourceResponseError("transport_url_invalid")
        if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
            raise SourceResponseError("test_network_disabled")
        if proxy_url_for_request(url, self.provider) or any(os.getenv(name) for name in PROXY_ENV):
            raise SourceResponseError("proxy_configuration_unsupported")
        key = scope_key(self.provider, endpoint=parsed.hostname)
        if cooldown_state(key):
            raise SourceResponseError("cooldown")
        remaining = min(4., self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError("timeout")
        end = min(self.deadline, time.monotonic() + remaining)
        limit = 2_500_000 if tdr_master else 2_000_000 if url == EZ_URL else 1_000_000 if tdr_pdf else 256_000
        target = url + ("?" + urlencode(params) if params else "")
        # A detail connection may use its existing request budget. The total
        # four-second cap and shared source deadline still bound the child.
        connect_budget = remaining if detail or english_detail else min(2., remaining)
        argv = ["/usr/bin/curl", "--disable", "--silent", "--max-time", str(remaining),
                "--connect-timeout", str(connect_budget), "--max-filesize", str(limit),
                "--proto", "=https", "--max-redirs", "0", "--retry", "0",
                "--dump-header", "/dev/fd/{HEADER_FD}", "--write-out", "%{stderr}%{json}"]
        if method == "POST":
            body = json.dumps(payload, ensure_ascii=False) if payload is not None else urlencode(data or {})
            content_type = "application/json" if payload is not None else "application/x-www-form-urlencoded"
            referer = ("https://info.tpex.org.tw/IIH/en/company.html?stkNo=" +
                       parse_qs(parsed.query).get("query", [""])[0] if tpex_infohub else
                       "https://mops.twse.com.tw/mops/")
            argv += ["--request", "POST", "--header", "Content-Type: " + content_type,
                     "--header", "Referer: " + referer, "--data-raw", body]
        argv.append(target)
        # This public frontend API works with our existing ordinary httpx
        # client. Choose the client by endpoint, never retry a refusal with a
        # different identity. The same capped pipes/deadline own its child.
        if url in {JSON_URL, TDR_DETAIL_URL, ORDINARY_DETAIL_URL}:
            argv = [sys.executable, str(Path(__file__).with_name("mops_monthly_http_child.py")),
                    url, json.dumps(payload, ensure_ascii=False), "{HEADER_FD}", str(remaining)]
        parts, rc, error = collect_capped_process(argv, end, body_limit=limit, headers=True)
        self.http_request_count += int(bool(parts.get("process_started")))
        status, headers = _headers(parts["headers"])
        try:
            meta = json.loads(parts["metadata"])
        except (ValueError, UnicodeDecodeError):
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        if status is None and type(meta.get("http_code")) is int and 200 <= meta["http_code"] <= 599:
            status = meta["http_code"]
        observation.update(http_status=status, http_status_observed=status is not None,
                           response_bytes=len(parts["body"]),
                           response_sha256=hashlib.sha256(parts["body"]).hexdigest())
        response = httpx.Response(status, headers=headers, content=parts["body"], request=httpx.Request(method, target)) if status else None
        if response is not None:
            observe_http_response(response)

        def fail(kind):
            exc = SourceResponseError(kind, status_code=status)
            if response is not None:
                exc.response = response
            if status in {401, 403, 429} or status and status >= 500:
                remember_failure(key, exc)
            raise exc

        if status is not None and status != 200:
            fail({401: "authentication", 403: "access_denied", 429: "rate_limited"}.get(
                status, "server_error" if status >= 500 else "http_error"))
        if error or rc:
            fail(error or (meta.get("error_kind") if meta.get("error_kind") in {"timeout", "transport_error"} else None)
                 or ("timeout" if rc == 28 else "response_too_large" if rc == 63 else "transport_error"))
        if (status != 200 or meta.get("http_code") != status or meta.get("url_effective") != target
                or meta.get("num_redirects") != 0):
            fail("transport_metadata_invalid")
        expected = ({"application/pdf"} if tdr_pdf else
                    {"text/html", "application/xhtml+xml"} if detail or english_detail or conference_notice or conference_month else
                    {"application/json", "text/json"})
        # Legacy EZSearch serves JSON under text/html; never admit HTML challenges.
        if url == EZ_URL and headers.get("content-type", "").split(";")[0].strip().lower() == "text/html":
            try:
                decoded = json.loads(parts["body"].decode("utf-8-sig"))
                if not isinstance(decoded, dict):
                    raise ValueError("invalid search envelope")
            except (ValueError, UnicodeDecodeError):
                fail("unexpected_content_type")
            expected.add("text/html")
        if headers.get("content-type", "").split(";")[0].strip().lower() not in expected:
            fail("unexpected_content_type")
        if headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
            fail("unsupported_content_encoding")
        if time.monotonic() >= self.deadline:
            fail("timeout")
        observation["response_complete"] = True
        native_epoch = time.time()
        if parts.get("process_started") is True:
            observation["response_retrieved_at_epoch"] = native_epoch
        # This evidence is attached only after the actual bounded child completed
        # and all status/URL/MIME/no-redirect checks passed. Arbitrary injected
        # httpx responses cannot seed resumable progress.
        if (detail or english_detail) and parts.get("process_started") is True:
            response.extensions["announcement_native_response"] = {
                "method":method, "url":target, "retrieved_at":native_epoch, "complete":True,
                "http_status_observed":True, "response_sha256":observation["response_sha256"]}
        if url in {IIH_URL, IIH_EN_URL, EZ_URL, JSON_URL} and parts.get("process_started") is True:
            response.extensions["announcement_index_native_response"] = {
                "method":method, "url":target, "retrieved_at":native_epoch, "complete":True,
                "http_status_observed":True, "response_sha256":observation["response_sha256"],
                "request_fingerprint":observation["request_fingerprint"]}
        return response
