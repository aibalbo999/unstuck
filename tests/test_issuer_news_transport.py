import base64
import json
import time
from hashlib import sha256

import pytest

from search_provider_runtime import SourceResponseError


@pytest.fixture
def transport(monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as module
    monkeypatch.delenv("STOCK_AGENT_TEST_NO_NETWORK", raising=False)
    for name in module.PROXY_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(module, "proxy_url_for_request", lambda *a: None)
    monkeypatch.setattr(module, "cooldown_state", lambda *a: None)
    monkeypatch.setattr(module, "observe_http_response", lambda *a: None)
    return module


def parts(url, status=200, extra=b"", content_type="application/json", **meta):
    return {"body": b'{"public":true}', "process_started": True,
            "headers": f"HTTP/2 {status}\r\nContent-Type: {content_type}\r\n".encode() + extra + b"\r\n",
            "metadata": json.dumps({"http_code": status, "url_effective": url, "num_redirects": 0, **meta}).encode()}


def test_one_ordinary_tls_request_with_fixed_destination_and_total_deadline(transport, monkeypatch):
    calls = []
    def collect(argv, deadline, **kwargs):
        calls.append((argv, deadline, kwargs)); return parts(transport.SINBON_INDEX), 0, None
    monkeypatch.setattr(transport, "collect_capped_process", collect)
    start = time.monotonic(); http = transport.IssuerNewsHttp(start + 20)
    receipt = http._download(transport.SINBON_INDEX, {})
    argv, deadline, limits = calls[0]
    assert len(calls) == 1 and argv[-1] == transport.SINBON_INDEX
    assert 0 < deadline - start <= 5.1 and limits["body_limit"] == 1000000
    assert not any(x in argv for x in ("--insecure", "--location", "--user-agent"))
    assert argv[argv.index("--retry") + 1] == "0" and argv[argv.index("--proto") + 1] == "=https"
    assert base64.b64decode(receipt["body_b64"]) == b'{"public":true}' and http.http_request_count == 1


@pytest.mark.parametrize("url", ["http://www.sinbon.com/api/news/items", "https://www.sinbon.com.evil.test/api/news/items",
                              "https://www.sinbon.com/api/news/detail/a?token=x", "https://www.sinbon.com/api/news/detail/../private",
                              "https://www.sanyang.com.tw/login", "https://openapi.twse.com.tw/v1/private"])
def test_out_of_contract_routes_do_not_start_child(transport, monkeypatch, url):
    monkeypatch.setattr(transport, "collect_capped_process", lambda *a, **k: pytest.fail("unexpected child"))
    http = transport.IssuerNewsHttp(time.monotonic() + 1)
    with pytest.raises(SourceResponseError): http._download(url, {})
    assert http.http_request_count == 0


@pytest.mark.parametrize("status,kind", [(403, "access_denied"), (429, "rate_limited"), (503, "server_error"), (302, "http_error")])
def test_real_refusal_keeps_priority_retry_after_and_cooldown(transport, monkeypatch, status, kind):
    failures = []
    monkeypatch.setattr(transport, "remember_failure", lambda key, exc: failures.append(exc))
    monkeypatch.setattr(transport, "collect_capped_process", lambda *a, **k: (parts(transport.SINBON_INDEX, status, b"Retry-After: 600\r\n"), 28, "timeout"))
    http = transport.IssuerNewsHttp(time.monotonic() + 1)
    with pytest.raises(SourceResponseError) as error: http._download(transport.SINBON_INDEX, {})
    assert error.value.error_kind == kind and error.value.response.headers["retry-after"] == "600"
    assert bool(failures) is (status in (403, 429, 503)) and http.http_request_count == 1


@pytest.mark.parametrize("change", [{"url_effective": "https://evil.test/"}, {"num_redirects": 1}, {"http_code": 201}])
def test_response_metadata_redirect_mismatch_is_not_a_receipt(transport, monkeypatch, change):
    monkeypatch.setattr(transport, "collect_capped_process", lambda *a, **k: (parts(transport.SINBON_INDEX, **change), 0, None))
    with pytest.raises(SourceResponseError): transport.IssuerNewsHttp(time.monotonic() + 1)._download(transport.SINBON_INDEX, {})


def test_cooldown_starts_zero_requests(transport, monkeypatch):
    monkeypatch.setattr(transport, "cooldown_state", lambda *a: {"until": time.time() + 600})
    monkeypatch.setattr(transport, "collect_capped_process", lambda *a, **k: pytest.fail("cooldown child"))
    http = transport.IssuerNewsHttp(time.monotonic() + 1)
    with pytest.raises(SourceResponseError): http._download(transport.SINBON_INDEX, {})
    assert http.http_request_count == 0


@pytest.mark.parametrize("stamp", [float("nan"), float("inf"), True, 10**500, -1, 0])
def test_invalid_cache_epoch_never_admits_bytes(transport, monkeypatch, stamp):
    raw = b'{"public":true}'
    receipt = {"url": transport.SINBON_INDEX, "body_b64": base64.b64encode(raw).decode(), "sha256": sha256(raw).hexdigest()}
    monkeypatch.setattr(transport, "shared_fetch", lambda *a, **k: (receipt, {"cache_hit": True, "fetched_at_epoch": stamp}))
    with pytest.raises(SourceResponseError): transport.IssuerNewsHttp(time.monotonic() + 1).get(transport.SINBON_INDEX)


def test_raw_cache_preserves_original_epoch_and_hash_and_zero_http(transport, monkeypatch):
    raw = b'{"public":true}'; stamp = time.time() - 10
    receipt = {"url": transport.SINBON_INDEX, "body_b64": base64.b64encode(raw).decode(), "sha256": sha256(raw).hexdigest()}
    monkeypatch.setattr(transport, "shared_fetch", lambda *a, **k: (receipt, {"cache_hit": True, "fetched_at_epoch": stamp}))
    http = transport.IssuerNewsHttp(time.monotonic() + 1)
    assert http.get(transport.SINBON_INDEX) == raw and http.http_request_count == 0
    assert http.components[0]["fetched_at_epoch"] == stamp
    receipt["body_b64"] = base64.b64encode(b'{"changed":true}').decode()
    with pytest.raises(SourceResponseError): http.get(transport.SINBON_INDEX)


@pytest.mark.parametrize("behavior", ["drip", "overflow"])
def test_actual_slow_or_large_child_is_stopped_and_reaped(transport, monkeypatch, behavior):
    import os
    import subprocess
    import sys
    from bounded_curl_process import collect_capped_process
    created = []; real = subprocess.Popen
    def spawn(*a, **k):
        child = real(*a, **k); created.append(child); return child
    monkeypatch.setattr(subprocess, "Popen", spawn)
    code = "import os,sys,time\nfd={HEADER_FD}\nos.write(fd,b'HTTP/2 200\\r\\nContent-Type: application/json\\r\\n\\r\\n')\n"
    code += ("sys.stdout.buffer.write(b'x'*1100000);sys.stdout.flush();time.sleep(5)\n" if behavior == "overflow"
             else "\nfor i in range(100):\n sys.stdout.write('x');sys.stdout.flush();time.sleep(.03)\n")
    monkeypatch.setattr(transport, "collect_capped_process", lambda argv, end, **kw: collect_capped_process([sys.executable, "-c", code], end, **kw))
    start = time.monotonic(); http = transport.IssuerNewsHttp(start + .25)
    with pytest.raises(SourceResponseError) as error: http._download(transport.SINBON_INDEX, {})
    assert error.value.error_kind == ("timeout" if behavior == "drip" else "response_too_large")
    assert time.monotonic() - start < 1.5 and http.http_request_count == 1 and len(created) == 1
    with pytest.raises(ProcessLookupError): os.kill(created[0].pid, 0)
