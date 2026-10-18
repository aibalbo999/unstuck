"""Official history's wall-clock and body limits also apply to slow responses."""
import json
import os
import sys
import time

import pytest
from search_provider_runtime import SourceResponseError


@pytest.fixture
def transport(monkeypatch):
    from data_fetch.market_sources import twse_history_transport as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    for key in source.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(source, "proxy_url_for_request", lambda *args: None)
    monkeypatch.setattr(source, "cooldown_state", lambda key: {})
    return source


def parts(url, *, status=200, body=b'{"code":200}', extra_headers=b''):
    return {"body": body,
            "headers": f"HTTP/2 {status}\r\nContent-Type: application/json\r\n".encode() + extra_headers + b"\r\n",
            "metadata": json.dumps({"http_code": status, "url_effective": url, "num_redirects": 0}).encode(),
            "process_started": True}


def test_post_uses_fixed_public_url_and_capped_child_without_retry_or_redirect(transport, monkeypatch):
    calls = []
    def collect(argv, end, **kwargs):
        calls.append((argv, end, kwargs))
        return parts(transport.EZ_URL), 0, None
    monkeypatch.setattr(transport, "collect_capped_process", collect)
    start = time.monotonic()
    client = transport.BoundedHistoryHttp(start + 20)
    response = client.post(transport.EZ_URL, data={"CO_ID": "2891"})
    assert response.json() == {"code": 200} and client.http_request_count == 1
    argv, end, kwargs = calls[0]
    assert end <= start + 4.1 and kwargs == {"body_limit": 2000000, "headers": True}
    assert argv[-1] == transport.EZ_URL and "--disable" in argv
    assert argv[argv.index("--retry") + 1] == "0"
    assert argv[argv.index("--max-redirs") + 1] == "0"
    assert "--insecure" not in argv and "-k" not in argv


def test_new_monthly_api_uses_ordinary_httpx_in_the_same_capped_child(transport, monkeypatch):
    calls = []
    def collect(argv, end, **kwargs):
        calls.append((argv, end, kwargs))
        return parts(transport.JSON_URL), 0, None
    monkeypatch.setattr(transport, "collect_capped_process", collect)
    start = time.monotonic()
    client = transport.BoundedHistoryHttp(start + 20)
    assert client.post(transport.JSON_URL, json={"companyId": "2891"}).json() == {"code": 200}
    argv, end, kwargs = calls[0]
    assert argv[0] == sys.executable and argv[1].endswith("/mops_monthly_http_child.py")
    assert argv[2] == transport.JSON_URL and json.loads(argv[3]) == {"companyId": "2891"}
    assert end <= start + 4.1 and kwargs == {"body_limit": 256000, "headers": True}


def test_tpex_infohub_uses_exact_company_query_with_capped_post(transport, monkeypatch):
    calls = []
    url = transport.TPEX_INFOHUB_API_URL + "?query=8299&lang=en-us"
    def collect(argv, end, **kwargs):
        calls.append((argv, end, kwargs))
        return parts(url), 0, None
    monkeypatch.setattr(transport, "collect_capped_process", collect)
    client = transport.BoundedHistoryHttp(time.monotonic() + 20,
                                         provider="TPEx Market InfoHub company disclosures")
    assert client.post(url, data={}).json() == {"code": 200}
    argv, _end, kwargs = calls[0]
    assert argv[-1] == url
    assert "Referer: https://info.tpex.org.tw/IIH/en/company.html?stkNo=8299" in argv
    assert kwargs == {"body_limit": 256000, "headers": True}

    with pytest.raises(SourceResponseError) as rejected:
        client.post(transport.TPEX_INFOHUB_API_URL + "?query=8299&lang=en-us&extra=1", data={})
    assert rejected.value.error_kind == "transport_url_invalid"


@pytest.mark.parametrize("body,accepted", [(b'\xef\xbb\xbf{"status":"success","data":[]}', True),
                                           (b'<html>challenge</html>', False)])
def test_only_legacy_ezsearch_accepts_real_json_under_html_content_type(transport, monkeypatch, body, accepted):
    p = parts(transport.EZ_URL, body=body)
    p["headers"] = b"HTTP/2 200\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
    monkeypatch.setattr(transport, "collect_capped_process", lambda *a, **k: (p, 0, None))
    client = transport.BoundedHistoryHttp(time.monotonic() + 1)
    if accepted:
        assert client.post(transport.EZ_URL, data={}).json() == {"status": "success", "data": []}
    else:
        with pytest.raises(SourceResponseError):
            client.post(transport.EZ_URL, data={})


