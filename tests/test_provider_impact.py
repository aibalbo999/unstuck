from __future__ import annotations

from collections.abc import Mapping
import json
import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class LookupItemsMapping(Mapping):
    def __init__(self, data):
        self._data = dict(data)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def items(self):
        raise KeyError("provider impact mapping items lookup unavailable")


class LookupItemMapping(Mapping):
    def __init__(self, data):
        self._data = dict(data)

    def __getitem__(self, key):
        if key == "broken":
            raise KeyError("provider impact mapping item lookup unavailable")
        return self._data[key]

    def __iter__(self):
        return iter(("broken", *self._data.keys()))

    def __len__(self):
        return len(self._data) + 1


def test_provider_impact_blocks_auto_rerun_for_core_critical_unhealthy_source():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "status": "partial",
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                    }
                ],
            },
        }
    )

    assert impact["schema_version"] == "provider_impact.v1"
    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source_scope"] == "core"
    assert impact["impacts"][0]["affects_core_data"] is True


def test_provider_impact_accepts_mapping_report_trust_and_alert_payloads():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        MappingProxyType(
            {
                "ticker": "NVDA",
                "filename": "nvda_report.html",
                "pipeline_id": "v2",
                "data_trust": MappingProxyType(
                    {
                        "reason_codes": ("provider_sla_critical",),
                        "provider_sla_alerts": (
                            MappingProxyType(
                                {
                                    "source": "market_data",
                                    "provider": "yfinance",
                                    "alert_level": "critical",
                                    "current_status": "unavailable",
                                    "current_record_count": 0,
                                }
                            ),
                        ),
                    }
                ),
            }
        )
    )

    assert impact["ticker"] == "NVDA"
    assert impact["filename"] == "nvda_report.html"
    assert impact["pipeline_id"] == "v2"
    assert impact["reason_codes"] == ["provider_sla_critical"]
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source_scope"] == "core"
    assert impact["impacts"][0]["affects_core_data"] is True


def test_provider_impact_accepts_mapping_payloads_when_items_accessor_lookup_fails():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        LookupItemsMapping(
            {
                "ticker": "NVDA",
                "filename": "nvda_report.html",
                "pipeline_id": "v2",
                "data_trust": LookupItemsMapping(
                    {
                        "reason_codes": ("provider_sla_critical",),
                        "provider_sla_alerts": (
                            LookupItemsMapping(
                                {
                                    "source": "market_data",
                                    "provider": "yfinance",
                                    "alert_level": "critical",
                                    "current_status": "unavailable",
                                    "current_record_count": 0,
                                }
                            ),
                        ),
                    }
                ),
            }
        )
    )

    assert impact["ticker"] == "NVDA"
    assert impact["filename"] == "nvda_report.html"
    assert impact["pipeline_id"] == "v2"
    assert impact["reason_codes"] == ["provider_sla_critical"]
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source"] == "market_data"


def test_provider_impact_accepts_mapping_payloads_when_item_lookup_fails():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        LookupItemMapping(
            {
                "ticker": "NVDA",
                "filename": "nvda_report.html",
                "pipeline_id": "v2",
                "data_trust": LookupItemMapping(
                    {
                        "reason_codes": ("provider_sla_critical",),
                        "provider_sla_alerts": (
                            LookupItemMapping(
                                {
                                    "source": "market_data",
                                    "provider": "yfinance",
                                    "alert_level": "critical",
                                    "current_status": "unavailable",
                                    "current_record_count": 0,
                                }
                            ),
                        ),
                    }
                ),
            }
        )
    )

    assert impact["ticker"] == "NVDA"
    assert impact["filename"] == "nvda_report.html"
    assert impact["pipeline_id"] == "v2"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source"] == "market_data"


def test_provider_impact_keeps_optional_critical_as_monitor_only():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "AAPL",
            "filename": "aapl_report.html",
            "pipeline_id": "v1",
            "data_trust": {
                "status": "fresh",
                "reason_codes": ["provider_sla_optional_critical"],
                "provider_sla_alerts": [
                    {
                        "source": "recent_catalysts",
                        "provider": "news-rss",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                    }
                ],
            },
        }
    )

    assert impact["summary"]["max_severity"] == "notice"
    assert impact["summary"]["recommended_action"] == "monitor_provider"
    assert impact["summary"]["blocks_auto_rerun"] is False
    assert impact["impacts"][0]["source_scope"] == "optional"
    assert impact["impacts"][0]["affects_core_data"] is False


