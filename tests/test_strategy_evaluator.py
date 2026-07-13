from strategy_evaluator import evaluate_strategy_artifacts


class BrokenStrategyFloat:
    def __float__(self):
        raise RuntimeError("strategy evaluator numeric conversion unavailable")


class BrokenStrategyTruthBool:
    def __bool__(self):
        raise RuntimeError("strategy evaluator bool truthiness unavailable")


class BrokenStrategyArtifactGet(dict):
    BROKEN_KEYS = {
        "metrics",
        "alpha_model_id",
        "pipeline_id",
        "trigger_source",
        "quality_funnel",
        "quality_outcome",
    }

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"strategy evaluator must not use artifact.get({key!r})")
        return super().get(key, default)


class BrokenStrategyMetricsGet(dict):
    BROKEN_KEYS = {"hit", "outcome", "strategy_roi_pct", "excess_return_pct", "max_drawdown_pct"}

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"strategy evaluator must not use metrics.get({key!r})")
        return super().get(key, default)


class BrokenStrategyQualityGet(dict):
    BROKEN_KEYS = {"outcome"}

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"strategy evaluator must not use quality.get({key!r})")
        return super().get(key, default)


class BrokenStrategyArtifactIterator(list):
    def __iter__(self):
        yield {
            "alpha_model_id": "mode-a-deep-research",
            "metrics": {
                "hit": True,
                "strategy_roi_pct": 3.0,
                "excess_return_pct": 1.0,
                "max_drawdown_pct": -1.0,
            },
        }
        raise RuntimeError("strategy evaluator artifact iterator unavailable")


class BrokenStrategyNativeArtifactList(list):
    def __iter__(self):
        raise RuntimeError("strategy evaluator artifact list iterator accessor unavailable")


def test_strategy_evaluator_compares_alpha_models_and_watchlist_triggers():
    artifacts = [
        {
            "alpha_model_id": "mode-a-deep-research",
            "metrics": {"hit": True, "strategy_roi_pct": 8.0, "excess_return_pct": 3.0, "max_drawdown_pct": -4.0},
        },
        {
            "alpha_model_id": "mode-a-deep-research",
            "metrics": {"hit": False, "strategy_roi_pct": -2.0, "excess_return_pct": -4.0, "max_drawdown_pct": -9.0},
        },
        {
            "alpha_model_id": "mode-d-event-swing",
            "trigger_source": "watchlist:revenue_breakout",
            "metrics": {"hit": True, "strategy_roi_pct": 5.0, "excess_return_pct": 6.0, "max_drawdown_pct": -2.5},
        },
    ]

    result = evaluate_strategy_artifacts(artifacts)

    assert result["schema_version"] == "strategy_evaluation.v1"
    assert result["summary"]["total_artifacts"] == 3
    assert result["summary"]["best_model_id"] == "mode-d-event-swing"
    assert result["models"]["mode-a-deep-research"]["hit_rate_pct"] == 50.0
    assert result["models"]["mode-a-deep-research"]["average_excess_return_pct"] == -0.5
    assert result["models"]["mode-d-event-swing"]["average_strategy_roi_pct"] == 5.0
    assert result["watchlist_triggers"]["watchlist:revenue_breakout"]["hit_rate_pct"] == 100.0


def test_strategy_evaluator_uses_dict_native_field_reads_for_artifact_mappings():
    artifacts = [
        BrokenStrategyArtifactGet(
            {
                "pipeline_id": "v2",
                "trigger_source": "watchlist:revenue_breakout",
                "quality_funnel": BrokenStrategyQualityGet({"outcome": "passed"}),
                "metrics": BrokenStrategyMetricsGet(
                    {
                        "outcome": "hit",
                        "strategy_roi_pct": 5.0,
                        "excess_return_pct": 2.0,
                        "max_drawdown_pct": -1.5,
                    }
                ),
            }
        )
    ]

    result = evaluate_strategy_artifacts(artifacts)

    assert result["summary"]["total_artifacts"] == 1
    assert result["summary"]["best_model_id"] == "mode-b-practical-trading"
    assert result["models"]["mode-b-practical-trading"]["hit_rate_pct"] == 100.0
    assert result["models"]["mode-b-practical-trading"]["average_excess_return_pct"] == 2.0
    assert result["watchlist_triggers"]["watchlist:revenue_breakout"]["count"] == 1
    assert result["quality_funnel"]["passed"]["hit_rate_pct"] == 100.0


