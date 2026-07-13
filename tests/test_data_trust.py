import json
import sys
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import data_trust  # noqa: E402
import data_trust_audit  # noqa: E402
import data_trust_scoring  # noqa: E402
import data_fetch.audit_helpers as audit_helpers  # noqa: E402
import report_reproducibility  # noqa: E402
from data_fetch.constants import DATA_SCHEMA_VERSION  # noqa: E402
from fixtures.data_payloads import fresh_audited_payload, provider_sla_alert, stale_audited_payload  # noqa: E402


class BrokenTruthText:
    def __init__(self, text: str):
        self.text = text

    def __bool__(self):
        raise ValueError("text truthiness unavailable")

    def __str__(self):
        return self.text


class BrokenTruthInt:
    def __init__(self, value: int):
        self.value = value

    def __bool__(self):
        raise ValueError("int truthiness unavailable")

    def __int__(self):
        return self.value


class BrokenTruthBool:
    def __bool__(self):
        raise ValueError("bool truthiness unavailable")


class BrokenLookupInt:
    def __int__(self):
        raise KeyError("integer lookup unavailable")


class BrokenLookupBool:
    def __bool__(self):
        raise KeyError("bool lookup unavailable")


class BrokenTruthDict(dict):
    def __bool__(self):
        raise ValueError("dict truthiness unavailable")


class BrokenGetDict(dict):
    def get(self, *_args, **_kwargs):
        raise RuntimeError("mapping get unavailable")


class BrokenLookupCopyDict(dict):
    def __iter__(self):
        raise KeyError("mapping copy iterator lookup unavailable")

    def keys(self):
        raise KeyError("mapping copy lookup unavailable")

    def __getitem__(self, key):
        raise KeyError("mapping copy item lookup unavailable")


class BrokenLenDict(dict):
    def __len__(self):
        raise RuntimeError("mapping length unavailable")


class BrokenString:
    def __init__(self, text: str = "broken"):
        self.text = text

    def __str__(self):
        raise ValueError(f"{self.text} string conversion unavailable")


class BrokenFloatScore:
    def __float__(self):
        raise RuntimeError("score conversion unavailable")


class BrokenLookupFloatScore:
    def __float__(self):
        raise KeyError("score lookup unavailable")


class BrokenTargetRows(list):
    def __iter__(self):
        yield {"target_price": "NT$120"}
        raise RuntimeError("target row iteration unavailable")


class BrokenTargetNativeRows(list):
    def __iter__(self):
        raise RuntimeError("target native row iterator accessor unavailable")


class BrokenTargetFirstNextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("target row first item unavailable")


class BrokenTargetFirstNextRows(list):
    def __iter__(self):
        return BrokenTargetFirstNextIterator()


class BrokenTargetLookupNativeRows(list):
    def __iter__(self):
        raise KeyError("target native row iterator lookup unavailable")


class BrokenTargetLookupNextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("target row lookup iterator unavailable")


class BrokenTargetLookupNextRows(list):
    def __iter__(self):
        return BrokenTargetLookupNextIterator()


class BrokenTargetMapping(dict):
    def items(self):
        yield ("recommendation", {"target_price": "NT$120"})
        raise RuntimeError("target mapping iteration unavailable")


class BrokenTargetNativeMapping(dict):
    def items(self):
        raise RuntimeError("target mapping items accessor unavailable")


class BrokenTargetLookupNativeMapping(dict):
    def items(self):
        raise KeyError("target mapping items lookup unavailable")


class BrokenTargetFirstNextItems:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("target mapping first item unavailable")


class BrokenTargetFirstNextMapping(dict):
    def items(self):
        return BrokenTargetFirstNextItems()


class BrokenTargetLookupNextItems:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("target mapping lookup iterator unavailable")


class BrokenTargetLookupNextMapping(dict):
    def items(self):
        return BrokenTargetLookupNextItems()


class BrokenTargetItemsIterable:
    def __iter__(self):
        raise RuntimeError("target mapping items iterator unavailable")


class BrokenTargetItemsIterableMapping(dict):
    def items(self):
        return BrokenTargetItemsIterable()


class BrokenNativeRowsList(list):
    def __iter__(self):
        raise RuntimeError("native row list iterator accessor unavailable")


class BrokenNativeTextList(list):
    def __iter__(self):
        raise RuntimeError("native text list iterator accessor unavailable")


class BrokenProviderSlaLookupIteratorRowsList(list):
    def __iter__(self):
        raise KeyError("provider SLA row iterator creation lookup unavailable")


class BrokenProviderSlaLookupIteratorTextList(list):
    def __iter__(self):
        raise KeyError("provider SLA text iterator creation lookup unavailable")


class BrokenProviderSlaFirstNextRowsIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("provider SLA row first item unavailable")


class BrokenProviderSlaFirstNextRowsList(list):
    def __iter__(self):
        return BrokenProviderSlaFirstNextRowsIterator()


class BrokenProviderSlaLookupNextRowsIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("provider SLA row lookup iterator unavailable")


class BrokenProviderSlaLookupNextRowsList(list):
    def __iter__(self):
        return BrokenProviderSlaLookupNextRowsIterator()


class BrokenProviderSlaFirstNextTextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("provider SLA text first item unavailable")


class BrokenProviderSlaFirstNextTextList(list):
    def __iter__(self):
        return BrokenProviderSlaFirstNextTextIterator()


class BrokenProviderSlaLookupNextTextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("provider SLA text lookup iterator unavailable")


class BrokenProviderSlaLookupNextTextList(list):
    def __iter__(self):
        return BrokenProviderSlaLookupNextTextIterator()


class BrokenNativeTuple(tuple):
    def __iter__(self):
        raise RuntimeError("native tuple iterator accessor unavailable")


class BrokenNativeSet(set):
    def __iter__(self):
        raise RuntimeError("native set iterator accessor unavailable")


class BrokenNativeFrozenSet(frozenset):
    def __iter__(self):
        raise RuntimeError("native frozenset iterator accessor unavailable")


class BrokenLookupNativeSet(set):
    def __iter__(self):
        raise KeyError("native set iterator lookup unavailable")


class BrokenLookupNativeFrozenSet(frozenset):
    def __iter__(self):
        raise KeyError("native frozenset iterator lookup unavailable")


class BrokenLookupSetIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("set iterator lookup unavailable")


class BrokenLookupNextSet(set):
    def __iter__(self):
        return BrokenLookupSetIterator()


class BrokenLookupNextFrozenSet(frozenset):
    def __iter__(self):
        return BrokenLookupSetIterator()


class BrokenFirstNextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("snapshot sequence first item unavailable")


class BrokenSnapshotFirstNextRows(list):
    def __iter__(self):
        return BrokenFirstNextIterator()


class BrokenNativeSnapshotMapping(dict):
    def items(self):
        raise RuntimeError("native snapshot mapping items accessor unavailable")


class BrokenItemsIterable:
    def __iter__(self):
        raise RuntimeError("snapshot mapping items iterable unavailable")


class BrokenSnapshotItemsIterableMapping(dict):
    def items(self):
        return BrokenItemsIterable()


class BrokenSnapshotFirstNextItems:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("snapshot mapping first item unavailable")


class BrokenSnapshotFirstNextMapping(dict):
    def items(self):
        return BrokenSnapshotFirstNextItems()


class BrokenSnapshotLookupFieldMapping(Mapping):
    def __init__(self, snapshot: dict):
        self._snapshot = snapshot

    def __getitem__(self, key):
        return self._snapshot[key]

    def __iter__(self):
        return iter(self._snapshot)

    def __len__(self):
        return len(self._snapshot)

    def __contains__(self, _key):
        raise KeyError("snapshot field containment lookup unavailable")

    def get(self, *_args, **_kwargs):
        raise KeyError("snapshot field get lookup unavailable")


def test_source_audit_success_error_and_skipped_cache_entries():
    data = {
        "ticker": "2330.TW",
        "current_price": 100,
        "years": ["2024", "2025"],
        "revenue_history": [10, 12],
        "net_income_history": [2, 3],
        "recent_catalysts": [{"title": "cached"}],
        "source_freshness": {
            "market_data": {"fetched_at_epoch": 100.0, "stale": False},
            "financial_statements": {"fetched_at_epoch": 100.0, "stale": False},
            "recent_catalysts": {"fetched_at_epoch": 100.0, "stale": False},
        },
    }

    audit_helpers._append_source_fetch_audit(
        data,
        "market_data",
        "yfinance",
        data_trust.AUDIT_STATUS_SUCCESS,
        fetched_at_epoch=100.0,
        started_at_epoch=99.5,
        finished_at_epoch=100.0,
    )
    audit_helpers._append_source_fetch_audit(
        data,
        "financial_statements",
        "yfinance",
        data_trust.AUDIT_STATUS_ERROR,
        fetched_at_epoch=100.0,
        started_at_epoch=99.0,
        finished_at_epoch=100.0,
        record_count=0,
        error_kind="missing_data",
        message="annual statement missing",
    )
    audit_helpers._append_skipped_fresh_cache_audit(data, ("recent_catalysts",), now_epoch=105.0)

    entries = data["source_audit"]
    assert entries[0]["status"] == "success"
    assert entries[0]["duration_ms"] == 500
    assert entries[1]["status"] == "error"
    assert entries[1]["error_kind"] == "missing_data"
    assert entries[2]["status"] == "skipped_fresh_cache"
    assert entries[2]["cache_hit"] is True


def test_source_audit_entry_text_fields_do_not_depend_on_truthiness():
    entry = data_trust.build_source_audit_entry(
        BrokenTruthText("market_data"),
        BrokenTruthText("fallback-provider"),
        "error",
        record_count=0,
        error_kind=BrokenTruthText("ConnectionError"),
        message=BrokenTruthText("temporary provider failure"),
    )

    assert entry["source"] == "market_data"
    assert entry["provider"] == "fallback-provider"
    assert entry["error_kind"] == "ConnectionError"
    assert entry["message"] == "temporary provider failure"


def test_source_audit_entry_text_fields_use_shared_text_safety_for_malformed_inputs():
    entry = data_trust.build_source_audit_entry(
        True,
        b"bad-provider",
        memoryview(b"success"),
        record_count=1,
        error_kind=True,
        message=bytearray(b"bad-message"),
    )

    assert entry["source"] == "unknown"
    assert entry["provider"] == ""
    assert entry["status"] == data_trust.AUDIT_STATUS_UNAVAILABLE
    assert entry["error_kind"] == ""
    assert entry["message"] == ""


def test_source_audit_entry_fetched_at_uses_safe_text_before_epoch_fallback():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        "success",
        fetched_at=True,
        fetched_at_epoch=100.0,
    )

    assert entry["fetched_at"] == "1970-01-01T00:01:40+00:00"


def test_source_audit_entry_fetched_at_epoch_validates_before_finished_fallback():
    for fetched_at_epoch in (True, float("nan"), float("inf")):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            fetched_at_epoch=fetched_at_epoch,
            finished_at_epoch=100.0,
        )

        assert entry["fetched_at"] == "1970-01-01T00:01:40+00:00"


def test_source_audit_entry_fetched_at_epoch_range_errors_fallback_to_finished_timestamp():
    entry = None
    error = None
    try:
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            fetched_at_epoch=1e20,
            finished_at_epoch=100.0,
        )
    except (OSError, OverflowError, ValueError) as exc:
        error = exc

    assert error is None
    assert entry["fetched_at"] == "1970-01-01T00:01:40+00:00"


