"""Safe article text extraction for external news pages."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
import trafilatura

from text_extractor_safety import (
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    SafeUrl,
    close_response as _close_response,
    host_is_public as _host_is_public,
    redirect_url as _redirect_url,
    request_with_pinned_dns as _request_with_pinned_dns,
    resolve_public_host as _resolve_public_host,
    response_peer_is_public as _response_peer_is_public,
    safe_public_url as _safe_public_url_impl,
    socket,
)


LOGGER = logging.getLogger(__name__)
MAX_RESPONSE_BYTES = 1_000_000
MAX_REDIRECTS = 5
DEFAULT_MAX_CHARS = 8_000


def extract_article_text(url: str, max_chars: int = DEFAULT_MAX_CHARS) -> str | None:
    """Download a public article URL and return normalized extracted text."""
    safe_url = _safe_public_url(url)
    if safe_url is None:
        return None
    response = _get_public_response(safe_url)
    if response is None:
        return None
    content = _read_bounded_content(response)
    if content is None:
        return None

    try:
        extracted = trafilatura.extract(
            content.decode(_response_encoding(response), errors="replace"),
            include_comments=False,
            include_tables=False,
        )
    except Exception as exc:
        _warn("extract", exc)
        return None
    text = _normalize_text(extracted)
    if not text:
        return None
    return text[:_bounded_max_chars(max_chars)]


def _get_public_response(url: SafeUrl) -> httpx.Response | None:
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        try:
            response = _request_with_pinned_dns(current_url)
            if not _is_redirect(response):
                response.raise_for_status()
        except httpx.HTTPError as exc:
            response = locals().get("response")
            _close_response(response)
            _warn("download", exc)
            return None
        if not _response_peer_is_public(response):
            _close_response(response)
            _warn("peer")
            return None
        if not _is_redirect(response):
            return response
        next_url = _redirect_url(current_url.url, response)
        safe_next_url = _safe_public_url(next_url)
        if safe_next_url is None:
            _warn("redirect")
            _close_response(response)
            return None
        _close_response(response)
        current_url = safe_next_url
    _warn("redirect")
    return None


def _read_bounded_content(response: Any) -> bytes | None:
    total = 0
    chunks: list[bytes] = []
    try:
        streamer = getattr(response, "iter_content", None)
        if not callable(streamer):
            streamer = getattr(response, "iter_bytes")
        iterator = streamer(chunk_size=8192)
    except AttributeError:
        content = getattr(response, "content", b"")
        try:
            if not isinstance(content, bytes) or len(content) > MAX_RESPONSE_BYTES:
                _warn("response-size")
                return None
            return content
        finally:
            _close_response(response)
    try:
        for chunk in iterator:
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                _warn("response-size")
                return None
            chunks.append(chunk)
        return b"".join(chunks)
    except httpx.HTTPError as exc:
        _warn("stream", exc)
        return None
    finally:
        _close_response(response)


def _is_redirect(response: Any) -> bool:
    return int(getattr(response, "status_code", 0) or 0) in {301, 302, 303, 307, 308}


def _safe_public_url(url: Any) -> SafeUrl | None:
    return _safe_public_url_impl(url, resolver=_resolve_public_host)


def _response_encoding(response: Any) -> str:
    encoding = getattr(response, "encoding", None) or getattr(response, "apparent_encoding", None)
    return str(encoding or "utf-8")


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _bounded_max_chars(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MAX_CHARS
    return max(1, min(parsed, DEFAULT_MAX_CHARS))


def _warn(operation: str, exc: BaseException | None = None) -> None:
    kind = exc.__class__.__name__ if exc else "Blocked"
    LOGGER.warning("Article text extraction %s failed [%s]", operation, kind)
