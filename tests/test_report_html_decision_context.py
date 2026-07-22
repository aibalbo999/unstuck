import sys
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_html_decision_context_normalizes_recommendation_targets_and_confidence():
    from reporting.html_decision_context import build_decision_context
    from reporting.utils import get_recommendation_color, get_recommendation_icon

    result = build_decision_context(
        {
            "recommendation": MappingProxyType({
                "建議": "買入",
                "3個月": "NT$110",
                "6個月": "NT$120",
                "12個月": "NT$130",
                "信心": "8/10",
            })
        },
        pipeline_id="v1",
    )

    assert result["recommendation"]["建議"] == "買入"
    assert result["rec_text"] == "買入"
    assert result["rec_color"] == get_recommendation_color("買入")
    assert result["rec_icon"] == get_recommendation_icon("買入")
    assert result["target_3m"] == "NT$110"
    assert result["target_6m"] == "NT$120"
    assert result["target_12m"] == "NT$130"
    assert result["confidence"] == "8/10"


def test_html_decision_context_builds_v4_trade_setup_and_color_override():
    from reporting.html_decision_context import build_decision_context

    result = build_decision_context(
        {
            "recommendation": {"建議": "持有"},
            "trade_setup": MappingProxyType({
                "trade_direction": "Short",
                "entry_zone": "NT$540-550",
                "target_price": "NT$500",
                "stop_loss": "NT$565",
                "core_catalyst": "需求降溫",
                "risk_level": "Low",
            }),
        },
        pipeline_id="v4",
    )

    assert result["trade_setup"] == {
        "trade_direction": "Short",
        "entry_zone": "NT$540-550",
        "target_price": "NT$500",
        "stop_loss": "NT$565",
        "core_catalyst": "需求降溫",
        "risk_level": "Low",
    }
    assert result["trade_direction"] == "Short"
    assert result["trade_direction_label"] == "偏空 Short"
    assert result["trade_direction_icon"] == "↓"
    assert result["swing_entry_zone"] == "NT$540-550"
    assert result["swing_target_price"] == "NT$500"
    assert result["swing_stop_loss"] == "NT$565"
    assert result["swing_risk_level"] == "低"
    assert result["rec_color"] == "#dc2626"


def test_html_decision_context_uses_safe_text_for_malformed_values():
    from reporting.html_decision_context import build_decision_context

    class MalformedText:
        def __str__(self):
            raise RuntimeError("html decision context text unavailable")

    result = build_decision_context(
        {
            "recommendation": {
                MalformedText(): MalformedText(),
                "3個月": MalformedText(),
                "建議": MalformedText(),
            },
            "trade_setup": {
                "trade_direction": MalformedText(),
                "entry_zone": MalformedText(),
                "risk_level": MalformedText(),
            },
        },
        pipeline_id="v4",
    )

    assert result["rec_text"] == "持有"
    assert result["target_3m"] == "N/A"
    assert result["target_6m"] == "N/A"
    assert result["target_12m"] == "N/A"
    assert result["confidence"] == "N/A"
    assert result["trade_setup"] == {}
    assert result["trade_direction_label"] == "中性 Neutral"
    assert result["swing_entry_zone"] == "N/A"


def test_html_decision_context_renders_decimal_non_finite_recommendation_fields_as_na():
    from reporting.html_decision_context import build_decision_context

    result = build_decision_context(
        {
            "recommendation": {
                "建議": "持有",
                "3個月": Decimal("NaN"),
                "6個月": Decimal("Infinity"),
                "12個月": Decimal("-Infinity"),
                "信心": Decimal("NaN"),
            }
        },
        pipeline_id="v1",
    )

    assert result["rec_text"] == "持有"
    assert result["target_3m"] == "N/A"
    assert result["target_6m"] == "N/A"
    assert result["target_12m"] == "N/A"
    assert result["confidence"] == "N/A"
    rendered = " ".join([result["target_3m"], result["target_6m"], result["target_12m"], result["confidence"]])
    assert "nan" not in rendered.lower()
    assert "infinity" not in rendered.lower()


def test_html_decision_context_omits_decimal_non_finite_trade_setup_fields():
    from reporting.html_decision_context import build_decision_context

    result = build_decision_context(
        {
            "recommendation": {"建議": "持有"},
            "trade_setup": {
                "trade_direction": Decimal("Infinity"),
                "entry_zone": Decimal("NaN"),
                "target_price": Decimal("Infinity"),
                "stop_loss": Decimal("-Infinity"),
                "core_catalyst": "財報更新",
                "risk_level": Decimal("NaN"),
            },
        },
        pipeline_id="v4",
    )

    assert result["trade_setup"] == {"core_catalyst": "財報更新"}
    assert result["trade_direction"] == "Neutral"
    assert result["trade_direction_label"] == "中性 Neutral"
    assert result["swing_entry_zone"] == "N/A"
    assert result["swing_target_price"] == "N/A"
    assert result["swing_stop_loss"] == "N/A"
    assert result["swing_risk_level"] == "高"
    assert "nan" not in str(result).lower()
    assert "infinity" not in str(result).lower()
