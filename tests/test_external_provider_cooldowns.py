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
