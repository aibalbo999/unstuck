"""Capped ordinary HTTPS and original-byte cache for two public issuer sites."""
from __future__ import annotations

import base64
from hashlib import sha256
import json
import math
import os
import re
import time
from urllib.parse import urlsplit

import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                     remember_failure, scope_key)
from shared_provider_cache import shared_fetch
from .construction_cohort_transport import _headers

PROVIDER = "Verified issuer news"
ROSTER_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
SANYANG_INDEX = "https://www.sanyang.com.tw/newslist"
SINBON_INDEX = "https://www.sinbon.com/api/news/items"
TCC_INDEX = "https://www.tccgroupholdings.com/news"
VENTEC_INDEX = "https://www.ventec-group.com/cht/news/"
PROXY_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def url_contract(url):
    if url == ROSTER_URL:
        return 2_500_000, {"application/json", "text/json"}
    if url == SANYANG_INDEX or re.fullmatch(r"https://www\.sanyang\.com\.tw/busnessnews-page[1-9]\d{0,7}", url):
        return 150_000, {"text/html", "application/xhtml+xml"}
    if url == SINBON_INDEX or re.fullmatch(r"https://www\.sinbon\.com/api/news/detail/[a-z0-9]+(?:-[a-z0-9]+){0,80}", url):
        return 1_000_000, {"application/json", "text/json"}
    if url == TCC_INDEX or re.fullmatch(r"https://www\.tccgroupholdings\.com/news/[A-Za-z0-9_-]{1,80}", url):
        return 600_000, {"text/html", "application/xhtml+xml"}
    from .realtek_issuer_news import INDEX as REALTEK_INDEX, ARTICLE as REALTEK_ARTICLE
    if url == REALTEK_INDEX:
        return 400_000, {"text/html", "application/xhtml+xml"}
    if REALTEK_ARTICLE.fullmatch(url):
        return 150_000, {"text/html", "application/xhtml+xml"}
    from .ventec_issuer_news import ARTICLE
    if url == VENTEC_INDEX or ARTICLE.fullmatch(url):
        return 150_000, {"text/html", "application/xhtml+xml"}
    raise SourceResponseError("transport_url_invalid")


def _newer_native_receipt(own, url, shared_stamp, limit):
    """Priority requires a usable full receipt, never its timestamp alone."""
    try:
        if not isinstance(own, dict) or own.get("error_kind"):
            return False
        stamp, until = own.get("fetched_at_epoch"), own.get("fresh_until_epoch")
        if (type(stamp) not in (int, float) or type(until) not in (int, float)
                or not math.isfinite(stamp) or not math.isfinite(until)
                or not 0 <= time.time() - stamp <= 1800 or not stamp > shared_stamp
                or not until > time.time() or not 0 < until - stamp <= 1801):
            return False
        value = own.get("value")
        if not isinstance(value, dict) or value.get("url") != url:
            return False
        encoded = value.get("body_b64")
        if not isinstance(encoded, str) or len(encoded) > (limit + 2) // 3 * 4:
            return False
        raw = base64.b64decode(encoded, validate=True)
        return 0 < len(raw) <= limit and sha256(raw).hexdigest() == value.get("sha256")
    except (ValueError, TypeError, OverflowError):
        return False


