import json
from datetime import date
from decimal import Decimal
from fractions import Fraction
from types import MappingProxyType

import pytest

from daily_decision_queue import build_daily_decision_queue


def test_daily_decision_source_labels_cover_queue_sources_and_are_immutable():
    from daily_decision_queue import SOURCE_ORDER
    from daily_decision_source_labels import SOURCE_LABELS, source_text

    assert set(SOURCE_ORDER) <= set(SOURCE_LABELS)
    for source in SOURCE_ORDER:
        assert source_text(source) != source

    with pytest.raises(TypeError):
        SOURCE_LABELS["watchlist"] = "Watchlist"


def test_daily_decision_source_labels_trim_source_keys_before_lookup():
    from daily_decision_source_labels import source_label, source_labels, source_text, source_texts

    assert source_label(" provider_impact ") == "資料來源"
    assert source_text("\tprovider_impact\n") == "資料來源 (provider_impact)"
    assert source_labels({" watchlist ": 2}) == {"watchlist": "追蹤清單"}
    assert source_texts({" watchlist ": 2}) == {"watchlist": "追蹤清單 (watchlist)"}


def test_daily_decision_source_label_maps_drop_blank_source_keys():
    from daily_decision_source_labels import source_labels, source_texts

    assert source_labels({"   ": 1, "\n\t": 2, " watchlist ": 3}) == {"watchlist": "追蹤清單"}
    assert source_texts({"   ": 1, "\n\t": 2, " watchlist ": 3}) == {"watchlist": "追蹤清單 (watchlist)"}


def test_daily_decision_source_label_maps_ignore_non_mapping_sources():
    from daily_decision_source_labels import source_labels, source_texts

    for raw_sources in (None, ["watchlist"], ("watchlist",)):
        assert source_labels(raw_sources) == {}
        assert source_texts(raw_sources) == {}


def test_daily_decision_source_helpers_ignore_non_string_source_keys():
    from daily_decision_source_labels import (
        normalize_source_counts,
        source_key,
        source_label,
        source_labels,
        source_text,
        source_texts,
    )

    assert source_key(123) == ""
    assert source_label(True) == ""
    assert source_text(b"watchlist") == ""
    assert source_labels({123: 1, True: 1, " watchlist ": 1}) == {"watchlist": "追蹤清單"}
    assert source_texts({123: 1, True: 1, " watchlist ": 1}) == {"watchlist": "追蹤清單 (watchlist)"}
    assert normalize_source_counts({123: 2, True: 3, " watchlist ": 1}) == {"watchlist": 1}


def test_daily_decision_source_count_normalization_drops_nonpositive_counts():
    from daily_decision_source_labels import normalize_source_counts, source_labels, source_texts

    counts = normalize_source_counts({
        " watchlist ": 2,
        "provider_impact": 0,
        "report_repair": -1,
        "screener": "bad",
    })

    assert counts == {"watchlist": 2}
    assert source_labels(counts) == {"watchlist": "追蹤清單"}
    assert source_texts(counts) == {"watchlist": "追蹤清單 (watchlist)"}


def test_daily_decision_source_count_normalization_ignores_non_mapping_sources():
    from daily_decision_source_labels import normalize_source_counts

    for raw_sources in (None, ["watchlist"], (("watchlist", 1),)):
        assert normalize_source_counts(raw_sources) == {}


def test_daily_decision_source_count_normalization_drops_boolean_and_nonfinite_counts():
    from daily_decision_source_labels import normalize_source_counts

    try:
        counts = normalize_source_counts({
            "watchlist": True,
            "provider_impact": float("inf"),
            "report_repair": float("nan"),
            "screener": 1,
        })
    except OverflowError as exc:
        pytest.fail(f"non-finite source counts should be ignored: {exc}")

    assert counts == {"screener": 1}


def test_daily_decision_source_count_normalization_drops_fractional_counts():
    from daily_decision_source_labels import normalize_source_counts

    counts = normalize_source_counts({
        "watchlist": 1.7,
        "provider_impact": 2.0,
        "report_repair": "3",
        "screener": "4.5",
    })

    assert counts == {"provider_impact": 2, "report_repair": 3}


def test_daily_decision_source_count_normalization_requires_integral_numeric_counts():
    from decimal import Decimal
    from fractions import Fraction

    from daily_decision_source_labels import normalize_source_counts

    counts = normalize_source_counts({
        "watchlist": Decimal("1.7"),
        "provider_impact": Fraction(3, 2),
        "report_repair": Decimal("2.0"),
        "screener": Fraction(4, 1),
        "monitor": "5",
    })

    assert counts == {"report_repair": 2, "screener": 4, "monitor": 5}


def test_daily_decision_source_count_normalization_rejects_arbitrary_numeric_objects():
    from daily_decision_source_labels import normalize_source_counts

    class SyntheticSourceCount:
        def __init__(self, value):
            self.value = value

        def __int__(self):
            return self.value

        def __eq__(self, other):
            return other == self.value

    counts = normalize_source_counts({
        "watchlist": SyntheticSourceCount(3),
        "provider_impact": SyntheticSourceCount(2),
        "report_repair": 2,
    })

    assert counts == {"report_repair": 2}


def test_daily_decision_source_count_normalization_rejects_string_subclass_counts():
    from daily_decision_source_labels import normalize_source_counts

    class SyntheticStringCount(str):
        def __int__(self):
            return 7

    counts = normalize_source_counts({
        "watchlist": SyntheticStringCount("0"),
        "report_repair": "2",
    })

    assert counts == {"report_repair": 2}


def test_daily_decision_source_count_normalization_ignores_count_conversion_failures():
    from daily_decision_source_labels import normalize_source_counts

    class BrokenTruthCount:
        def __bool__(self):
            raise RuntimeError("source count truthiness unavailable")

    class BrokenIntCount:
        def __bool__(self):
            return True

        def __int__(self):
            raise RuntimeError("source count int unavailable")

    class BrokenCompareCount:
        def __bool__(self):
            return True

        def __int__(self):
            return 1

        def __eq__(self, other):
            raise RuntimeError("source count comparison unavailable")

    counts = normalize_source_counts({
        "watchlist": BrokenTruthCount(),
        "provider_impact": BrokenIntCount(),
        "notification_delivery": BrokenCompareCount(),
        "report_repair": 2,
    })

    assert counts == {"report_repair": 2}


def test_daily_decision_source_count_normalization_ignores_arithmetic_conversion_failures():
    from daily_decision_source_labels import normalize_source_counts

    class BrokenArithmeticTruthCount:
        def __bool__(self):
            raise ZeroDivisionError("source count arithmetic truthiness unavailable")

    class BrokenArithmeticIntCount:
        def __bool__(self):
            return True

        def __int__(self):
            raise ArithmeticError("source count arithmetic int unavailable")

    class BrokenArithmeticCompareCount:
        def __bool__(self):
            return True

        def __int__(self):
            return 1

        def __eq__(self, other):
            raise ArithmeticError("source count arithmetic comparison unavailable")

    counts = normalize_source_counts({
        "watchlist": BrokenArithmeticTruthCount(),
        "provider_impact": BrokenArithmeticIntCount(),
        "notification_delivery": BrokenArithmeticCompareCount(),
        "report_repair": 2,
    })

    assert counts == {"report_repair": 2}


def test_daily_decision_source_display_overrides_normalize_active_source_keys():
    from daily_decision_source_labels import source_display_overrides

    assert source_display_overrides(
        {" watchlist ": 2, "\tprovider_impact\n": 1},
        {"watchlist": " 人工清單 ", "provider_impact": "資料服務", "ghost_source": "幽靈來源"},
    ) == {"watchlist": "人工清單", "provider_impact": "資料服務"}


def test_daily_decision_source_display_overrides_ignore_non_mapping_active_sources():
    from daily_decision_source_labels import source_display_overrides

    overrides = {"watchlist": "人工清單"}
    for active_sources in (None, ["watchlist"], ("watchlist",)):
        assert source_display_overrides(active_sources, overrides) == {}


def test_daily_decision_source_helpers_ignore_mapping_accessor_failures():
    from daily_decision_source_labels import (
        normalize_source_counts,
        source_display_overrides,
        source_labels,
        source_texts,
    )

    class BrokenSourceMapping:
        def keys(self):
            raise RuntimeError("source keys unavailable")

        def items(self):
            raise RuntimeError("source items unavailable")

    broken_sources = BrokenSourceMapping()

    assert source_labels(broken_sources) == {}
    assert source_texts(broken_sources) == {}
    assert normalize_source_counts(broken_sources) == {}
    assert source_display_overrides(broken_sources, {"watchlist": "人工清單"}) == {}
    assert source_display_overrides({"watchlist": 1}, broken_sources) == {}


def test_daily_decision_source_helpers_ignore_arithmetic_mapping_failures():
    from daily_decision_source_labels import (
        normalize_source_counts,
        source_display_overrides,
        source_labels,
        source_texts,
    )

    class ArithmeticSourceMapping:
        def keys(self):
            raise ArithmeticError("source keys overflow")

        def items(self):
            raise ArithmeticError("source items overflow")

    arithmetic_sources = ArithmeticSourceMapping()

    assert source_labels(arithmetic_sources) == {}
    assert source_texts(arithmetic_sources) == {}
    assert normalize_source_counts(arithmetic_sources) == {}
    assert source_display_overrides(arithmetic_sources, {"watchlist": "人工清單"}) == {}
    assert source_display_overrides({"watchlist": 1}, arithmetic_sources) == {}


