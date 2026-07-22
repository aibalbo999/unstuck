def test_investment_thesis_rendering_uses_mode_profile_and_facade_identity():
    from investment_thesis import investment_thesis_markdown as facade_markdown
    from investment_thesis_rendering import investment_thesis_markdown

    assert facade_markdown is investment_thesis_markdown

    markdown = investment_thesis_markdown({
        "pipeline_id": "v2",
        "health_score": "7\nok",
        "information_richness": {"grade": "B\n級", "summary": "可追蹤"},
        "mirror_test": {"status": "pass", "lines": ["部位檢查\n仍有效"]},
        "core_assumptions": [{"assumption": "營收不惡化", "validation": "月營收", "frequency": "每月"}],
        "red_lines": [{"severity": "高", "condition": "跌破停損", "action": "降部位"}],
        "next_review": {"trigger": "下一次收盤", "focus": "風險報酬"},
    })

    assert "## 部位決策與風控紀律" in markdown
    assert "- **部位計畫健康度:** 7 ok/10" in markdown
    assert "- **資訊豐富度:** B 級（可追蹤）" in markdown
    assert "### 部位檢查五句話" in markdown
    assert "- 部位檢查 仍有效" in markdown


def test_investment_thesis_rendering_drops_string_empty_tokens():
    from investment_thesis_rendering import investment_thesis_markdown

    markdown = investment_thesis_markdown({
        "pipeline_id": "v1",
        "discipline_heading": "NaN",
        "health_label": "Infinity",
        "health_score": "-Infinity",
        "information_richness": {"grade": "N/A", "summary": "NaN"},
        "mirror_heading": "Infinity",
        "mirror_test": {"status": "NaN", "lines": ["Infinity", "有效鏡子測試"]},
        "assumptions_heading": "NaN",
        "core_assumptions": [
            {"assumption": "NaN", "validation": "Infinity", "frequency": "-Infinity"},
            {"assumption": "有效假設", "validation": "有效驗證", "frequency": "每季"},
        ],
        "red_lines_heading": "-Infinity",
        "red_lines": [
            {"severity": "NaN", "condition": "Infinity", "action": "-Infinity"},
            {"severity": "高", "condition": "有效紅線", "action": "降低部位"},
        ],
        "data_gaps": ["NaN", "有效缺口"],
        "next_review": {"trigger": "Infinity", "focus": "有效重點"},
    })

    lowered = markdown.lower()

    assert "nan" not in lowered
    assert "infinity" not in lowered
    assert "## 長線投資論文與決策紀律" in markdown
    assert "- 有效鏡子測試" in markdown
    assert "- **有效假設**：有效驗證（每季）" in markdown
    assert "- **高**：有效紅線 -> 降低部位" in markdown
    assert "- 有效缺口" in markdown