@pytest.mark.parametrize("kind", ["disabled", "bad_url", "proxy", "expired", "cooldown"])
def test_locally_blocked_transfer_never_starts_a_network_child(transport, monkeypatch, kind):
    monkeypatch.setattr(transport, "collect_capped_process", lambda *a, **k: pytest.fail("unexpected child"))
    client = transport.BoundedHistoryHttp(time.monotonic() + 1)
    url = transport.JSON_URL
    if kind == "disabled":
        monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "1")
    elif kind == "bad_url":
        url = "https://evil.invalid/"
    elif kind == "proxy":
        monkeypatch.setattr(transport, "proxy_url_for_request", lambda *a: "http://secret.invalid")
    elif kind == "expired":
        client.deadline = time.monotonic() - 1
    else:
        monkeypatch.setattr(transport, "cooldown_state", lambda key: {"retry_at": time.time() + 3600})
    with pytest.raises(SourceResponseError):
        client.post(url, json={"companyId": "2891"})
    assert client.http_request_count == 0


@pytest.mark.parametrize("status,kind", [(403, "access_denied"), (429, "rate_limited"), (503, "server_error")])
def test_actual_refusal_retains_retry_after_even_if_body_times_out(transport, monkeypatch, status, kind):
    remembered = []
    monkeypatch.setattr(transport, "remember_failure", lambda key, exc: remembered.append((key, exc)))
    p = parts(transport.JSON_URL, status=status, extra_headers=b"Retry-After: 3600\r\n")
    monkeypatch.setattr(transport, "collect_capped_process", lambda *a, **k: (p, 28, "timeout"))
    with pytest.raises(SourceResponseError) as error:
        transport.BoundedHistoryHttp(time.monotonic() + 1).post(transport.JSON_URL, json={})
    assert error.value.error_kind == kind
    assert error.value.response.headers["retry-after"] == "3600"
    assert len(remembered) == 1


def test_truncated_retry_after_header_is_not_recorded_as_a_shorter_delay(transport, monkeypatch):
    monkeypatch.setattr(transport, "remember_failure", lambda key, exc: {})
    p = parts(transport.JSON_URL, status=429)
    p["headers"] = b"HTTP/2 429\r\nRetry-After: 36"
    monkeypatch.setattr(transport, "collect_capped_process", lambda *a, **k: (p, 1, "response_headers_too_large"))
    with pytest.raises(SourceResponseError) as error:
        transport.BoundedHistoryHttp(time.monotonic() + 1).post(transport.JSON_URL, json={})
    assert error.value.status_code == 429 and "retry-after" not in error.value.response.headers


@pytest.mark.parametrize("behavior", ["drip", "overflow"])
def test_slow_or_oversized_real_child_is_stopped_and_reaped(transport, monkeypatch, behavior):
    import subprocess
    from bounded_curl_process import collect_capped_process
    created, original = [], subprocess.Popen
    def spawn(*args, **kwargs):
        assert args[0][0] == sys.executable and kwargs["shell"] is False
        child = original(*args, **kwargs)
        created.append(child)
        return child
    monkeypatch.setattr(subprocess, "Popen", spawn)
    code = "import os,sys,time\nfd={HEADER_FD}\nos.write(fd,b'HTTP/2 200\\r\\nContent-Type: application/json\\r\\n\\r\\n')\n"
    if behavior == "overflow":
        code += "sys.stdout.buffer.write(b'x'*300000);sys.stdout.flush();time.sleep(5)\n"
    else:
        code += "\nfor i in range(100):\n sys.stdout.write('x');sys.stdout.flush();time.sleep(.03)\n"
    monkeypatch.setattr(transport, "collect_capped_process", lambda argv, end, **kw: collect_capped_process(
        [sys.executable, "-c", code], end, **kw))
    start = time.monotonic()
    with pytest.raises(SourceResponseError) as error:
        transport.BoundedHistoryHttp(start + .25).post(transport.JSON_URL, json={})
    assert error.value.error_kind == ("timeout" if behavior == "drip" else "response_too_large")
    assert time.monotonic() - start < 1.5 and len(created) == 1
    with pytest.raises(ProcessLookupError):
        os.kill(created[0].pid, 0)