def test_provider_impact_treats_core_health_notice_as_non_blocking():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "MSFT",
            "filename": "msft_report.html",
            "pipeline_id": "v1",
            "data_trust": {
                "status": "fresh",
                "reason_codes": ["provider_sla_core_health_notice"],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "success",
                        "current_record_count": 1,
                        "current_source_has_healthy_entry": True,
                    }
                ],
            },
        }
    )

    assert impact["summary"]["max_severity"] == "notice"
    assert impact["summary"]["recommended_action"] == "monitor_provider"
    assert impact["summary"]["blocks_auto_rerun"] is False
    assert impact["impacts"][0]["current_fetch_healthy"] is True


def test_provider_impact_uses_shared_text_safety_for_report_identity_fields():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": True,
            "filename": b"nvda_report.html",
            "report_filename": "nvda_report.html",
            "pipeline_id": memoryview(b"v2"),
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                    }
                ],
            },
        }
    )

    assert impact["ticker"] == ""
    assert impact["filename"] == "nvda_report.html"
    assert impact["pipeline_id"] == "v1"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"


def test_provider_impact_ledger_summarizes_report_level_impacts():
    from provider_impact import build_provider_impact_ledger

    ledger = build_provider_impact_ledger([
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [{"source": "market_data", "provider": "yfinance", "alert_level": "critical"}],
            },
        },
        {
            "ticker": "AAPL",
            "filename": "aapl_report.html",
            "pipeline_id": "v1",
            "data_trust": {
                "reason_codes": ["provider_sla_optional_critical"],
                "provider_sla_alerts": [{"source": "recent_catalysts", "provider": "news-rss", "alert_level": "critical"}],
            },
        },
    ])

    assert ledger["schema_version"] == "provider_impact_ledger.v1"
    assert ledger["summary"]["reports_with_impacts"] == 2
    assert ledger["summary"]["blocked_reports"] == 1
    assert [item["filename"] for item in ledger["items"]] == ["nvda_report.html", "aapl_report.html"]


def test_provider_impact_ledger_accepts_mapping_reports_envelope():
    from provider_impact import build_provider_impact_ledger

    ledger = build_provider_impact_ledger(
        MappingProxyType(
            {
                "reports": (
                    MappingProxyType(
                        {
                            "ticker": "NVDA",
                            "filename": "nvda_report.html",
                            "pipeline_id": "v2",
                            "data_trust": MappingProxyType(
                                {
                                    "reason_codes": ("provider_sla_critical",),
                                    "provider_sla_alerts": (
                                        MappingProxyType(
                                            {
                                                "source": "market_data",
                                                "provider": "yfinance",
                                                "alert_level": "critical",
                                                "current_status": "unavailable",
                                                "current_record_count": 0,
                                            }
                                        ),
                                    ),
                                }
                            ),
                        }
                    ),
                )
            }
        )
    )

    assert ledger["summary"]["sampled_reports"] == 1
    assert ledger["summary"]["reports_with_impacts"] == 1
    assert ledger["summary"]["blocked_reports"] == 1
    assert ledger["items"][0]["filename"] == "nvda_report.html"
    assert ledger["items"][0]["summary"]["recommended_action"] == "wait_provider_recovery"


def test_provider_impact_ledger_preserves_valid_reports_before_iterator_failures():
    from provider_impact import build_provider_impact_ledger

    ledger = build_provider_impact_ledger(BrokenProviderImpactReportIterator())

    assert ledger["summary"]["sampled_reports"] == 1
    assert ledger["summary"]["reports_with_impacts"] == 1
    assert ledger["summary"]["blocked_reports"] == 1
    assert ledger["items"][0]["ticker"] == "NVDA"
    assert ledger["items"][0]["summary"]["recommended_action"] == "wait_provider_recovery"


def test_provider_impact_ledger_report_tuple_sequences_are_evaluated():
    from provider_impact import build_provider_impact_ledger

    ledger = build_provider_impact_ledger(
        (
            {
                "ticker": "NVDA",
                "filename": "nvda_report.html",
                "pipeline_id": "v2",
                "data_trust": {
                    "reason_codes": ["provider_sla_critical"],
                    "provider_sla_alerts": [
                        {
                            "source": "market_data",
                            "provider": "yfinance",
                            "alert_level": "critical",
                            "current_status": "unavailable",
                            "current_record_count": 0,
                        }
                    ],
                },
            },
        )
    )

    assert ledger["summary"]["sampled_reports"] == 1
    assert ledger["summary"]["reports_with_impacts"] == 1
    assert ledger["summary"]["blocked_reports"] == 1
    assert ledger["items"][0]["summary"]["recommended_action"] == "wait_provider_recovery"


