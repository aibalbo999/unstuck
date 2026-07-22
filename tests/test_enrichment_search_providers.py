import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_fetch import enrichment_providers  # noqa: E402
from data_fetch.enrichment_search_providers import (  # noqa: E402
    AlternativePeerDiscoveryProvider,
    AlternativeSearchProvider,
)


def test_alternative_search_providers_are_reexported_from_legacy_facade():
    assert enrichment_providers.AlternativeSearchProvider is AlternativeSearchProvider
    assert enrichment_providers.AlternativePeerDiscoveryProvider is AlternativePeerDiscoveryProvider
    assert AlternativeSearchProvider.source == "recent_catalysts"
    assert AlternativePeerDiscoveryProvider.source == "peer_discovery"
