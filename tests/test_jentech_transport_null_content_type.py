import json
import time


def test_published_pdf_redirect_accepts_absent_curl_content_type(monkeypatch):
    from data_fetch.market_sources import jentech_conference_transport as transport

    source_url = (
        "https://www.jentech.com.tw/zh/_files/ugd/"
        "4b19cc_9fdfa4603d2d4a07b8bb32722b7b976f.pdf"
    )
    location = transport.cdn_url(source_url)
    raw_headers = (
        b"HTTP/2 301\r\n"
        + f"Location: {location}\r\n".encode("ascii")
        + b"Content-Length: 0\r\n"
        + b"Cache-Control: public, max-age=0\r\n"
        + b"Age: 15\r\n\r\n"
    )
    curl_metadata = {
        "http_code": 301,
        "url_effective": source_url,
        "num_redirects": 0,
        "size_download": 0,
        "content_type": None,
        "method": "GET",
        "proxy_used": 0,
    }

    def fake_curl(_argv, _deadline, *, body_limit, headers):
        assert body_limit == 1
        return ({
            "body": b"",
            "headers": raw_headers,
            "metadata": json.dumps(curl_metadata).encode("utf-8"),
            "body_bytes_read": 0,
            "process_started": True,
        }, 0, None)

    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    for name in transport.PROXY_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(transport, "proxy_url_for_request", lambda *_args: None)
    monkeypatch.setattr(transport, "collect_capped_process", fake_curl)

    http = transport.JentechConferenceHttp(time.monotonic() + 10, force_refresh=True)
    http._authorized.add(source_url)
    monkeypatch.setattr(http, "_external_guards", lambda _url: None)
    diagnostic = {"url": source_url, "http_request_sent": False}

    response = http.download_original(source_url, diagnostic)

    assert diagnostic["http_status"] == 301
    assert diagnostic["http_request_sent"] is True
    assert diagnostic["response_bytes"] == 0
    assert response["response_metadata"]["content_type"] == ""