def test_source_audit_entry_finished_at_epoch_uses_current_time_when_malformed(monkeypatch):
    monkeypatch.setattr(data_trust_audit.time, "time", lambda: 100.0)

    for finished_at_epoch in (True, 0, -1, float("nan"), float("inf")):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            finished_at_epoch=finished_at_epoch,
        )

        assert entry["fetched_at"] == "1970-01-01T00:01:40+00:00"


def test_source_audit_entry_status_uses_safe_text_conversion():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        BrokenTruthText("success"),
        record_count=1,
    )

    assert entry["status"] == "success"


def test_source_audit_entry_duration_ignores_boolean_override_and_uses_epoch_delta():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        "success",
        started_at_epoch=99.5,
        finished_at_epoch=100.0,
        duration_ms=True,
    )

    assert entry["duration_ms"] == 500


def test_source_audit_entry_duration_ignores_non_finite_override_and_uses_epoch_delta():
    for duration_override in (float("nan"), float("inf"), float("-inf")):
        entry = None
        error = None
        try:
            entry = data_trust.build_source_audit_entry(
                "market_data",
                "fallback-provider",
                "success",
                started_at_epoch=99.5,
                finished_at_epoch=100.0,
                duration_ms=duration_override,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            error = exc

        assert error is None
        assert entry["duration_ms"] == 500


def test_source_audit_entry_duration_ignores_overflowing_override_and_uses_epoch_delta():
    entry = None
    error = None
    try:
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            started_at_epoch=99.5,
            finished_at_epoch=100.0,
            duration_ms=10**400,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        error = exc

    assert error is None
    assert entry["duration_ms"] == 500


def test_source_audit_entry_duration_ignores_non_finite_epoch_delta():
    for started_at_epoch, finished_at_epoch in (
        (float("nan"), 100.0),
        (99.5, float("inf")),
        (float("-inf"), 100.0),
    ):
        entry = None
        error = None
        try:
            entry = data_trust.build_source_audit_entry(
                "market_data",
                "fallback-provider",
                "success",
                started_at_epoch=started_at_epoch,
                finished_at_epoch=finished_at_epoch,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            error = exc

        assert error is None
        assert entry["duration_ms"] is None


def test_source_audit_entry_duration_ignores_overflowing_epoch_delta():
    for started_at_epoch, finished_at_epoch in (
        (10**400, 100.0),
        (99.5, 10**400),
    ):
        entry = None
        error = None
        try:
            entry = data_trust.build_source_audit_entry(
                "market_data",
                "fallback-provider",
                "success",
                started_at_epoch=started_at_epoch,
                finished_at_epoch=finished_at_epoch,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            error = exc

        assert error is None
        assert entry["duration_ms"] is None


def test_source_audit_entry_duration_ignores_out_of_range_epoch_delta(monkeypatch):
    monkeypatch.setattr(data_trust_audit.time, "time", lambda: 100.0)

    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        "success",
        started_at_epoch=99.5,
        finished_at_epoch=1e20,
    )

    assert entry["fetched_at"] == "1970-01-01T00:01:40+00:00"
    assert entry["duration_ms"] is None


def test_source_audit_entry_record_count_does_not_depend_on_truthiness():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        "success",
        record_count=BrokenTruthInt(7),
    )

    assert entry["record_count"] == 7


def test_source_audit_entry_record_count_treats_bool_as_malformed_count():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        "success",
        record_count=True,
    )

    assert entry["record_count"] == 0


def test_source_audit_entry_record_count_treats_fractional_numbers_as_malformed_counts():
    for record_count in (1.5, Decimal("2.5")):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            record_count=record_count,
        )

        assert entry["record_count"] == 0


def test_source_audit_entry_bool_fields_do_not_depend_on_truthiness():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        "success",
        cache_hit=BrokenTruthBool(),
        stale=BrokenTruthBool(),
    )

    assert entry["cache_hit"] is False
    assert entry["stale"] is False


def test_source_audit_entry_bool_fields_treat_lookup_truthiness_failures_as_false():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        "success",
        cache_hit=BrokenLookupBool(),
        stale=BrokenLookupBool(),
    )

    assert entry["cache_hit"] is False
    assert entry["stale"] is False


def test_source_audit_entry_bool_fields_treat_false_text_as_false():
    for false_text in ("false", "False", "0", "no", "off", ""):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=false_text,
            stale=false_text,
        )

        assert entry["cache_hit"] is False
        assert entry["stale"] is False


def test_source_audit_entry_bool_fields_treat_numeric_text_as_numeric_values():
    explicit_values = (("0.0", False), ("1.0", True))
    malformed_values = (("0.5", False), ("2", False), ("-1", False), ("NaN", False), ("Infinity", False))
    for raw_value, expected_bool in explicit_values + malformed_values:
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=raw_value,
            stale=raw_value,
        )

        assert entry["cache_hit"] is expected_bool
        assert entry["stale"] is expected_bool


def test_source_audit_entry_bool_fields_treat_freeform_text_as_malformed():
    for malformed_text in ("cached", "stale", "unknown", "N/A", "enabled-ish"):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=malformed_text,
            stale=malformed_text,
        )

        assert entry["cache_hit"] is False
        assert entry["stale"] is False


def test_source_audit_entry_bool_fields_treat_binary_values_as_malformed():
    for malformed_value in (b"false", bytearray(b"true"), memoryview(b"1")):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=malformed_value,
            stale=malformed_value,
        )

        assert entry["cache_hit"] is False
        assert entry["stale"] is False


def test_source_audit_entry_bool_fields_treat_non_finite_numbers_as_malformed():
    for malformed_value in (float("nan"), float("inf"), float("-inf"), Decimal("NaN")):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=malformed_value,
            stale=malformed_value,
        )

        assert entry["cache_hit"] is False
        assert entry["stale"] is False


def test_source_audit_entry_bool_fields_treat_fractional_numbers_as_malformed():
    for malformed_value in (0.5, -0.5, Decimal("0.5"), Decimal("2")):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=malformed_value,
            stale=malformed_value,
        )

        assert entry["cache_hit"] is False
        assert entry["stale"] is False


def test_source_audit_entry_bool_fields_treat_rational_numbers_as_numeric_values():
    explicit_values = ((Fraction(0, 1), False), (Fraction(1, 1), True))
    malformed_values = ((Fraction(1, 2), False), (Fraction(2, 1), False))
    for raw_value, expected_bool in explicit_values + malformed_values:
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=raw_value,
            stale=raw_value,
        )

        assert entry["cache_hit"] is expected_bool
        assert entry["stale"] is expected_bool


def test_source_audit_entry_bool_fields_treat_overflowing_real_numbers_as_malformed():
    for malformed_value in (10**400, Fraction(10**400, 1)):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=malformed_value,
            stale=malformed_value,
        )

        assert entry["cache_hit"] is False
        assert entry["stale"] is False


def test_source_audit_entry_bool_fields_treat_complex_numbers_as_malformed():
    for malformed_value in (complex(1, 0), complex(0, 1)):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=malformed_value,
            stale=malformed_value,
        )

        assert entry["cache_hit"] is False
        assert entry["stale"] is False


def test_source_audit_entry_bool_fields_treat_containers_as_malformed():
    for malformed_value in ([False], (True,), {"value": False}, {True}, frozenset({False})):
        entry = data_trust.build_source_audit_entry(
            "market_data",
            "fallback-provider",
            "success",
            cache_hit=malformed_value,
            stale=malformed_value,
        )

        assert entry["cache_hit"] is False
        assert entry["stale"] is False


def test_source_record_count_source_key_does_not_depend_on_truthiness():
    count = data_trust.source_record_count(
        BrokenTruthText("market_data"),
        {
            "current_price": 100,
            "market_cap_raw": 200,
            "pe_ratio_raw": None,
            "pb_ratio": "N/A",
            "price_history": [99, 100],
        },
    )

    assert count == 3


def test_source_record_count_root_data_uses_mapping_safe_field_reads():
    count = data_trust.source_record_count(
        "market_data",
        BrokenGetDict(
            {
                "current_price": 100,
                "market_cap_raw": None,
                "pe_ratio_raw": None,
                "pb_ratio": None,
                "price_history": [99, 100],
            }
        ),
    )

    assert count == 2


def test_source_record_count_institutional_trading_uses_mapping_safe_field_reads():
    count = data_trust.source_record_count(
        "institutional_trading",
        {
            "institutional_trading": BrokenGetDict(
                {"daily_total_net_buy_last_10": [{"date": "2026-07-10"}]}
            )
        },
    )

    assert count == 1


def test_source_record_count_institutional_trading_empty_daily_only_is_missing():
    count = data_trust.source_record_count(
        "institutional_trading",
        {"institutional_trading": {"daily_total_net_buy_last_10": []}},
    )

    assert count == 0


def test_source_record_count_global_market_context_uses_mapping_safe_field_reads():
    count = data_trust.source_record_count(
        "global_market_context",
        {"global_market_context": BrokenGetDict({"items": [{"region": "US"}]})},
    )

    assert count == 1


def test_source_record_count_international_news_context_uses_mapping_safe_field_reads():
    count = data_trust.source_record_count(
        "international_news_context",
        {"international_news_context": BrokenGetDict({"topics": [{"headline": "Fed"}]})},
    )

    assert count == 1


def test_source_record_count_pe_river_chart_uses_mapping_safe_field_reads():
    count = data_trust.source_record_count(
        "pe_river_chart",
        {"pe_river_chart": BrokenGetDict({"years": ["2024"], "eps_twd": []})},
    )

    assert count == 1


def test_source_record_count_pe_river_chart_bands_use_mapping_safe_count():
    count = data_trust.source_record_count(
        "pe_river_chart",
        {
            "pe_river_chart": {
                "bands": MappingProxyType(
                    {
                        "low": [10, 11],
                        "mid": [12],
                    }
                )
            }
        },
    )

    assert count == 2


def test_source_record_count_pe_river_chart_empty_bands_fall_back_to_years():
    count = data_trust.source_record_count(
        "pe_river_chart",
        {
            "pe_river_chart": {
                "bands": {"low": (), "mid": []},
                "years": ["2024", "2025"],
                "eps_twd": [],
            }
        },
    )

    assert count == 2


def test_source_record_count_lists_use_native_sequence_fallback():
    count = data_trust.source_record_count(
        "financial_statements",
        {
            "years": BrokenNativeRowsList(["2024", "2025"]),
            "revenue_history": [],
            "net_income_history": [],
            "fcf_history": [],
        },
    )

    assert count == 2


def test_source_record_count_tuple_source_values_count_as_rows():
    count = data_trust.source_record_count(
        "custom_enrichment",
        {"custom_enrichment": ({"headline": "A"}, {"headline": "B"})},
    )

    assert count == 2


def test_source_record_count_default_mapping_values_use_mapping_safe_count():
    count = data_trust.source_record_count(
        "custom_metrics",
        {"custom_metrics": BrokenLenDict({"alpha": 1, "beta": 2})},
    )

    assert count == 2


def test_source_record_count_default_mapping_values_require_child_values():
    count = data_trust.source_record_count(
        "custom_metrics",
        {"custom_metrics": {"alpha": None, "beta": "", "gamma": []}},
    )

    assert count == 0


def test_source_record_count_value_presence_avoids_mapping_truthiness():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": None,
            "market_cap_raw": None,
            "pe_ratio_raw": None,
            "pb_ratio": None,
            "price_history": BrokenTruthDict({"dates": ["2026-06-07"], "prices": [100]}),
        },
    )

    assert count == 1


