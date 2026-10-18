"""Anonymous, capped single-day FinMind news requests with original-byte cache."""
from __future__ import annotations

import base64
from datetime import date
from hashlib import sha256
import json
import math
import os
import re
import time
from urllib.parse import urlencode

import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response, read_response
from provider_resilience import call_provider_with_resilience
from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                     remember_failure, scope_key)
from shared_provider_cache import shared_fetch
from .construction_cohort_transport import _headers

PROVIDER = "FinMind news"
ENDPOINT = "https://api.finmindtrade.com/api/v4/data"
MAX_BYTES = 700_000
PROXY_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def news_url(stock_id, day):
    if not isinstance(stock_id, str) or not re.fullmatch(r"[0-9]{4,6}", stock_id):
        raise SourceResponseError("invalid_stock_id")
    try:
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError:
        raise SourceResponseError("invalid_query_date") from None
    return ENDPOINT + "?" + urlencode({"dataset": "TaiwanStockNews", "data_id": stock_id, "start_date": day})


def decode_payload(raw):
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise SourceResponseError("parse_error") from None
    if not isinstance(payload, dict) or type(payload.get("status")) is not int:
        raise SourceResponseError("parse_error")
    if payload["status"] != 200:
        status = payload["status"]
        raise SourceResponseError({401: "authentication", 403: "access_denied", 429: "rate_limited"}.get(
            status, "provider_error"), status_code=status)
    if not isinstance(payload.get("data"), list) or len(payload["data"]) > 2000:
        raise SourceResponseError("parse_error")
    return payload["data"]


def _failure_key(url):
    return "finmind-news-daily-failure:v1:" + sha256(url.encode()).hexdigest()


def _save_failure(url, diagnostic):
    from cache_store import set_cache_json
    value = {key: diagnostic[key] for key in ("error_kind", "http_status", "api_status", "retry_after_epoch", "raw_http_receipt")
             if key in diagnostic}
    value.update(url=url, failed_at_epoch=time.time())
    try:
        set_cache_json(_failure_key(url), value, ttl_seconds=86400)
    except Exception:
        pass


def _cached_failure(url):
    from cache_store import get_cache_json
    try:
        value = get_cache_json(_failure_key(url))
        if (isinstance(value, dict) and value.get("url") == url
                and type(value.get("failed_at_epoch")) in (int, float)
                and math.isfinite(value["failed_at_epoch"])
                and 0 <= time.time() - value["failed_at_epoch"] <= 120):
            return {key: value[key] for key in ("error_kind", "http_status", "api_status", "retry_after_epoch", "raw_http_receipt")
                    if key in value}
    except Exception:
        pass
    return {}


