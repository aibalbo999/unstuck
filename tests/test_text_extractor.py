from __future__ import annotations

import requests
from urllib.parse import urlsplit

import text_extractor


class Response:
    def __init__(
        self,
        *,
        content: bytes = b"<html>article</html>",
        url: str = "https://news.example/a",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        peer_ip: str = "93.184.216.34",
    ) -> None:
        self.content = content
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self.closed = False
        self.raw = RawConnection(peer_ip)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def iter_content(self, chunk_size=8192):
        for index in range(0, len(self.content), chunk_size):
            yield self.content[index:index + chunk_size]

    def close(self):
        self.closed = True


class RawConnection:
    def __init__(self, peer_ip: str) -> None:
        self._connection = Connection(peer_ip)


class Connection:
    def __init__(self, peer_ip: str) -> None:
        self.sock = Socket(peer_ip)


class Socket:
    def __init__(self, peer_ip: str) -> None:
        self.peer_ip = peer_ip

    def getpeername(self):
        return (self.peer_ip, 443)


def test_extract_article_text_returns_clean_bounded_text(monkeypatch):
    monkeypatch.setattr(text_extractor, "_resolve_public_host", lambda *_args: True)
    monkeypatch.setattr(text_extractor.requests, "get", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(
        text_extractor.trafilatura,
        "extract",
        lambda *_args, **_kwargs: "正文  \n\n內容",
    )

    assert text_extractor.extract_article_text("https://news.example/a", max_chars=4) == "正文 內"


def test_extract_article_text_passes_safe_download_options(monkeypatch):
    captured = {}
    monkeypatch.setattr(text_extractor, "_resolve_public_host", lambda *_args: True)
    monkeypatch.setattr(text_extractor.trafilatura, "extract", lambda *_args, **_kwargs: "body")

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(text_extractor.requests, "get", fake_get)

    assert text_extractor.extract_article_text("https://news.example/a") == "body"
    assert captured["url"] == "https://news.example/a"
    assert captured["timeout"] == text_extractor.REQUEST_TIMEOUT_SECONDS
    assert captured["allow_redirects"] is False
    assert captured["stream"] is True
    assert "Mozilla" in captured["headers"]["User-Agent"]


def test_extract_article_text_rejects_unsafe_urls():
    for url in [
        "file:///etc/passwd",
        "ftp://news.example/a",
        "http://localhost/a",
        "http://127.0.0.1/a",
        "http://[::1]/a",
        "http://10.0.0.1/a",
        "http://172.16.0.1/a",
        "http://192.168.0.1/a",
        "https://news.example:bad/a",
        "https://news.example:99999/a",
        "https://news.example:0/a",
    ]:
        assert text_extractor.extract_article_text(url) is None


def test_extract_article_text_invalid_port_does_not_touch_network(monkeypatch):
    called = False

    def fake_get(*_args, **_kwargs):
        nonlocal called
        called = True
        return Response()

    monkeypatch.setattr(text_extractor.requests, "get", fake_get)

    assert text_extractor.extract_article_text("https://news.example:99999/a") is None
    assert called is False


def test_extract_article_text_rejects_private_dns_resolution(monkeypatch):
    monkeypatch.setattr(text_extractor, "_resolve_public_host", lambda *_args: False)

    assert text_extractor.extract_article_text("https://news.example/a") is None


def test_extract_article_text_rejects_private_request_peer(monkeypatch):
    monkeypatch.setattr(text_extractor, "_resolve_public_host", lambda *_args: True)
    response = Response(peer_ip="127.0.0.1")
    monkeypatch.setattr(text_extractor.requests, "get", lambda *_args, **_kwargs: response)

    assert text_extractor.extract_article_text("https://news.example/a") is None
    assert response.closed is True


def test_extract_article_text_pins_validated_dns_during_request(monkeypatch):
    public_info = [(
        text_extractor.socket.AF_INET,
        text_extractor.socket.SOCK_STREAM,
        0,
        "",
        ("93.184.216.34", 0),
    )]
    private_info = [(
        text_extractor.socket.AF_INET,
        text_extractor.socket.SOCK_STREAM,
        0,
        "",
        ("127.0.0.1", 443),
    )]
    calls = []

    def fake_getaddrinfo(host, port, *args, **kwargs):
        calls.append(host)
        return public_info if len(calls) == 1 else private_info

    def fake_get(url, **_kwargs):
        host = urlsplit(url).hostname
        resolved = text_extractor.socket.getaddrinfo(host, 443, type=text_extractor.socket.SOCK_STREAM)
        assert resolved[0][4] == ("93.184.216.34", 443)
        return Response(peer_ip="93.184.216.34")

    monkeypatch.setattr(text_extractor.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(text_extractor.requests, "get", fake_get)
    monkeypatch.setattr(text_extractor.trafilatura, "extract", lambda *_args, **_kwargs: "body")

    assert text_extractor.extract_article_text("https://news.example/a") == "body"


def test_extract_article_text_rejects_redirect_to_private_host_before_request(monkeypatch):
    monkeypatch.setattr(text_extractor, "_resolve_public_host", lambda *_args: True)
    requested = []

    def fake_get(url, **_kwargs):
        requested.append(url)
        return Response(
            url=url,
            status_code=302,
            headers={"Location": "http://127.0.0.1/admin"},
        )

    monkeypatch.setattr(text_extractor.requests, "get", fake_get)

    assert text_extractor.extract_article_text("https://news.example/a") is None
    assert requested == ["https://news.example/a"]


def test_extract_article_text_handles_timeout_http_and_empty_extraction(monkeypatch):
    monkeypatch.setattr(text_extractor, "_resolve_public_host", lambda *_args: True)

    def timeout(*_args, **_kwargs):
        raise requests.Timeout("private body")

    monkeypatch.setattr(text_extractor.requests, "get", timeout)
    assert text_extractor.extract_article_text("https://news.example/a") is None

    monkeypatch.setattr(
        text_extractor.requests,
        "get",
        lambda *_args, **_kwargs: Response(status_code=403),
    )
    assert text_extractor.extract_article_text("https://news.example/a") is None

    monkeypatch.setattr(text_extractor.requests, "get", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(text_extractor.trafilatura, "extract", lambda *_args, **_kwargs: "   ")
    assert text_extractor.extract_article_text("https://news.example/a") is None


def test_extract_article_text_limits_download_bytes(monkeypatch):
    monkeypatch.setattr(text_extractor, "_resolve_public_host", lambda *_args: True)
    monkeypatch.setattr(
        text_extractor.requests,
        "get",
        lambda *_args, **_kwargs: Response(content=b"a" * (text_extractor.MAX_RESPONSE_BYTES + 1)),
    )

    assert text_extractor.extract_article_text("https://news.example/a") is None


def test_extract_article_text_stops_streaming_after_byte_limit(monkeypatch):
    monkeypatch.setattr(text_extractor, "_resolve_public_host", lambda *_args: True)
    chunks_read = []

    class StreamingResponse(Response):
        def iter_content(self, chunk_size=8192):
            for chunk in [b"a" * text_extractor.MAX_RESPONSE_BYTES, b"b", b"c"]:
                chunks_read.append(chunk)
                yield chunk

    response = StreamingResponse()
    monkeypatch.setattr(text_extractor.requests, "get", lambda *_args, **_kwargs: response)

    assert text_extractor.extract_article_text("https://news.example/a") is None
    assert len(chunks_read) == 2
    assert response.closed is True


def test_extract_article_text_handles_streaming_timeout(monkeypatch):
    monkeypatch.setattr(text_extractor, "_resolve_public_host", lambda *_args: True)

    class StreamingResponse(Response):
        def iter_content(self, chunk_size=8192):
            yield b"partial"
            raise requests.Timeout("private body")

    monkeypatch.setattr(text_extractor.requests, "get", lambda *_args, **_kwargs: StreamingResponse())

    assert text_extractor.extract_article_text("https://news.example/a") is None