def test_source_record_count_value_presence_treats_empty_tuple_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": None,
            "market_cap_raw": None,
            "pe_ratio_raw": None,
            "pb_ratio": None,
            "price_history": (),
        },
    )

    assert count == 0


def test_source_record_count_value_presence_treats_boolean_scalars_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": False,
            "market_cap_raw": True,
            "pe_ratio_raw": None,
            "pb_ratio": None,
            "price_history": None,
        },
    )

    assert count == 0


def test_source_record_count_value_presence_treats_non_finite_numbers_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": float("nan"),
            "market_cap_raw": float("inf"),
            "pe_ratio_raw": float("-inf"),
            "pb_ratio": None,
            "price_history": None,
        },
    )

    assert count == 0


def test_source_record_count_value_presence_treats_overflowing_numbers_as_missing():
    for overflowing_number in (10**400, Fraction(10**400, 1)):
        count = None
        error = None
        try:
            count = data_trust.source_record_count(
                "market_data",
                {
                    "current_price": overflowing_number,
                    "market_cap_raw": None,
                    "pe_ratio_raw": None,
                    "pb_ratio": None,
                    "price_history": None,
                },
            )
        except OverflowError as exc:
            error = exc

        assert error is None
        assert count == 0


def test_source_record_count_value_presence_treats_non_finite_numeric_strings_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": "NaN",
            "market_cap_raw": "Infinity",
            "pe_ratio_raw": "-Infinity",
            "pb_ratio": "0",
            "price_history": None,
        },
    )

    assert count == 1


def test_source_record_count_value_presence_treats_placeholder_strings_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": "None",
            "market_cap_raw": "null",
            "pe_ratio_raw": "--",
            "pb_ratio": "0",
            "price_history": None,
        },
    )

    assert count == 1


def test_source_record_count_value_presence_treats_non_finite_decimals_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": Decimal("NaN"),
            "market_cap_raw": Decimal("Infinity"),
            "pe_ratio_raw": Decimal("-Infinity"),
            "pb_ratio": Decimal("0"),
            "price_history": None,
        },
    )

    assert count == 1


def test_source_record_count_value_presence_treats_binary_scalars_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": b"101.5",
            "market_cap_raw": bytearray(b"2000"),
            "pe_ratio_raw": memoryview(b"15"),
            "pb_ratio": None,
            "price_history": None,
        },
    )

    assert count == 0


def test_source_record_count_value_presence_treats_complex_scalars_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": complex(101.5, 0),
            "market_cap_raw": complex(2000, 1),
            "pe_ratio_raw": None,
            "pb_ratio": None,
            "price_history": None,
        },
    )

    assert count == 0


def test_source_record_count_value_presence_treats_empty_mapping_proxy_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": None,
            "market_cap_raw": None,
            "pe_ratio_raw": None,
            "pb_ratio": None,
            "price_history": MappingProxyType({}),
        },
    )

    assert count == 0


def test_source_record_count_value_presence_treats_empty_set_as_missing():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": None,
            "market_cap_raw": None,
            "pe_ratio_raw": None,
            "pb_ratio": None,
            "price_history": set(),
        },
    )

    assert count == 0


def test_source_record_count_set_source_values_count_as_rows():
    count = data_trust.source_record_count(
        "custom_enrichment",
        {"custom_enrichment": {"alpha", "beta"}},
    )

    assert count == 2


def test_source_record_count_set_source_values_use_native_iterator_fallback():
    for row_batch in (BrokenNativeSet({"alpha", "beta"}), BrokenNativeFrozenSet({"alpha", "beta"})):
        count = data_trust.source_record_count(
            "custom_enrichment",
            {"custom_enrichment": row_batch},
        )

        assert count == 2


def test_source_record_count_set_source_values_survive_lookup_iterator_creation_failures():
    for row_batch in (BrokenLookupNativeSet({"alpha", "beta"}), BrokenLookupNativeFrozenSet({"alpha", "beta"})):
        count = data_trust.source_record_count(
            "custom_enrichment",
            {"custom_enrichment": row_batch},
        )

        assert count == 2


def test_source_record_count_set_source_values_survive_lookup_iterator_failures():
    for row_batch in (BrokenLookupNextSet({"alpha", "beta"}), BrokenLookupNextFrozenSet({"alpha", "beta"})):
        count = data_trust.source_record_count(
            "custom_enrichment",
            {"custom_enrichment": row_batch},
        )

        assert count == 2


def test_source_record_count_value_presence_requires_sequence_items_with_value():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": None,
            "market_cap_raw": None,
            "pe_ratio_raw": None,
            "pb_ratio": None,
            "price_history": [None, "", "N/A"],
        },
    )

    assert count == 0


def test_source_record_count_value_presence_requires_mapping_children_with_value():
    count = data_trust.source_record_count(
        "market_data",
        {
            "current_price": None,
            "market_cap_raw": None,
            "pe_ratio_raw": None,
            "pb_ratio": None,
            "price_history": {"dates": [], "prices": []},
        },
    )

    assert count == 0


def test_append_source_audit_preserves_tuple_entries():
    payload = {"source_audit": ({"source": "market_data", "provider": "yfinance"},)}

    result = data_trust.append_source_audit(
        payload,
        {"source": "financial_statements", "provider": "yfinance"},
    )

    assert result is payload
    assert payload["source_audit"] == [
        {"source": "market_data", "provider": "yfinance"},
        {"source": "financial_statements", "provider": "yfinance"},
    ]


def test_normalize_data_trust_uses_dict_native_field_reads():
    alert = {"provider": "yfinance", "alert_level": "warning"}

    normalized = data_trust.normalize_data_trust(
        BrokenGetDict(
            {
                "status": "partial",
                "critical_failures": ["financial_statements"],
                "stale_sources": ["market_data"],
                "last_market_data_at": "2026-06-07T01:00:00+00:00",
                "notes": ["核心來源部分降級。"],
                "reason_codes": ["provider_sla_warning"],
                "score": 72,
                "score_reasons": ["manual score"],
                "provider_sla_alerts": [alert],
            }
        )
    )

    assert normalized == {
        "status": "partial",
        "critical_failures": ["financial_statements"],
        "stale_sources": ["market_data"],
        "last_market_data_at": "2026-06-07T01:00:00+00:00",
        "notes": ["核心來源部分降級。"],
        "reason_codes": ["provider_sla_warning"],
        "score": 72,
        "score_reasons": ["manual score"],
        "provider_sla_alerts": [alert],
    }


def test_normalize_data_trust_accepts_mapping_safe_payloads():
    alert = MappingProxyType({"provider": "yfinance", "alert_level": "warning"})
    trust_payload = MappingProxyType(
        {
            "status": "fresh",
            "critical_failures": (),
            "stale_sources": (),
            "last_market_data_at": " 2026-06-07T01:00:00+00:00 ",
            "notes": ("只讀 payload 仍保留有效資料可信度。",),
            "reason_codes": ("fresh_core_sources",),
            "score": 91,
            "score_reasons": ("manual score reason",),
            "provider_sla_alerts": (alert,),
        }
    )

    normalized = data_trust.normalize_data_trust(trust_payload)

    assert normalized["status"] == "fresh"
    assert normalized["score"] == 91
    assert normalized["last_market_data_at"] == "2026-06-07T01:00:00+00:00"
    assert normalized["notes"] == ["只讀 payload 仍保留有效資料可信度。"]
    assert normalized["reason_codes"] == ["fresh_core_sources"]
    assert normalized["score_reasons"] == ["manual score reason"]
    assert normalized["provider_sla_alerts"] == [{"provider": "yfinance", "alert_level": "warning"}]


def test_normalize_data_trust_reason_codes_do_not_depend_on_truthiness():
    normalized = data_trust.normalize_data_trust(
        {
            "status": "fresh",
            "score": 90,
            "reason_codes": BrokenTruthText("manual_reason"),
        }
    )

    assert normalized["reason_codes"] == ["manual_reason"]


def test_normalize_data_trust_notes_use_string_list_conversion():
    normalized = data_trust.normalize_data_trust(
        {
            "status": "fresh",
            "score": 90,
            "notes": ("有效資料可信度備註。", b"bad-note"),
        }
    )

    assert normalized["notes"] == ["有效資料可信度備註。"]


def test_normalize_data_trust_text_lists_drop_non_finite_numeric_items():
    normalized = data_trust.normalize_data_trust(
        {
            "status": "partial",
            "score": 72,
            "critical_failures": [float("inf"), "market_data"],
            "stale_sources": [float("-inf"), "financial_statements"],
            "notes": [float("nan"), Decimal("NaN"), "有效資料可信度備註。"],
            "reason_codes": [Decimal("Infinity"), "manual_reason"],
            "score_reasons": [float("inf"), "manual score reason"],
        }
    )

    assert normalized["critical_failures"] == ["market_data"]
    assert normalized["stale_sources"] == ["financial_statements"]
    assert normalized["notes"] == ["有效資料可信度備註。"]
    assert normalized["reason_codes"] == ["manual_reason"]
    assert normalized["score_reasons"] == ["manual score reason"]


def test_normalize_data_trust_score_treats_boolean_values_as_malformed():
    for score in (True, False):
        normalized = data_trust.normalize_data_trust(
            {
                "status": "fresh",
                "score": score,
                "reason_codes": ["fresh_core_sources"],
            }
        )

        assert normalized["score"] == 95


def test_normalize_data_trust_last_market_data_at_uses_safe_text_conversion():
    normalized = data_trust.normalize_data_trust(
        {
            "status": "fresh",
            "score": 90,
            "last_market_data_at": " 2026-06-07T01:00:00+00:00 ",
        }
    )

    assert normalized["last_market_data_at"] == "2026-06-07T01:00:00+00:00"

    for malformed_timestamp in (True, False, b"2026-06-07T01:00:00+00:00", memoryview(b"bad")):
        normalized = data_trust.normalize_data_trust(
            {
                "status": "fresh",
                "score": 90,
                "last_market_data_at": malformed_timestamp,
            }
        )

        assert normalized["last_market_data_at"] is None


def test_normalize_data_trust_text_lists_use_native_sequence_fallback():
    normalized = data_trust.normalize_data_trust(
        {
            "status": "partial",
            "critical_failures": BrokenNativeTextList(["market_data"]),
            "stale_sources": BrokenNativeTextList(["financial_statements"]),
            "notes": BrokenNativeTextList(["有效資料可信度備註。"]),
            "reason_codes": BrokenNativeTextList(["manual_reason"]),
            "score_reasons": BrokenNativeTextList(["manual score reason"]),
            "score": 72,
        }
    )

    assert normalized["critical_failures"] == ["market_data"]
    assert normalized["stale_sources"] == ["financial_statements"]
    assert normalized["notes"] == ["有效資料可信度備註。"]
    assert normalized["reason_codes"] == ["manual_reason"]
    assert normalized["score_reasons"] == ["manual score reason"]


def test_normalize_data_trust_provider_sla_alerts_use_dict_list_conversion():
    alert = {"provider": "yfinance", "alert_level": "warning"}

    for alerts in ((alert,), BrokenNativeRowsList([alert])):
        normalized = data_trust.normalize_data_trust(
            {
                "status": "partial",
                "score": 72,
                "provider_sla_alerts": alerts,
            }
        )

        assert normalized.get("provider_sla_alerts") == [alert]