def test_daily_decision_source_helpers_ignore_mapping_attribute_failures():
    from daily_decision_source_labels import (
        normalize_source_counts,
        source_display_overrides,
        source_labels,
        source_texts,
    )

    class BrokenAccessorMapping:
        def __getattribute__(self, name):
            if name in {"keys", "items"}:
                raise RuntimeError(f"source {name} accessor failed")
            return super().__getattribute__(name)

    broken_sources = BrokenAccessorMapping()

    assert source_labels(broken_sources) == {}
    assert source_texts(broken_sources) == {}
    assert normalize_source_counts(broken_sources) == {}
    assert source_display_overrides(broken_sources, {"watchlist": "人工清單"}) == {}
    assert source_display_overrides({"watchlist": 1}, broken_sources) == {}


def test_daily_decision_source_helpers_ignore_source_key_trim_failures():
    from daily_decision_source_labels import (
        normalize_source_counts,
        source_display_overrides,
        source_key,
        source_label,
        source_labels,
        source_text,
        source_texts,
    )

    class BrokenSourceKey(str):
        def strip(self):
            raise RuntimeError("source key trim failed")

    broken_source = BrokenSourceKey("watchlist")
    sources = {broken_source: 3, " report_repair ": 2}

    assert source_key(broken_source) == ""
    assert source_label(broken_source) == ""
    assert source_text(broken_source) == ""
    assert normalize_source_counts(sources) == {"report_repair": 2}
    assert source_labels(sources) == {"report_repair": "報告修復"}
    assert source_texts(sources) == {"report_repair": "報告修復 (report_repair)"}
    assert source_display_overrides(
        sources,
        {broken_source: "惡意來源", "report_repair": " 報告品質 "},
    ) == {"report_repair": "報告品質"}


def test_daily_decision_source_helpers_ignore_non_string_source_key_trim_results():
    from daily_decision_source_labels import (
        normalize_source_counts,
        source_display_overrides,
        source_key,
        source_label,
        source_labels,
        source_text,
        source_texts,
    )

    class NonStringTrimSourceKey(str):
        def strip(self):
            return {"source": "watchlist"}

    malformed_source = NonStringTrimSourceKey("watchlist")
    sources = {malformed_source: 3, " report_repair ": 2}

    assert source_key(malformed_source) == ""
    assert source_label(malformed_source) == ""
    assert source_text(malformed_source) == ""
    assert normalize_source_counts(sources) == {"report_repair": 2}
    assert source_labels(sources) == {"report_repair": "報告修復"}
    assert source_texts(sources) == {"report_repair": "報告修復 (report_repair)"}
    assert source_display_overrides(
        sources,
        {malformed_source: "惡意來源", "report_repair": " 報告品質 "},
    ) == {"report_repair": "報告品質"}


def test_daily_decision_source_display_overrides_ignore_malformed_trimmed_values():
    from daily_decision_source_labels import source_display_overrides

    class BrokenOverrideText(str):
        def strip(self):
            raise RuntimeError("override trim failed")

    class NonStringOverrideText(str):
        def strip(self):
            return {"label": "資料來源"}

    assert source_display_overrides(
        {"watchlist": 1, "provider_impact": 1, "report_repair": 1},
        {
            "watchlist": BrokenOverrideText("人工清單"),
            "provider_impact": NonStringOverrideText("資料來源"),
            "report_repair": " 報告品質 ",
        },
    ) == {"report_repair": "報告品質"}


def test_daily_decision_source_helpers_ignore_string_subclass_trim_results():
    from daily_decision_source_labels import (
        normalize_source_counts,
        source_display_overrides,
        source_key,
        source_label,
        source_labels,
        source_text,
        source_texts,
    )

    class DangerousTrimResult(str):
        def __hash__(self):
            raise RuntimeError("trim result hash failed")

    class DangerousSourceKey(str):
        def strip(self):
            return DangerousTrimResult("watchlist")

    class DangerousOverrideText(str):
        def strip(self):
            return DangerousTrimResult("人工清單")

    dangerous_source = DangerousSourceKey("watchlist")
    sources = {dangerous_source: 3, " report_repair ": 2}

    assert source_key(dangerous_source) == ""
    assert source_label(dangerous_source) == ""
    assert source_text(dangerous_source) == ""
    assert normalize_source_counts(sources) == {"report_repair": 2}
    assert source_labels(sources) == {"report_repair": "報告修復"}
    assert source_texts(sources) == {"report_repair": "報告修復 (report_repair)"}
    assert source_display_overrides(
        {"watchlist": 1, "report_repair": 1},
        {"watchlist": DangerousOverrideText("人工清單"), "report_repair": " 報告品質 "},
    ) == {"report_repair": "報告品質"}


def test_daily_decision_source_helpers_ignore_malformed_mapping_items():
    from daily_decision_source_labels import normalize_source_counts, source_display_overrides

    class MalformedItemsMapping:
        def items(self):
            return [
                "watchlist",
                ("provider_impact", 1, "extra"),
                123,
                (" report_repair ", 2),
            ]

    class MalformedOverrideMapping:
        def items(self):
            return [
                "watchlist",
                ("provider_impact", "資料來源", "extra"),
                (" report_repair ", " 報告品質 "),
            ]

    assert normalize_source_counts(MalformedItemsMapping()) == {"report_repair": 2}
    assert source_display_overrides(
        {"report_repair": 1, "provider_impact": 1},
        MalformedOverrideMapping(),
    ) == {"report_repair": "報告品質"}


def test_daily_decision_source_helpers_ignore_mapping_item_unpack_failures():
    from daily_decision_source_labels import normalize_source_counts, source_display_overrides

    class BrokenItem:
        def __iter__(self):
            raise RuntimeError("source item unavailable")

    class BrokenItemsMapping:
        def items(self):
            return [
                BrokenItem(),
                (" report_repair ", 2),
            ]

    class BrokenOverrideMapping:
        def items(self):
            return [
                BrokenItem(),
                (" report_repair ", " 報告品質 "),
            ]

    assert normalize_source_counts(BrokenItemsMapping()) == {"report_repair": 2}
    assert source_display_overrides(
        {"report_repair": 1},
        BrokenOverrideMapping(),
    ) == {"report_repair": "報告品質"}


def test_daily_decision_source_helpers_ignore_lookup_failures():
    from daily_decision_source_labels import (
        normalize_source_counts,
        source_display_overrides,
        source_labels,
        source_texts,
    )

    class LookupBrokenItem:
        def __iter__(self):
            raise KeyError("source item lookup unavailable")

    class LookupBrokenItemsMapping:
        def items(self):
            return [
                LookupBrokenItem(),
                (" report_repair ", 2),
            ]

    class LookupBrokenKeysMapping:
        def keys(self):
            yield " report_repair "
            raise IndexError("source keys lookup unavailable")

    assert normalize_source_counts(LookupBrokenItemsMapping()) == {"report_repair": 2}
    assert source_display_overrides(
        {"report_repair": 1},
        LookupBrokenItemsMapping(),
    ) == {}
    assert source_labels(LookupBrokenKeysMapping()) == {"report_repair": "報告修復"}
    assert source_texts(LookupBrokenKeysMapping()) == {"report_repair": "報告修復 (report_repair)"}


def test_daily_decision_source_helpers_preserve_items_before_iterator_failure():
    from daily_decision_source_labels import normalize_source_counts, source_display_overrides

    class FailingItemsMapping:
        def items(self):
            yield (" report_repair ", 2)
            raise RuntimeError("source items iterator failed")

    class FailingOverrideMapping:
        def items(self):
            yield (" report_repair ", " 報告品質 ")
            raise RuntimeError("source override iterator failed")

    assert normalize_source_counts(FailingItemsMapping()) == {"report_repair": 2}
    assert source_display_overrides(
        {"report_repair": 1},
        FailingOverrideMapping(),
    ) == {"report_repair": "報告品質"}


def test_daily_decision_source_helpers_ignore_malformed_mapping_keys():
    from daily_decision_source_labels import source_display_overrides, source_labels, source_texts

    class StringKeysMapping:
        def keys(self):
            return "watchlist"

    malformed_sources = StringKeysMapping()

    assert source_labels(malformed_sources) == {}
    assert source_texts(malformed_sources) == {}
    assert source_display_overrides(malformed_sources, {"watchlist": "人工清單"}) == {}


def test_daily_decision_source_helpers_preserve_keys_before_iterator_failure():
    from daily_decision_source_labels import source_display_overrides, source_labels, source_texts

    class FailingKeysMapping:
        def keys(self):
            yield " report_repair "
            raise RuntimeError("source keys iterator failed")

    active_sources = FailingKeysMapping()

    assert source_labels(active_sources) == {"report_repair": "報告修復"}
    assert source_texts(active_sources) == {"report_repair": "報告修復 (report_repair)"}
    assert source_display_overrides(
        active_sources,
        {"report_repair": " 報告品質 "},
    ) == {"report_repair": "報告品質"}


def test_daily_decision_source_display_overrides_ignore_non_string_values():
    from daily_decision_source_labels import source_display_overrides

    assert source_display_overrides(
        {"watchlist": 2, "provider_impact": 1, "report_repair": 1},
        {"watchlist": 123, "provider_impact": True, "report_repair": " 報告品質 "},
    ) == {"report_repair": "報告品質"}