class IssuerNewsHttp:
    route_contract = staticmethod(url_contract)

    def request_timeout_seconds(self, url):
        return 5.

    def connect_timeout_seconds(self, url):
        return 2.

    def __init__(self, deadline):
        self.deadline = deadline
        self.http_request_count = 0
        self.components = []

    def _download(self, url, diagnostic):
        limit, expected_types = self.route_contract(url)
        if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
            raise SourceResponseError("test_network_disabled")
        if proxy_url_for_request(url, PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):
            raise SourceResponseError("proxy_configuration_unsupported")
        key = scope_key(PROVIDER, endpoint=urlsplit(url).hostname)
        if cooldown_state(key):
            raise SourceResponseError("cooldown")
        remaining = min(self.request_timeout_seconds(url), self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError("timeout")
        argv = ["/usr/bin/curl", "--disable", "--silent", "--max-time", str(remaining),
                "--connect-timeout", str(min(self.connect_timeout_seconds(url), remaining)), "--max-filesize", str(limit),
                "--proto", "=https", "--max-redirs", "0", "--retry", "0",
                "--dump-header", "/dev/fd/{HEADER_FD}", "--write-out", "%{stderr}%{json}", url]
        parts, rc, error = collect_capped_process(argv, min(self.deadline, time.monotonic() + remaining),
                                                 body_limit=limit, headers=True)
        diagnostic["http_request_sent"] = bool(parts.get("process_started"))
        self.http_request_count += int(diagnostic["http_request_sent"])
        status, headers = _headers(parts["headers"])
        try:
            meta = json.loads(parts["metadata"])
        except (ValueError, UnicodeDecodeError):
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        if status is None and type(meta.get("http_code")) is int and 200 <= meta["http_code"] <= 599:
            status = meta["http_code"]
        response = httpx.Response(status, headers=headers, request=httpx.Request("GET", url)) if status else None
        if response is not None:
            observe_http_response(response)

        def fail(kind):
            diagnostic["error_kind"] = kind
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
            fail(error or ("timeout" if rc == 28 else "response_too_large" if rc == 63 else "transport_error"))
        if (status != 200 or meta.get("http_code") != status or meta.get("url_effective") != url
                or meta.get("num_redirects") != 0):
            fail("transport_metadata_invalid")
        if headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
            fail("unsupported_content_encoding")
        if headers.get("content-type", "").split(";")[0].strip().lower() not in expected_types:
            fail("unexpected_content_type")
        if time.monotonic() >= self.deadline:
            fail("timeout")
        return {"url": url, "body_b64": base64.b64encode(parts["body"]).decode("ascii"),
                "sha256": sha256(parts["body"]).hexdigest()}

    def get(self, url):
        limit, _ = self.route_contract(url)
        diagnostic = {"url": url, "http_request_sent": False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError("timeout")
        if url == ROSTER_URL:
            from cache_store import get_cache_json
            from .official_company_legal_name import read_cached_listed_roster_bytes
            shared = read_cached_listed_roster_bytes()
            if shared is not None:
                # Prefer a newer, fresh native response when present. Its bytes
                # still pass the existing shared-fetch/hash validation below.
                try:
                    key = "shared_provider:v1:" + sha256(("issuer-news-raw:v1:" + url).encode()).hexdigest()
                    own = get_cache_json(key)
                    own_newer = _newer_native_receipt(own, url, shared[1]["fetched_at_epoch"], limit)
                except Exception:
                    own_newer = False
                if not own_newer:
                    if time.monotonic() >= self.deadline:
                        raise SourceResponseError("timeout")
                    raw, metadata = shared
                    diagnostic.update(metadata)
                    return raw
            if time.monotonic() >= self.deadline:
                raise SourceResponseError("timeout")
        value, meta = shared_fetch(
            "issuer-news-raw:v1:" + url, lambda: self._download(url, diagnostic),
            freshness_seconds=1800, retention_seconds=1800, error_retry_seconds=120,
            lock_wait_seconds=1,
        )
        diagnostic.update(cache_hit=bool(meta.get("cache_hit")), fetched_at_epoch=meta.get("fetched_at_epoch"))
        if meta.get("error_kind") or meta.get("stale"):
            raise SourceResponseError(diagnostic.get("error_kind") or meta.get("error_kind") or "stale_receipt")
        stamp = meta.get("fetched_at_epoch")
        try:
            valid_stamp = type(stamp) in (int, float) and math.isfinite(stamp) and 0 <= time.time() - stamp <= 1800
        except (ValueError, OverflowError):
            valid_stamp = False
        if not valid_stamp or not isinstance(value, dict) or value.get("url") != url:
            raise SourceResponseError("cache_receipt_invalid")
        encoded = value.get("body_b64")
        if not isinstance(encoded, str) or len(encoded) > (limit + 2) // 3 * 4:
            raise SourceResponseError("cache_receipt_invalid")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, UnicodeError) as exc:
            raise SourceResponseError("cache_receipt_invalid") from exc
        if not 0 < len(raw) <= limit or sha256(raw).hexdigest() != value.get("sha256"):
            raise SourceResponseError("cache_receipt_invalid")
        if time.monotonic() >= self.deadline:
            raise SourceResponseError("timeout")
        return raw