def test_data_trust_statuses_fresh_stale_error_unknown():
    fresh = fresh_audited_payload(provider="yfinance")
    fresh_trust = data_trust.build_data_trust(fresh)
    assert fresh_trust["status"] == "fresh"
    assert fresh_trust["score"] >= 90
    assert "fresh_core_sources" in fresh_trust["reason_codes"]

    stale = stale_audited_payload(source="market_data")
    stale_trust = data_trust.build_data_trust(stale)
    assert stale_trust["status"] == "stale"
    assert 0 <= stale_trust["score"] < fresh_trust["score"]
    assert "market_data" in stale_trust["stale_sources"]

    error = {
        "source_audit": [
            data_trust.build_source_audit_entry("market_data", "yfinance", "error", record_count=0),
            data_trust.build_source_audit_entry("financial_statements", "yfinance", "error", record_count=0),
        ]
    }
    trust = data_trust.build_data_trust(error)
    assert trust["status"] == "error"
    assert trust["score"] <= 20
    assert trust["critical_failures"] == ["market_data", "financial_statements"]

    unknown = data_trust.build_data_trust({})
    assert unknown["status"] == "unknown"
    assert unknown["score"] == 35
    assert unknown["score_reasons"]
    assert "missing_data_trust_snapshot" in unknown["reason_codes"]


def test_data_trust_scoring_uses_shared_text_safety_for_audit_source_names(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": True, "status": "error", "record_count": 0},
                {"source": b"market_data", "status": "error", "record_count": 0},
                {"source": memoryview(b"financial_statements"), "status": "error", "record_count": 0},
                {"source": "market_data", "status": "success", "record_count": 1},
                {"source": "financial_statements", "status": "success", "record_count": 1},
            ]
        }
    )

    assert trust["status"] == "fresh"
    assert "fresh_core_sources" in trust["reason_codes"]
    assert not any(code.startswith("optional_source_error:") for code in trust["reason_codes"])


def test_latest_audit_by_source_uses_safe_row_conversion():
    latest = data_trust_scoring.latest_audit_by_source(
        [
            BrokenGetDict({"source": "market_data", "status": "success"}),
            BrokenGetDict({"source": "financial_statements", "status": "error"}),
        ]
    )

    assert latest["market_data"]["status"] == "success"
    assert latest["financial_statements"]["status"] == "error"


def test_optional_sources_with_status_uses_safe_row_conversion():
    optional_sources = data_trust_scoring.optional_sources_with_status(
        BrokenGetDict(
            {
                "market_data": BrokenGetDict({"status": BrokenTruthText("not_configured")}),
                "recent_catalysts": BrokenGetDict({"status": BrokenTruthText("not_configured")}),
                "peer_discovery": BrokenGetDict({"status": "degraded_enrichment"}),
            }
        ),
        "not_configured",
    )

    assert optional_sources == ["recent_catalysts"]


def test_has_usable_critical_data_uses_safe_audit_maps():
    assert data_trust_scoring.has_usable_critical_data(
        {},
        BrokenGetDict(
            {
                "market_data": BrokenGetDict({"status": BrokenTruthText("success")}),
                "financial_statements": BrokenGetDict({"status": BrokenTruthText("skipped_fresh_cache")}),
            }
        ),
    ) is True


def test_build_data_trust_uses_string_safe_audit_status_comparison(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": "market_data", "status": BrokenTruthText("error"), "record_count": 0},
                {"source": "financial_statements", "status": BrokenTruthText("error"), "record_count": 0},
            ]
        }
    )

    assert trust["status"] == "error"
    assert trust["critical_failures"] == ["market_data", "financial_statements"]
    assert "critical_sources_error" in trust["reason_codes"]


def test_build_data_trust_last_market_timestamp_uses_safe_text(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    trust = data_trust.build_data_trust(
        {
            "source_freshness": {
                "market_data": {"fetched_at": BrokenTruthText("2026-06-01T00:00:00+00:00")},
            },
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ],
        }
    )

    assert trust["status"] == "fresh"
    assert trust["last_market_data_at"] == "2026-06-01T00:00:00+00:00"


def test_build_data_trust_final_score_uses_safe_post_sla_mapping(monkeypatch):
    def fake_apply_provider_sla_to_trust(_data, _trust):
        return BrokenGetDict(
            {
                "status": "partial",
                "critical_failures": ["market_data"],
                "stale_sources": [],
                "last_market_data_at": None,
                "notes": ["Provider SLA 後仍需保留信心分數。"],
                "reason_codes": ["source_error:market_data"],
            }
        )

    monkeypatch.setattr(data_trust_scoring, "apply_provider_sla_to_trust", fake_apply_provider_sla_to_trust)
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ]
        }
    )

    assert trust["status"] == "partial"
    assert trust["score"] == 60
    assert "核心來源異常：market_data" in trust["score_reasons"]


def test_build_data_trust_post_sla_status_uses_canonical_status(monkeypatch):
    def fake_apply_provider_sla_to_trust(_data, _trust):
        return {
            "status": "surprising-status",
            "critical_failures": [],
            "stale_sources": [],
            "last_market_data_at": None,
            "notes": ["Provider SLA 回傳非 canonical status。"],
            "reason_codes": ["fresh_core_sources"],
        }

    monkeypatch.setattr(data_trust_scoring, "apply_provider_sla_to_trust", fake_apply_provider_sla_to_trust)
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ]
        }
    )

    assert trust["status"] == "unknown"
    assert trust["score"] == 35


def test_build_data_trust_post_sla_list_metadata_is_normalized(monkeypatch):
    def fake_apply_provider_sla_to_trust(_data, _trust):
        return {
            "status": "partial",
            "critical_failures": BrokenTruthText("market_data"),
            "stale_sources": BrokenTruthText("financial_statements"),
            "last_market_data_at": None,
            "notes": BrokenTruthText("Provider SLA metadata normalized."),
            "reason_codes": BrokenTruthText("provider_sla_critical"),
        }

    monkeypatch.setattr(data_trust_scoring, "apply_provider_sla_to_trust", fake_apply_provider_sla_to_trust)
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ]
        }
    )

    assert trust["critical_failures"] == ["market_data"]
    assert trust["stale_sources"] == ["financial_statements"]
    assert trust["notes"] == ["Provider SLA metadata normalized."]
    assert trust["reason_codes"] == ["provider_sla_critical"]
    assert trust["score"] == 42


def test_build_data_trust_post_sla_last_market_timestamp_is_normalized(monkeypatch):
    def fake_apply_provider_sla_to_trust(_data, _trust):
        return {
            "status": "fresh",
            "critical_failures": [],
            "stale_sources": [],
            "last_market_data_at": BrokenTruthText(" 2026-06-01T00:00:00+00:00 "),
            "notes": ["Provider SLA timestamp normalized."],
            "reason_codes": ["fresh_core_sources"],
        }

    monkeypatch.setattr(data_trust_scoring, "apply_provider_sla_to_trust", fake_apply_provider_sla_to_trust)
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ]
        }
    )

    assert trust["last_market_data_at"] == "2026-06-01T00:00:00+00:00"
    assert trust["score"] == 95


def test_build_data_trust_post_sla_provider_alerts_are_normalized(monkeypatch):
    alert = {"source": "market_data", "provider": "yfinance", "alert_level": "warning"}

    def fake_apply_provider_sla_to_trust(_data, _trust):
        return {
            "status": "fresh",
            "critical_failures": [],
            "stale_sources": [],
            "last_market_data_at": None,
            "notes": ["Provider SLA alerts normalized."],
            "reason_codes": ["fresh_core_sources"],
            "provider_sla_alerts": BrokenProviderSlaFirstNextRowsList([alert]),
        }

    monkeypatch.setattr(data_trust_scoring, "apply_provider_sla_to_trust", fake_apply_provider_sla_to_trust)
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ]
        }
    )

    assert type(trust["provider_sla_alerts"]) is list
    assert trust["provider_sla_alerts"] == [alert]
    assert trust["score"] == 95


def test_build_data_trust_preserves_base_trust_when_provider_sla_policy_fails(monkeypatch):
    def raise_provider_sla_policy(_data, _trust):
        raise RuntimeError("provider SLA policy unavailable")

    monkeypatch.setattr(data_trust_scoring, "apply_provider_sla_to_trust", raise_provider_sla_policy)
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ]
        }
    )

    assert trust["status"] == "fresh"
    assert "fresh_core_sources" in trust["reason_codes"]
    assert trust["score"] == 95


def test_build_data_trust_preserves_base_trust_when_provider_sla_policy_lookup_fails(monkeypatch):
    def raise_provider_sla_policy(_data, _trust):
        raise KeyError("provider SLA policy lookup unavailable")

    monkeypatch.setattr(data_trust_scoring, "apply_provider_sla_to_trust", raise_provider_sla_policy)
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ]
        }
    )

    assert trust["status"] == "fresh"
    assert "fresh_core_sources" in trust["reason_codes"]
    assert trust["score"] == 95


def test_build_data_trust_policy_failure_uses_unmutated_base_trust_snapshot(monkeypatch):
    def mutate_then_raise_provider_sla_policy(_data, trust):
        trust["status"] = "error"
        trust["critical_failures"].append("market_data")
        trust["stale_sources"].append("market_data")
        trust["reason_codes"].append("provider_sla_critical")
        trust["notes"].append("provider SLA partial mutation before failure")
        raise RuntimeError("provider SLA policy failed after mutation")

    monkeypatch.setattr(data_trust_scoring, "apply_provider_sla_to_trust", mutate_then_raise_provider_sla_policy)
    trust = data_trust.build_data_trust(
        {
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ]
        }
    )

    assert trust["status"] == "fresh"
    assert trust["critical_failures"] == []
    assert trust["stale_sources"] == []
    assert "fresh_core_sources" in trust["reason_codes"]
    assert "provider_sla_critical" not in trust["reason_codes"]
    assert trust["score"] == 95


