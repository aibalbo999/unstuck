import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_management_sentiment_overlay_normalizes_mapping_safe_structured_output():
    from reporting.analysis_structured_overlays import build_management_sentiment

    result = build_management_sentiment(
        MappingProxyType({
            "structured_outputs": MappingProxyType({
                "20": MappingProxyType({
                    "guidance_tone": "謹慎\n樂觀",
                    "confidence": "8.25",
                    "highlights": (
                        {"keyword": "需求\n回溫", "quote": "AI 訂單\n恢復成長"},
                        {"keyword": "毛利改善", "quote": "產品組合優化"},
                        {"keyword": "現金流", "quote": "自由現金流轉正"},
                        {"keyword": "超額列", "quote": "不應顯示"},
                    ),
                })
            })
        })
    )

    assert result == {
        "tone": "謹慎 樂觀",
        "confidence": 8.25,
        "highlights": [
            {"keyword": "需求 回溫", "quote": "AI 訂單 恢復成長"},
            {"keyword": "毛利改善", "quote": "產品組合優化"},
            {"keyword": "現金流", "quote": "自由現金流轉正"},
        ],
        "available": True,
    }


def test_downside_overlay_caps_risks_and_normalizes_severity():
    from reporting.analysis_structured_overlays import build_downside_view

    result = build_downside_view({
        "structured_outputs": {
            21: {
                "thesis_summary": "估值偏高\n現金流承壓",
                "downside_risks": [
                    {"title": "風險 A", "evidence": "證據 A", "impact": "影響 A", "severity": "critical"},
                    {"title": "風險 B", "evidence": "證據 B", "impact": "", "severity": "medium"},
                    {"title": "風險 C", "evidence": "證據 C", "severity": "invalid"},
                    {"title": "風險 D", "evidence": "證據 D", "severity": "low"},
                    {"title": "風險 E", "evidence": "證據 E", "severity": "high"},
                    {"title": "風險 F", "evidence": "證據 F", "severity": "critical"},
                ],
            }
        }
    })

    assert result["summary"] == "估值偏高 現金流承壓"
    assert len(result["risks"]) == 5
    assert result["risks"][0] == {
        "title": "風險 A",
        "evidence": "證據 A",
        "severity": "critical",
        "impact": "影響 A",
    }
    assert result["risks"][1] == {
        "title": "風險 B",
        "evidence": "證據 B",
        "severity": "medium",
    }
    assert result["risks"][2]["severity"] == "high"
    assert result["available"] is True


def test_structured_overlays_use_safe_text_for_malformed_values():
    from reporting.analysis_structured_overlays import build_downside_view, build_management_sentiment

    class MalformedText:
        def __str__(self):
            raise RuntimeError("analysis overlay text unavailable")

    context = {
        "structured_outputs": {
            20: {
                "guidance_tone": MalformedText(),
                "confidence": MalformedText(),
                "highlights": [{"keyword": MalformedText(), "quote": "有效亮點"}],
            },
            21: {
                "thesis_summary": MalformedText(),
                "downside_risks": [
                    {
                        "title": MalformedText(),
                        "evidence": MalformedText(),
                        "impact": MalformedText(),
                        "severity": MalformedText(),
                    }
                ],
            },
        }
    }

    management = build_management_sentiment(context)
    downside = build_downside_view(context)

    assert management["tone"] == "資料不足"
    assert management["confidence"] is None
    assert management["highlights"] == [{"keyword": "亮點", "quote": "有效亮點"}]
    assert downside["summary"] == "紅軍分析未產出可用結論。"
    assert downside["risks"] == [{"title": "下行風險", "evidence": "資料不足", "severity": "high"}]


def test_management_sentiment_overlay_drops_non_finite_confidence():
    from reporting.analysis_structured_overlays import build_management_sentiment

    result = build_management_sentiment({
        "structured_outputs": {
            20: {
                "guidance_tone": "謹慎樂觀",
                "confidence": float("nan"),
            }
        }
    })

    assert result["confidence"] is None
    assert "nan" not in str(result).lower()


def test_management_sentiment_overlay_parses_scientific_confidence_text():
    from reporting.analysis_structured_overlays import build_management_sentiment

    result = build_management_sentiment({
        "structured_outputs": {
            20: {
                "guidance_tone": "謹慎樂觀",
                "confidence": "1e1/10",
            }
        }
    })

    assert result["confidence"] == 10.0

    result = build_management_sentiment({
        "structured_outputs": {
            20: {
                "guidance_tone": "謹慎樂觀",
                "confidence": "1e309/10",
            }
        }
    })

    assert result["confidence"] is None


def test_structured_overlays_drop_string_empty_tokens_from_report_text():
    from reporting.analysis_structured_overlays import build_downside_view, build_management_sentiment

    context = {
        "structured_outputs": {
            20: {
                "guidance_tone": "NaN",
                "highlights": [{"keyword": "Infinity", "quote": "有效亮點"}],
            },
            21: {
                "thesis_summary": "-Infinity",
                "downside_risks": [
                    {"title": "N/A", "evidence": "Infinity", "impact": "NaN", "severity": "N/A"}
                ],
            },
        }
    }

    management = build_management_sentiment(context)
    downside = build_downside_view(context)

    assert management["tone"] == "資料不足"
    assert management["highlights"] == [{"keyword": "亮點", "quote": "有效亮點"}]
    assert downside["summary"] == "紅軍分析未產出可用結論。"
    assert downside["risks"] == [{"title": "下行風險", "evidence": "資料不足", "severity": "high"}]
    assert "nan" not in str({"management": management, "downside": downside}).lower()
    assert "infinity" not in str({"management": management, "downside": downside}).lower()
