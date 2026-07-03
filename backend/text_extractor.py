"""Safe article text extraction for external news pages."""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura


LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT_SECONDS = 8.0
MAX_RESPONSE_BYTES = 1_000_000
MAX_REDIRECTS = 5
DEFAULT_MAX_CHARS = 8_000
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


@dataclass(frozen=True)
class SafeUrl:
    url: str
    host: str
    port: int
    addr_infos: tuple[Any, ...] | None


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


def _response_peer_is_public(response: Any) -> bool:
    peer = _response_peer_ip(response)
    if not peer:
        _warn("peer")
        return False
    return _host_is_public(str(peer))


def _response_peer_ip(response: Any) -> str | None:
    try:
        return str(response.raw._connection.sock.getpeername()[0])
    except (AttributeError, IndexError, TypeError, OSError):
        pass
    try:
        stream = getattr(response, "extensions", {}).get("network_stream")
        get_extra_info = getattr(stream, "get_extra_info", None)
        sock = get_extra_info("socket") if callable(get_extra_info) else None
        return str(sock.getpeername()[0]) if sock is not None else None
    except (AttributeError, IndexError, TypeError, OSError):
        return None


def _close_response(response: Any) -> None:
    close = getattr(response, "close", None)
    if callable(close):
        close()
    client = getattr(response, "_stock_agent_httpx_client", None)
    client_close = getattr(client, "close", None)
    if callable(client_close):
        client_close()


def _is_redirect(response: Any) -> bool:
    return int(getattr(response, "status_code", 0) or 0) in {301, 302, 303, 307, 308}


def _redirect_url(current_url: str, response: Any) -> str:
    location = getattr(response, "headers", {}).get("Location", "")
    return urljoin(current_url, location)


def _request_with_pinned_dns(safe_url: SafeUrl) -> httpx.Response:
    with _pinned_getaddrinfo(safe_url):
        client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
        try:
            request = client.build_request("GET", safe_url.url)
            response = client.send(request, stream=True)
        except Exception:
            client.close()
            raise
        setattr(response, "_stock_agent_httpx_client", client)
        return response


@contextmanager
def _pinned_getaddrinfo(safe_url: SafeUrl) -> Iterator[None]:
    if not safe_url.addr_infos:
        yield
        return
    original_getaddrinfo = socket.getaddrinfo

    def pinned(host, port, family=0, type=0, proto=0, flags=0):
        if str(host).strip().rstrip(".").lower() == safe_url.host:
            return [_with_sockaddr_port(info, int(port or safe_url.port)) for info in safe_url.addr_infos]
        return original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = pinned
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo


def _safe_public_url(url: Any) -> SafeUrl | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.strip().rstrip(".").lower()
    if host in {"localhost"} or not _host_is_public(host):
        return None
    try:
        explicit_port = parsed.port
    except ValueError:
        return None
    port = explicit_port or (443 if parsed.scheme.lower() == "https" else 80)
    if port <= 0:
        return None
    addr_infos = _resolve_public_host(host, port)
    if not addr_infos:
        return None
    return SafeUrl(raw, host, port, None if addr_infos is True else tuple(addr_infos))


def _with_sockaddr_port(info: Any, port: int) -> Any:
    family, socktype, proto, canonname, sockaddr = info
    if len(sockaddr) == 2:
        return family, socktype, proto, canonname, (sockaddr[0], port)
    if len(sockaddr) == 4:
        return family, socktype, proto, canonname, (sockaddr[0], port, sockaddr[2], sockaddr[3])
    return info


def _host_is_public(host: str) -> bool:
    try:
        return _ip_is_public(ipaddress.ip_address(host))
    except ValueError:
        return True


def _resolve_public_host(host: str, port: int) -> tuple[Any, ...] | bool | None:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        _warn("dns", exc)
        return None
    addresses = {item[4][0] for item in infos}
    if not addresses or not all(_host_is_public(address) for address in addresses):
        return None
    return tuple(infos)


def _ip_is_public(address: ipaddress._BaseAddress) -> bool:
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


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