def test_strategy_evaluator_hit_flag_truthiness_falls_back_to_outcome():
    artifacts = [
        {
            "alpha_model_id": "mode-a-deep-research",
            "metrics": {
                "hit": BrokenStrategyTruthBool(),
                "outcome": "hit",
                "strategy_roi_pct": 4.0,
                "excess_return_pct": 1.5,
                "max_drawdown_pct": -2.0,
            },
        }
    ]

    result = evaluate_strategy_artifacts(artifacts)

    assert result["summary"]["total_artifacts"] == 1
    assert result["models"]["mode-a-deep-research"]["hit_rate_pct"] == 100.0
    assert result["models"]["mode-a-deep-research"]["average_excess_return_pct"] == 1.5


def test_strategy_evaluator_artifact_iterators_preserve_valid_items_before_failures():
    result = evaluate_strategy_artifacts(BrokenStrategyArtifactIterator())

    assert result["summary"]["total_artifacts"] == 1
    assert result["summary"]["best_model_id"] == "mode-a-deep-research"
    assert result["models"]["mode-a-deep-research"]["hit_rate_pct"] == 100.0
    assert result["models"]["mode-a-deep-research"]["average_excess_return_pct"] == 1.0


def test_strategy_evaluator_artifact_native_lists_survive_iterator_accessor_failures():
    artifacts = BrokenStrategyNativeArtifactList(
        [
            {
                "alpha_model_id": "mode-a-deep-research",
                "metrics": {
                    "hit": True,
                    "strategy_roi_pct": 3.5,
                    "excess_return_pct": 1.25,
                    "max_drawdown_pct": -0.75,
                },
            }
        ]
    )

    result = evaluate_strategy_artifacts(artifacts)

    assert result["summary"]["total_artifacts"] == 1
    assert result["summary"]["best_model_id"] == "mode-a-deep-research"
    assert result["models"]["mode-a-deep-research"]["average_strategy_roi_pct"] == 3.5
    assert result["models"]["mode-a-deep-research"]["average_excess_return_pct"] == 1.25


def test_strategy_evaluator_artifact_tuple_sequences_are_evaluated():
    artifacts = (
        {
            "alpha_model_id": "mode-a-deep-research",
            "metrics": {
                "hit": True,
                "strategy_roi_pct": 2.5,
                "excess_return_pct": 0.75,
                "max_drawdown_pct": -0.5,
            },
        },
    )

    result = evaluate_strategy_artifacts(artifacts)

    assert result["summary"]["total_artifacts"] == 1
    assert result["summary"]["best_model_id"] == "mode-a-deep-research"
    assert result["models"]["mode-a-deep-research"]["average_strategy_roi_pct"] == 2.5
    assert result["models"]["mode-a-deep-research"]["average_excess_return_pct"] == 0.75


def test_strategy_evaluator_numeric_conversion_failures_do_not_interrupt_comparison():
    artifacts = [
        {
            "alpha_model_id": "mode-a-deep-research",
            "metrics": {
                "hit": True,
                "strategy_roi_pct": BrokenStrategyFloat(),
                "excess_return_pct": BrokenStrategyFloat(),
                "max_drawdown_pct": BrokenStrategyFloat(),
            },
        }
    ]

    result = evaluate_strategy_artifacts(artifacts)

    assert result["summary"]["total_artifacts"] == 1
    assert result["summary"]["best_model_id"] == "mode-a-deep-research"
    assert result["models"]["mode-a-deep-research"]["hit_rate_pct"] == 100.0
    assert result["models"]["mode-a-deep-research"]["average_strategy_roi_pct"] == 0.0
    assert result["models"]["mode-a-deep-research"]["average_excess_return_pct"] == 0.0
    assert result["models"]["mode-a-deep-research"]["worst_max_drawdown_pct"] == 0.0
