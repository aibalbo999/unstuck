from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_fmp_news_cools_down_after_restricted_response(monkeypatch):
    import external_data_fmp as fmp

    class FakeResponse:
        status_code = 402

    class FakeHTTPStatusError(RuntimeError):
        response = FakeResponse()

    calls = []
    now = {"value": 1000.0}

    async def restricted(_client, url, _params):
        calls.append(url)
        raise FakeHTTPStatusError("402 Payment Required")

    monkeypatch.setattr(fmp, "FMP_API_KEY", "test-key")
    monkeypatch.setattr(fmp, "_async_json_get", restricted)
    monkeypatch.setattr(fmp, "_now", lambda: now["value"])
    monkeypatch.setattr(fmp, "_restricted_cooldown_seconds", lambda: 60.0)
    fmp.clear_fmp_endpoint_cooldowns()

    assert asyncio.run(fmp.fetch_fmp_news_catalysts_async("1623.TW")) == []
    assert len(calls) == 1

    assert asyncio.run(fmp.fetch_fmp_news_catalysts_async("1623.TW")) == []
    assert len(calls) == 1

    now["value"] += 61.0
    assert asyncio.run(fmp.fetch_fmp_news_catalysts_async("1623.TW")) == []
    assert len(calls) == 2
    fmp.clear_fmp_endpoint_cooldowns()


def test_google_search_cools_down_after_restricted_response(monkeypatch):
    import external_data_google as google

    class FakeResponse:
        status_code = 403

    class FakeHTTPStatusError(RuntimeError):
        response = FakeResponse()

    calls = []
    now = {"value": 1000.0}

    async def restricted(_client, _url, params):
        calls.append(params["q"])
        raise FakeHTTPStatusError("403 Forbidden")

    monkeypatch.setattr(google, "GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(google, "GOOGLE_CSE_ID", "test-cx")
    monkeypatch.setattr(google, "_async_json_get", restricted)
    monkeypatch.setattr(google, "_now", lambda: now["value"])
    monkeypatch.setattr(google, "_restricted_cooldown_seconds", lambda: 60.0)
    google.clear_google_search_cooldown()

    assert asyncio.run(google.fetch_google_search_catalysts_async("1623.TW", "大東電", {})) == []
    assert len(calls) == 1

    assert asyncio.run(google.fetch_google_peer_discovery_results_async("1623.TW", "大東電", "Industrial", "Electrical")) == []
    assert len(calls) == 1

    now["value"] += 61.0
    assert asyncio.run(google.fetch_google_peer_discovery_results_async("1623.TW", "大東電", "Industrial", "Electrical")) == []
    assert len(calls) == 2
    google.clear_google_search_cooldown()


def test_google_search_sends_optional_referer_header(monkeypatch):
    import external_data_google as google

    calls = []

    async def ok(_client, _url, params, headers=None):
        calls.append({"query": params["q"], "headers": headers})
        return {"items": []}

    monkeypatch.setattr(google, "GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(google, "GOOGLE_CSE_ID", "test-cx")
    monkeypatch.setattr(google, "GOOGLE_SEARCH_REFERER", "http://localhost:8080/")
    monkeypatch.setattr(google, "_async_json_get", ok)
    google.clear_google_search_cooldown()

    assert asyncio.run(google.fetch_google_search_catalysts_async("1623.TW", "大東電", {})) == []
    assert calls[0]["headers"] == {"Referer": "http://localhost:8080/"}
    google.clear_google_search_cooldown()


def test_google_search_referrer_block_hint_identifies_configuration_issue():
    import external_data_google as google

    class FakeResponse:
        status_code = 403

        def json(self):
            return {
                "error": {
                    "message": "Requests from referer <empty> are blocked.",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                            "reason": "API_KEY_HTTP_REFERRER_BLOCKED",
                            "domain": "googleapis.com",
                        }
                    ],
                }
            }

    class FakeHTTPStatusError(RuntimeError):
        response = FakeResponse()

    hint = google.describe_google_search_setup_hint(FakeHTTPStatusError("403 Forbidden"))

    assert "HTTP Referrer" in hint
    assert "GOOGLE_SEARCH_REFERER" in hint


def test_google_search_project_access_hint_identifies_closed_json_api():
    import external_data_google as google

    class FakeResponse:
        status_code = 403

        def json(self):
            return {
                "error": {
                    "message": "This project does not have the access to Custom Search JSON API.",
                    "errors": [
                        {
                            "message": "This project does not have the access to Custom Search JSON API.",
                            "domain": "global",
                            "reason": "forbidden",
                        }
                    ],
                    "status": "PERMISSION_DENIED",
                }
            }

    class FakeHTTPStatusError(RuntimeError):
        response = FakeResponse()

    hint = google.describe_google_search_setup_hint(FakeHTTPStatusError("403 Forbidden"))

    assert "Custom Search JSON API access" in hint
    assert "older Google Cloud project" in hint
