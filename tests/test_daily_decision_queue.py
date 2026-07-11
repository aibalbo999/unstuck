from datetime import date

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


def test_daily_decision_queue_excludes_latency_and_retry_route_warnings():
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

    assert queue["summary"]["total_actionable"] == 2
    assert queue["summary"]["sources"] == {"model_route_budget": 2}
    assert [item["warning_id"] for item in queue["items"]] == [
        "quality_gate_failures",
        "future_route_condition",
    ]
    assert [item["type"] for item in queue["items"]] == [
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