def test_provider_impact_ledger_native_report_lists_survive_iterator_accessor_failures():
    from provider_impact import build_provider_impact_ledger

    ledger = build_provider_impact_ledger(
        BrokenProviderImpactNativeDictList(
            [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_report.html",
                    "pipeline_id": "v2",
                    "data_trust": {
                        "reason_codes": ["provider_sla_critical"],
                        "provider_sla_alerts": [
                            {
                                "source": "market_data",
                                "provider": "yfinance",
                                "alert_level": "critical",
                                "current_status": "unavailable",
                                "current_record_count": 0,
                            }
                        ],
                    },
                }
            ]
        )
    )

    assert ledger["summary"]["sampled_reports"] == 1
    assert ledger["summary"]["reports_with_impacts"] == 1
    assert ledger["summary"]["blocked_reports"] == 1
    assert ledger["items"][0]["summary"]["recommended_action"] == "wait_provider_recovery"


def test_provider_impact_ledger_sort_key_does_not_depend_on_ticker_truthiness():
    from provider_impact import build_provider_impact_ledger

    ledger = build_provider_impact_ledger([
        {
            "ticker": BrokenProviderImpactTruthText("NVDA"),
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                    }
                ],
            },
        }
    ])

    assert ledger["summary"]["reports_with_impacts"] == 1
    assert ledger["summary"]["blocked_reports"] == 1
    assert ledger["items"][0]["summary"]["recommended_action"] == "wait_provider_recovery"


class BrokenProviderImpactReportGet(dict):
    BROKEN_KEYS = {"ticker", "filename", "report_filename", "pipeline_id", "data_trust"}

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"provider impact must not use report.get({key!r})")
        return super().get(key, default)


class BrokenProviderImpactTrustGet(dict):
    BROKEN_KEYS = {"reason_codes", "provider_sla_alerts"}

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"provider impact must not use trust.get({key!r})")
        return super().get(key, default)


class BrokenProviderImpactAlertGet(dict):
    BROKEN_KEYS = {
        "source",
        "provider",
        "alert_level",
        "current_status",
        "current_record_count",
        "current_source_has_healthy_entry",
        "current_stale",
    }

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"provider impact must not use alert.get({key!r})")
        return super().get(key, default)


class BrokenProviderImpactTruthText:
    def __init__(self, text: str):
        self.text = text

    def __bool__(self):
        raise RuntimeError("provider impact text truthiness unavailable")

    def __str__(self):
        return self.text


class BrokenProviderImpactTruthInt:
    def __init__(self, value: int):
        self.value = value

    def __bool__(self):
        raise RuntimeError("provider impact int truthiness unavailable")

    def __int__(self):
        return self.value


class BrokenProviderImpactLookupInt:
    def __int__(self):
        raise KeyError("provider impact int lookup unavailable")


class BrokenProviderImpactLookupBool:
    def __bool__(self):
        raise KeyError("provider impact bool lookup unavailable")


class BrokenProviderImpactTruthBool:
    def __bool__(self):
        raise RuntimeError("provider impact bool truthiness unavailable")


class BrokenProviderImpactString:
    def __str__(self):
        raise RuntimeError("provider impact reason code string unavailable")


class BrokenProviderImpactReasonCodeIterator(list):
    def __iter__(self):
        yield "provider_sla_critical"
        raise RuntimeError("provider impact reason code iterator unavailable")


class BrokenProviderImpactAlertIterator(list):
    def __iter__(self):
        yield {
            "source": "market_data",
            "provider": "yfinance",
            "alert_level": "critical",
            "current_status": "unavailable",
            "current_record_count": 0,
            "current_stale": False,
        }
        raise RuntimeError("provider impact alert iterator unavailable")


class BrokenProviderImpactReportIterator(list):
    def __init__(self):
        super().__init__([None])

    def __iter__(self):
        yield {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                    }
                ],
            },
        }
        raise RuntimeError("provider impact report iterator unavailable")


class BrokenProviderImpactNativeTextList(list):
    def __iter__(self):
        raise RuntimeError("provider impact text list iterator accessor unavailable")


class BrokenProviderImpactNativeDictList(list):
    def __iter__(self):
        raise RuntimeError("provider impact dict list iterator accessor unavailable")


class BrokenProviderImpactLookupIteratorTextList(list):
    def __iter__(self):
        raise KeyError("provider impact text list iterator creation lookup unavailable")


