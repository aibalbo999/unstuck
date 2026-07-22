import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_shared_decision_context_normalizes_recommendation_for_all_renderers():
    from reporting.decision_context import build_decision_context
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

    assert result["rec_text"] == "買入"
    assert result["rec_color"] == get_recommendation_color("買入")
    assert result["rec_icon"] == get_recommendation_icon("買入")
    assert result["target_3m"] == "NT$110"
    assert result["target_6m"] == "NT$120"
    assert result["target_12m"] == "NT$130"
    assert result["confidence"] == "8/10"


def test_markdown_decision_section_renders_standard_recommendation_lines():
    from reporting.markdown_decision_context import build_markdown_decision_section
    from reporting.mode_templates import get_report_template_profile

    markdown = build_markdown_decision_section(
        {
            "recommendation": {
                "建議": "買進",
                "3個月": "NT$110",
                "6個月": "NT$120",
                "12個月": "NT$130",
                "信心": "8/10",
            }
        },
        pipeline_id="v1",
        mode_template=get_report_template_profile("v1"),
    )

    assert markdown == "\n".join([
        "## 🎯 最終投資建議",
        "- **綜合建議:** 買入",
        "- **3個月目標:** NT$110",
        "- **6個月目標:** NT$120",
        "- **12個月目標:** NT$130",
        "- **信心指數:** 8/10",
    ])


def test_markdown_decision_section_renders_v4_trade_setup_from_shared_context():
    from reporting.markdown_decision_context import build_markdown_decision_section
    from reporting.mode_templates import get_report_template_profile

    markdown = build_markdown_decision_section(
        {
            "trade_setup": MappingProxyType({
                "trade_direction": "Short",
                "entry_zone": "NT$540-550",
                "target_price": "NT$500",
                "stop_loss": "NT$565",
                "core_catalyst": "需求降溫",
                "risk_level": "Low",
            })
        },
        pipeline_id="v4",
        mode_template=get_report_template_profile("v4"),
    )

    assert markdown == "\n".join([
        "## 極短線交易計畫",
        "- **交易方向:** Short",
        "- **進場區間:** NT$540-550",
        "- **1-2週目標:** NT$500",
        "- **嚴格停損:** NT$565",
        "- **核心催化劑:** 需求降溫",
        "- **短期波動風險:** Low",
    ])


def test_markdown_decision_section_uses_safe_text_for_malformed_trade_values():
    from reporting.markdown_decision_context import build_markdown_decision_section
    from reporting.mode_templates import get_report_template_profile

    class MalformedText:
        def __str__(self):
            raise RuntimeError("markdown decision context text unavailable")

    markdown = build_markdown_decision_section(
        {
            "trade_setup": {
                "trade_direction": MalformedText(),
                "entry_zone": MalformedText(),
                "target_price": MalformedText(),
                "stop_loss": MalformedText(),
                "core_catalyst": "有效催化事件",
                "risk_level": MalformedText(),
            }
        },
        pipeline_id="v4",
        mode_template=get_report_template_profile("v4"),
    )

    assert "- **交易方向:** Neutral" in markdown
    assert "- **進場區間:** N/A" in markdown
    assert "- **核心催化劑:** 有效催化事件" in markdown
    assert "- **短期波動風險:** High" in markdown
    assert "markdown decision context text unavailable" not in markdown
