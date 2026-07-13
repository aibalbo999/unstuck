from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_outcome_calibration_attributes_low_trust_miss_to_data_quality_issue():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=[
            {
                "report_filename": "2308_low_trust.html",
                "ticker": "2308.TW",
                "pipeline_id": "v2",
                "horizon_months": 3,
                "outcome": "miss",
                "strategy_roi_pct": -12.5,
                "reason": "buy_thesis_not_met",
            }
        ],
        reports=[
            {
                "filename": "2308_low_trust.html",
                "ticker": "2308.TW",
                "pipeline_id": "v2",
                "data_trust": {"status": "partial", "score": 48},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            }
        ],
    )

    detail = ledger["details"][0]
    assert detail["miss_attribution"] == "data_quality_issue"
    assert detail["quality_signal"]["data_trust_status"] == "partial"
    assert ledger["summary"]["miss_attribution_counts"]["data_quality_issue"] == 1
    assert ledger["summary"]["miss_attribution_counts"].get("thesis_wrong", 0) == 0


def test_outcome_calibration_groups_content_credibility_warning_reports():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=[
            {
                "report_filename": "2330_warning.html",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "horizon_months": 6,
                "outcome": "miss",
                "strategy_roi_pct": -5.0,
                "reason": "buy_thesis_not_met",
            }
        ],
        reports=[
            {
                "filename": "2330_warning.html",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "data_trust": {"status": "fresh", "score": 92},
                "content_credibility": {"status": "warning", "summary": "缺少 recommendation evidence coverage"},
                "report_conformance": {"status": "passed"},
            }
        ],
    )

    assert ledger["details"][0]["miss_attribution"] == "insufficient_evidence"
    assert ledger["quality_groups"]["content_credibility_status"]["warning"]["count"] == 1
    assert ledger["quality_groups"]["content_credibility_status"]["warning"]["miss_count"] == 1
    assert ledger["by_pipeline"]["v1"]["content_credibility_warning_count"] == 1


def test_outcome_calibration_is_idempotent_and_summarizes_pipeline_and_horizon():
    from outcome_calibration import build_outcome_calibration

    backtests = [
        {
            "report_filename": "aapl_hit.html",
            "ticker": "AAPL",
            "pipeline_id": "v1",
            "horizon_months": 3,
            "outcome": "hit",
            "strategy_roi_pct": 8.0,
            "market_return_pct": 8.0,
            "reason": "direction_and_target_met",
        },
        {
            "report_filename": "nvda_miss.html",
            "ticker": "NVDA",
            "pipeline_id": "v1",
            "horizon_months": 3,
            "outcome": "miss",
            "strategy_roi_pct": -4.0,
            "market_return_pct": -4.0,
            "reason": "buy_thesis_not_met",
        },
    ]
    reports = [
        {
            "filename": "aapl_hit.html",
            "ticker": "AAPL",
            "pipeline_id": "v1",
            "data_trust": {"status": "fresh"},
            "content_credibility": {"status": "passed"},
            "report_conformance": {"status": "passed"},
        },
        {
            "filename": "nvda_miss.html",
            "ticker": "NVDA",
            "pipeline_id": "v1",
            "data_trust": {"status": "fresh"},
            "content_credibility": {"status": "passed"},
            "report_conformance": {"status": "passed"},
        },
    ]

    first = build_outcome_calibration(backtests=backtests, reports=reports)
    second = build_outcome_calibration(backtests=backtests, reports=reports)

    assert first == second
    assert first["schema_version"] == "outcome_calibration.v1"
    assert first["summary"]["total_evaluated"] == 2
    assert first["summary"]["hit_rate_pct"] == 50.0
    assert first["by_pipeline"]["v1"]["average_strategy_roi_pct"] == 2.0
    assert first["by_horizon"]["3"]["hit_rate_pct"] == 50.0
    assert first["strategy_evaluation"]["summary"]["total_artifacts"] == 2


def test_outcome_calibration_does_not_overattribute_when_report_metadata_is_missing():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=[
            {
                "report_filename": "missing_report.html",
                "ticker": "TSLA",
                "pipeline_id": "v3",
                "horizon_months": 12,
                "outcome": "miss",
                "strategy_roi_pct": -2.0,
                "reason": "",
            }
        ],
        reports=[],
    )

    assert ledger["details"][0]["quality_signal"]["data_trust_status"] == "unknown"
    assert ledger["details"][0]["miss_attribution"] == "unknown"


class BrokenOutcomeBacktestGet(dict):
    BROKEN_KEYS = {
        "report_filename",
        "ticker",
        "pipeline_id",
        "horizon_months",
        "outcome",
        "strategy_roi_pct",
        "market_return_pct",
        "reason",
    }

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"outcome calibration must not use backtest.get({key!r})")
        return super().get(key, default)