class BrokenProviderImpactLookupIteratorDictList(list):
    def __iter__(self):
        raise KeyError("provider impact dict list iterator creation lookup unavailable")


class BrokenProviderImpactFirstNextDictIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("provider impact dict list first item unavailable")


class BrokenProviderImpactFirstNextDictList(list):
    def __iter__(self):
        return BrokenProviderImpactFirstNextDictIterator()


class BrokenProviderImpactLookupDictIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("provider impact dict list lookup unavailable")


class BrokenProviderImpactLookupDictList(list):
    def __iter__(self):
        return BrokenProviderImpactLookupDictIterator()


class BrokenProviderImpactFirstNextTextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("provider impact text list first item unavailable")


class BrokenProviderImpactFirstNextTextList(list):
    def __iter__(self):
        return BrokenProviderImpactFirstNextTextIterator()


class BrokenProviderImpactLookupTextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("provider impact text list lookup unavailable")


class BrokenProviderImpactLookupTextList(list):
    def __iter__(self):
        return BrokenProviderImpactLookupTextIterator()


def test_provider_impact_keeps_core_critical_mapping_when_accessor_fails():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        BrokenProviderImpactReportGet(
            {
                "ticker": "NVDA",
                "filename": "nvda_report.html",
                "pipeline_id": "v2",
                "data_trust": BrokenProviderImpactTrustGet(
                    {
                        "reason_codes": ["provider_sla_critical"],
                        "provider_sla_alerts": [
                            BrokenProviderImpactAlertGet(
                                {
                                    "source": "market_data",
                                    "provider": "yfinance",
                                    "alert_level": "critical",
                                    "current_status": "unavailable",
                                    "current_record_count": 0,
                                    "current_source_has_healthy_entry": False,
                                    "current_stale": False,
                                }
                            )
                        ],
                    }
                ),
            }
        )
    )

    assert impact["ticker"] == "NVDA"
    assert impact["filename"] == "nvda_report.html"
    assert impact["pipeline_id"] == "v2"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source_scope"] == "core"
    assert impact["impacts"][0]["affects_core_data"] is True


def test_provider_impact_current_fetch_fields_do_not_depend_on_truthiness():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": BrokenProviderImpactTruthText("unavailable"),
                        "current_record_count": BrokenProviderImpactTruthInt(0),
                        "current_source_has_healthy_entry": BrokenProviderImpactTruthBool(),
                        "current_stale": BrokenProviderImpactTruthBool(),
                    }
                ],
            },
        }
    )

    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["current_fetch_healthy"] is False


def test_provider_impact_current_fetch_lookup_scalar_failures_do_not_interrupt_recovery_impact():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": BrokenProviderImpactLookupInt(),
                        "current_source_has_healthy_entry": BrokenProviderImpactLookupBool(),
                        "current_stale": BrokenProviderImpactLookupBool(),
                    }
                ],
            },
        }
    )

    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["current_fetch_healthy"] is False


def test_provider_impact_alert_text_fields_do_not_depend_on_truthiness():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [
                    {
                        "source": BrokenProviderImpactTruthText("market_data"),
                        "provider": BrokenProviderImpactTruthText("yfinance"),
                        "alert_level": BrokenProviderImpactTruthText("critical"),
                        "current_status": "unavailable",
                        "current_record_count": 0,
                        "current_stale": False,
                    }
                ],
            },
        }
    )

    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source"] == "market_data"
    assert impact["impacts"][0]["provider"] == "yfinance"
    assert impact["impacts"][0]["alert_level"] == "critical"


def test_provider_impact_report_identity_fields_do_not_depend_on_truthiness():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": BrokenProviderImpactTruthText("nvda_report.html"),
            "pipeline_id": BrokenProviderImpactTruthText("v2"),
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                    }
                ],
            },
        }
    )

    assert impact["filename"] == "nvda_report.html"
    assert impact["pipeline_id"] == "v2"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True


def test_provider_impact_ticker_output_is_json_safe():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": BrokenProviderImpactTruthText("NVDA"),
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                    }
                ],
            },
        }
    )

    assert impact["ticker"] == "NVDA"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    json.dumps(impact, ensure_ascii=False)


def test_provider_impact_reason_codes_preserve_valid_items_before_string_failures():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical", BrokenProviderImpactString()],
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                        "current_stale": False,
                    }
                ],
            },
        }
    )

    assert impact["reason_codes"] == ["provider_sla_critical"]
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True