def test_daily_decision_queue_orders_repairs_backtests_reruns_and_route_warnings():
    queue = build_daily_decision_queue(
        reports=[
            {
                "ticker": "2308.TW",
                "filename": "2308_due.html",
                "pipeline_id": "v1",
                "date": "2025-01-02",
                "decision_freshness": {"requires_rerun": True},
            }
        ],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_blocked.html",
                "pipeline_id": "v2",
                "title": "內容可信度未通過",
                "detail": "目標價與買入建議不一致。",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 1000,
            }
        ],
        rerun_reports=[
            {
                "ticker": "2308.TW",
                "filename": "2308_due.html",
                "pipeline_id": "v1",
                "decision_freshness": {"requires_rerun": True},
            }
        ],
        high_priority_watchlist=[{"ticker": "2454.TW", "enabled": True, "decision_priority": "high"}],
        candidates=[{"ticker": "3661.TW", "score": 93}],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "model_route_budget": {
                "warnings": [
                    {
                        "id": "quality_gate_failures",
                        "route": "v2/gemini-2.5-pro",
                        "message": "quality_gate_failures=1",
                    }
                ]
            }
        },
        as_of=date(2026, 7, 8),
    )

    assert queue["schema_version"] == "daily_decision_queue.v1"
    assert queue["summary"]["total_actionable"] == 6
    assert queue["summary"]["displayed_count"] == 5
    types = [item["type"] for item in queue["items"]]
    assert types[:4] == ["manual_review", "model_route_warning", "backtest_due", "rerun_report"]
    assert types.index("backtest_due") < types.index("rerun_report")
    assert queue["items"][0]["source"] == "report_repair"
    assert queue["items"][1]["route"] == "v2/gemini-2.5-pro"
    assert queue["items"][2]["horizon_months"] == 3


def test_daily_decision_queue_free_mode_violations_use_string_safe_list():
    class Violation:
        def __str__(self):
            return "provider:openai_paid_key_required"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={
            "enabled": True,
            "can_run_without_paid_keys": False,
            "violations": (Violation(),),
        },
    )

    assert queue["items"][0]["type"] == "fix_free_mode"
    assert queue["items"][0]["violations"] == ["provider:openai_paid_key_required"]


def test_daily_decision_queue_free_mode_can_run_flag_uses_bool_safe_fallback():
    class BrokenFlag:
        def __bool__(self):
            raise RuntimeError("free mode can-run truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={
            "enabled": True,
            "can_run_without_paid_keys": BrokenFlag(),
            "violations": ["provider:openai_paid_key_required"],
        },
    )

    assert queue["items"][0]["type"] == "fix_free_mode"
    assert queue["items"][0]["violations"] == ["provider:openai_paid_key_required"]


def test_daily_decision_queue_display_limit_does_not_depend_on_truthiness():
    class BrokenLimit:
        def __bool__(self):
            raise RuntimeError("daily queue display limit truthiness unavailable")

        def __int__(self):
            return 2

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_blocked.html",
                "pipeline_id": "v2",
                "title": "內容可信度未通過",
                "detail": "目標價與買入建議不一致。",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 1000,
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[{"ticker": "2454.TW", "enabled": True, "decision_priority": "high"}],
        candidates=[{"ticker": "3661.TW", "score": 93}],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        limit=BrokenLimit(),
    )

    assert queue["summary"]["total_actionable"] == 3
    assert queue["summary"]["displayed_count"] == 2
    assert queue["secondary_count"] == 1
    assert [item["type"] for item in queue["items"]] == ["manual_review", "run_watchlist"]


def test_daily_decision_queue_watchlist_items_do_not_depend_on_truthiness():
    class BrokenWatchlist(list):
        def __bool__(self):
            raise RuntimeError("daily queue watchlist truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=BrokenWatchlist([
            {"ticker": "2454.TW", "enabled": True, "decision_priority": "high"}
        ]),
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["summary"]["sources"] == {"watchlist": 1}
    assert queue["items"][0]["type"] == "run_watchlist"
    assert queue["items"][0]["title"] == "1 檔 watchlist 待分析"
    assert queue["items"][0]["detail"] == "2454.TW"


def test_daily_decision_queue_preserves_blocked_repair_boundaries():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "title": "資料快照完整性未通過",
                "detail": "snapshot_hash mismatch",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 980,
                "blocks_auto_rerun": True,
                "reason_codes": ["data_snapshot_integrity_invalid"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["summary"]["sources"] == {"report_repair": 1}
    action = queue["items"][0]
    assert action["type"] == "manual_review"
    assert action["blocks_auto_rerun"] is True
    assert action["reason_codes"] == ["data_snapshot_integrity_invalid"]


def test_daily_decision_queue_report_repair_items_do_not_depend_on_truthiness():
    class BrokenRepairItems(list):
        def __bool__(self):
            raise RuntimeError("daily queue repair items truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=BrokenRepairItems([
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "title": "資料快照完整性未通過",
                "detail": "snapshot_hash mismatch",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 980,
                "blocks_auto_rerun": True,
                "reason_codes": ["data_snapshot_integrity_invalid"],
            }
        ]),
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["summary"]["sources"] == {"report_repair": 1}
    assert queue["items"][0]["type"] == "manual_review"


def test_daily_decision_queue_report_repair_partial_iterator_failures_use_remaining_native_items():
    class PartialBrokenRepairIterator:
        def __init__(self, first_row):
            self._first_row = first_row
            self._step = 0

        def __iter__(self):
            return self

        def __next__(self):
            self._step += 1
            if self._step == 1:
                return self._first_row
            raise RuntimeError("daily queue repair items stopped early")

    class PartialBrokenRepairItems(list):
        def __iter__(self):
            return PartialBrokenRepairIterator(list.__getitem__(self, 0))

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=PartialBrokenRepairItems([
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "title": "資料快照完整性未通過",
                "detail": "snapshot_hash mismatch",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 980,
                "blocks_auto_rerun": True,
                "reason_codes": ["data_snapshot_integrity_invalid"],
            },
            {
                "ticker": "2317.TW",
                "filename": "2317_stale.html",
                "pipeline_id": "v1",
                "title": "資料來源過期",
                "detail": "market data stale",
                "recommended_action": "refresh_data",
                "severity": "warning",
                "priority_score": 970,
                "reason_codes": ["data_trust_stale"],
            },
        ]),
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["summary"]["sources"] == {"report_repair": 2}
    assert queue["summary"]["total_actionable"] == 2
    assert [item["filename"] for item in queue["items"]] == ["2330_corrupt.html", "2317_stale.html"]


def test_daily_decision_queue_report_repair_reason_codes_partial_iterator_failures_use_remaining_native_items():
    class PartialBrokenReasonCodeIterator:
        def __init__(self, first_code):
            self._first_code = first_code
            self._step = 0

        def __iter__(self):
            return self

        def __next__(self):
            self._step += 1
            if self._step == 1:
                return self._first_code
            raise RuntimeError("daily queue repair reason codes stopped early")

    class PartialBrokenReasonCodes(list):
        def __iter__(self):
            return PartialBrokenReasonCodeIterator(list.__getitem__(self, 0))

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "title": "資料快照完整性未通過",
                "detail": "snapshot_hash mismatch",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 980,
                "blocks_auto_rerun": True,
                "reason_codes": PartialBrokenReasonCodes([
                    "data_snapshot_integrity_invalid",
                    "data_trust_stale",
                ]),
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["reason_codes"] == [
        "data_snapshot_integrity_invalid",
        "data_trust_stale",
    ]