def test_build_data_trust_uses_safe_source_data_and_audit_collections(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    source_audit = [
        {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
        {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
    ]

    for payload in (
        BrokenGetDict({"source_audit": source_audit}),
        {"source_audit": tuple(source_audit)},
        {"source_audit": BrokenNativeRowsList(source_audit)},
    ):
        trust = data_trust.build_data_trust(payload)

        assert trust["status"] == "fresh"
        assert "fresh_core_sources" in trust["reason_codes"]


def test_build_data_trust_accepts_mapping_safe_source_payloads(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    trust = data_trust.build_data_trust(
        MappingProxyType(
            {
                "source_audit": (
                    MappingProxyType(
                        {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1}
                    ),
                    MappingProxyType(
                        {
                            "source": "financial_statements",
                            "provider": "yfinance",
                            "status": "success",
                            "record_count": 1,
                        }
                    ),
                )
            }
        )
    )

    assert trust["status"] == "fresh"
    assert trust["score"] == 95
    assert "fresh_core_sources" in trust["reason_codes"]


def test_build_data_trust_source_freshness_child_maps_use_safe_conversion(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    trust = data_trust.build_data_trust(
        {
            "source_freshness": {
                "market_data": BrokenGetDict(
                    {
                        "stale": True,
                        "fetched_at": "2026-06-01T00:00:00+00:00",
                    }
                ),
                "financial_statements": BrokenGetDict({"stale": False}),
            },
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ],
        }
    )

    assert trust["status"] == "stale"
    assert trust["stale_sources"] == ["market_data"]
    assert trust["last_market_data_at"] == "2026-06-01T00:00:00+00:00"


def test_build_data_trust_source_freshness_stale_flags_use_bool_safe_conversion(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    trust = data_trust.build_data_trust(
        {
            "source_freshness": {
                "market_data": {
                    "stale": BrokenTruthBool(),
                    "fetched_at": "2026-06-01T00:00:00+00:00",
                },
                "financial_statements": {"stale": False},
            },
            "source_audit": [
                {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
                {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
            ],
        }
    )

    assert trust["status"] == "fresh"
    assert trust["stale_sources"] == []
    assert trust["last_market_data_at"] == "2026-06-01T00:00:00+00:00"


def test_build_data_trust_data_source_notes_use_string_list_conversion(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    source_audit = [
        {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1},
        {"source": "financial_statements", "provider": "yfinance", "status": "success", "record_count": 1},
    ]

    malformed = data_trust.build_data_trust(
        {
            "source_audit": source_audit,
            "data_source_notes": BrokenTruthBool(),
        }
    )
    assert malformed["status"] == "fresh"
    assert "data_source_notes_present" not in malformed["reason_codes"]

    valid = data_trust.build_data_trust(
        {
            "source_audit": source_audit,
            "data_source_notes": ("TTM 淨利率已依最新財報補值。", b"bad-note"),
        }
    )
    assert "data_source_notes_present" in valid["reason_codes"]


def test_optional_not_configured_sources_do_not_degrade_fresh_core_data(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "recent_catalysts",
            "Alternative Search",
            "not_configured",
            record_count=0,
            message="Alternative Search 未設定，僅略過補充催化劑。",
        )
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert "optional_source_not_configured:recent_catalysts" in trust["reason_codes"]
    assert "recent_catalysts" not in trust["critical_failures"]
    assert any("補充來源未設定" in note for note in trust["notes"])


def test_optional_degraded_enrichment_is_not_treated_as_core_failure(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "peer_discovery",
            "Alternative Search",
            "degraded_enrichment",
            record_count=0,
            message="同業搜尋補充來源降級，核心財務資料仍可用。",
        )
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert "optional_source_degraded:peer_discovery" in trust["reason_codes"]
    assert "peer_discovery" not in trust["critical_failures"]
    assert any("補充來源降級" in note for note in trust["notes"])


def test_optional_stale_enrichment_sources_do_not_degrade_fresh_core_data(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_freshness"].update(
        {
            "recent_catalysts": {
                "stale": True,
                "fetched_at": "2026-06-01T00:00:00+00:00",
                "fetched_at_epoch": 1780243200,
            },
            "social_sentiment": {
                "stale": True,
                "fetched_at": "2026-06-01T00:00:00+00:00",
                "fetched_at_epoch": 1780243200,
            },
        }
    )
    payload["source_audit"].extend(
        [
            data_trust.build_source_audit_entry(
                "recent_catalysts",
                "cache",
                "unavailable",
                record_count=1,
                cache_hit=True,
                stale=True,
            ),
            data_trust.build_source_audit_entry(
                "social_sentiment",
                "cache",
                "unavailable",
                record_count=1,
                cache_hit=True,
                stale=True,
            ),
        ]
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert trust["stale_sources"] == []
    assert "optional_source_stale:recent_catalysts" in trust["reason_codes"]
    assert "optional_source_stale:social_sentiment" in trust["reason_codes"]
    assert not any(code.startswith("source_stale:") for code in trust["reason_codes"])


def test_optional_source_errors_do_not_degrade_fresh_core_data(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "recent_catalysts",
            "News/Search providers",
            "error",
            record_count=0,
            error_kind="ConnectionError",
            message="補充新聞來源暫時無法連線。",
        )
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert "optional_source_error:recent_catalysts" in trust["reason_codes"]
    assert "source_error:recent_catalysts" not in trust["reason_codes"]


def test_data_trust_audit_source_text_does_not_depend_on_truthiness(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        {
            "source": BrokenTruthText("market_data"),
            "provider": "fallback-quote",
            "status": "error",
            "record_count": 0,
            "stale": False,
        }
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "partial"
    assert "source_error:market_data" in trust["reason_codes"]


def test_provider_sla_warning_notes_current_provider_without_downgrade(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [provider_sla_alert(provider="fake-yfinance", level="warning", attempts=3)],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_warning_note" in trust["reason_codes"]
    assert any("來源健康度觀察" in note for note in trust["notes"])


def test_core_provider_sla_critical_is_notice_when_current_fetch_succeeded(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=20)],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert "provider_sla_critical" not in trust["reason_codes"]
    assert "provider_sla_core_health_notice" in trust["reason_codes"]
    assert any("本次資料抓取成功" in note for note in trust["notes"])


def test_core_provider_sla_critical_for_failed_secondary_provider_is_notice_when_source_succeeded(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "market_data",
            "fallback-quote",
            "unavailable",
            record_count=0,
            message="備援 quote provider 本次未回傳。",
        )
    )
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [
            provider_sla_alert(source="market_data", provider="fallback-quote", level="critical", attempts=20)
        ],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert "provider_sla_critical" not in trust["reason_codes"]
    assert "provider_sla_core_health_notice" in trust["reason_codes"]


def test_optional_provider_sla_critical_is_notice_without_global_downgrade(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].extend(
        [
            data_trust.build_source_audit_entry(
                "recent_catalysts",
                "cache",
                "skipped_fresh_cache",
                record_count=1,
                cache_hit=True,
            ),
            data_trust.build_source_audit_entry(
                "social_sentiment",
                "cache",
                "skipped_fresh_cache",
                record_count=1,
                cache_hit=True,
            ),
        ]
    )
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [
            provider_sla_alert(source="recent_catalysts", provider="cache", level="critical", attempts=20),
            provider_sla_alert(source="social_sentiment", provider="cache", level="critical", attempts=20),
        ],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert "provider_sla_critical" not in trust["reason_codes"]
    assert "provider_sla_optional_critical" in trust["reason_codes"]
    assert any("補充來源健康度警示" in note for note in trust["notes"])


def test_provider_sla_critical_downgrades_current_provider_trust(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_freshness"]["market_data"] = {
        "stale": True,
        "fetched_at": "2026-06-01T00:00:00+00:00",
        "fetched_at_epoch": 1780243200,
    }
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "market_data",
            "fake-yfinance",
            "unavailable",
            record_count=0,
            stale=True,
        )
    )
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "partial"
    assert trust["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in trust["reason_codes"]
    assert any("來源健康度警示" in note for note in trust["notes"])


def test_provider_sla_row_mapping_get_failures_do_not_interrupt_trust_downgrade():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            BrokenGetDict(
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            )
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [
        BrokenGetDict(
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "alert_level": "critical",
                "alert_message": "success rate low",
                "success_rate": 0.4,
                "last_status": "error",
                "alert_basis": "last_24h",
                "windows": {"last_24h": {"attempts": 3}},
            }
        )
    ]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert result["provider_sla_alerts"][0]["evidence_attempts"] == 3
    assert "provider_sla_critical" in result["reason_codes"]
    assert any("來源健康度警示" in note for note in result["notes"])


def test_provider_sla_row_mapping_copy_lookup_failures_preserve_downgrade_evidence():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            BrokenLookupCopyDict(
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            )
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [
        BrokenLookupCopyDict(
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "alert_level": "critical",
                "alert_message": "success rate low",
                "success_rate": 0.4,
                "last_status": "error",
                "alert_basis": "last_24h",
                "windows": {"last_24h": {"attempts": 3}},
            }
        )
    ]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert result["provider_sla_alerts"][0]["evidence_attempts"] == 3
    assert "provider_sla_critical" in result["reason_codes"]
    assert any("來源健康度警示" in note for note in result["notes"])


def test_provider_sla_source_data_get_failure_does_not_interrupt_trust_downgrade():
    import data_trust_sla_policy

    payload = BrokenGetDict(
        {
            "source_audit": [
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            ]
        }
    )
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_nested_window_get_failure_falls_back_to_alert_attempts():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alert = provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)
    alert["windows"] = BrokenGetDict({"last_24h": {"attempts": 3}})

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=[alert])

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["evidence_attempts"] == 3
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_source_audit_lookup_scalar_failures_do_not_interrupt_trust_downgrade():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": BrokenLookupInt(),
                "stale": BrokenLookupBool(),
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["current_record_count"] == 0
    assert result["provider_sla_alerts"][0]["current_stale"] is False
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_lookup_attempt_failures_do_not_interrupt_policy():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alert = provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)
    alert["attempts"] = BrokenLookupInt()
    alert["windows"] = {"last_24h": {"attempts": BrokenLookupInt()}}

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=[alert])

    assert result is trust
    assert result["status"] == "fresh"
    assert "provider_sla_critical" not in result["reason_codes"]


def test_provider_sla_source_audit_native_lists_preserve_downgrade_evidence():
    import data_trust_sla_policy

    payload = {
        "source_audit": BrokenNativeRowsList(
            [
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            ]
        )
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_alert_native_lists_preserve_downgrade_evidence():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = BrokenNativeRowsList([provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)])

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_source_audit_rows_survive_lookup_iterator_creation_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": BrokenProviderSlaLookupIteratorRowsList(
            [
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            ]
        )
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_alert_rows_survive_lookup_iterator_creation_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = BrokenProviderSlaLookupIteratorRowsList(
        [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]
    )

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_source_audit_rows_survive_first_next_iterator_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": BrokenProviderSlaFirstNextRowsList(
            [
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            ]
        )
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_alert_rows_survive_first_next_iterator_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = BrokenProviderSlaFirstNextRowsList(
        [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]
    )

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_source_audit_rows_survive_lookup_iterator_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": BrokenProviderSlaLookupNextRowsList(
            [
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            ]
        )
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_alert_rows_survive_lookup_iterator_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = BrokenProviderSlaLookupNextRowsList(
        [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]
    )

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_trust_metadata_native_lists_preserve_existing_context():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {
        "status": "fresh",
        "notes": BrokenNativeTextList(["既有資料可信度備註"]),
        "reason_codes": BrokenNativeTextList(["existing_manual_review"]),
    }
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert "existing_manual_review" in result["reason_codes"]
    assert "provider_sla_critical" in result["reason_codes"]
    assert result["notes"][0] == "既有資料可信度備註"
    assert any("來源健康度警示" in note for note in result["notes"])


def test_provider_sla_trust_metadata_survives_lookup_iterator_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {
        "status": "fresh",
        "notes": BrokenProviderSlaLookupNextTextList(["既有資料可信度備註"]),
        "reason_codes": BrokenProviderSlaLookupNextTextList(["existing_manual_review"]),
    }
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert "existing_manual_review" in result["reason_codes"]
    assert "provider_sla_critical" in result["reason_codes"]
    assert result["notes"][0] == "既有資料可信度備註"
    assert any("來源健康度警示" in note for note in result["notes"])


def test_provider_sla_trust_metadata_survives_lookup_iterator_creation_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {
        "status": "fresh",
        "notes": BrokenProviderSlaLookupIteratorTextList(["既有資料可信度備註"]),
        "reason_codes": BrokenProviderSlaLookupIteratorTextList(["existing_manual_review"]),
    }
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert "existing_manual_review" in result["reason_codes"]
    assert "provider_sla_critical" in result["reason_codes"]
    assert result["notes"][0] == "既有資料可信度備註"
    assert any("來源健康度警示" in note for note in result["notes"])