def test_provider_impact_reason_codes_preserve_valid_items_before_iterator_failures():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": BrokenProviderImpactReasonCodeIterator(),
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                        "current_stale": False,
                    }
                ],
            },
        }
    )

    assert impact["reason_codes"] == ["provider_sla_critical"]
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True


def test_provider_impact_reason_code_tuple_sequences_preserve_blocking_evidence():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ("provider_sla_critical",),
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                        "current_stale": False,
                    }
                ],
            },
        }
    )

    assert impact["reason_codes"] == ["provider_sla_critical"]
    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True


def test_provider_impact_reason_code_native_lists_preserve_blocking_evidence():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": BrokenProviderImpactNativeTextList(["provider_sla_critical"]),
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                        "current_stale": False,
                    }
                ],
            },
        }
    )

    assert impact["reason_codes"] == ["provider_sla_critical"]
    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True


def test_provider_impact_reason_codes_survive_lookup_iterator_creation_failures():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": BrokenProviderImpactLookupIteratorTextList(["provider_sla_critical"]),
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                        "current_stale": False,
                    }
                ],
            },
        }
    )

    assert impact["reason_codes"] == ["provider_sla_critical"]
    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True


def test_provider_impact_reason_codes_survive_first_next_iterator_failures():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": BrokenProviderImpactFirstNextTextList(["provider_sla_critical"]),
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                        "current_stale": False,
                    }
                ],
            },
        }
    )

    assert impact["reason_codes"] == ["provider_sla_critical"]
    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True


def test_provider_impact_reason_codes_survive_lookup_iterator_failures():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": BrokenProviderImpactLookupTextList(["provider_sla_critical"]),
                "provider_sla_alerts": [
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                        "current_stale": False,
                    }
                ],
            },
        }
    )

    assert impact["reason_codes"] == ["provider_sla_critical"]
    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True


def test_provider_impact_alerts_preserve_valid_items_before_iterator_failures():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": BrokenProviderImpactAlertIterator(),
            },
        }
    )

    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source"] == "market_data"


def test_provider_impact_alert_native_lists_preserve_blocking_evidence():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": BrokenProviderImpactNativeDictList(
                    [
                        {
                            "source": "market_data",
                            "provider": "yfinance",
                            "alert_level": "critical",
                            "current_status": "unavailable",
                            "current_record_count": 0,
                            "current_stale": False,
                        }
                    ]
                ),
            },
        }
    )

    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source"] == "market_data"


def test_provider_impact_alerts_survive_first_next_iterator_failures():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": BrokenProviderImpactFirstNextDictList(
                    [
                        {
                            "source": "market_data",
                            "provider": "yfinance",
                            "alert_level": "critical",
                            "current_status": "unavailable",
                            "current_record_count": 0,
                            "current_stale": False,
                        }
                    ]
                ),
            },
        }
    )

    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source"] == "market_data"


def test_provider_impact_alerts_survive_lookup_iterator_failures():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": BrokenProviderImpactLookupDictList(
                    [
                        {
                            "source": "market_data",
                            "provider": "yfinance",
                            "alert_level": "critical",
                            "current_status": "unavailable",
                            "current_record_count": 0,
                            "current_stale": False,
                        }
                    ]
                ),
            },
        }
    )

    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source"] == "market_data"


def test_provider_impact_alerts_survive_lookup_iterator_creation_failures():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": BrokenProviderImpactLookupIteratorDictList(
                    [
                        {
                            "source": "market_data",
                            "provider": "yfinance",
                            "alert_level": "critical",
                            "current_status": "unavailable",
                            "current_record_count": 0,
                            "current_stale": False,
                        }
                    ]
                ),
            },
        }
    )

    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source"] == "market_data"


def test_provider_impact_alert_tuple_sequences_preserve_blocking_evidence():
    from provider_impact import build_provider_impact

    impact = build_provider_impact(
        {
            "ticker": "NVDA",
            "filename": "nvda_report.html",
            "pipeline_id": "v2",
            "data_trust": {
                "reason_codes": ["provider_sla_critical"],
                "provider_sla_alerts": (
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "alert_level": "critical",
                        "current_status": "unavailable",
                        "current_record_count": 0,
                        "current_stale": False,
                    },
                ),
            },
        }
    )

    assert impact["summary"]["max_severity"] == "critical"
    assert impact["summary"]["recommended_action"] == "wait_provider_recovery"
    assert impact["summary"]["blocks_auto_rerun"] is True
    assert impact["impacts"][0]["source"] == "market_data"
