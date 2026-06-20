import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from data_fetch.enrichment_merge import _merge_optional_http_bundle  # noqa: E402
from data_fetch.provider_registry import ProviderRegistry  # noqa: E402


def test_default_provider_registry_includes_chip_macro_and_alternative_sources():
    sources = {provider.source for provider in ProviderRegistry().providers}

    assert "macro_indicators" in sources
    assert "chip_data" in sources
    assert "alternative_data" in sources


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
