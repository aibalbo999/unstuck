import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import reporting.legacy_report_gen as report_gen  # noqa: E402


def _extract_section(markdown: str, heading: str) -> str:
    marker = f"## {heading}"
    start = markdown.find(marker)
    if start < 0:
        return ""
    body_start = start + len(marker)
    next_start = markdown.find("\n## ", body_start)
    if next_start < 0:
        return markdown[body_start:].strip()
    return markdown[body_start:next_start].strip()


def _context(pipeline_id: str) -> dict:
    trade_setup = {
        "trade_direction": "Long",
        "entry_zone": "NT$168-172",
        "target_price": "NT$182",
        "stop_loss": "NT$162",
        "core_catalyst": "下週法說會可能釋出新產品出貨上修訊號。",
        "risk_level": "Medium",
    }
    parsed = {
        "recommendation": {
            "建議": "持有" if pipeline_id != "v3" else "放空",
            "3個月": "NT$100",
            "6個月": "NT$110",
            "12個月": "NT$120",
            "信心": "7/10",
        },
        "price_targets": {"熊市情境": 80, "基本情境": 100, "牛市情境": 120},
        "moat_scores": {"整體護城河": 7},
        "trade_setup": trade_setup if pipeline_id == "v4" else {},
    }
    return {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": pipeline_id,
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "data_schema_version": 4,
            "current_price": 100.0,
            "current_price_fmt": "NT$100.00",
            "market_cap_fmt": "NT$100億",
            "pe_ratio": "20.0x",
            "pb_ratio": "5.00x",
            "gross_margin": "50.0%",
            "roe": "20.0%",
            "dividend_yield": "2.00%",
            "beta": "1.00",
            "years": ["2024", "2025"],
            "revenue_history": [10, 12],
            "net_income_history": [2, 3],
            "fcf_history": [1, 2],
            "gross_margin_history": [50, 52],
            "op_margin_history": [30, 31],
            "net_margin_history": [20, 25],
            "roe_history": [18, 20],
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {
            17: "## 一、當前市場正在炒作的夢想題材\nAI 題材已過熱。",
            18: "## 一、夢想 vs 財務現實對撞\n法人籌碼顯示派發。",
            19: (
                "## 一、泡沫狙擊結論\n估值與籌碼背離。\n\n"
                "## 四、做空觸發條件（Catalyst for crash）\n- 財測下修。\n\n"
                "## 五、防軋空停損點（Stop-loss level）\n- 突破前高。"
            ),
            22: "## 一、均線與趨勢結構\n短線趨勢轉強。",
            23: "## 一、外資與投信連續買賣超\n法人連續買超。",
            24: "## 極短線交易計畫\n短線偏多但需嚴守停損。",
        },
        "structured_outputs": {24: trade_setup} if pipeline_id == "v4" else {},
        "parsed": parsed,
        "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
    }


def test_each_pipeline_has_distinct_report_template_profile():
    from reporting.mode_templates import get_report_template_profile

    profiles = {pipeline_id: get_report_template_profile(pipeline_id) for pipeline_id in ("v1", "v2", "v3", "v4")}

    assert [profiles[key]["template_id"] for key in ("v1", "v2", "v3", "v4")] == [
        "mode_a_research",
        "mode_b_trading",
        "mode_c_contrarian",
        "mode_d_event_swing",
    ]
    assert profiles["v1"]["summary_heading"] == "一頁式摘要"
    assert profiles["v2"]["summary_heading"] == "實戰交易摘要"
    assert profiles["v3"]["summary_heading"] == "逆勢風險摘要"
    assert profiles["v4"]["summary_heading"] == "事件波段摘要"
    assert profiles["v3"]["decision_heading"] == "泡沫狙擊結論"
    assert profiles["v4"]["decision_heading"] == "極短線交易計畫"
    assert "視覺重點" not in profiles["v1"]["audience"]
    assert all(profile["visual_focus"] for profile in profiles.values())
    assert [profiles[key]["discipline_heading"] for key in ("v1", "v2", "v3", "v4")] == [
        "長線投資論文與決策紀律",
        "部位決策與風控紀律",
        "逆勢論文與風控紀律",
        "交易計畫與風控紀律",
    ]