def test_provider_sla_trust_metadata_survives_first_next_iterator_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {
        "status": "fresh",
        "notes": BrokenProviderSlaFirstNextTextList(["既有資料可信度備註"]),
        "reason_codes": BrokenProviderSlaFirstNextTextList(["existing_manual_review"]),
    }
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert "existing_manual_review" in result["reason_codes"]
    assert "provider_sla_critical" in result["reason_codes"]
    assert result["notes"][0] == "既有資料可信度備註"
    assert any("來源健康度警示" in note for note in result["notes"])


def test_data_snapshot_sanitizes_sensitive_keys():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TEST",
            "pipeline_id": "v1",
            "deterministic_fallbacks": [
                {
                    "agent_num": 14,
                    "trigger": "repair_429_failure",
                    "message": "已套用 deterministic 三情境估值 fallback",
                }
            ],
            "data": {
                "ticker": "TEST",
                "api_key": "SHOULD_NOT_APPEAR",
                "nested": {
                    "prompt": "DO NOT SAVE PROMPT",
                    "safe_value": 123,
                },
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        }
    )
    encoded = json.dumps(snapshot, ensure_ascii=False)

    assert "SHOULD_NOT_APPEAR" not in encoded
    assert "DO NOT SAVE PROMPT" not in encoded
    assert snapshot["data"]["nested"]["safe_value"] == 123
    assert snapshot["deterministic_fallbacks"][0]["trigger"] == "repair_429_failure"
    assert snapshot["snapshot_hash"] == data_trust.snapshot_content_hash(snapshot)
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True
    tampered = dict(snapshot)
    tampered["ticker"] = "TAMPERED"
    assert data_trust.validate_data_snapshot(tampered)["valid"] is False


