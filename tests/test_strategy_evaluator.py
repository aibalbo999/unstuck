from strategy_evaluator import evaluate_strategy_artifacts


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
