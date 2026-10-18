"""Bounded, original-byte transport for official latest-quarter snapshots."""
from __future__ import annotations

import base64
from hashlib import sha256
import json
import math
import os
import time
from urllib.parse import urlsplit

import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response, read_response
from search_provider_runtime import (
    SourceResponseError, cooldown_state, observe_http_response, remember_failure, scope_key,
)
from shared_provider_cache import shared_fetch
from .construction_cohort_transport import _headers

PROVIDER = "TWSE/MOPS official latest-quarter financial statements"
MAX_BYTES = 1_500_000
OPENAPI_MAX_BYTES = 2_000_000
FRESH_SECONDS = 1800
OPENAPI_BASE_URL = "https://openapi.twse.com.tw/v1/opendata"
PROXY_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def allowed_urls():
    mops = {
        f"https://mopsfin.twse.com.tw/opendata/t187ap{statement}_{market}_{sector}.csv"
        for statement in ("06", "07")
        for market in ("L", "O")
        for sector in ("ci", "basi", "fh", "ins", "bd", "mim")
    }
    openapi = {
        f"{OPENAPI_BASE_URL}/t187ap{statement}_L_{sector}"
        for statement in ("06", "07")
        for sector in ("ci", "basi", "fh", "ins", "bd", "mim")
    }
    return mops | openapi


def url_contract(url):
    if url not in allowed_urls():
        raise SourceResponseError("transport_url_invalid")
    if url.startswith(OPENAPI_BASE_URL + "/"):
        return OPENAPI_MAX_BYTES, {"application/json"}
    return MAX_BYTES, {"text/csv", "application/csv", "application/vnd.ms-excel"}


class QuarterlyFinancialHttp:
    def __init__(self, deadline):
        self.deadline = deadline
        self.http_request_count = 0
        self.components = []

    def _download(self, url, diagnostic):
        limit, expected_types = url_contract(url)
        if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
            raise SourceResponseError("test_network_disabled")
        if proxy_url_for_request(url, PROVIDER) or any(os.getenv(key) for key in PROXY_ENV):
            raise SourceResponseError("proxy_configuration_unsupported")
        key = scope_key(PROVIDER, endpoint=urlsplit(url).hostname)
        if cooldown_state(key):
            raise SourceResponseError("cooldown")
        remaining = min(5.0, self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError("timeout")
        argv = ["/usr/bin/curl", "--disable", "--silent", "--max-time", str(remaining),
                "--connect-timeout", str(min(2.0, remaining)), "--max-filesize", str(limit),
                "--proto", "=https", "--max-redirs", "0", "--retry", "0",
                "--dump-header", "/dev/fd/{HEADER_FD}", "--write-out", "%{stderr}%{json}", url]
        parts, rc, error = collect_capped_process(
            argv, min(self.deadline, time.monotonic() + remaining), body_limit=limit, headers=True)
        diagnostic["http_request_sent"] = bool(parts.get("process_started"))
        self.http_request_count += int(diagnostic["http_request_sent"])
        status, headers = _headers(parts["headers"])
        try:
            metadata = json.loads(parts["metadata"])
        except (ValueError, UnicodeDecodeError):
            metadata = {}
        metadata = metadata if isinstance(metadata, dict) else {}
        if status is None and type(metadata.get("http_code")) is int and 200 <= metadata["http_code"] <= 599:
            status = metadata["http_code"]
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
        if (status != 200 or metadata.get("http_code") != status or metadata.get("url_effective") != url
                or metadata.get("num_redirects") != 0):
            fail("transport_metadata_invalid")
        if headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
            fail("unsupported_content_encoding")
        if headers.get("content-type", "").split(";")[0].strip().lower() not in expected_types:
            fail("unexpected_content_type")
        if time.monotonic() >= self.deadline:
            fail("timeout")
        raw = parts["body"]
        receipt = archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200, max_bytes=limit)
        diagnostic.update(http_status=200, original_receipt=receipt,
                          response_sha256=sha256(raw).hexdigest(), response_bytes=len(raw))
        if receipt.get("status") != "archived" or read_response(receipt, max_bytes=limit) != raw:
            fail("original_receipt_unverified")
        return {"url": url, "body_b64": base64.b64encode(raw).decode("ascii"),
                "sha256": sha256(raw).hexdigest(), "original_receipt": receipt}

    def get(self, url):
        limit, _ = url_contract(url)
        diagnostic = {"url": url, "http_request_sent": False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError("timeout")
        value, metadata = shared_fetch(
            "mops-quarterly-financial-raw:v1:" + url,
            lambda: self._download(url, diagnostic),
            freshness_seconds=FRESH_SECONDS, retention_seconds=FRESH_SECONDS,
            error_retry_seconds=120, lock_wait_seconds=1,
        )
        diagnostic.update(cache_hit=bool(metadata.get("cache_hit")),
                          fetched_at_epoch=metadata.get("fetched_at_epoch"))
        if metadata.get("error_kind") or metadata.get("stale"):
            raise SourceResponseError(diagnostic.get("error_kind") or metadata.get("error_kind") or "stale_receipt")
        try:
            stamp = metadata.get("fetched_at_epoch")
            receipt = value.get("original_receipt") if isinstance(value, dict) else None
            raw = base64.b64decode(value["body_b64"], validate=True)
            retrieved = receipt.get("retrieved_at")
            if (not isinstance(value, dict) or value.get("url") != url or len(raw) == 0 or len(raw) > limit
                    or sha256(raw).hexdigest() != value.get("sha256")
                    or type(stamp) not in (int, float) or not math.isfinite(stamp)
                    or not 0 <= time.time() - stamp < FRESH_SECONDS
                    or type(retrieved) not in (int, float) or not math.isfinite(retrieved)
                    or not 0 <= stamp - retrieved <= 10 or not 0 <= time.time() - retrieved < FRESH_SECONDS
                    or receipt.get("status") != "archived" or receipt.get("source_url") != url
                    or receipt.get("http_status") != 200 or receipt.get("finality_guaranteed") is not False
                    or receipt.get("historical_point_in_time_verified") is not False
                    or receipt.get("raw_response_sha256") != value["sha256"]
                    or receipt.get("raw_response_bytes") != len(raw)
                    or read_response(receipt, max_bytes=limit) != raw):
                raise ValueError("invalid quarterly financial response receipt")
        except (ValueError, KeyError, TypeError, OSError, EOFError, OverflowError):
            raise SourceResponseError("cache_receipt_invalid") from None
        diagnostic["original_receipt"] = receipt
        diagnostic.update(http_status=200, response_sha256=value["sha256"], response_bytes=len(raw))
        if time.monotonic() >= self.deadline:
            raise SourceResponseError("timeout")
        return raw, receipt