def test_data_snapshot_integrity_hash_metadata_does_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "HASH",
            "pipeline_id": "v1",
            "data": {
                "ticker": "HASH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    snapshot["snapshot_hash"] = BrokenTruthText(snapshot["snapshot_hash"])

    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True


def test_data_snapshot_validators_use_dict_native_field_reads():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "VALID",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "VALID",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    wrapped_snapshot = BrokenGetDict(snapshot)

    assert data_trust.verify_data_snapshot_integrity(wrapped_snapshot)["valid"] is True
    assert data_trust.validate_data_snapshot(wrapped_snapshot) == {"valid": True, "errors": []}


def test_data_snapshot_validators_preserve_mapping_fields_when_lookup_accessors_fail():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "VALID",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "VALID",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    wrapped_snapshot = BrokenSnapshotLookupFieldMapping(snapshot)

    integrity = data_trust.verify_data_snapshot_integrity(wrapped_snapshot)

    assert integrity["valid"] is True
    assert integrity["hash"] == snapshot["snapshot_hash"]
    assert data_trust.validate_data_snapshot(wrapped_snapshot) == {"valid": True, "errors": []}


def test_data_snapshot_content_hash_keys_use_safe_text_conversion():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "HASH",
            "pipeline_id": "v1",
            "data": {
                "ticker": "HASH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    expected_hash = snapshot["snapshot_hash"]
    snapshot[BrokenString("bad hash key")] = "SHOULD_NOT_APPEAR"

    integrity = data_trust.verify_data_snapshot_integrity(snapshot)

    assert integrity["valid"] is True
    assert integrity["hash"] == expected_hash


def test_data_snapshot_content_hash_uses_safe_mapping_items():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "HASH",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "HASH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    wrapped_snapshot = BrokenNativeSnapshotMapping(snapshot)

    assert data_trust.snapshot_content_hash(wrapped_snapshot) == snapshot["snapshot_hash"]
    assert data_trust.verify_data_snapshot_integrity(wrapped_snapshot)["valid"] is True


def test_data_snapshot_content_hash_accepts_mapping_snapshot_wrappers():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "HASH",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "HASH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    wrapped_snapshot = MappingProxyType(snapshot)

    assert data_trust.snapshot_content_hash(wrapped_snapshot) == snapshot["snapshot_hash"]
    assert data_trust.verify_data_snapshot_integrity(wrapped_snapshot)["valid"] is True


def test_data_snapshot_content_hash_survives_first_next_mapping_failures():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "HASH",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "HASH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    wrapped_snapshot = BrokenSnapshotFirstNextMapping(snapshot)

    assert data_trust.snapshot_content_hash(wrapped_snapshot) == snapshot["snapshot_hash"]
    assert data_trust.verify_data_snapshot_integrity(wrapped_snapshot)["valid"] is True


def test_data_snapshot_size_governance_uses_sanitized_snapshot_keys():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "SIZE",
            "pipeline_id": "v1",
            "data": {
                "ticker": "SIZE",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    snapshot[BrokenString("bad governance key")] = "SHOULD_NOT_APPEAR"

    governed = data_trust.apply_snapshot_size_governance(snapshot, max_bytes=100_000)
    encoded = json.dumps(governed, ensure_ascii=False)

    assert "SHOULD_NOT_APPEAR" not in encoded
    assert data_trust.verify_data_snapshot_integrity(governed)["valid"] is True


def test_data_snapshot_size_bytes_uses_sanitized_snapshot_keys():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "SIZE",
            "pipeline_id": "v1",
            "data": {
                "ticker": "SIZE",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    snapshot[BrokenString("bad size key")] = "SHOULD_NOT_APPEAR"

    assert data_trust.snapshot_size_bytes(snapshot) == data_trust.snapshot_size_bytes(
        data_trust.sanitize_for_snapshot(snapshot)
    )


def test_data_snapshot_identity_fields_do_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": BrokenTruthText("CTX"),
            "company_name": BrokenTruthText("Context Co"),
            "pipeline_id": BrokenTruthText("v2"),
            "data": {
                "ticker": "DATA",
                "company_name": "Data Co",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["ticker"] == "CTX"
    assert snapshot["company_name"] == "Context Co"
    assert snapshot["pipeline"] == "v2"


def test_data_snapshot_identity_fields_use_shared_text_safety_for_malformed_inputs():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": True,
            "company_name": b"Bad Co",
            "pipeline_id": memoryview(b"bad-pipeline"),
            "data": {
                "ticker": "DATA",
                "company_name": "Data Co",
                "pipeline_id": "v1",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["ticker"] == "DATA"
    assert snapshot["company_name"] == "Data Co"
    assert snapshot["pipeline"] == "v1"


def test_data_snapshot_build_uses_dict_native_context_and_data_reads():
    snapshot = data_trust.build_data_snapshot(
        BrokenGetDict(
            {
                "ticker": "2330.TW",
                "company_name": "台積電",
                "pipeline_id": "v2",
                "pipeline_label": "完整分析",
                "agent_sequence": [1, 16],
                "conclusion_generated_at": "2026-06-07T00:00:00+00:00",
                "snapshot_refreshed_at": "2026-06-07T00:05:00+00:00",
                "decision_validity_status": "stale",
                "requires_rerun_reason": "market_data_changed",
                "refreshed_from_report": "2330_v2.html",
                "refreshed_without_analysis_rerun": True,
                "analysis_text_stale_message": "價格已刷新，結論待重跑。",
                "analyses": {16: "final recommendation"},
                "structured_outputs": {16: {"recommendation": {"target_price": "NT$120"}}},
                "parsed": {"recommendation": {"target_price": "NT$120"}},
                "deterministic_fallbacks": ["valuation_fallback"],
                "report_lint": {"status": "passed"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
                "data": BrokenGetDict(
                    {
                        "data_schema_version": DATA_SCHEMA_VERSION,
                        "ticker": "DATA",
                        "company_name": "Data Co",
                        "source_freshness": {"market_data": {"status": "fresh"}},
                        "source_audit": [],
                        "data_source_notes": ["來源已核對"],
                        "data_trust": BrokenGetDict(
                            {
                                "status": "fresh",
                                "score": 90,
                                "reason_codes": ["fresh_core_sources"],
                            }
                        ),
                    }
                ),
            }
        ),
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["ticker"] == "2330.TW"
    assert snapshot["company_name"] == "台積電"
    assert snapshot["pipeline"] == "v2"
    assert snapshot["snapshot_refreshed_at"] == "2026-06-07T00:05:00+00:00"
    assert snapshot["decision_validity_status"] == "stale"
    assert snapshot["requires_rerun_reason"] == "market_data_changed"
    assert snapshot["refreshed_without_analysis_rerun"] is True
    assert snapshot["data_schema_version"] == DATA_SCHEMA_VERSION
    assert snapshot["source_freshness"] == {"market_data": {"status": "fresh"}}
    assert snapshot["data_source_notes"] == ["來源已核對"]
    assert snapshot["deterministic_fallbacks"] == ["valuation_fallback"]
    assert snapshot["report_lint"] == {"status": "passed"}
    assert snapshot["content_credibility"] == {"status": "passed"}
    assert snapshot["report_conformance"] == {"status": "passed"}
    assert snapshot["rerun_context"]["analyses"] == {"16": "final recommendation"}
    assert snapshot["rerun_context"]["pipeline_label"] == "完整分析"
    assert snapshot["data_confidence_score"] == 90
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True


def test_data_snapshot_reproducibility_source_audit_fields_do_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "AUDIT",
            "pipeline_id": "v2",
            "data": {
                "ticker": "AUDIT",
                "source_audit": [
                    {
                        "provider": BrokenTruthText(" yfinance "),
                        "fetched_at": BrokenTruthText("2026-06-07T00:00:00+00:00"),
                    },
                    {
                        "provider": BrokenTruthText(" yfinance "),
                        "fetched_at": BrokenTruthText("2026-06-07T01:00:00+00:00"),
                    },
                ],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    packet = snapshot["reproducibility_packet"]

    assert packet["provider_list"] == ["yfinance"]
    assert packet["source_data_time"] == "2026-06-07T01:00:00+00:00"


def test_reproducibility_packet_uses_dict_native_mapping_reads():
    packet = report_reproducibility.build_reproducibility_packet(
        BrokenGetDict(
            {
                "ticker": "2330.TW",
                "prompt_version": "runtime-rules:test",
                "pipeline_id": "v2",
                "code_commit": "abc123",
                "metadata": BrokenGetDict({"model_id": "gemini-test-model"}),
                "data": BrokenGetDict(
                    {
                        "ticker": "DATA",
                        "pipeline_id": "v1",
                        "source_audit": [
                            BrokenGetDict(
                                {
                                    "provider": " yfinance ",
                                    "fetched_at": "2026-06-07T01:00:00+00:00",
                                }
                            )
                        ],
                    }
                ),
            }
        ),
        data_trust.unknown_data_trust(),
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert packet == {
        "ticker": "2330.TW",
        "data_snapshot_hash": "",
        "prompt_version": "runtime-rules:test",
        "prompt_fingerprint": "",
        "model_id": "gemini-test-model",
        "pipeline_id": "v2",
        "code_commit": "abc123",
        "code_dirty": None,
        "generated_at": "2026-06-07T00:10:00+00:00",
        "provider_list": ["yfinance"],
        "source_data_time": "2026-06-07T01:00:00+00:00",
    }


def test_reproducibility_packet_accepts_mapping_safe_contexts():
    packet = report_reproducibility.build_reproducibility_packet(
        MappingProxyType(
            {
                "ticker": "2330.TW",
                "prompt_version": "runtime-rules:test",
                "pipeline_id": "v2",
                "code_commit": "abc123",
                "code_dirty": True,
                "metadata": MappingProxyType({"model_id": "gemini-test-model"}),
                "data": MappingProxyType(
                    {
                        "ticker": "DATA",
                        "pipeline_id": "v1",
                        "source_audit": (
                            MappingProxyType(
                                {
                                    "provider": " yfinance ",
                                    "fetched_at": "2026-06-07T01:00:00+00:00",
                                }
                            ),
                        ),
                    }
                ),
            }
        ),
        data_trust.unknown_data_trust(),
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert packet == {
        "ticker": "2330.TW",
        "data_snapshot_hash": "",
        "prompt_version": "runtime-rules:test",
        "prompt_fingerprint": "",
        "model_id": "gemini-test-model",
        "pipeline_id": "v2",
        "code_commit": "abc123",
        "code_dirty": True,
        "generated_at": "2026-06-07T00:10:00+00:00",
        "provider_list": ["yfinance"],
        "source_data_time": "2026-06-07T01:00:00+00:00",
    }


def test_reproducibility_source_audit_helpers_accept_mapping_safe_data():
    data = MappingProxyType(
        {
            "source_audit": (
                MappingProxyType(
                    {
                        "provider": " yfinance ",
                        "fetched_at": "2026-06-07T01:00:00+00:00",
                    }
                ),
                MappingProxyType(
                    {
                        "provider": " FinMind ",
                        "fetched_at": "2026-06-07T02:00:00+00:00",
                    }
                ),
            )
        }
    )

    providers = report_reproducibility.provider_list_from_audit(data)
    source_time = report_reproducibility.source_data_time(data, data_trust.unknown_data_trust())

    assert providers == ["yfinance", "FinMind"]
    assert source_time == "2026-06-07T02:00:00+00:00"


def test_reproducibility_packet_uses_shared_text_safety_for_identity_fields():
    packet = report_reproducibility.build_reproducibility_packet(
        {
            "ticker": True,
            "prompt_version": memoryview(b"bad-prompt-version"),
            "pipeline_id": bytearray(b"bad-pipeline"),
            "code_commit": b"bad-commit",
            "metadata": {"model_id": memoryview(b"bad-model")},
            "data": {
                "ticker": "DATA",
                "prompt_version": "runtime-rules:data",
                "pipeline_id": "v1",
                "code_commit": "data-commit",
                "source_audit": [
                    {"provider": True, "fetched_at": True},
                    {"provider": " yfinance ", "fetched_at": memoryview(b"bad-time")},
                    {"provider": " fmp ", "fetched_at": "2026-06-07T02:00:00+00:00"},
                ],
            },
        },
        data_trust.unknown_data_trust(),
        generated_at=memoryview(b"bad-generated-at"),
    )

    assert packet["ticker"] == "DATA"
    assert packet["prompt_version"] == "runtime-rules:data"
    assert packet["pipeline_id"] == "v1"
    assert packet["code_commit"] == "data-commit"
    assert packet["model_id"] == "unknown"
    assert packet["generated_at"] == ""
    assert packet["provider_list"] == ["yfinance", "fmp"]
    assert packet["source_data_time"] == "2026-06-07T02:00:00+00:00"


def test_reproducibility_packet_preserves_source_audit_when_iterator_lookup_fails():
    class BrokenSourceAuditIterator(list):
        def __iter__(self):
            raise KeyError("source audit iterator unavailable")

    packet = report_reproducibility.build_reproducibility_packet(
        {
            "ticker": "2330.TW",
            "data": {
                "source_audit": BrokenSourceAuditIterator([
                    {"provider": " yfinance ", "fetched_at": "2026-06-07T01:00:00+00:00"},
                    {"provider": " FinMind ", "fetched_at": "2026-06-07T02:00:00+00:00"},
                ]),
            },
        },
        data_trust.unknown_data_trust(),
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert packet["provider_list"] == ["yfinance", "FinMind"]
    assert packet["source_data_time"] == "2026-06-07T02:00:00+00:00"


def test_data_snapshot_sanitizer_tolerates_malformed_string_conversion():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "SAFE",
            "pipeline_id": "v1",
            "data": {
                "ticker": "SAFE",
                "nested": {
                    BrokenString("bad key"): "SHOULD_NOT_APPEAR",
                    "bad_value": BrokenString("bad value"),
                    "safe_value": 123,
                },
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    encoded = json.dumps(snapshot, ensure_ascii=False)

    assert "SHOULD_NOT_APPEAR" not in encoded
    assert snapshot["data"]["nested"]["bad_value"] == ""
    assert snapshot["data"]["nested"]["safe_value"] == 123


def test_data_snapshot_sanitizer_only_preserves_sha256_prompt_fingerprints():
    assert data_trust.sanitize_for_snapshot({"prompt_fingerprint": "A" * 64}) == {
        "prompt_fingerprint": "a" * 64,
    }
    assert data_trust.sanitize_for_snapshot({"prompt_fingerprint": "not-a-sha256"}) == {}


def test_data_snapshot_sanitizer_native_sequences_preserve_items():
    sanitized = data_trust.sanitize_for_snapshot(
        {
            "list_rows": BrokenNativeRowsList([{"provider": "yfinance"}]),
            "tuple_rows": BrokenNativeTuple(({"provider": "TWSE"},)),
        }
    )

    assert sanitized == {
        "list_rows": [{"provider": "yfinance"}],
        "tuple_rows": [{"provider": "TWSE"}],
    }


def test_data_snapshot_sanitizer_native_sequences_preserve_items_when_first_next_fails():
    sanitized = data_trust.sanitize_for_snapshot(
        {
            "list_rows": BrokenSnapshotFirstNextRows([{"provider": "TPEX"}]),
        }
    )

    assert sanitized == {
        "list_rows": [{"provider": "TPEX"}],
    }


def test_data_snapshot_sanitizer_native_mappings_preserve_items():
    sanitized = data_trust.sanitize_for_snapshot(
        BrokenNativeSnapshotMapping(
            {
                "provider": "yfinance",
                "nested": {"fetched_at": "2026-06-07T00:00:00+00:00"},
            }
        )
    )

    assert sanitized == {
        "provider": "yfinance",
        "nested": {"fetched_at": "2026-06-07T00:00:00+00:00"},
    }


def test_data_snapshot_sanitizer_native_mappings_preserve_items_when_items_iterable_fails():
    sanitized = data_trust.sanitize_for_snapshot(
        BrokenSnapshotItemsIterableMapping(
            {
                "provider": "TWSE",
                "nested": {"fetched_at": "2026-06-07T01:00:00+00:00"},
            }
        )
    )

    assert sanitized == {
        "provider": "TWSE",
        "nested": {"fetched_at": "2026-06-07T01:00:00+00:00"},
    }


def test_data_snapshot_saves_sanitized_rerun_context():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TEST",
            "pipeline_id": "v2",
            "analyses": {
                11: "macro analysis",
                16: "final recommendation",
            },
            "structured_outputs": {
                16: {
                    "recommendation": {"建議": "持有"},
                    "retry_metadata": "SHOULD_NOT_APPEAR",
                }
            },
            "parsed": {"recommendation": {"建議": "持有"}},
            "prompt": "DO NOT SAVE PROMPT",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TEST",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        }
    )
    encoded = json.dumps(snapshot, ensure_ascii=False)

    assert snapshot["snapshot_schema_version"] == data_trust.DATA_SNAPSHOT_SCHEMA_VERSION
    assert snapshot["rerun_context"]["analyses"]["11"] == "macro analysis"
    assert snapshot["rerun_context"]["structured_outputs"]["16"]["recommendation"]["建議"] == "持有"
    assert "DO NOT SAVE PROMPT" not in encoded
    assert "SHOULD_NOT_APPEAR" not in encoded


def test_data_snapshot_rerun_context_text_does_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TEXT",
            "pipeline_id": "v2",
            "analyses": {11: BrokenTruthText("macro analysis")},
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TEXT",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["rerun_context"]["analyses"]["11"] == "macro analysis"


def test_data_snapshot_rerun_context_agent_keys_use_safe_text_conversion():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TEXT",
            "pipeline_id": "v2",
            "analyses": {
                BrokenString("bad agent key"): "SHOULD_NOT_APPEAR",
                11: "macro analysis",
            },
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TEXT",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["rerun_context"]["analyses"] == {"11": "macro analysis"}
    assert "SHOULD_NOT_APPEAR" not in json.dumps(snapshot, ensure_ascii=False)


def test_data_snapshot_adds_confidence_guardrail_and_repro_packet(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "abc123")
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v2",
        "prompt_version": "runtime-rules:test",
        "prompt_fingerprint": "a" * 64,
        "model_id": "gemini-test-model",
        "parsed": {
            "recommendation": {
                "建議": "買入",
                "12個月": "NT$1,200",
                "信心": "8/10",
            },
            "price_targets": {
                "熊市情境": 900,
                "基本情境": 1100,
                "牛市情境": 1300,
            },
        },
        "structured_outputs": {
            16: {
                "recommendation": {
                    "target_price": "NT$1,200",
                }
            }
        },
        "data": {
            "data_schema_version": DATA_SCHEMA_VERSION,
            "ticker": "2330.TW",
            "company_name": "台積電",
            "source_freshness": {},
            "source_audit": [
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "status": "success",
                    "fetched_at": "2026-06-07T00:00:00+00:00",
                    "record_count": 1,
                },
                {
                    "source": "financial_statements",
                    "provider": "TWSE",
                    "status": "error",
                    "fetched_at": "2026-06-06T00:00:00+00:00",
                    "record_count": 0,
                },
            ],
            "data_trust": {
                "status": "error",
                "critical_failures": ["financial_statements"],
                "stale_sources": [],
                "last_market_data_at": "2026-06-07T00:00:00+00:00",
                "notes": ["核心財報來源異常。"],
                "score": 20,
            },
        },
    }

    snapshot = data_trust.build_data_snapshot(
        context,
        pipeline_id="v2",
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["data_confidence_score"] == 20
    guardrail = snapshot["conclusion_guardrails"]["explicit_target_price"]
    assert guardrail["allowed"] is False
    assert guardrail["min_data_confidence_score"] == 60
    assert "parsed.recommendation.12個月" in guardrail["detected_fields"]
    assert "parsed.price_targets.基本情境" in guardrail["detected_fields"]
    assert "structured_outputs.16.recommendation.target_price" in guardrail["detected_fields"]
    packet = snapshot["reproducibility_packet"]
    assert packet["ticker"] == "2330.TW"
    assert packet["data_snapshot_hash"] == snapshot["snapshot_hash"]
    assert packet["prompt_version"] == "runtime-rules:test"
    assert packet["prompt_fingerprint"] == "a" * 64
    assert packet["model_id"] == "gemini-test-model"
    assert packet["pipeline_id"] == "v2"
    assert packet["code_commit"] == "abc123"
    assert packet["generated_at"] == "2026-06-07T00:10:00+00:00"
    assert packet["provider_list"] == ["yfinance", "TWSE"]
    assert packet["source_data_time"] == "2026-06-07T00:00:00+00:00"
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True


def test_reproducibility_packet_preserves_dirty_code_state():
    packet = report_reproducibility.build_reproducibility_packet(
        {
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "code_commit": "abc123",
            "code_dirty": True,
            "data": {"ticker": "2330.TW", "source_audit": []},
        },
        {},
        "2026-06-07T00:10:00+00:00",
    )

    assert packet["code_commit"] == "abc123"
    assert packet["code_dirty"] is True


def test_data_snapshot_target_price_detector_tolerates_malformed_text_conversion():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TARGET",
            "pipeline_id": "v2",
            "parsed": {
                "recommendation": {
                    BrokenString("bad target key"): "SHOULD_NOT_APPEAR",
                    "target_price": BrokenString("bad target value"),
                    "safe_target_price": "NT$120",
                }
            },
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TARGET",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    detected_fields = snapshot["conclusion_guardrails"]["explicit_target_price"]["detected_fields"]

    assert detected_fields == ["parsed.recommendation.safe_target_price"]
    assert "SHOULD_NOT_APPEAR" not in json.dumps(snapshot, ensure_ascii=False)


def test_explicit_target_price_detector_uses_native_root_mapping_reads():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        BrokenGetDict(
            {
                "parsed": {"recommendation": {"target_price": "NT$120"}},
                "structured_outputs": {"forecast": {"price_targets": "NT$130"}},
            }
        )
    )

    assert fields == [
        "parsed.recommendation.target_price",
        "structured_outputs.forecast.price_targets",
    ]


def test_explicit_target_price_detector_accepts_mapping_safe_contexts():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        MappingProxyType(
            {
                "parsed": MappingProxyType(
                    {
                        "recommendation": MappingProxyType(
                            {
                                "target_price": "NT$120",
                            }
                        )
                    }
                ),
                "structured_outputs": MappingProxyType(
                    {
                        "forecast": MappingProxyType(
                            {
                                "price_targets": "NT$130",
                            }
                        )
                    }
                ),
            }
        )
    )

    assert fields == [
        "parsed.recommendation.target_price",
        "structured_outputs.forecast.price_targets",
    ]


def test_explicit_target_price_detector_preserves_valid_list_items_before_iterator_failure():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": {"recommendation_targets": BrokenTargetRows()}}
    )

    assert fields == ["parsed.recommendation_targets.0.target_price"]


def test_explicit_target_price_detector_accepts_tuple_sequences():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": {"recommendation_targets": ({"target_price": "NT$120"},)}}
    )

    assert fields == ["parsed.recommendation_targets.0.target_price"]


def test_explicit_target_price_detector_native_lists_preserve_valid_items():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": {"recommendation_targets": BrokenTargetNativeRows([{"target_price": "NT$120"}])}}
    )

    assert fields == ["parsed.recommendation_targets.0.target_price"]


def test_explicit_target_price_detector_lists_survive_first_next_iterator_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": {"recommendation_targets": BrokenTargetFirstNextRows([{"target_price": "NT$120"}])}}
    )

    assert fields == ["parsed.recommendation_targets.0.target_price"]


def test_explicit_target_price_detector_lists_survive_lookup_iterator_creation_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": {"recommendation_targets": BrokenTargetLookupNativeRows([{"target_price": "NT$120"}])}}
    )

    assert fields == ["parsed.recommendation_targets.0.target_price"]


def test_explicit_target_price_detector_lists_survive_lookup_iterator_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": {"recommendation_targets": BrokenTargetLookupNextRows([{"target_price": "NT$120"}])}}
    )

    assert fields == ["parsed.recommendation_targets.0.target_price"]


def test_explicit_target_price_detector_preserves_valid_mapping_items_before_iterator_failure():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetMapping()}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_native_mappings_preserve_valid_items():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetNativeMapping({"recommendation": {"target_price": "NT$120"}})}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_mappings_survive_lookup_items_accessor_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetLookupNativeMapping({"recommendation": {"target_price": "NT$120"}})}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_mappings_survive_first_next_iterator_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetFirstNextMapping({"recommendation": {"target_price": "NT$120"}})}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_mappings_survive_lookup_iterator_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetLookupNextMapping({"recommendation": {"target_price": "NT$120"}})}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_mappings_survive_items_iterable_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetItemsIterableMapping({"recommendation": {"target_price": "NT$120"}})}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_ignores_non_finite_numeric_targets():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {
            "parsed": {
                "recommendation": {
                    "nan_target_price": float("nan"),
                    "inf_target_price": float("inf"),
                    "negative_inf_target_price": float("-inf"),
                    "valid_target_price": 120.5,
                }
            }
        }
    )

    assert fields == ["parsed.recommendation.valid_target_price"]


