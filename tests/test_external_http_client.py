from __future__ import annotations

import sys
from pathlib import Path
import asyncio


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import external_http_client  # noqa: E402


def test_external_http_proxy_rotation_uses_global_proxy_urls(monkeypatch):
    external_http_client.clear_proxy_rotation_state()
    monkeypatch.setenv("PROVIDER_PROXY_URLS", "http://proxy-a:8080, http://proxy-b:8080")

    first = external_http_client.proxy_url_for_provider("unknown")
    second = external_http_client.proxy_url_for_provider("unknown")
    third = external_http_client.proxy_url_for_provider("unknown")

    assert first == "http://proxy-a:8080"
    assert second == "http://proxy-b:8080"
    assert third == "http://proxy-a:8080"
    external_http_client.clear_proxy_rotation_state()


def test_external_http_proxy_rotation_prefers_provider_specific_urls(monkeypatch):
    external_http_client.clear_proxy_rotation_state()
    monkeypatch.setenv("PROVIDER_PROXY_URLS", "http://global-proxy:8080")
    monkeypatch.setenv("PROVIDER_PROXY_GOOGLE_SEARCH_URLS", "http://google-proxy:8080")

    assert external_http_client.proxy_url_for_provider("Google Search") == "http://google-proxy:8080"
    assert external_http_client.proxy_url_for_provider("FMP") == "http://global-proxy:8080"
    external_http_client.clear_proxy_rotation_state()


def test_sync_json_get_passes_rotated_proxy_to_httpx(monkeypatch):
    external_http_client.clear_proxy_rotation_state()
    monkeypatch.setenv("PROVIDER_PROXY_FMP_URLS", "http://fmp-proxy:8080")
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(external_http_client.httpx, "get", fake_get)

    assert external_http_client.sync_json_get(
        "https://financialmodelingprep.com/stable/quote",
        {"symbol": "AAPL"},
    ) == {"ok": True}
    assert calls[0]["proxy"] == "http://fmp-proxy:8080"
    external_http_client.clear_proxy_rotation_state()


def test_sync_get_passes_rotated_proxy_and_returns_response(monkeypatch):
    external_http_client.clear_proxy_rotation_state()
    monkeypatch.setenv("PROVIDER_PROXY_TAIWAN_OPEN_DATA_URLS", "http://tw-proxy:8080")
    calls = []

    class FakeResponse:
        content = b"csv"

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(external_http_client.httpx, "get", fake_get)

    response = external_http_client.sync_get(
        "https://rate.bot.com.tw/xrt/flcsv/0/day",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=5,
        provider="Taiwan Open Data",
    )

    assert response.content == b"csv"
    assert calls[0]["proxy"] == "http://tw-proxy:8080"
    assert calls[0]["timeout"] == 5
    external_http_client.clear_proxy_rotation_state()


def test_sync_post_passes_rotated_proxy_and_returns_response(monkeypatch):
    external_http_client.clear_proxy_rotation_state()
    monkeypatch.setenv("PROVIDER_PROXY_MOPS_URLS", "http://mops-proxy:8080")
    calls = []

    class FakeResponse:
        text = "<table></table>"

        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(external_http_client.httpx, "post", fake_post)

    response = external_http_client.sync_post(
        "https://mops.twse.com.tw/mops/web/ajax_t164sb03",
        data={"co_id": "2330"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=7,
        provider="MOPS",
    )

    assert response.text == "<table></table>"
    assert calls[0]["data"] == {"co_id": "2330"}
    assert calls[0]["proxy"] == "http://mops-proxy:8080"
    assert calls[0]["timeout"] == 7
    external_http_client.clear_proxy_rotation_state()


def test_async_client_passes_rotated_proxy_to_httpx_async_client(monkeypatch):
    external_http_client.clear_proxy_rotation_state()
    monkeypatch.setenv("PROVIDER_PROXY_GDELT_URLS", "http://gdelt-proxy:8080")
    calls = []

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(external_http_client.httpx, "AsyncClient", FakeAsyncClient)

    client = external_http_client.async_client("GDELT")

    assert isinstance(client, FakeAsyncClient)
    assert calls[0]["proxy"] == "http://gdelt-proxy:8080"
    external_http_client.clear_proxy_rotation_state()


def test_fmp_async_fetch_uses_fmp_proxy_pool(monkeypatch):
    import external_data_fmp as fmp

    external_http_client.clear_proxy_rotation_state()
    monkeypatch.setenv("PROVIDER_PROXY_FMP_URLS", "http://fmp-proxy:8080")
    monkeypatch.setattr(fmp, "FMP_API_KEY", "test-fmp")
    calls = []

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    async def fake_json_get(_client, _url, _params):
        return []

    monkeypatch.setattr(external_http_client.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(fmp, "_async_json_get", fake_json_get)

    assert asyncio.run(fmp.fetch_fmp_quote_fallback_async("AAPL")) == {}
    assert calls[0]["proxy"] == "http://fmp-proxy:8080"
    external_http_client.clear_proxy_rotation_state()


def test_gdelt_async_client_uses_gdelt_proxy_pool(monkeypatch):
    import external_data_gdelt as gdelt

    external_http_client.clear_proxy_rotation_state()
    monkeypatch.setenv("PROVIDER_PROXY_GDELT_URLS", "http://gdelt-proxy:8080")
    calls = []

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(gdelt.httpx, "AsyncClient", FakeAsyncClient)

    client = gdelt.async_client()

    assert isinstance(client, FakeAsyncClient)
    assert calls[0]["proxy"] == "http://gdelt-proxy:8080"
    external_http_client.clear_proxy_rotation_state()


def test_external_http_proxy_configuration_is_documented():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    operator_guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")

    assert "PROVIDER_PROXY_URLS" in readme
    assert "PROVIDER_PROXY_FMP_URLS" in readme
    assert "PROVIDER_PROXY_GDELT_URLS" in operator_guide