def test_daily_decision_queue_ops_payload_does_not_depend_on_truthiness():
    class BrokenOps(dict):
        def __bool__(self):
            raise RuntimeError("daily queue ops truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "title": "資料快照完整性未通過",
                "detail": "snapshot_hash mismatch",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 980,
                "blocks_auto_rerun": True,
                "reason_codes": ["data_snapshot_integrity_invalid"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops=BrokenOps({
            "model_route_budget": {
                "warnings": [
                    {
                        "id": "quality_gate_failures",
                        "route": "analysis",
                        "message": "quality gates failing",
                    }
                ]
            }
        }),
    )

    assert queue["summary"]["sources"] == {"report_repair": 1, "model_route_budget": 1}
    assert [item["type"] for item in queue["items"][:2]] == ["manual_review", "model_route_warning"]
    assert queue["items"][1]["warning_id"] == "quality_gate_failures"


def test_daily_decision_queue_repair_detail_does_not_depend_on_truthiness():
    class BrokenRepairDetail:
        def __bool__(self):
            raise RuntimeError("daily queue repair detail truthiness unavailable")

        def __str__(self):
            return "snapshot_hash mismatch"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "title": "資料快照完整性未通過",
                "detail": BrokenRepairDetail(),
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 980,
                "blocks_auto_rerun": True,
                "reason_codes": ["data_snapshot_integrity_invalid"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["detail"] == "snapshot_hash mismatch"


def test_daily_decision_queue_repair_title_does_not_depend_on_truthiness():
    class BrokenRepairTitle:
        def __bool__(self):
            raise RuntimeError("daily queue repair title truthiness unavailable")

        def __str__(self):
            return "資料快照完整性未通過"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "title": BrokenRepairTitle(),
                "detail": "snapshot_hash mismatch",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 980,
                "blocks_auto_rerun": True,
                "reason_codes": ["data_snapshot_integrity_invalid"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["title"] == "2330.TW v2 資料快照完整性未通過"


def test_daily_decision_queue_repair_filename_does_not_depend_on_truthiness():
    class BrokenRepairFilename:
        def __bool__(self):
            raise RuntimeError("daily queue repair filename truthiness unavailable")

        def __str__(self):
            return "2330_corrupt.html"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": BrokenRepairFilename(),
                "report_filename": "2330_alias.html",
                "pipeline_id": "v2",
                "title": "資料快照完整性未通過",
                "detail": "snapshot_hash mismatch",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 980,
                "blocks_auto_rerun": True,
                "reason_codes": ["data_snapshot_integrity_invalid"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["filename"] == "2330_corrupt.html"
    assert queue["items"][0]["report_filename"] == "2330_corrupt.html"


def test_daily_decision_queue_repair_recommended_action_does_not_depend_on_truthiness():
    class BrokenRecommendedAction:
        def __bool__(self):
            raise RuntimeError("daily queue repair recommended action truthiness unavailable")

        def __str__(self):
            return "refresh_data_snapshot"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_stale.html",
                "pipeline_id": "v2",
                "title": "資料快照需刷新",
                "detail": "先刷新資料快照。",
                "recommended_action": BrokenRecommendedAction(),
                "severity": "warning",
                "priority_score": 820,
                "blocks_auto_rerun": False,
                "reason_codes": ["data_trust_stale"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["type"] == "refresh_data_snapshot"
    assert queue["items"][0]["recommended_action"] == "refresh_data_snapshot"


def test_daily_decision_queue_repair_ticker_does_not_depend_on_truthiness():
    class BrokenRepairTicker:
        def __bool__(self):
            raise RuntimeError("daily queue repair ticker truthiness unavailable")

        def __str__(self):
            return "2330.TW"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": BrokenRepairTicker(),
                "filename": "2330_stale.html",
                "pipeline_id": "v2",
                "title": "資料快照需刷新",
                "detail": "先刷新資料快照。",
                "recommended_action": "refresh_data_snapshot",
                "severity": "warning",
                "priority_score": 820,
                "blocks_auto_rerun": False,
                "reason_codes": ["data_trust_stale"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["ticker"] == "2330.TW"
    assert queue["items"][0]["title"] == "2330.TW v2 資料快照需刷新"


def test_daily_decision_queue_repair_pipeline_id_does_not_depend_on_truthiness():
    class BrokenRepairPipelineId:
        def __bool__(self):
            raise RuntimeError("daily queue repair pipeline id truthiness unavailable")

        def __str__(self):
            return "v2"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_stale.html",
                "pipeline_id": BrokenRepairPipelineId(),
                "title": "資料快照需刷新",
                "detail": "先刷新資料快照。",
                "recommended_action": "refresh_data_snapshot",
                "severity": "warning",
                "priority_score": 820,
                "blocks_auto_rerun": False,
                "reason_codes": ["data_trust_stale"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["pipeline_id"] == "v2"
    assert queue["items"][0]["title"] == "2330.TW v2 資料快照需刷新"


def test_daily_decision_queue_repair_priority_score_does_not_depend_on_truthiness():
    class BrokenRepairPriorityScore:
        def __bool__(self):
            raise RuntimeError("daily queue repair priority score truthiness unavailable")

        def __int__(self):
            return 820

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_stale.html",
                "pipeline_id": "v2",
                "title": "資料快照需刷新",
                "detail": "先刷新資料快照。",
                "recommended_action": "refresh_data_snapshot",
                "severity": "warning",
                "priority_score": BrokenRepairPriorityScore(),
                "blocks_auto_rerun": False,
                "reason_codes": ["data_trust_stale"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["priority_score"] == 820


def test_daily_decision_queue_repair_priority_score_int_failures_fall_back():
    class BrokenRepairPriorityScore:
        def __int__(self):
            raise RuntimeError("daily queue repair priority int unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_priority.html",
                "pipeline_id": "v2",
                "title": "內容可信度未通過",
                "detail": "priority conversion failure should fall back.",
                "recommended_action": "manual_review",
                "priority_score": BrokenRepairPriorityScore(),
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["summary"]["sources"] == {"report_repair": 1}
    assert queue["summary"]["top_priority_score"] == 700
    assert queue["items"][0]["priority_score"] == 700


def test_daily_decision_queue_repair_severity_uses_string_safe_payload():
    class StringableSeverity:
        def __bool__(self):
            raise RuntimeError("daily queue repair severity truthiness unavailable")

        def __str__(self):
            return "blocked"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_stale.html",
                "pipeline_id": "v2",
                "title": "資料快照需刷新",
                "detail": "先刷新資料快照。",
                "recommended_action": "manual_review",
                "severity": StringableSeverity(),
                "priority_score": 820,
                "blocks_auto_rerun": True,
                "reason_codes": ["data_snapshot_integrity_invalid"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["severity"] == "blocked"


def test_daily_decision_queue_repair_action_label_uses_string_safe_payload():
    class StringableActionLabel:
        def __bool__(self):
            raise RuntimeError("daily queue repair action label truthiness unavailable")

        def __str__(self):
            return "人工檢查"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "2330.TW",
                "filename": "2330_stale.html",
                "pipeline_id": "v2",
                "title": "資料快照需刷新",
                "detail": "先刷新資料快照。",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 820,
                "action_label": StringableActionLabel(),
                "blocks_auto_rerun": True,
                "reason_codes": ["data_snapshot_integrity_invalid"],
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["action_label"] == "人工檢查"


def test_daily_decision_candidate_preserves_company_and_reason_context():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[
            {
                "ticker": "2408.TW",
                "company_name": "南亞科",
                "reason": "外資買超 15430 張、投信買超 3250 張、自營商 0 張",
                "score": 18680.0,
            }
        ],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    candidate = queue["items"][0]
    assert candidate == {
        "source": "screener",
        "type": "review_candidate",
        "priority_score": 420,
        "title": "2408.TW 南亞科",
        "detail": "外資買超 15430 張、投信買超 3250 張、自營商 0 張",
        "ticker": "2408.TW",
        "company_name": "南亞科",
        "reason": "外資買超 15430 張、投信買超 3250 張、自營商 0 張",
        "score": 18680.0,
    }


def test_daily_decision_candidate_items_do_not_depend_on_truthiness():
    class BrokenCandidates(list):
        def __bool__(self):
            raise RuntimeError("daily queue candidate truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=BrokenCandidates([
            {
                "ticker": "2408.TW",
                "company_name": "南亞科",
                "reason": "外資買超 15430 張",
                "score": 18680.0,
            }
        ]),
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["summary"]["sources"] == {"screener": 1}
    assert queue["items"][0]["type"] == "review_candidate"
    assert queue["items"][0]["title"] == "2408.TW 南亞科"
    assert queue["items"][0]["detail"] == "外資買超 15430 張"


def test_daily_decision_candidate_text_fields_do_not_depend_on_truthiness():
    class BrokenCandidateText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("daily queue candidate text truthiness unavailable")

        def __str__(self):
            return self.value

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[
            {
                "ticker": BrokenCandidateText("2408.TW"),
                "company_name": BrokenCandidateText("南亞科"),
                "reason": BrokenCandidateText("外資買超 15430 張"),
                "score": 18680.0,
            }
        ],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    candidate = queue["items"][0]
    assert candidate["type"] == "review_candidate"
    assert candidate["title"] == "2408.TW 南亞科"
    assert candidate["detail"] == "外資買超 15430 張"
    assert candidate["ticker"] == "2408.TW"
    assert candidate["company_name"] == "南亞科"
    assert candidate["reason"] == "外資買超 15430 張"


def test_daily_decision_candidate_falls_back_when_company_and_reason_are_missing():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[{"ticker": "2408.TW", "score": 18680.0}],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    candidate = queue["items"][0]
    assert candidate["title"] == "2408.TW"
    assert candidate["detail"] == "市場掃描候選"


def test_daily_decision_queue_excludes_latency_but_preserves_retry_route_warnings():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "model_route_budget": {
                "warnings": [
                    {
                        "id": "slow_route",
                        "route": "v1/gemini-3.5-flash",
                        "message": "p95_latency_ms=399974",
                    },
                    {
                        "id": "retry_storm",
                        "route": "v2/gemma-4-31b-it",
                        "message": "retry_count=7",
                    },
                    {
                        "id": "quality_gate_failures",
                        "route": "v3/gemini-3.5-flash",
                        "message": "quality_gate_failures=1",
                    },
                    {
                        "id": "future_route_condition",
                        "route": "v5/future-model",
                        "message": "future condition",
                    },
                ]
            }
        },
    )

    assert queue["summary"]["total_actionable"] == 3
    assert queue["summary"]["sources"] == {"model_route_budget": 3}
    assert [item["warning_id"] for item in queue["items"]] == [
        "quality_gate_failures",
        "retry_storm",
        "future_route_condition",
    ]
    assert [item["type"] for item in queue["items"]] == [
        "model_route_warning",
        "model_route_warning",
        "model_route_warning",
    ]


def test_daily_decision_queue_excludes_nonblocking_provider_monitor():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "2324.TW",
                    "summary": {
                        "recommended_action": "monitor_provider",
                        "blocks_auto_rerun": False,
                    },
                },
                {
                    "ticker": "NVDA",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                },
            ]
        },
    )

    assert queue["summary"]["total_actionable"] == 1
    assert queue["summary"]["sources"] == {"provider_impact": 1}
    assert queue["items"][0]["ticker"] == "NVDA"
    assert queue["items"][0]["type"] == "wait_provider_recovery"
    assert queue["items"][0]["blocks_auto_rerun"] is True


def test_daily_decision_queue_uses_provider_impact_to_outrank_watchlist():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[{"ticker": "2308.TW", "enabled": True, "decision_priority": "high"}],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                        "max_severity": "critical",
                    },
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ]
        },
    )

    assert [item["type"] for item in queue["items"][:2]] == ["wait_provider_recovery", "run_watchlist"]
    assert queue["items"][0]["source"] == "provider_impact"
    assert queue["items"][0]["priority_score"] > queue["items"][1]["priority_score"]
    assert queue["summary"]["source_labels"] == {"provider_impact": "資料來源", "watchlist": "追蹤清單"}
    assert queue["summary"]["source_texts"] == {
        "provider_impact": "資料來源 (provider_impact)",
        "watchlist": "追蹤清單 (watchlist)",
    }