def test_data_snapshot_existing_data_trust_does_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TRUST",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TRUST",
                "source_audit": [],
                "data_trust": BrokenTruthDict(
                    {
                        "status": "fresh",
                        "score": 90,
                        "reason_codes": ["manual_reason"],
                        "notes": ["manual trust snapshot"],
                    }
                ),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["data_trust"]["status"] == "fresh"
    assert snapshot["data_trust"]["reason_codes"] == ["manual_reason"]
    assert snapshot["data_confidence_score"] == 90


def test_data_snapshot_existing_data_trust_accepts_mapping_safe_payloads():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TRUST",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TRUST",
                "source_audit": [],
                "data_trust": MappingProxyType(
                    {
                        "status": "fresh",
                        "score": 91,
                        "reason_codes": ("fresh_core_sources",),
                        "notes": ("read-only trust snapshot",),
                    }
                ),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["data_trust"]["status"] == "fresh"
    assert snapshot["data_trust"]["reason_codes"] == ["fresh_core_sources"]
    assert snapshot["data_confidence_score"] == 91


def test_data_snapshot_source_data_accepts_mapping_safe_payloads(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TRUST",
            "pipeline_id": "v2",
            "data": MappingProxyType(
                {
                    "data_schema_version": DATA_SCHEMA_VERSION,
                    "ticker": "TRUST",
                    "source_audit": (
                        MappingProxyType(
                            {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1}
                        ),
                        MappingProxyType(
                            {
                                "source": "financial_statements",
                                "provider": "yfinance",
                                "status": "success",
                                "record_count": 1,
                            }
                        ),
                    ),
                }
            ),
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["data_trust"]["status"] == "fresh"
    assert snapshot["data_trust"]["score"] == 95
    assert snapshot["data_confidence_score"] == 95


def test_data_snapshot_context_accepts_mapping_safe_payloads(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    snapshot = data_trust.build_data_snapshot(
        MappingProxyType(
            {
                "ticker": "TRUST",
                "pipeline_id": "v2",
                "data": {
                    "data_schema_version": DATA_SCHEMA_VERSION,
                    "ticker": "TRUST",
                    "source_audit": (
                        MappingProxyType(
                            {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1}
                        ),
                        MappingProxyType(
                            {
                                "source": "financial_statements",
                                "provider": "yfinance",
                                "status": "success",
                                "record_count": 1,
                            }
                        ),
                    ),
                },
            }
        ),
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["ticker"] == "TRUST"
    assert snapshot["pipeline"] == "v2"
    assert snapshot["data_trust"]["status"] == "fresh"
    assert snapshot["data_confidence_score"] == 95


def test_data_snapshot_existing_data_trust_score_conversion_failure_uses_status_score():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TRUST",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TRUST",
                "source_audit": [],
                "data_trust": {
                    "status": "fresh",
                    "score": BrokenFloatScore(),
                    "reason_codes": [],
                    "notes": ["manual trust snapshot"],
                },
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["data_trust"]["status"] == "fresh"
    assert snapshot["data_trust"]["score"] == 95
    assert snapshot["data_confidence_score"] == 95


def test_data_snapshot_existing_data_trust_lookup_score_conversion_failure_uses_status_score():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TRUST",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TRUST",
                "source_audit": [],
                "data_trust": {
                    "status": "fresh",
                    "score": BrokenLookupFloatScore(),
                    "reason_codes": [],
                    "notes": ["manual trust snapshot"],
                },
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["data_trust"]["status"] == "fresh"
    assert snapshot["data_trust"]["score"] == 95
    assert snapshot["data_confidence_score"] == 95


def test_data_snapshot_refresh_flag_does_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "REFRESH",
            "pipeline_id": "v2",
            "refreshed_without_analysis_rerun": BrokenTruthBool(),
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "REFRESH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["refreshed_without_analysis_rerun"] is False


def test_data_snapshot_refresh_flag_lookup_failure_falls_back_to_false():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "REFRESH",
            "pipeline_id": "v2",
            "refreshed_without_analysis_rerun": BrokenLookupBool(),
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "REFRESH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["refreshed_without_analysis_rerun"] is False


def test_low_confidence_snapshot_allows_ranges_or_insufficient_data():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "RANGE",
            "pipeline_id": "v2",
            "parsed": {
                "recommendation": {
                    "12個月": "NT$90 至 NT$110",
                    "信心": "3/10",
                },
                "price_targets": {"基本情境": "資料不足，僅提供 NT$90-110 區間"},
            },
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "RANGE",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    guardrail = snapshot["conclusion_guardrails"]["explicit_target_price"]
    assert snapshot["data_confidence_score"] == 35
    assert guardrail["allowed"] is False
    assert guardrail["detected_fields"] == []
    assert "資料不足" in guardrail["message"]
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True


def test_data_snapshot_accepts_legacy_v2_schema():
    snapshot = {
        "snapshot_schema_version": 2,
        "ticker": "TEST",
        "pipeline": "v1",
        "generated_at": "2026-06-07T00:00:00+00:00",
        "data_schema_version": DATA_SCHEMA_VERSION,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": data_trust.unknown_data_trust(),
        "data": {"ticker": "TEST"},
    }

    assert data_trust.validate_data_snapshot(snapshot)["valid"] is True


def test_data_snapshot_schema_validation_and_truncation():
    audit = [
        data_trust.build_source_audit_entry(
            "market_data",
            "fake",
            "success",
            record_count=2,
            message="kept in full audit",
        )
    ]
    context = {
        "ticker": "BIG",
        "pipeline_id": "v2",
        "data": {
            "data_schema_version": DATA_SCHEMA_VERSION,
            "ticker": "BIG",
            "company_name": "Big Fixture",
            "current_price": 100,
            "years": ["2024", "2025"],
            "revenue_history": [10, 12],
            "net_income_history": [2, 3],
            "source_freshness": {
                "market_data": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
                "financial_statements": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
            },
            "source_audit": audit,
            "data_trust": {
                "status": "fresh",
                "critical_failures": [],
                "stale_sources": [],
                "last_market_data_at": "2026-06-07T00:00:00+00:00",
                "notes": ["fixture"],
            },
            "recent_catalysts": [{"title": "x" * 180} for _ in range(20)],
            "peer_discovery_results": [{"title": "y" * 180} for _ in range(20)],
            "dynamic_peer_metrics": [{"name": "z" * 180} for _ in range(20)],
            "internal_retry_metadata": "SHOULD_NOT_APPEAR",
        },
    }

    snapshot = data_trust.build_data_snapshot(context, max_bytes=1600)
    encoded = json.dumps(snapshot, ensure_ascii=False)

    assert snapshot["snapshot_schema_version"] == data_trust.DATA_SNAPSHOT_SCHEMA_VERSION
    assert snapshot["snapshot_truncated"] is True
    assert snapshot["snapshot_size_bytes"] == data_trust.snapshot_size_bytes(snapshot)
    assert snapshot["snapshot_hash"] == data_trust.snapshot_content_hash(snapshot)
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True
    assert snapshot["snapshot_omitted_sections"]
    assert snapshot["source_audit"] == audit
    assert snapshot["data_trust"]["status"] == "fresh"
    assert "SHOULD_NOT_APPEAR" not in encoded
    assert data_trust.validate_data_snapshot(snapshot)["valid"] is True


def test_data_snapshot_schema_validation_rejects_old_shape():
    validation = data_trust.validate_data_snapshot({"ticker": "OLD"})

    assert validation["valid"] is False
    assert "unsupported snapshot_schema_version" in validation["errors"]