class FinMindNewsHttp:
    def __init__(self, deadline):
        self.deadline = deadline
        self.components = []
        self.http_request_count = 0

    def _download(self, url, diagnostic):
        if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
            raise SourceResponseError("test_network_disabled")
        if proxy_url_for_request(url, PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):
            raise SourceResponseError("proxy_configuration_unsupported")
        key = scope_key(PROVIDER, endpoint=ENDPOINT)
        if cooldown_state(key):
            raise SourceResponseError("cooldown")
        remaining = min(3., self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError("timeout")
        argv = ["/usr/bin/curl", "--disable", "--silent", "--max-time", str(remaining),
                "--connect-timeout", str(min(2., remaining)), "--max-filesize", str(MAX_BYTES),
                "--proto", "=https", "--max-redirs", "0", "--retry", "0",
                "--dump-header", "/dev/fd/{HEADER_FD}", "--write-out", "%{stderr}%{json}", url]
        parts, rc, error = collect_capped_process(argv, min(self.deadline, time.monotonic() + remaining),
                                                 body_limit=MAX_BYTES, headers=True)
        diagnostic["http_request_sent"] = bool(parts.get("process_started"))
        self.http_request_count += int(diagnostic["http_request_sent"])
        status, headers = _headers(parts["headers"])
        try:
            meta = json.loads(parts["metadata"])
        except (ValueError, UnicodeError):
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        if status is None and type(meta.get("http_code")) is int and 200 <= meta["http_code"] <= 599:
            status = meta["http_code"]
        diagnostic["http_status"] = status
        response = httpx.Response(status, headers=headers, request=httpx.Request("GET", url)) if status else None
        if response is not None:
            observe_http_response(response)
        if rc == 0 and not error and parts["body"]:
            diagnostic["raw_http_receipt"] = archive_response(
                parts["body"], source_url=url, retrieved_at=time.time(), http_status=status)

        def fail(kind, code=status):
            diagnostic["error_kind"] = kind
            exc = SourceResponseError(kind, status_code=code)
            if response is not None:
                exc.response = response
            state = remember_failure(key, exc)
            diagnostic["retry_after_epoch"] = state["retry_at"]
            _save_failure(url, diagnostic)
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
        if headers.get("content-type", "").split(";")[0].strip().lower() not in {"application/json", "text/json"}:
            fail("unexpected_content_type")
        if diagnostic.get("raw_http_receipt", {}).get("status") != "archived":
            fail("raw_archive_failed")
        try:
            rows = decode_payload(parts["body"])
        except SourceResponseError as exc:
            diagnostic["api_status"] = exc.status_code
            fail(exc.error_kind, exc.status_code)
        if time.monotonic() >= self.deadline:
            fail("timeout")
        return {"url": url, "body_b64": base64.b64encode(parts["body"]).decode("ascii"),
                "sha256": sha256(parts["body"]).hexdigest(), "raw_http_receipt": diagnostic["raw_http_receipt"],
                "empty": not rows}

    def get(self, stock_id, day):
        url = news_url(stock_id, day)
        diagnostic = {"url": url, "query_date": day, "http_request_sent": False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError("timeout")

        def download():
            try:
                return self._download(url, diagnostic)
            except SourceResponseError as exc:
                diagnostic["error_kind"] = exc.error_kind
                raise
            except Exception:
                diagnostic["error_kind"] = "transport_error"
                raise SourceResponseError("transport_error") from None

        value, meta = shared_fetch(
            "finmind-news-daily-raw:v1:" + url,
            lambda: call_provider_with_resilience(PROVIDER, download, (), {}),
            freshness_seconds=1800, retention_seconds=1800, error_retry_seconds=120,
            result_ttl=lambda value: 300 if value.get("empty") else 1800, lock_wait_seconds=1,
        )
        diagnostic.update(cache_hit=bool(meta.get("cache_hit")), fetched_at_epoch=meta.get("fetched_at_epoch"),
                          cooldown=bool(meta.get("cooldown")))
        if meta.get("error_kind") or meta.get("stale"):
            if not diagnostic.get("error_kind"):
                diagnostic.update(_cached_failure(url))
            diagnostic["error_kind"] = diagnostic.get("error_kind") or meta.get("error_kind") or "stale_receipt"
            raise SourceResponseError(diagnostic["error_kind"], status_code=diagnostic.get("http_status"))
        stamp = meta.get("fetched_at_epoch")
        try:
            valid_stamp = type(stamp) in (int, float) and math.isfinite(stamp) and 0 <= time.time() - stamp <= 1800
        except (ValueError, OverflowError):
            valid_stamp = False
        if not valid_stamp or not isinstance(value, dict) or value.get("url") != url:
            raise SourceResponseError("cache_receipt_invalid")
        try:
            encoded = value["body_b64"]
            if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
                raise ValueError
            raw = base64.b64decode(encoded, validate=True)
            receipt = value["raw_http_receipt"]
            if not isinstance(receipt, dict):
                raise ValueError
            if (not 0 < len(raw) <= MAX_BYTES or sha256(raw).hexdigest() != value.get("sha256")
                    or receipt.get("status") != "archived" or receipt.get("evidence_kind") != "raw_http_response_bytes"
                    or type(receipt.get("raw_response_bytes")) is not int or receipt["raw_response_bytes"] != len(raw)
                    or receipt.get("source_url") != url or receipt.get("http_status") != 200
                    or type(receipt.get("retrieved_at")) not in (int, float)
                    or not math.isfinite(receipt["retrieved_at"])
                    or not 0 <= stamp - receipt["retrieved_at"] <= 10 or read_response(receipt) != raw):
                raise ValueError
        except (ValueError, KeyError, TypeError, OSError, EOFError, OverflowError):
            raise SourceResponseError("cache_receipt_invalid") from None
        diagnostic["raw_http_receipt"] = receipt
        diagnostic["http_status"] = 200
        diagnostic["fetched_at_epoch"] = receipt["retrieved_at"]
        if time.monotonic() >= self.deadline:
            raise SourceResponseError("timeout")
        return raw, receipt