class BrokenOutcomeReportGet(dict):
    BROKEN_KEYS = {
        "filename",
        "report_filename",
        "ticker",
        "pipeline_id",
        "data_trust",
        "data_trust_status",
        "content_credibility",
        "report_conformance",
        "decision_freshness",
    }

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"outcome calibration must not use report.get({key!r})")
        return super().get(key, default)


class BrokenOutcomeGateGet(dict):
    BROKEN_KEYS = {
        "status",
        "score",
        "data_confidence_score",
        "requires_rerun",
    }

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"outcome calibration must not use gate.get({key!r})")
        return super().get(key, default)


class BrokenOutcomeTruthText:
    def __init__(self, text: str):
        self.text = text

    def __bool__(self):
        raise RuntimeError("outcome calibration text truthiness unavailable")

    def __str__(self):
        return self.text


class BrokenOutcomeTruthNumber:
    def __init__(self, value: float):
        self.value = value

    def __bool__(self):
        raise RuntimeError("outcome calibration number truthiness unavailable")

    def __float__(self):
        return self.value


class BrokenOutcomeFloat:
    def __float__(self):
        raise RuntimeError("outcome calibration numeric conversion unavailable")


class BrokenOutcomeTruthBool:
    def __bool__(self):
        raise RuntimeError("outcome calibration bool truthiness unavailable")


class BrokenOutcomeRows(list):
    def __bool__(self):
        raise RuntimeError("outcome calibration row collection truthiness unavailable")


class BrokenOutcomeReportTruth(dict):
    def __bool__(self):
        raise RuntimeError("outcome calibration report truthiness unavailable")


def test_outcome_calibration_keeps_quality_signal_mappings_when_accessor_fails():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=[
            BrokenOutcomeBacktestGet(
                {
                    "report_filename": "2330_low_trust.html",
                    "ticker": "2330.TW",
                    "pipeline_id": "v2",
                    "horizon_months": 3,
                    "outcome": "miss",
                    "strategy_roi_pct": -7.25,
                    "market_return_pct": 1.5,
                    "reason": "buy_thesis_not_met",
                }
            )
        ],
        reports=[
            BrokenOutcomeReportGet(
                {
                    "filename": "2330_low_trust.html",
                    "ticker": "2330.TW",
                    "pipeline_id": "v2",
                    "data_trust": BrokenOutcomeGateGet({"status": "stale", "score": 42}),
                    "content_credibility": BrokenOutcomeGateGet({"status": "passed"}),
                    "report_conformance": BrokenOutcomeGateGet({"status": "passed"}),
                    "decision_freshness": BrokenOutcomeGateGet({"status": "current", "requires_rerun": False}),
                }
            )
        ],
    )

    detail = ledger["details"][0]
    assert detail["report_filename"] == "2330_low_trust.html"
    assert detail["ticker"] == "2330.TW"
    assert detail["pipeline_id"] == "v2"
    assert detail["miss_attribution"] == "data_quality_issue"
    assert detail["quality_signal"]["data_trust_status"] == "stale"
    assert detail["quality_signal"]["data_trust_score"] == 42.0
    assert ledger["quality_groups"]["data_trust_status"]["stale"]["miss_count"] == 1


def test_outcome_calibration_row_collections_do_not_depend_on_truthiness():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=BrokenOutcomeRows(
            [
                {
                    "report_filename": "2330_low_trust.html",
                    "ticker": "2330.TW",
                    "pipeline_id": "v2",
                    "horizon_months": 3,
                    "outcome": "miss",
                    "strategy_roi_pct": -7.25,
                    "reason": "buy_thesis_not_met",
                }
            ]
        ),
        reports=BrokenOutcomeRows(
            [
                {
                    "filename": "2330_low_trust.html",
                    "ticker": "2330.TW",
                    "pipeline_id": "v2",
                    "data_trust": {"status": "stale", "score": 42},
                    "content_credibility": {"status": "passed"},
                    "report_conformance": {"status": "passed"},
                }
            ]
        ),
    )

    assert ledger["summary"]["total_evaluated"] == 1
    detail = ledger["details"][0]
    assert detail["miss_attribution"] == "data_quality_issue"
    assert detail["quality_signal"]["data_trust_status"] == "stale"


def test_outcome_calibration_matched_report_does_not_depend_on_truthiness():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=[
            {
                "report_filename": "2330_low_trust.html",
                "ticker": "2330.TW",
                "pipeline_id": "v2",
                "horizon_months": 3,
                "outcome": "miss",
                "strategy_roi_pct": -7.25,
                "reason": "buy_thesis_not_met",
            }
        ],
        reports=[
            BrokenOutcomeReportTruth(
                {
                    "filename": "2330_low_trust.html",
                    "ticker": "2330.TW",
                    "pipeline_id": "v2",
                    "data_trust": {"status": "stale", "score": 42},
                    "content_credibility": {"status": "passed"},
                    "report_conformance": {"status": "passed"},
                }
            )
        ],
    )

    detail = ledger["details"][0]
    assert detail["report_filename"] == "2330_low_trust.html"
    assert detail["miss_attribution"] == "data_quality_issue"
    assert detail["quality_signal"]["data_trust_status"] == "stale"


