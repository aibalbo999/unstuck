from data_fetch import FetchRequest, ProviderRegistry, ProviderResult
from data_fetch.provider_base import DataProvider
from free_mode_contract import build_free_mode_contract, free_mode_enabled


class FreeOnlyProvider(DataProvider):
    name = "Free official feed"
    source = "financial_statements"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"financial_statements"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        return ProviderResult(source=self.source, provider=self.name, status="success", value={})


class PaidOnlyProvider(DataProvider):
    name = "Paid terminal feed"
    source = "financial_statements"
    markets = {"tw"}
    cost_tier = "optional_paid"
    capabilities = {"financial_statements"}
    requires_env = ("PAID_TERMINAL_KEY",)

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        return ProviderResult(source=self.source, provider=self.name, status="success", value={})


def test_free_mode_enabled_defaults_to_true_and_accepts_explicit_false(monkeypatch):
    monkeypatch.delenv("FREE_MODE", raising=False)
    monkeypatch.delenv("STOCK_AGENT_FREE_MODE", raising=False)
    assert free_mode_enabled() is True

    monkeypatch.setenv("FREE_MODE", "false")
    assert free_mode_enabled() is False


def test_free_mode_contract_flags_required_paid_sources_without_breaking_optional_paid(monkeypatch):
    monkeypatch.setenv("FREE_MODE", "true")
    request = FetchRequest.from_ticker("2330.TW")
    registry = ProviderRegistry([PaidOnlyProvider()])

    contract = build_free_mode_contract(registry, request)

    assert contract["enabled"] is True
    assert contract["can_run_without_paid_keys"] is False
    assert contract["violations"] == [
        {
            "source": "financial_statements",
            "market": "tw",
            "reason": "no_free_provider",
        }
    ]
    assert contract["providers"][0]["cost_tier"] == "optional_paid"
    assert contract["providers"][0]["requires_env"] == ["PAID_TERMINAL_KEY"]


def test_free_mode_contract_passes_when_each_required_source_has_free_provider(monkeypatch):
    monkeypatch.setenv("FREE_MODE", "true")
    request = FetchRequest.from_ticker("2330.TW")
    registry = ProviderRegistry([FreeOnlyProvider(), PaidOnlyProvider()])

    contract = build_free_mode_contract(registry, request)

    assert contract["can_run_without_paid_keys"] is True
    assert contract["violations"] == []
    assert [provider["name"] for provider in contract["providers"]] == [
        "Free official feed",
        "Paid terminal feed",
    ]
