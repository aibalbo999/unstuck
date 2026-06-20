import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, **kwargs):
        self.calls.append((url, dict(params or {}), kwargs))
        series_id = params["series_id"]
        observations = {
            "DGS10": [{"date": "2026-06-17", "value": "4.20"}],
            "CPIAUCSL": [
                {"date": "2025-05-01", "value": "320.000"},
                {"date": "2026-05-01", "value": "329.600"},
            ],
            "VIXCLS": [{"date": "2026-06-17", "value": "18.44"}],
        }[series_id]
        return FakeResponse({"observations": observations})


def test_fetch_key_macro_indicators_formats_latest_macro_context(monkeypatch):
    from macro_fetcher import fetch_key_macro_indicators

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    session = FakeSession()

    result = fetch_key_macro_indicators(session=session, use_cache=False)

    assert result["source"] == "FRED"
    assert result["indicators"]["us_10y_yield"]["series_id"] == "DGS10"
    assert result["indicators"]["us_10y_yield"]["value"] == pytest.approx(4.20)
    assert result["indicators"]["us_cpi_yoy"]["value"] == pytest.approx(3.0)
    assert result["indicators"]["vix"]["value"] == pytest.approx(18.44)
    assert "美國10年期公債殖利率 4.20%" in result["summary_text"]
    assert "CPI年增率 3.00%" in result["summary_text"]
    assert "VIX 18.44" in result["summary_text"]
    assert [call[1]["series_id"] for call in session.calls] == ["DGS10", "CPIAUCSL", "VIXCLS"]


def test_fetch_key_macro_indicators_requires_api_key(monkeypatch):
    from macro_fetcher import fetch_key_macro_indicators

    monkeypatch.delenv("FRED_API_KEY", raising=False)

    result = fetch_key_macro_indicators(session=FakeSession(), use_cache=False)

    assert result["status"] == "not_configured"
    assert "FRED_API_KEY" in result["message"]
