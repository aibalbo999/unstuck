import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from report_refresh_diff import refresh_data_diff, refresh_requires_analysis_rerun  # noqa: E402


def test_refresh_data_diff_reports_source_status_transition_from_helper():
    previous_snapshot = MappingProxyType(
        {
            "data_trust": MappingProxyType(
                {
                    "status": "stale",
                    "critical_failures": (),
                    "stale_sources": ("market_data",),
                    "reason_codes": ("source_stale:market_data",),
                }
            ),
            "source_audit": (
                MappingProxyType(
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "status": "error",
                        "message": "stale quote",
                    }
                ),
            ),
        }
    )
    refreshed_snapshot = MappingProxyType(
        {
            "data_trust": MappingProxyType(
                {
                    "status": "fresh",
                    "critical_failures": (),
                    "stale_sources": (),
                    "reason_codes": ("fresh_core_sources",),
                }
            ),
            "source_audit": (
                MappingProxyType(
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "status": "success",
                        "message": "fresh quote",
                    }
                ),
            ),
        }
    )

    diff = refresh_data_diff(previous_snapshot, refreshed_snapshot)

    assert diff["data_trust_status"] == {"before": "stale", "after": "fresh", "changed": True}
    assert diff["stale_sources"] == {"removed": ["market_data"], "added": []}
    assert diff["source_status_changes"] == [
        {
            "source": "market_data",
            "provider": "yfinance",
            "before": "error",
            "after": "success",
            "message": "fresh quote",
        }
    ]


def test_refresh_requires_analysis_rerun_ignores_provider_sla_only_partial_change():
    previous_snapshot = {
        "data": {"current_price": 100},
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "reason_codes": []},
    }
    refreshed_snapshot = {
        "data": {"current_price": 100},
        "data_trust": {
            "status": "partial",
            "critical_failures": [],
            "stale_sources": [],
            "reason_codes": ["provider_sla_critical"],
        },
    }
    refresh_diff = {
        "stale_sources": {"removed": [], "added": []},
        "critical_failures": {"removed": [], "added": []},
    }

    assert refresh_requires_analysis_rerun(previous_snapshot, refreshed_snapshot, refresh_diff) is False
