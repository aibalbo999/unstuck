import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _parsed(*, target_12m="NT$130", scenarios=None):
    return {
        "recommendation": {"12個月": target_12m},
        "price_targets": scenarios or {"熊市情境": 80, "基本情境": 120, "牛市情境": 140},
    }


def test_scenario_range_warns_when_12m_target_is_outside_allowed_bounds():
    from reporting.content_credibility_scenario_range import evaluate_recommendation_target_scenario_range

    result = evaluate_recommendation_target_scenario_range(_parsed(target_12m="NT$200"))

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "recommendation_target_outside_scenario_range"
    assert result["warnings"][0]["details"]["allowed_upper_bound"] == 182.0


def test_scenario_range_passes_when_12m_target_is_inside_allowed_bounds():
    from reporting.content_credibility_scenario_range import evaluate_recommendation_target_scenario_range

    result = evaluate_recommendation_target_scenario_range(_parsed(target_12m="NT$130"))

    assert result["warnings"] == []
    assert result["checks"][0]["status"] == "passed"


def test_scenario_range_skips_when_a_canonical_scenario_is_missing():
    from reporting.content_credibility_scenario_range import evaluate_recommendation_target_scenario_range

    result = evaluate_recommendation_target_scenario_range(_parsed(scenarios={"熊市情境": 80, "牛市情境": 140}))

    assert result["warnings"] == []
    assert result["checks"][0]["status"] == "passed"
    assert "略過" in result["checks"][0]["message"]