def test_daily_decision_queue_preserves_report_filename_alias_for_provider_impact_action():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "NVDA",
                    "report_filename": "nvda_provider_alias.html",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ]
        },
    )

    assert queue["summary"]["sources"] == {"provider_impact": 1}
    assert queue["items"][0]["type"] == "wait_provider_recovery"
    assert queue["items"][0]["filename"] == "nvda_provider_alias.html"


def test_daily_decision_queue_provider_impact_ledger_does_not_depend_on_truthiness():
    class BrokenProviderLedger(dict):
        def __bool__(self):
            raise RuntimeError("daily queue provider ledger truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger=BrokenProviderLedger({
            "items": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ]
        }),
    )

    assert queue["summary"]["sources"] == {"provider_impact": 1}
    assert queue["items"][0]["type"] == "wait_provider_recovery"


def test_daily_decision_queue_accepts_mapping_provider_impact_ledger():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger=MappingProxyType(
            {
                "items": [
                    {
                        "ticker": "NVDA",
                        "filename": "nvda_provider.html",
                        "pipeline_id": "v2",
                        "summary": {
                            "recommended_action": "wait_provider_recovery",
                            "blocks_auto_rerun": True,
                        },
                        "impacts": [{"message": "market_data/yfinance critical"}],
                    }
                ]
            }
        ),
    )

    assert queue["summary"]["sources"] == {"provider_impact": 1}
    assert queue["items"][0]["type"] == "wait_provider_recovery"
    assert queue["items"][0]["filename"] == "nvda_provider.html"


def test_daily_decision_queue_accepts_mapping_provider_impact_summary():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "summary": MappingProxyType(
                        {
                            "recommended_action": "wait_provider_recovery",
                            "blocks_auto_rerun": True,
                        }
                    ),
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ]
        },
    )

    assert queue["summary"]["sources"] == {"provider_impact": 1}
    assert queue["items"][0]["type"] == "wait_provider_recovery"
    assert queue["items"][0]["recommended_action"] == "wait_provider_recovery"


def test_daily_decision_queue_provider_impact_filename_alias_does_not_depend_on_truthiness():
    class BrokenProviderFilename:
        def __bool__(self):
            raise RuntimeError("daily queue provider filename truthiness unavailable")

        def __str__(self):
            return "nvda_provider.html"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "NVDA",
                    "filename": BrokenProviderFilename(),
                    "report_filename": "ignored_provider_alias.html",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ]
        },
    )

    assert queue["items"][0]["filename"] == "nvda_provider.html"
    assert queue["items"][0]["report_filename"] == "nvda_provider.html"


def test_daily_decision_queue_provider_impact_items_do_not_depend_on_truthiness():
    class BrokenProviderItems(list):
        def __bool__(self):
            raise RuntimeError("daily queue provider items truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": BrokenProviderItems([
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ])
        },
    )

    assert queue["summary"]["sources"] == {"provider_impact": 1}
    assert queue["items"][0]["type"] == "wait_provider_recovery"


def test_daily_decision_queue_provider_impact_blocks_flag_does_not_interrupt_queue():
    class BrokenProviderBlocks:
        def __bool__(self):
            raise RuntimeError("daily queue provider blocks truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": BrokenProviderBlocks(),
                    },
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ]
        },
    )

    assert queue["summary"]["total_actionable"] == 0
    assert queue["items"][0]["type"] == "monitor"


def test_daily_decision_queue_provider_impact_recommended_action_does_not_depend_on_truthiness():
    class BrokenProviderRecommendedAction:
        def __bool__(self):
            raise RuntimeError("daily queue provider recommended action truthiness unavailable")

        def __str__(self):
            return "wait_provider_recovery"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": BrokenProviderRecommendedAction(),
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ]
        },
    )

    assert queue["items"][0]["type"] == "wait_provider_recovery"
    assert queue["items"][0]["recommended_action"] == "wait_provider_recovery"


def test_daily_decision_queue_provider_impact_ticker_uses_string_safe_payload():
    class BrokenProviderTicker:
        def __bool__(self):
            raise RuntimeError("daily queue provider ticker truthiness unavailable")

        def __str__(self):
            return "NVDA"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": BrokenProviderTicker(),
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ]
        },
    )

    assert queue["items"][0]["ticker"] == "NVDA"
    assert queue["items"][0]["title"] == "NVDA provider 影響需處理"


def test_daily_decision_queue_provider_impact_pipeline_id_uses_string_safe_payload():
    class BrokenProviderPipelineId:
        def __bool__(self):
            raise RuntimeError("daily queue provider pipeline id truthiness unavailable")

        def __str__(self):
            return "v2"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": BrokenProviderPipelineId(),
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "market_data/yfinance critical"}],
                }
            ]
        },
    )

    assert queue["items"][0]["pipeline_id"] == "v2"


def test_daily_decision_queue_provider_impact_message_uses_string_safe_detail():
    class BrokenProviderImpactMessage:
        def __bool__(self):
            raise RuntimeError("daily queue provider impact message truthiness unavailable")

        def __str__(self):
            return "market_data/yfinance critical"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": BrokenProviderImpactMessage()}],
                }
            ]
        },
    )

    assert queue["items"][0]["detail"] == "market_data/yfinance critical"


def test_daily_decision_queue_uses_ticker_pipeline_key_when_filename_missing():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "NVDA",
                "pipeline_id": "v2",
                "title": "內容可信度未通過",
                "detail": "缺少 filename 的 report 仍應以 ticker/pipeline 去重。",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 1000,
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "NVDA",
                    "pipeline_id": "v2",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "同一份報告的 provider impact 已由 repair item 承接。"}],
                }
            ]
        },
    )

    assert queue["summary"]["total_actionable"] == 1
    assert queue["summary"]["sources"] == {"report_repair": 1}
    assert queue["items"][0]["type"] == "manual_review"
    assert queue["items"][0]["ticker"] == "NVDA"


def test_daily_decision_queue_preserves_report_filename_alias_for_repair_identity():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            {
                "ticker": "NVDA",
                "report_filename": "nvda_alias.html",
                "pipeline_id": "v2",
                "title": "內容可信度未通過",
                "detail": "repair item 只有 report_filename 也應保留 artifact identity。",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 1000,
            }
        ],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "report_filename": "nvda_alias.html",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "同一 artifact 的 provider impact 已由 repair item 承接。"}],
                }
            ]
        },
    )

    assert queue["summary"]["total_actionable"] == 1
    assert queue["summary"]["sources"] == {"report_repair": 1}
    assert queue["items"][0]["filename"] == "nvda_alias.html"
    assert queue["items"][0]["type"] == "manual_review"


def test_daily_decision_queue_computes_backtest_due_from_report_filename_alias():
    queue = build_daily_decision_queue(
        reports=[
            {
                "ticker": "NVDA",
                "report_filename": "nvda_due_alias.html",
                "pipeline_id": "v2",
                "date": "2025-01-02",
            }
        ],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 9),
    )

    assert queue["summary"]["total_actionable"] == 1
    assert queue["summary"]["sources"] == {"backtest_due": 1}
    assert queue["items"][0]["type"] == "backtest_due"
    assert queue["items"][0]["filename"] == "nvda_due_alias.html"
    assert queue["items"][0]["horizon_months"] == 3


def test_daily_decision_queue_computed_backtest_report_filename_does_not_depend_on_truthiness():
    class BrokenBacktestReportFilename:
        def __bool__(self):
            raise RuntimeError("daily queue computed backtest report filename truthiness unavailable")

        def __str__(self):
            return "nvda_due.html"

    queue = build_daily_decision_queue(
        reports=[
            {
                "ticker": "NVDA",
                "filename": BrokenBacktestReportFilename(),
                "pipeline_id": "v2",
                "date": "2025-01-02",
            }
        ],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 9),
    )

    assert queue["summary"]["sources"] == {"backtest_due": 1}
    item = queue["items"][0]
    assert item["type"] == "backtest_due"
    assert item["filename"] == "nvda_due.html"
    assert item["report_filename"] == "nvda_due.html"
    assert item["pipeline_id"] == "v2"
    assert item["horizon_months"] == 3


def test_daily_decision_queue_preserves_report_filename_alias_for_backtest_due_action():
    queue = build_daily_decision_queue(
        reports=[
            {
                "ticker": "NVDA",
                "report_filename": "nvda_due_alias.html",
                "pipeline_id": "v2",
                "date": "2025-01-02",
            }
        ],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 9),
    )

    assert queue["items"][0]["type"] == "backtest_due"
    assert queue["items"][0]["filename"] == "nvda_due_alias.html"
    assert queue["items"][0]["report_filename"] == "nvda_due_alias.html"


def test_daily_decision_queue_explicit_backtests_do_not_depend_on_truthiness():
    class BrokenDueBacktests(list):
        def __bool__(self):
            raise RuntimeError("daily queue due backtests truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={
            "summary": {},
            "details": [],
            "due_backtests": BrokenDueBacktests([
                {
                    "ticker": "NVDA",
                    "report_filename": "nvda_due_alias.html",
                    "pipeline_id": "v2",
                    "horizon_months": 6,
                }
            ]),
        },
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 11),
    )

    assert queue["summary"]["sources"] == {"backtest_due": 1}
    assert queue["items"][0]["type"] == "backtest_due"
    assert queue["items"][0]["filename"] == "nvda_due_alias.html"
    assert queue["items"][0]["report_filename"] == "nvda_due_alias.html"
    assert queue["items"][0]["horizon_months"] == 6


def test_daily_decision_queue_integer_conversion_treats_boolean_horizon_as_malformed():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={
            "summary": {},
            "details": [],
            "due_backtests": [
                {
                    "ticker": "NVDA",
                    "report_filename": "nvda_due_alias.html",
                    "pipeline_id": "v2",
                    "horizon_months": True,
                }
            ],
        },
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 11),
    )

    assert queue["items"][0]["type"] == "backtest_due"
    assert queue["items"][0]["title"] == "NVDA 3M 回測到期"
    assert queue["items"][0]["horizon_months"] == 3


