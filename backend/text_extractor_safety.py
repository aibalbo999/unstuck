"""Network safety helpers for article text extraction."""

from __future__ import annotations

import ipaddress
import logging
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator
from urllib.parse import urljoin, urlsplit

import httpx


LOGGER = logging.getLogger("text_extractor")
REQUEST_TIMEOUT_SECONDS = 8.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
Resolver = Callable[[str, int], tuple[Any, ...] | bool | None]


@dataclass(frozen=True)
class SafeUrl:
    url: str
    host: str
    port: int
    addr_infos: tuple[Any, ...] | None


def safe_public_url(url: Any, *, resolver: Resolver | None = None) -> SafeUrl | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.strip().rstrip(".").lower()
    if host in {"localhost"} or not host_is_public(host):
        return None
    try:
        explicit_port = parsed.port
    except ValueError:
        return None
    port = explicit_port or (443 if parsed.scheme.lower() == "https" else 80)
    if port <= 0:
        return None
    addr_infos = (resolver or resolve_public_host)(host, port)
    if not addr_infos:
        return None
    return SafeUrl(raw, host, port, None if addr_infos is True else tuple(addr_infos))


def request_with_pinned_dns(safe_url: SafeUrl) -> httpx.Response:
    with pinned_getaddrinfo(safe_url):
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
def pinned_getaddrinfo(safe_url: SafeUrl) -> Iterator[None]:
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


def response_peer_is_public(response: Any) -> bool:
    peer = _response_peer_ip(response)
    return bool(peer) and host_is_public(str(peer))


def close_response(response: Any) -> None:
    close = getattr(response, "close", None)
    if callable(close):
        close()
    client = getattr(response, "_stock_agent_httpx_client", None)
    client_close = getattr(client, "close", None)
    if callable(client_close):
        client_close()


def redirect_url(current_url: str, response: Any) -> str:
    location = getattr(response, "headers", {}).get("Location", "")
    return urljoin(current_url, location)


def host_is_public(host: str) -> bool:
    try:
        return _ip_is_public(ipaddress.ip_address(host))
    except ValueError:
        return True


def resolve_public_host(host: str, port: int) -> tuple[Any, ...] | bool | None:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        LOGGER.warning("Article text extraction %s failed [%s]", "dns", exc.__class__.__name__)
        return None
    addresses = {item[4][0] for item in infos}
    if not addresses or not all(host_is_public(address) for address in addresses):
        return None
    return tuple(infos)


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


def _with_sockaddr_port(info: Any, port: int) -> Any:
    family, socktype, proto, canonname, sockaddr = info
    if len(sockaddr) == 2:
        return family, socktype, proto, canonname, (sockaddr[0], port)
    if len(sockaddr) == 4:
        return family, socktype, proto, canonname, (sockaddr[0], port, sockaddr[2], sockaddr[3])
    return info


def _ip_is_public(address: ipaddress._BaseAddress) -> bool:
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
