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


def test_fmp_permission_guard_survives_restart_without_blocking_quote(monkeypatch):
    import httpx
    import external_data_fmp as fmp
    calls = []
    monkeypatch.setattr(fmp, 'FMP_API_KEY', 'test-key')
    fmp.clear_fmp_endpoint_cooldowns()
    def get(url, params):
        calls.append(url)
        if '/news/' in url:
            response = httpx.Response(402, request=httpx.Request('GET', url))
            response.raise_for_status()
        return [{'symbol': 'AAPL', 'price': 200}]
    monkeypatch.setattr(fmp, '_sync_json_get', get)
    assert fmp.fetch_fmp_news_catalysts('AAPL') == []
    fmp.clear_fmp_endpoint_cooldowns()  # new worker loses only process memory
    assert fmp.fetch_fmp_news_catalysts('AAPL') == []
    assert fmp.fetch_fmp_quote_fallback('AAPL')['price'] == 200
    assert len(calls) == 2
