def test_text_extractor_safety_facade_keeps_network_helpers_patchable(monkeypatch):
    import text_extractor
    import text_extractor_safety

    assert text_extractor._request_with_pinned_dns is text_extractor_safety.request_with_pinned_dns
    assert text_extractor._response_peer_is_public is text_extractor_safety.response_peer_is_public
    assert text_extractor.socket is text_extractor_safety.socket

    public_info = [(
        text_extractor_safety.socket.AF_INET,
        text_extractor_safety.socket.SOCK_STREAM,
        0,
        "",
        ("93.184.216.34", 0),
    )]
    monkeypatch.setattr(text_extractor_safety, "resolve_public_host", lambda *_args: public_info)

    safe_url = text_extractor_safety.safe_public_url("https://news.example/a")

    assert safe_url is not None
    assert safe_url.host == "news.example"
    assert safe_url.port == 443
    assert safe_url.addr_infos == tuple(public_info)


def test_text_extractor_safety_rejects_non_public_hosts_without_dns(monkeypatch):
    import text_extractor_safety

    called = False

    def fake_resolver(*_args):
        nonlocal called
        called = True
        return True

    monkeypatch.setattr(text_extractor_safety, "resolve_public_host", fake_resolver)

    assert text_extractor_safety.safe_public_url("http://127.0.0.1/private") is None
    assert text_extractor_safety.safe_public_url("file:///etc/passwd") is None
    assert called is False


def test_text_extractor_safety_logs_dns_resolution_failure(caplog, monkeypatch):
    import logging

    import text_extractor_safety

    def broken_getaddrinfo(*_args, **_kwargs):
        raise OSError("dns unavailable")

    monkeypatch.setattr(text_extractor_safety.socket, "getaddrinfo", broken_getaddrinfo)

    with caplog.at_level(logging.WARNING, logger="text_extractor"):
        assert text_extractor_safety.resolve_public_host("news.example", 443) is None

    assert "Article text extraction dns failed [OSError]" in caplog.text