def test_pipeline_mode_contract_documents_templates_and_decision_intents():
    from pipeline_modes import get_pipeline_definition
    from reporting.mode_templates import get_report_template_profile

    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")
    intents = {
        "v1": "判斷是否納入長線研究清單",
        "v2": "決定進場、續抱或減碼",
        "v3": "檢查泡沫、避險與做空風險",
        "v4": "短線事件與波段交易計畫",
    }

    assert "前後端模式契約" in contract
    for pipeline_id, intent in intents.items():
        definition = get_pipeline_definition(pipeline_id)
        profile = get_report_template_profile(pipeline_id)

        assert f"`{pipeline_id}`" in contract
        assert definition["label"] in contract
        assert definition["short_label"] in contract
        assert profile["template_id"] in contract
        assert profile["summary_heading"] in contract
        assert profile["decision_heading"] in contract
        assert profile["core_question"] in contract
        assert intent in contract


def test_markdown_report_uses_mode_specific_template_headings():
    expectations = {
        "v1": ("## 一頁式摘要", "## 🎯 最終投資建議", "長線基本面投資人", "## 長線投資論文與決策紀律"),
        "v2": ("## 實戰交易摘要", "## 🎯 實戰交易決策", "主動交易與部位管理", "## 部位決策與風控紀律"),
        "v3": ("## 逆勢風險摘要", "## 🎯 泡沫狙擊結論", "逆勢交易與風險控管", "## 逆勢論文與風控紀律"),
        "v4": ("## 事件波段摘要", "## 極短線交易計畫", "短線波段與事件交易", "## 交易計畫與風控紀律"),
    }

    for pipeline_id, (summary_heading, decision_heading, audience, discipline_heading) in expectations.items():
        markdown = report_gen.generate_markdown_report(_context(pipeline_id))

        assert "## 報告模板與閱讀路徑" in markdown
        assert summary_heading in markdown
        assert decision_heading in markdown
        assert discipline_heading in markdown
        assert f"**適用受眾:** {audience}" in markdown
        if pipeline_id != "v1":
            assert "## 一頁式摘要" not in markdown
            assert "## 投資論文與決策紀律" not in markdown
        if pipeline_id == "v4":
            assert "## 🎯 最終投資建議" not in markdown


def test_mode_specific_decision_discipline_avoids_wrong_horizon_language():
    v3_markdown = report_gen.generate_markdown_report(_context("v3"))
    v3_discipline = _extract_section(v3_markdown, "逆勢論文與風控紀律")

    assert "做空觸發" in v3_discipline
    assert "防軋空" in v3_discipline
    assert "護城河判斷" not in v3_discipline

    v4_markdown = report_gen.generate_markdown_report(_context("v4"))
    v4_discipline = _extract_section(v4_markdown, "交易計畫與風控紀律")

    assert "交易方向" in v4_discipline
    assert "停損" in v4_discipline
    assert "催化" in v4_discipline
    assert "護城河判斷" not in v4_discipline
    assert "12 個月參考目標" not in v4_discipline


def test_report_index_parses_mode_specific_summary_and_decision_sections():
    from report_index_parsing import parse_recommendation_summary

    v3_markdown = report_gen.generate_markdown_report(_context("v3"))
    v3_summary = parse_recommendation_summary(
        "2330_TW_v3_report_20260708_000000.html",
        markdown_text=v3_markdown,
    )

    assert v3_summary["recommendation"] == "放空"
    assert v3_summary["summary"]
    assert "泡沫" in v3_summary["summary"] or "空方" in v3_summary["summary"]

    v4_markdown = report_gen.generate_markdown_report(_context("v4"))
    v4_summary = parse_recommendation_summary(
        "2330_TW_v4_report_20260708_000000.html",
        markdown_text=v4_markdown,
    )

    assert v4_summary["summary"]
    assert "1-2 週交易方向" in v4_summary["summary"]


def test_html_report_shows_mode_template_reading_path():
    html = report_gen.generate_html_report(_context("v3"))

    assert 'data-template-id="mode_c_contrarian"' in html
    assert "報告模板與閱讀路徑" in html
    assert "逆勢交易與風險控管" in html
    assert "泡沫證據鏈" in html
    assert "做空觸發條件" in html
    assert "逆勢論文與風控紀律" in html