def test_outcome_calibration_data_trust_score_does_not_depend_on_truthiness():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=[
            {
                "report_filename": "2330_low_trust.html",
                "ticker": "2330.TW",
                "pipeline_id": "v2",
                "horizon_months": 3,
                "outcome": "miss",
                "strategy_roi_pct": -7.25,
                "reason": "buy_thesis_not_met",
            }
        ],
        reports=[
            {
                "filename": "2330_low_trust.html",
                "ticker": "2330.TW",
                "pipeline_id": "v2",
                "data_trust": {
                    "status": "stale",
                    "score": BrokenOutcomeTruthNumber(0.0),
                    "data_confidence_score": 99,
                },
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            }
        ],
    )

    detail = ledger["details"][0]
    assert detail["miss_attribution"] == "data_quality_issue"
    assert detail["quality_signal"]["data_trust_score"] == 0.0
    assert ledger["quality_groups"]["data_trust_status"]["stale"]["miss_count"] == 1


def test_outcome_calibration_numeric_conversion_failures_do_not_interrupt_learning():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=[
            {
                "report_filename": "2330_low_trust.html",
                "ticker": "2330.TW",
                "pipeline_id": "v2",
                "horizon_months": 3,
                "outcome": "miss",
                "strategy_roi_pct": BrokenOutcomeFloat(),
                "market_return_pct": BrokenOutcomeFloat(),
                "reason": "buy_thesis_not_met",
            }
        ],
        reports=[
            {
                "filename": "2330_low_trust.html",
                "ticker": "2330.TW",
                "pipeline_id": "v2",
                "data_trust": {
                    "status": "stale",
                    "score": BrokenOutcomeFloat(),
                    "data_confidence_score": BrokenOutcomeFloat(),
                },
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            }
        ],
    )

    detail = ledger["details"][0]
    assert detail["strategy_roi_pct"] is None
    assert detail["market_return_pct"] is None
    assert detail["quality_signal"]["data_trust_score"] is None
    assert detail["miss_attribution"] == "data_quality_issue"
    assert ledger["summary"]["average_strategy_roi_pct"] == 0.0
    assert ledger["quality_groups"]["data_trust_status"]["stale"]["miss_count"] == 1


def test_outcome_calibration_decision_freshness_flag_does_not_depend_on_truthiness():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=[
            {
                "report_filename": "2330_low_trust.html",
                "ticker": "2330.TW",
                "pipeline_id": "v2",
                "horizon_months": 3,
                "outcome": "miss",
                "strategy_roi_pct": -7.25,
                "reason": "buy_thesis_not_met",
            }
        ],
        reports=[
            {
                "filename": "2330_low_trust.html",
                "ticker": "2330.TW",
                "pipeline_id": "v2",
                "data_trust": {"status": "stale", "score": 42},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
                "decision_freshness": {"requires_rerun": BrokenOutcomeTruthBool()},
            }
        ],
    )

    detail = ledger["details"][0]
    assert detail["miss_attribution"] == "data_quality_issue"
    assert detail["quality_signal"]["decision_freshness_status"] == "unknown"
    assert ledger["quality_groups"]["data_trust_status"]["stale"]["miss_count"] == 1


def test_outcome_calibration_report_identity_does_not_depend_on_truthiness():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(
        backtests=[
            {
                "report_filename": BrokenOutcomeTruthText("2330_low_trust.html"),
                "ticker": BrokenOutcomeTruthText("2330.TW"),
                "pipeline_id": BrokenOutcomeTruthText("v2"),
                "horizon_months": 3,
                "outcome": "miss",
                "strategy_roi_pct": -7.25,
                "market_return_pct": 1.5,
                "reason": "buy_thesis_not_met",
            }
        ],
        reports=[
            {
                "filename": BrokenOutcomeTruthText("2330_low_trust.html"),
                "ticker": BrokenOutcomeTruthText("2330.TW"),
                "pipeline_id": BrokenOutcomeTruthText("v2"),
                "data_trust": {"status": "stale", "score": 42},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            }
        ],
    )

    detail = ledger["details"][0]
    assert detail["report_filename"] == "2330_low_trust.html"
    assert detail["ticker"] == "2330.TW"
    assert detail["pipeline_id"] == "v2"
    assert detail["miss_attribution"] == "data_quality_issue"
    assert detail["quality_signal"]["data_trust_status"] == "stale"