def test_daily_decision_queue_integer_conversion_treats_fractional_float_horizon_as_malformed():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={
            "summary": {},
            "details": [],
            "due_backtests": [
                {
                    "ticker": "NVDA",
                    "report_filename": "nvda_due_alias.html",
                    "pipeline_id": "v2",
                    "horizon_months": 1.7,
                }
            ],
        },
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 11),
    )

    assert queue["items"][0]["type"] == "backtest_due"
    assert queue["items"][0]["title"] == "NVDA 3M 回測到期"
    assert queue["items"][0]["horizon_months"] == 3


@pytest.mark.parametrize("horizon", [Decimal("1.7"), Fraction(3, 2)])
def test_daily_decision_queue_integer_conversion_treats_fractional_exact_numeric_horizon_as_malformed(horizon):
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={
            "summary": {},
            "details": [],
            "due_backtests": [
                {
                    "ticker": "NVDA",
                    "report_filename": "nvda_due_alias.html",
                    "pipeline_id": "v2",
                    "horizon_months": horizon,
                }
            ],
        },
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 11),
    )

    assert queue["items"][0]["type"] == "backtest_due"
    assert queue["items"][0]["title"] == "NVDA 3M 回測到期"
    assert queue["items"][0]["horizon_months"] == 3


def test_daily_decision_queue_backtest_due_text_fields_do_not_depend_on_truthiness():
    class BrokenBacktestDueText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("daily queue backtest due text truthiness unavailable")

        def __str__(self):
            return self.value

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={
            "summary": {},
            "details": [],
            "due_backtests": [
                {
                    "ticker": BrokenBacktestDueText("NVDA"),
                    "filename": BrokenBacktestDueText("nvda_due.html"),
                    "pipeline_id": BrokenBacktestDueText("v2"),
                    "horizon_months": 6,
                }
            ],
        },
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 11),
    )

    assert queue["summary"]["sources"] == {"backtest_due": 1}
    item = queue["items"][0]
    assert item["type"] == "backtest_due"
    assert item["title"] == "NVDA 6M 回測到期"
    assert item["ticker"] == "NVDA"
    assert item["filename"] == "nvda_due.html"
    assert item["report_filename"] == "nvda_due.html"
    assert item["pipeline_id"] == "v2"
    assert item["horizon_months"] == 6


def test_daily_decision_queue_backtest_details_do_not_depend_on_truthiness():
    class BrokenBacktestDetails(list):
        def __bool__(self):
            raise RuntimeError("daily queue backtest details truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[
            {
                "ticker": "NVDA",
                "report_filename": "nvda_due_alias.html",
                "pipeline_id": "v2",
                "date": "2025-01-02",
            }
        ],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={
            "summary": {},
            "details": BrokenBacktestDetails([
                {
                    "report_filename": "other_report.html",
                    "horizon_months": 3,
                }
            ]),
        },
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 11),
    )

    assert queue["summary"]["sources"] == {"backtest_due": 1}
    assert queue["items"][0]["type"] == "backtest_due"
    assert queue["items"][0]["filename"] == "nvda_due_alias.html"
    assert queue["items"][0]["horizon_months"] == 3


def test_daily_decision_queue_backtest_reports_do_not_depend_on_truthiness():
    class BrokenReports(list):
        def __bool__(self):
            raise RuntimeError("daily queue reports truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=BrokenReports([
            {
                "ticker": "NVDA",
                "report_filename": "nvda_due_alias.html",
                "pipeline_id": "v2",
                "date": "2025-01-02",
            }
        ]),
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 11),
    )

    assert queue["summary"]["sources"] == {"backtest_due": 1}
    assert queue["items"][0]["type"] == "backtest_due"
    assert queue["items"][0]["filename"] == "nvda_due_alias.html"
    assert queue["items"][0]["horizon_months"] == 3


def test_daily_decision_queue_computed_backtest_report_dates_use_string_safe_conversion():
    class BrokenDate:
        def __bool__(self):
            raise RuntimeError("daily queue report date truthiness unavailable")

        def __str__(self):
            return "2025-01-02T09:30:00"

    queue = build_daily_decision_queue(
        reports=[
            {
                "ticker": "NVDA",
                "filename": "nvda_due.html",
                "pipeline_id": "v2",
                "date": BrokenDate(),
            },
            {
                "ticker": "TSMC",
                "filename": "tsmc_due.html",
                "pipeline_id": "v1",
                "date": "2025-01-02",
            },
        ],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        as_of=date(2026, 7, 11),
    )

    assert queue["summary"]["sources"] == {"backtest_due": 2}
    assert [item["filename"] for item in queue["items"]] == ["nvda_due.html", "tsmc_due.html"]
    assert {item["horizon_months"] for item in queue["items"]} == {3}


def test_daily_decision_queue_preserves_report_filename_alias_for_rerun_action():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[
            {
                "ticker": "NVDA",
                "report_filename": "nvda_rerun_alias.html",
                "pipeline_id": "v2",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照與結論不同步。",
                },
            }
        ],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["summary"]["sources"] == {"rerun_report": 1}
    assert queue["items"][0]["type"] == "rerun_report"
    assert queue["items"][0]["filename"] == "nvda_rerun_alias.html"


def test_daily_decision_queue_rerun_reports_do_not_depend_on_truthiness():
    class BrokenRerunReports(list):
        def __bool__(self):
            raise RuntimeError("daily queue rerun reports truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=BrokenRerunReports([
            {
                "ticker": "NVDA",
                "report_filename": "nvda_rerun_alias.html",
                "pipeline_id": "v2",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照與結論不同步。",
                },
            }
        ]),
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["summary"]["sources"] == {"rerun_report": 1}
    assert queue["items"][0]["type"] == "rerun_report"
    assert queue["items"][0]["filename"] == "nvda_rerun_alias.html"
    assert queue["items"][0]["pipeline_id"] == "v2"


def test_daily_decision_queue_rerun_ticker_does_not_depend_on_truthiness():
    class BrokenRerunTicker:
        def __bool__(self):
            raise RuntimeError("daily queue rerun ticker truthiness unavailable")

        def __str__(self):
            return "NVDA"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[
            {
                "ticker": BrokenRerunTicker(),
                "filename": "nvda_rerun.html",
                "pipeline_id": "v2",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照與結論不同步。",
                },
            }
        ],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["ticker"] == "NVDA"
    assert queue["items"][0]["title"] == "NVDA v2 結論需重跑"


def test_daily_decision_queue_rerun_pipeline_id_does_not_depend_on_truthiness():
    class BrokenRerunPipelineId:
        def __bool__(self):
            raise RuntimeError("daily queue rerun pipeline truthiness unavailable")

        def __str__(self):
            return "v2"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[
            {
                "ticker": "NVDA",
                "filename": "nvda_rerun.html",
                "pipeline_id": BrokenRerunPipelineId(),
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照與結論不同步。",
                },
            }
        ],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["pipeline_id"] == "v2"
    assert queue["items"][0]["title"] == "NVDA v2 結論需重跑"


def test_daily_decision_queue_rerun_filename_alias_does_not_depend_on_truthiness():
    class BrokenRerunFilename:
        def __bool__(self):
            raise RuntimeError("daily queue rerun filename truthiness unavailable")

        def __str__(self):
            return "nvda_rerun.html"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[
            {
                "ticker": "NVDA",
                "filename": BrokenRerunFilename(),
                "report_filename": "ignored_alias.html",
                "pipeline_id": "v2",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照與結論不同步。",
                },
            }
        ],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["filename"] == "nvda_rerun.html"
    assert queue["items"][0]["report_filename"] == "nvda_rerun.html"


def test_daily_decision_queue_rerun_detail_does_not_depend_on_truthiness():
    class BrokenRerunDetail:
        def __bool__(self):
            raise RuntimeError("daily queue rerun detail truthiness unavailable")

        def __str__(self):
            return "資料快照與結論不同步。"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[
            {
                "ticker": "NVDA",
                "filename": "nvda_rerun.html",
                "pipeline_id": "v2",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": BrokenRerunDetail(),
                },
            }
        ],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["detail"] == "資料快照與結論不同步。"


def test_daily_decision_queue_report_key_ticker_does_not_depend_on_truthiness():
    class BrokenReportKeyTicker:
        def __bool__(self):
            raise RuntimeError("daily queue report key ticker truthiness unavailable")

        def __str__(self):
            return "NVDA"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[
            {
                "ticker": BrokenReportKeyTicker(),
                "pipeline_id": "v2",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照與結論不同步。",
                },
            }
        ],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["ticker"] == "NVDA"
    assert queue["items"][0]["title"] == "NVDA v2 結論需重跑"


def test_daily_decision_queue_report_key_pipeline_id_does_not_depend_on_truthiness():
    class BrokenReportKeyPipelineId:
        def __bool__(self):
            raise RuntimeError("daily queue report key pipeline truthiness unavailable")

        def __str__(self):
            return "v2"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[
            {
                "ticker": "NVDA",
                "pipeline_id": BrokenReportKeyPipelineId(),
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照與結論不同步。",
                },
            }
        ],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["pipeline_id"] == "v2"
    assert queue["items"][0]["title"] == "NVDA v2 結論需重跑"


