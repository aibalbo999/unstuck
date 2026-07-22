import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.content_credibility_alignment import evaluate_recommendation_target_alignment  # noqa: E402


def test_alignment_blocks_buy_when_target_is_not_above_current_price():
    result = evaluate_recommendation_target_alignment(
        recommendation_present=True,
        recommendation_label="買入",
        current_price=100.0,
        main_target={"price": 90.0, "source": "recommendation.12個月"},
    )

    assert result["blocking_issues"][0]["id"] == "buy_target_below_current_price"
    assert result["checks"][0]["id"] == "recommendation_target_alignment"
    assert result["checks"][0]["status"] == "blocked"
    assert result["blocking_issues"][0]["details"]["upside_pct"] == -10.0


def test_alignment_warns_when_hold_target_move_is_extreme():
    result = evaluate_recommendation_target_alignment(
        recommendation_present=True,
        recommendation_label="持有",
        current_price=100.0,
        main_target={"price": 135.0, "source": "price_targets.基本情境"},
    )

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "hold_recommendation_extreme_target_move"
    assert result["checks"][0]["status"] == "warning"


def test_alignment_warns_when_inputs_are_missing_but_recommendation_exists():
    result = evaluate_recommendation_target_alignment(
        recommendation_present=True,
        recommendation_label="買入",
        current_price=None,
        main_target=None,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "missing_price_alignment_inputs"
    assert result["checks"][0]["status"] == "warning"


def test_alignment_passes_when_no_recommendation_or_target_is_recorded():
    result = evaluate_recommendation_target_alignment(
        recommendation_present=False,
        recommendation_label="持有",
        current_price=None,
        main_target=None,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"] == []
    assert result["checks"][0]["status"] == "passed"
