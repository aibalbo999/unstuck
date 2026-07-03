import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from data_fetch.enrichment_merge import _merge_optional_http_bundle  # noqa: E402
from data_fetch.provider_registry import ProviderRegistry  # noqa: E402
from data_fetch.taiwan_open_data_provider import TaiwanOpenDataProvider  # noqa: E402
import data_fetch.taiwan_open_data_provider as taiwan_open_data_provider  # noqa: E402
from data_fetch.types import FetchRequest  # noqa: E402


def test_default_provider_registry_includes_chip_macro_and_alternative_sources():
    sources = {provider.source for provider in ProviderRegistry().providers}

    assert "macro_indicators" in sources
    assert "chip_data" in sources
    assert "alternative_data" in sources
    assert "social_sentiment" in sources
    assert "sec_edgar" in sources
    assert "taiwan_open_data" in sources


def test_optional_http_bundle_merges_external_agent_contexts():
    data = {"ticker": "2308.TW", "source_audit": []}
    merged = _merge_optional_http_bundle(
        data,
        {
            "macro_indicators": {"status": "success", "source": "FRED"},
            "chip_data": {"tdcc_shareholder_distribution": {"major_holders_gt_1000_lots_pct": 42.1}},
            "alternative_data": {"job_openings_104": {"job_count": 128}},
        },
        refreshed_sources=("macro_indicators", "chip_data", "alternative_data"),
    )

    assert merged["macro_indicators"]["source"] == "FRED"
    assert merged["chip_data"]["tdcc_shareholder_distribution"]["major_holders_gt_1000_lots_pct"] == 42.1
    assert merged["alternative_data"]["job_openings_104"]["job_count"] == 128


def test_optional_http_bundle_merges_additional_free_context_sources():
    data = {"ticker": "AAPL", "source_audit": []}
    merged = _merge_optional_http_bundle(
        data,
        {
            "social_sentiment": {"dcard": [{"title": "Dcard"}], "mobile01": [], "pttweb": []},
            "sec_edgar": {"recent_filings": [{"form": "10-K", "filingDate": "2026-02-01"}]},
            "taiwan_open_data": {"rates": {"USD": {"buy": "31.00", "sell": "31.50"}}},
        },
        refreshed_sources=("social_sentiment", "sec_edgar", "taiwan_open_data"),
    )

    assert merged["social_sentiment"]["dcard"][0]["title"] == "Dcard"
    assert merged["sentiment_context"]["social_sentiment"]["dcard"][0]["title"] == "Dcard"
    assert merged["sec_edgar"]["recent_filings"][0]["form"] == "10-K"
    assert merged["taiwan_open_data"]["rates"]["USD"]["sell"] == "31.50"
    latest_sources = {entry["source"]: entry for entry in merged["source_audit"]}
    assert latest_sources["social_sentiment"]["status"] == "success"
    assert latest_sources["sec_edgar"]["status"] == "success"
    assert latest_sources["taiwan_open_data"]["status"] == "success"


def test_taiwan_open_data_provider_falls_back_to_fred_when_bot_is_challenged(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, content: bytes, status_code: int = 200, json_payload=None):
            self.content = content
            self.status_code = status_code
            self._json_payload = json_payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._json_payload

    def fake_get(url, **_kwargs):
        calls.append(url)
        if "rate.bot.com.tw" in url:
            return FakeResponse(b"<!DOCTYPE html><title>Challenge Validation</title>")
        return FakeResponse(
            b'{"result":"success"}',
            json_payload={"result": "success", "rates": {"TWD": 31.93}, "time_last_update_utc": "Fri, 03 Jul 2026 00:00:01 +0000"},
        )

    monkeypatch.setattr(taiwan_open_data_provider, "sync_get", fake_get)

    result = TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW"))

    assert result.status == "success"
    assert result.value["source"] == "open.er-api.com fallback"
    assert result.value["rates"]["USD"]["sell"] == "31.9300"
    assert result.audit["record_count"] == 1
    assert len(calls) == 2