def test_daily_decision_queue_reads_action_fields_without_mapping_get_accessors():
    class BrokenGetDict(dict):
        def get(self, *args, **kwargs):
            raise RuntimeError("mapping get accessor unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[
            BrokenGetDict({
                "ticker": "NVDA",
                "filename": "nvda_repair.html",
                "pipeline_id": "v2",
                "title": "內容可信度未通過",
                "detail": "目標價與建議不一致。",
                "recommended_action": "manual_review",
                "severity": "blocked",
                "priority_score": 1000,
            })
        ],
        rerun_reports=[
            BrokenGetDict({
                "ticker": "TSM",
                "filename": "tsm_rerun.html",
                "pipeline_id": "v1",
                "decision_freshness": BrokenGetDict({
                    "requires_rerun_reason": "資料快照與結論不同步。",
                }),
            })
        ],
        high_priority_watchlist=[BrokenGetDict({"ticker": "2454.TW", "decision_priority": "high"})],
        candidates=[BrokenGetDict({"ticker": "3661.TW", "score": 93})],
        performance=BrokenGetDict({
            "due_backtests": [
                BrokenGetDict({
                    "ticker": "AMD",
                    "filename": "amd_due.html",
                    "pipeline_id": "v1",
                    "horizon_months": 6,
                })
            ],
            "details": [],
        }),
        free_mode=BrokenGetDict({"enabled": True, "can_run_without_paid_keys": True, "violations": []}),
        provider_impact_ledger=BrokenGetDict({
            "items": [
                BrokenGetDict({
                    "ticker": "MSFT",
                    "filename": "msft_provider.html",
                    "pipeline_id": "v2",
                    "summary": BrokenGetDict({
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    }),
                    "impacts": [BrokenGetDict({"message": "market_data/yfinance critical"})],
                })
            ]
        }),
        ops=BrokenGetDict({
            "model_route_budget": BrokenGetDict({
                "warnings": [
                    BrokenGetDict({
                        "id": "quality_gate_failures",
                        "route": "v2/gemini-2.5-pro",
                        "message": "quality gate failure rate high",
                    })
                ]
            })
        }),
        limit=8,
    )

    assert [item["type"] for item in queue["items"]] == [
        "manual_review",
        "wait_provider_recovery",
        "model_route_warning",
        "backtest_due",
        "rerun_report",
        "run_watchlist",
        "review_candidate",
    ]
    assert queue["items"][0]["filename"] == "nvda_repair.html"
    assert queue["items"][1]["detail"] == "market_data/yfinance critical"
    assert queue["items"][2]["route"] == "v2/gemini-2.5-pro"
    assert queue["items"][3]["horizon_months"] == 6
    assert queue["summary"]["sources"] == {
        "report_repair": 1,
        "provider_impact": 1,
        "model_route_budget": 1,
        "backtest_due": 1,
        "rerun_report": 1,
        "watchlist": 1,
        "screener": 1,
    }


def test_daily_decision_queue_surfaces_notification_delivery_health():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[{"ticker": "2308.TW", "enabled": True, "decision_priority": "high"}],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 2,
                "retry_exhausted_count": 1,
                "channel_counts": {"telegram_webhook": 2, "local": 1},
                "failure_reason_counts": {"timeout": 2, "auth": 1},
                "attention_contexts": [
                    {
                        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
                        "channel_id": "telegram_webhook",
                        "delivery_status": "failed",
                        "attempt_count": 2,
                        "last_error": "temporary webhook timeout",
                        "context": {
                            "source": "provider_impact",
                            "ticker": "NVDA",
                            "filename": "nvda_provider.html",
                            "target_panel": "provider-sla-panel",
                            "operator_action_label": "查看來源",
                            "queue_rank": 1,
                        },
                    }
                ],
            }
        },
    )

    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["source"] == "notification_delivery"
    assert queue["items"][0]["priority_score"] > queue["items"][1]["priority_score"]
    assert queue["items"][0]["failed_count"] == 2
    assert queue["items"][0]["retry_exhausted_count"] == 1
    assert queue["items"][0]["channel_counts"]["telegram_webhook"] == 2
    assert queue["items"][0]["failure_reason_counts"] == {"timeout": 2, "auth": 1}
    assert queue["items"][0]["attention_contexts"][0]["context"]["ticker"] == "NVDA"
    assert queue["items"][0]["attention_contexts"][0]["context"]["target_panel"] == "provider-sla-panel"
    assert "reason=timeout 2, auth 1" in queue["items"][0]["detail"]
    assert queue["items"][0]["suppress_notification"] is True
    assert queue["summary"]["sources"]["notification_delivery"] == 1


def test_daily_decision_queue_notification_delivery_counts_do_not_depend_on_truthiness():
    class BrokenDeliveryCount:
        def __bool__(self):
            raise RuntimeError("daily queue notification delivery count truthiness unavailable")

        def __int__(self):
            return 2

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "ok",
                "failed_count": BrokenDeliveryCount(),
                "retry_exhausted_count": 0,
                "failure_reason_counts": {"timeout": 2},
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["failed_count"] == 2
    assert queue["items"][0]["retry_exhausted_count"] == 0
    assert "failed=2, exhausted=0" in queue["items"][0]["detail"]


def test_daily_decision_queue_notification_delivery_summary_accepts_mapping_payloads():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": MappingProxyType({
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
            })
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["failed_count"] == 1


def test_daily_decision_queue_notification_delivery_nested_counts_accept_mapping_payloads():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "channel_counts": MappingProxyType({"telegram_webhook": 2, "local": 1}),
                "failure_reason_counts": MappingProxyType({"timeout": 2, "auth": 1}),
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["channel_counts"] == {"telegram_webhook": 2, "local": 1}
    assert queue["items"][0]["failure_reason_counts"] == {"timeout": 2, "auth": 1}
    assert "reason=timeout 2, auth 1" in queue["items"][0]["detail"]


def test_daily_decision_queue_notification_delivery_rejects_binary_and_boolean_counts():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": b"2",
                "retry_exhausted_count": True,
                "channel_counts": {
                    memoryview(b"telegram_webhook"): b"2",
                    "local": bytearray(b"1"),
                },
                "failure_reason_counts": {
                    "timeout": b"2",
                    "auth": True,
                    memoryview(b"network"): 4,
                    "network": 2,
                },
            }
        },
    )

    item = queue["items"][0]
    assert item["failed_count"] == 0
    assert item["retry_exhausted_count"] == 0
    assert item["channel_counts"] == {"unknown": 0, "local": 0}
    assert item["failure_reason_counts"] == {"timeout": 0, "auth": 0, "network": 2}
    assert item["detail"] == "failed=0, exhausted=0, reason=network 2"
    assert json.loads(json.dumps(item))["failure_reason_counts"] == {"timeout": 0, "auth": 0, "network": 2}


def test_daily_decision_queue_notification_delivery_attention_contexts_accept_tuple_payloads():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "attention_contexts": (
                    {
                        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
                        "channel_id": "telegram_webhook",
                        "context": {"ticker": "NVDA", "target_panel": "provider-sla-panel"},
                    },
                ),
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["attention_contexts"][0]["context"]["ticker"] == "NVDA"
    assert queue["items"][0]["attention_contexts"][0]["context"]["target_panel"] == "provider-sla-panel"


def test_daily_decision_queue_notification_delivery_attention_context_rows_accept_mapping_payloads():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "attention_contexts": [
                    MappingProxyType({
                        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
                        "channel_id": "telegram_webhook",
                        "context": MappingProxyType({
                            "ticker": "NVDA",
                            "target_panel": "provider-sla-panel",
                        }),
                    })
                ],
            }
        },
    )

    context_row = queue["items"][0]["attention_contexts"][0]
    assert isinstance(context_row, dict)
    assert isinstance(context_row["context"], dict)
    assert context_row["context"]["ticker"] == "NVDA"
    assert context_row["context"]["target_panel"] == "provider-sla-panel"


def test_daily_decision_queue_notification_delivery_attention_context_dict_subclasses_normalize_to_plain_dicts():
    class CustomContextDict(dict):
        pass

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "attention_contexts": [
                    CustomContextDict({
                        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
                        "channel_id": "telegram_webhook",
                        "context": CustomContextDict({
                            "ticker": "NVDA",
                            "target_panel": "provider-sla-panel",
                        }),
                    })
                ],
            }
        },
    )

    context_row = queue["items"][0]["attention_contexts"][0]
    assert type(context_row) is dict
    assert type(context_row["context"]) is dict
    assert context_row["context"]["ticker"] == "NVDA"
    assert context_row["context"]["target_panel"] == "provider-sla-panel"


def test_daily_decision_queue_notification_delivery_attention_context_nested_mappings_normalize_to_plain_dicts():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "attention_contexts": [
                    {
                        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
                        "channel_id": "telegram_webhook",
                        "context": {
                            "ticker": "NVDA",
                            "metadata": MappingProxyType({
                                "target_panel": "provider-sla-panel",
                                "cta": "查看來源",
                            }),
                        },
                    }
                ],
            }
        },
    )

    metadata = queue["items"][0]["attention_contexts"][0]["context"]["metadata"]
    assert type(metadata) is dict
    assert metadata["target_panel"] == "provider-sla-panel"
    assert metadata["cta"] == "查看來源"


def test_daily_decision_queue_notification_delivery_attention_context_nested_mapping_items_failures_fall_back():
    class BrokenMetadataItems(dict):
        def items(self):
            raise RuntimeError("daily queue notification attention context metadata items unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "attention_contexts": [
                    {
                        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
                        "channel_id": "telegram_webhook",
                        "context": {
                            "ticker": "NVDA",
                            "metadata": BrokenMetadataItems({
                                "target_panel": "provider-sla-panel",
                                "cta": "查看來源",
                            }),
                        },
                    }
                ],
            }
        },
    )

    metadata = queue["items"][0]["attention_contexts"][0]["context"]["metadata"]
    assert type(metadata) is dict
    assert metadata == {"target_panel": "provider-sla-panel", "cta": "查看來源"}


