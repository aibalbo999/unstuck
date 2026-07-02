from data_fetch import FetchRequest, ProviderResult
from data_fetch.provider_base import DataProvider, provider_result_from_payload


class CapabilityProvider(DataProvider):
    name = "Capability demo"
    source = "recent_catalysts"
    markets = {"us"}
    cost_tier = "free_with_key"
    capabilities = {"news", "search"}
    requires_env = ("DEMO_KEY",)
    freshness_seconds = 900


def test_data_provider_exposes_structured_capability_contract():
    provider = CapabilityProvider()

    capability = provider.capability(FetchRequest.from_ticker("AAPL"))

    assert capability == {
        "name": "Capability demo",
        "source": "recent_catalysts",
        "markets": ["us"],
        "cost_tier": "free_with_key",
        "capabilities": ["news", "search"],
        "requires_env": ["DEMO_KEY"],
        "freshness_seconds": 900,
        "enabled_in_free_mode": True,
        "supports_request": True,
    }


def test_provider_result_preserves_provenance_fields_from_payload_audit():
    payload = {
        "source_audit": [
            {
                "source": "recent_catalysts",
                "provider": "Google News RSS",
                "status": "success",
                "record_count": 3,
                "as_of": "2026-07-02T09:00:00+08:00",
                "confidence": 0.82,
                "raw_ref": "cache:recent:2330",
            }
        ],
        "items": [{"title": "news"}],
    }

    result = provider_result_from_payload("recent_catalysts", "Google News RSS", payload)

    assert result.as_of == "2026-07-02T09:00:00+08:00"
    assert result.confidence == 0.82
    assert result.raw_ref == "cache:recent:2330"