def test_daily_decision_queue_notification_delivery_attention_context_nested_sequence_iterator_failures_fall_back():
    class BrokenMetadataList(list):
        def __iter__(self):
            raise RuntimeError("daily queue notification attention context metadata iterator unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "attention_contexts": [
                    {
                        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
                        "channel_id": "telegram_webhook",
                        "context": {
                            "ticker": "NVDA",
                            "metadata": {
                                "tags": BrokenMetadataList(["provider-sla", "cta-visible"]),
                            },
                        },
                    }
                ],
            }
        },
    )

    tags = queue["items"][0]["attention_contexts"][0]["context"]["metadata"]["tags"]
    assert type(tags) is list
    assert tags == ["provider-sla", "cta-visible"]


def test_daily_decision_queue_notification_delivery_health_does_not_depend_on_truthiness():
    class BrokenDeliveryHealth:
        def __bool__(self):
            raise RuntimeError("daily queue notification delivery health truthiness unavailable")

        def __str__(self):
            return "warning"

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": BrokenDeliveryHealth(),
                "failed_count": 0,
                "retry_exhausted_count": 0,
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["failed_count"] == 0
    assert queue["items"][0]["retry_exhausted_count"] == 0


def test_daily_decision_queue_notification_delivery_channel_counts_do_not_depend_on_truthiness():
    class BrokenChannelCounts(dict):
        def __bool__(self):
            raise RuntimeError("daily queue notification channel counts truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 0,
                "retry_exhausted_count": 0,
                "channel_counts": BrokenChannelCounts({"telegram_webhook": 2, "local": 1}),
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["channel_counts"] == {"telegram_webhook": 2, "local": 1}


def test_daily_decision_queue_notification_delivery_failure_reasons_do_not_depend_on_truthiness():
    class BrokenFailureReasonCounts(dict):
        def __bool__(self):
            raise RuntimeError("daily queue notification failure reason truthiness unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 0,
                "retry_exhausted_count": 0,
                "failure_reason_counts": BrokenFailureReasonCounts({"timeout": 2, "auth": 1}),
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["failure_reason_counts"] == {"timeout": 2, "auth": 1}
    assert "reason=timeout 2, auth 1" in queue["items"][0]["detail"]


def test_daily_decision_queue_notification_delivery_failure_reason_items_failures_use_native_items():
    class BrokenFailureReasonItems(dict):
        def items(self):
            raise RuntimeError("daily queue notification failure reason items unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "failure_reason_counts": BrokenFailureReasonItems({"timeout": 1}),
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["failure_reason_counts"] == {"timeout": 1}
    assert queue["items"][0]["detail"] == "failed=1, exhausted=0, reason=timeout 1"


def test_daily_decision_queue_notification_delivery_failure_reason_values_use_integer_fallback():
    class BrokenFailureReasonCount:
        def __str__(self):
            raise RuntimeError("daily queue notification failure reason count text unavailable")

        def __int__(self):
            return 2

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 2,
                "retry_exhausted_count": 0,
                "failure_reason_counts": {"timeout": BrokenFailureReasonCount()},
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["detail"] == "failed=2, exhausted=0, reason=timeout 2"


def test_daily_decision_queue_notification_delivery_failure_reason_unrenderable_counts_do_not_emit_zero_reason():
    class UnrenderableFailureReasonCount:
        def __str__(self):
            raise RuntimeError("daily queue notification failure reason count text unavailable")

        def __int__(self):
            raise RuntimeError("daily queue notification failure reason count integer unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "failure_reason_counts": {"timeout": UnrenderableFailureReasonCount()},
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["detail"] == "failed=1, exhausted=0"


def test_daily_decision_queue_notification_delivery_failure_reason_non_positive_counts_do_not_emit_reason_detail():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 2,
                "retry_exhausted_count": 0,
                "failure_reason_counts": {"timeout": 0, "auth": -1, "network": 2},
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["detail"] == "failed=2, exhausted=0, reason=network 2"


def test_daily_decision_queue_notification_delivery_failure_reason_boolean_counts_do_not_emit_reason_detail():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 2,
                "retry_exhausted_count": 0,
                "failure_reason_counts": {"timeout": True, "auth": False, "network": 2},
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["detail"] == "failed=2, exhausted=0, reason=network 2"


def test_daily_decision_queue_notification_delivery_failure_reason_fractional_counts_do_not_emit_reason_detail():
    from decimal import Decimal
    from fractions import Fraction

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 4,
                "retry_exhausted_count": 0,
                "failure_reason_counts": {
                    "timeout": 1.7,
                    "auth": Decimal("1.5"),
                    "rate_limited": Fraction(3, 2),
                    "network": Decimal("2.0"),
                    "configuration": Fraction(4, 1),
                    "other": "5",
                },
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["detail"] == (
        "failed=4, exhausted=0, reason=network 2, configuration 4, other 5"
    )


def test_daily_decision_queue_notification_delivery_failure_reason_malformed_keys_do_not_emit_reason_detail():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 4,
                "retry_exhausted_count": 0,
                "failure_reason_counts": {
                    True: 2,
                    7: 3,
                    "   ": 1,
                    "network": 4,
                    "unknown": 5,
                },
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["detail"] == "failed=4, exhausted=0, reason=network 4, unknown 5"


def test_daily_decision_queue_notification_delivery_failure_reason_raw_keys_do_not_emit_reason_detail():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 5,
                "retry_exhausted_count": 0,
                "failure_reason_counts": {
                    "TimeoutError('smtp timeout')": 2,
                    "smtp_auth_error": 1,
                    " TIMEOUT ": 3,
                    "network": 4,
                    "other": 5,
                },
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["detail"] == "failed=5, exhausted=0, reason=timeout 3, network 4, other 5"


def test_daily_decision_queue_notification_delivery_failure_reason_duplicate_buckets_are_aggregated():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 8,
                "retry_exhausted_count": 0,
                "failure_reason_counts": {
                    " TIMEOUT ": 3,
                    "timeout": 2,
                    "Network": 4,
                    "network": 1,
                    "other": 2,
                },
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["detail"] == "failed=8, exhausted=0, reason=timeout 5, network 5, other 2"


def test_daily_decision_queue_notification_delivery_failure_reason_partial_item_failures_use_remaining_native_items():
    class PartialBrokenReasonItems:
        def __init__(self):
            self._step = 0

        def __iter__(self):
            return self

        def __next__(self):
            self._step += 1
            if self._step == 1:
                return ("timeout", 1)
            raise RuntimeError("daily queue notification failure reason items stopped early")

    class PartialBrokenFailureReasonCounts(dict):
        def items(self):
            return PartialBrokenReasonItems()

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 3,
                "retry_exhausted_count": 0,
                "failure_reason_counts": PartialBrokenFailureReasonCounts({
                    "timeout": 1,
                    "network": 2,
                }),
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["detail"] == "failed=3, exhausted=0, reason=timeout 1, network 2"


def test_daily_decision_queue_notification_delivery_attention_contexts_iterator_failures_use_native_items():
    class BrokenAttentionContexts(list):
        def __iter__(self):
            raise RuntimeError("daily queue notification attention contexts iterator unavailable")

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 1,
                "retry_exhausted_count": 0,
                "attention_contexts": BrokenAttentionContexts([
                    {
                        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
                        "channel_id": "telegram_webhook",
                        "context": {"ticker": "NVDA", "target_panel": "provider-sla-panel"},
                    }
                ]),
            }
        },
    )

    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert queue["items"][0]["attention_contexts"][0]["context"]["ticker"] == "NVDA"
    assert queue["items"][0]["attention_contexts"][0]["context"]["target_panel"] == "provider-sla-panel"


def test_daily_decision_queue_notification_delivery_attention_contexts_partial_iterator_failures_use_remaining_native_items():
    class PartialBrokenAttentionContextIterator:
        def __init__(self, first_row):
            self._first_row = first_row
            self._step = 0

        def __iter__(self):
            return self

        def __next__(self):
            self._step += 1
            if self._step == 1:
                return self._first_row
            raise RuntimeError("daily queue notification attention contexts stopped early")

    class PartialBrokenAttentionContexts(list):
        def __iter__(self):
            return PartialBrokenAttentionContextIterator(list.__getitem__(self, 0))

    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "notification_delivery": {
                "health": "warning",
                "failed_count": 2,
                "retry_exhausted_count": 0,
                "attention_contexts": PartialBrokenAttentionContexts([
                    {
                        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
                        "channel_id": "telegram_webhook",
                        "context": {"ticker": "NVDA", "target_panel": "provider-sla-panel"},
                    },
                    {
                        "delivery_key": "notification_delivery.v1|discord_webhook|watchlist-action",
                        "channel_id": "discord_webhook",
                        "context": {"ticker": "TSM", "target_panel": "watchlist-panel"},
                    },
                ]),
            }
        },
    )

    contexts = queue["items"][0]["attention_contexts"]
    assert queue["summary"]["sources"] == {"notification_delivery": 1}
    assert queue["items"][0]["type"] == "fix_notification_delivery"
    assert [row["context"]["ticker"] for row in contexts] == ["NVDA", "TSM"]
    assert contexts[1]["context"]["target_panel"] == "watchlist-panel"


def test_daily_decision_queue_monitor_fallback_is_not_counted_as_actionable():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert queue["items"][0]["type"] == "monitor"
    assert queue["summary"]["total_actionable"] == 0
    assert queue["summary"]["displayed_count"] == 1
    assert queue["summary"]["top_priority_score"] == 0
    assert queue["secondary_count"] == 0
