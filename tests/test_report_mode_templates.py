import sys
from decimal import Decimal
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


def test_markdown_report_uses_mapping_safe_investment_thesis_payload():
    class BrokenTruthinessThesis(dict):
        def __bool__(self):
            raise KeyError("markdown thesis truthiness unavailable")

    context = _context("v1")
    context["investment_thesis"] = BrokenTruthinessThesis({
        "pipeline_id": "v1",
        "discipline_heading": "長線投資論文與決策紀律",
        "health_label": "論文健康度",
        "health_score": 7,
        "information_richness": {"grade": "A", "summary": "資料充足"},
        "mirror_test": {
            "status": "pass",
            "lines": ["保留 Markdown 投資論文"],
        },
        "mirror_heading": "鏡子測試五句話",
        "assumptions_heading": "核心假設",
        "core_assumptions": [
            {
                "assumption": "毛利率維持",
                "validation": "追蹤季報",
                "frequency": "每季",
            }
        ],
        "red_lines_heading": "紅線",
        "red_lines": [],
        "data_gaps": [],
        "next_review": {
            "trigger": "下一次季報",
            "focus": "確認營收與毛利率",
        },
    })

    markdown = report_gen.generate_markdown_report(context)

    assert "保留 Markdown 投資論文" in markdown


def test_markdown_reference_source_table_escapes_model_route_cell(monkeypatch):
    import reporting.markdown_renderer as markdown_renderer

    monkeypatch.setattr(markdown_renderer, "format_model_routes", lambda pipeline_id: "gemini|flash\nprimary")

    markdown = report_gen.generate_markdown_report(_context("v1"))
    reference_section = markdown.split("## 📚 參考資料來源與數據誤差訴明", 1)[1]

    assert "AI 分析師論述（gemini/flash primary）" in reference_section
    assert "AI 分析師論述（gemini|flash" not in reference_section
    assert "gemini|flash\nprimary" not in reference_section


def test_markdown_single_line_fields_collapse_embedded_newlines():
    context = _context("v1")
    context["ticker"] = "2330\n.TW"
    context["company_name"] = "台積電\nADR"
    context["data"]["company_name"] = "台積電\nADR"
    context["data"]["fetch_date"] = "2026年06月07日\n收盤後"
    context["data"]["current_price_fmt"] = "NT$100\n盤後"
    context["parsed"]["recommendation"]["3個月"] = "NT$100\n短線"

    markdown = report_gen.generate_markdown_report(context)

    assert "# 2330 .TW 台積電 ADR -" in markdown
    assert "📅 分析日期：2026年06月07日 收盤後" in markdown
    assert "- **股價:** NT$100 盤後" in markdown
    assert "- **3個月目標:** NT$100 短線" in markdown
    assert "# 2330\n.TW" not in markdown
    assert "台積電\nADR" not in markdown
    assert "NT$100\n盤後" not in markdown


def test_markdown_key_metrics_render_non_finite_numbers_as_na():
    context = _context("v1")
    context["data"]["market_cap_fmt"] = float("nan")
    context["data"]["pe_ratio"] = float("inf")
    context["data"]["pb_ratio"] = float("-inf")

    markdown = report_gen.generate_markdown_report(context)
    key_metrics = markdown.split("## 📊 關鍵指標", 1)[1].split("---", 1)[0]

    assert "- **市值:** N/A" in key_metrics
    assert "- **P/E:** N/A" in key_metrics
    assert "- **P/B:** N/A" in key_metrics
    assert "nan" not in key_metrics.lower()
    assert "inf" not in key_metrics.lower()


def test_markdown_key_metrics_render_decimal_non_finite_numbers_as_na():
    context = _context("v1")
    context["data"]["market_cap_fmt"] = Decimal("NaN")
    context["data"]["pe_ratio"] = Decimal("Infinity")
    context["data"]["pb_ratio"] = Decimal("-Infinity")

    markdown = report_gen.generate_markdown_report(context)
    key_metrics = markdown.split("## 📊 關鍵指標", 1)[1].split("---", 1)[0]

    assert "- **市值:** N/A" in key_metrics
    assert "- **P/E:** N/A" in key_metrics
    assert "- **P/B:** N/A" in key_metrics
    assert "nan" not in key_metrics.lower()
    assert "infinity" not in key_metrics.lower()


def test_markdown_key_metrics_render_string_empty_tokens_as_na():
    context = _context("v1")
    context["data"]["market_cap_fmt"] = "NaN"
    context["data"]["pe_ratio"] = "Infinity"
    context["data"]["pb_ratio"] = "-Infinity"
    context["data"]["gross_margin"] = "N/A"

    markdown = report_gen.generate_markdown_report(context)
    key_metrics = markdown.split("## 📊 關鍵指標", 1)[1].split("---", 1)[0]

    assert "- **市值:** N/A" in key_metrics
    assert "- **P/E:** N/A" in key_metrics
    assert "- **P/B:** N/A" in key_metrics
    assert "- **毛利率:** N/A" in key_metrics
    assert "nan" not in key_metrics.lower()
    assert "infinity" not in key_metrics.lower()


def test_mode_template_renderers_use_shared_text_safety_for_display_fields():
    from reporting.mode_templates import (
        build_mode_template_html,
        build_mode_template_markdown,
        decision_markdown_heading,
        summary_markdown_heading,
    )

    profile = {
        "template_id": b"bad-template-id",
        "template_name": b"bad-template-name",
        "audience": bytearray(b"bad-audience"),
        "core_question": memoryview(b"bad-core-question"),
        "decision_heading": b"bad-decision-heading",
        "summary_heading": bytearray(b"bad-summary-heading"),
        "visual_focus": [b"bad-visual-focus", "有效視覺重點"],
        "reading_path": [memoryview(b"bad-reading-path"), "有效閱讀路徑"],
    }

    rendered = "\n".join([
        build_mode_template_html(profile),
        build_mode_template_markdown(profile),
        decision_markdown_heading(profile),
        summary_markdown_heading(profile),
    ])

    assert "有效視覺重點" in rendered
    assert "有效閱讀路徑" in rendered
    assert "模式模板" in rendered
    assert "## 🎯 最終投資建議" in rendered
    assert "## 一頁式摘要" in rendered
    assert "bad-template-id" not in rendered
    assert "bad-template-name" not in rendered
    assert "bad-audience" not in rendered
    assert "bad-core-question" not in rendered
    assert "bad-decision-heading" not in rendered
    assert "bad-summary-heading" not in rendered
    assert "bad-visual-focus" not in rendered
    assert "bad-reading-path" not in rendered


def test_mode_template_markdown_collapses_embedded_newlines_in_display_fields():
    from reporting.mode_templates import (
        build_mode_template_markdown,
        decision_markdown_heading,
        summary_markdown_heading,
    )

    profile = {
        "template_id": "mode_d_event_swing",
        "template_name": "模式 D\n事件波段模板",
        "audience": "短線波段\n與事件交易",
        "core_question": "是否有明確催化\n進場區間與停損。",
        "summary_heading": "事件波段\n摘要",
        "decision_heading": "極短線\n交易計畫",
        "visual_focus": ["技術動能\n與主力籌碼", "催化事件"],
        "reading_path": ["先看交易\n方向", "最後核對催化\n是否有效"],
    }

    rendered = "\n".join([
        build_mode_template_markdown(profile),
        summary_markdown_heading(profile),
        decision_markdown_heading(profile),
    ])

    assert "- **模板:** 模式 D 事件波段模板" in rendered
    assert "- **適用受眾:** 短線波段 與事件交易" in rendered
    assert "- **核心問題:** 是否有明確催化 進場區間與停損。" in rendered
    assert "- **視覺重點:** 技術動能 與主力籌碼、催化事件" in rendered
    assert "- **閱讀路徑:** 先看交易 方向 → 最後核對催化 是否有效" in rendered
    assert "## 事件波段 摘要" in rendered
    assert "## 極短線 交易計畫" in rendered
    assert "模式 D\n事件波段模板" not in rendered
    assert "技術動能\n與主力籌碼" not in rendered
    assert "極短線\n交易計畫" not in rendered


def test_mode_template_renderers_preserve_tuple_focus_and_reading_path():
    from reporting.mode_templates import build_mode_template_html, build_mode_template_markdown

    profile = {
        "template_id": "mode_b_trading",
        "template_name": "模式 B 實戰交易模板",
        "audience": "主動交易",
        "core_question": "是否值得進場",
        "visual_focus": ("籌碼與情緒", "風險控管"),
        "reading_path": ("先看總經與籌碼", "最後決定部位"),
    }

    rendered = "\n".join([
        build_mode_template_html(profile),
        build_mode_template_markdown(profile),
    ])

    assert "籌碼與情緒" in rendered
    assert "風險控管" in rendered
    assert "先看總經與籌碼" in rendered
    assert "最後決定部位" in rendered
    assert "N/A" not in rendered


def test_analysis_overlay_peer_comparison_accepts_tuple_asset_history():
    from reporting.analysis_overlays import build_peer_comparison_rows

    rows = build_peer_comparison_rows({
        "ticker": "2330.TW",
        "company_name": "台積電",
        "revenue_ttm_raw": 200_000_000_000,
        "total_assets_history": (80, 100),
    })

    assert rows[0]["is_target"] is True
    assert rows[0]["asset_turnover"] == 2.0


def test_analysis_overlay_numeric_rows_drop_non_finite_numbers():
    from reporting.analysis_overlays import build_dcf_scenario_rows, build_peer_comparison_rows

    scenario_rows = build_dcf_scenario_rows({
        "quant_metrics": {
            "dcf_scenarios": {
                "bear": {
                    "intrinsic_value": float("nan"),
                    "wacc_pct": float("inf"),
                    "growth_bias_pct": float("-inf"),
                    "margin_bias_pct": "Infinity",
                }
            }
        }
    })
    peer_rows = build_peer_comparison_rows({
        "ticker": "2330.TW",
        "company_name": "台積電",
        "gross_margin_raw": float("nan"),
        "roe_raw": float("inf"),
        "revenue_ttm_raw": float("nan"),
        "total_assets_history": [float("inf")],
        "dynamic_peer_metrics": [
            {
                "name": "同業甲",
                "gross_margin_pct": float("nan"),
                "roe_pct": float("-inf"),
                "pe_ttm": "NaN",
                "ps_ttm": "Infinity",
            }
        ],
    })

    assert scenario_rows[0]["intrinsic_value"] is None
    assert scenario_rows[0]["wacc_pct"] is None
    assert scenario_rows[0]["growth_bias_pct"] is None
    assert scenario_rows[0]["margin_bias_pct"] is None
    assert peer_rows[0]["gross_margin_pct"] is None
    assert peer_rows[0]["roe_pct"] is None
    assert peer_rows[0]["asset_turnover"] is None
    assert peer_rows[1]["gross_margin_pct"] is None
    assert peer_rows[1]["roe_pct"] is None
    rendered = str(scenario_rows + peer_rows).lower()
    assert "nan" not in rendered
    assert "inf" not in rendered


def test_analysis_overlay_numeric_rows_parse_scientific_text_with_units():
    from reporting.analysis_overlays import build_dcf_scenario_rows, build_peer_comparison_rows

    scenario_rows = build_dcf_scenario_rows({
        "quant_metrics": {
            "dcf_scenarios": {
                "base": {
                    "intrinsic_value": "NT$1e3",
                    "wacc_pct": "1e1%",
                    "growth_bias_pct": "1e309%",
                    "margin_bias_pct": "-2.5e1%",
                }
            }
        }
    })
    peer_rows = build_peer_comparison_rows({
        "ticker": "2330.TW",
        "company_name": "台積電",
        "gross_margin": "5e1%",
        "roe": "2.5e1%",
        "pe_ratio": "NT$1e309",
        "ps_ratio": "1.5e1x",
        "revenue_ttm_raw": "2e11",
        "total_assets_history": ["1e2"],
        "dynamic_peer_metrics": [
            {
                "name": "同業甲",
                "gross_margin_pct": "4e1%",
                "roe_pct": "1.5e1%",
                "pe_ttm": "NT$1e309",
                "ps_ttm": "2e1x",
            }
        ],
    })

    assert scenario_rows[0]["intrinsic_value"] == 1000.0
    assert scenario_rows[0]["wacc_pct"] == 10.0
    assert scenario_rows[0]["growth_bias_pct"] is None
    assert scenario_rows[0]["margin_bias_pct"] == -25.0
    assert peer_rows[0]["gross_margin_pct"] == 50.0
    assert peer_rows[0]["roe_pct"] == 25.0
    assert peer_rows[0]["pe_ttm"] is None
    assert peer_rows[0]["ps_ttm"] == 15.0
    assert peer_rows[0]["asset_turnover"] == 2.0
    assert peer_rows[1]["gross_margin_pct"] == 40.0
    assert peer_rows[1]["roe_pct"] == 15.0
    assert peer_rows[1]["pe_ttm"] is None
    assert peer_rows[1]["ps_ttm"] == 20.0


def test_report_summary_and_decision_use_shared_text_safety_for_snapshot_fields():
    context = _context("v4")
    context["data"]["ticker"] = b"bad-summary-ticker"
    context["data"]["company_name"] = bytearray(b"bad-summary-company")
    context["parsed"]["trade_setup"] = {
        "trade_direction": b"bad-trade-direction",
        "entry_zone": bytearray(b"bad-entry-zone"),
        "target_price": memoryview(b"bad-target-price"),
        "stop_loss": b"bad-stop-loss",
        "core_catalyst": "有效催化事件。",
        "risk_level": memoryview(b"bad-risk-level"),
    }

    markdown = report_gen.generate_markdown_report(context)
    html = report_gen.generate_html_report(context)
    rendered = markdown + html

    assert "有效催化事件。" in rendered
    assert "bad-summary-ticker" not in rendered
    assert "bad-summary-company" not in rendered
    assert "bad-trade-direction" not in rendered
    assert "bad-entry-zone" not in rendered
    assert "bad-target-price" not in rendered
    assert "bad-stop-loss" not in rendered
    assert "bad-risk-level" not in rendered


def test_markdown_report_data_payload_uses_mapping_safe_conversion():
    context = _context("v1")
    context["data"] = b"bad-markdown-data-payload"

    try:
        markdown = report_gen.generate_markdown_report(context)
    except (TypeError, ValueError, AttributeError) as exc:
        raise AssertionError(f"malformed markdown data payload should not break rendering: {exc}") from exc

    assert "台積電" in markdown
    assert "bad-markdown-data-payload" not in markdown


def test_markdown_report_parsed_payload_uses_mapping_safe_conversion():
    context = _context("v1")
    context["parsed"] = b"bad-markdown-parsed-payload"

    try:
        markdown = report_gen.generate_markdown_report(context)
    except AttributeError as exc:
        raise AssertionError(f"malformed markdown parsed payload should not break rendering: {exc}") from exc

    assert "台積電" in markdown
    assert "bad-markdown-parsed-payload" not in markdown


def test_markdown_report_parsed_child_maps_use_mapping_safe_conversion():
    context = _context("v4")
    context["parsed"] = {
        "recommendation": bytearray(b"bad-markdown-recommendation-map"),
        "price_targets": b"bad-markdown-price-target-map",
        "trade_setup": memoryview(b"bad-markdown-trade-setup-map"),
    }

    try:
        markdown = report_gen.generate_markdown_report(context)
    except AttributeError as exc:
        raise AssertionError(f"malformed markdown parsed child maps should not break rendering: {exc}") from exc

    assert "台積電" in markdown
    assert "bad-markdown-recommendation-map" not in markdown
    assert "bad-markdown-price-target-map" not in markdown
    assert "bad-markdown-trade-setup-map" not in markdown


def test_tear_sheet_summary_does_not_double_prefix_target_price_currency():
    context = _context("v1")
    context["parsed"]["price_targets"]["基本情境"] = "NT$120"

    markdown = report_gen.generate_markdown_report(context)

    assert "基本情境目標價為 NT$120" in markdown
    assert "NT$NT$" not in markdown


def test_report_renderers_analyses_payload_uses_mapping_safe_conversion():
    context = _context("v1")
    context["analyses"] = b"bad-analyses-map"

    try:
        markdown = report_gen.generate_markdown_report(context)
        html = report_gen.generate_html_report(context)
    except AttributeError as exc:
        raise AssertionError(f"malformed analyses payload should not break report rendering: {exc}") from exc

    rendered = markdown + html
    assert "台積電" in rendered
    assert "bad-analyses-map" not in rendered


def test_report_renderers_structured_outputs_payload_uses_mapping_safe_conversion():
    context = _context("v3")
    context["structured_outputs"] = b"bad-structured-output-map"

    try:
        markdown = report_gen.generate_markdown_report(context)
        html = report_gen.generate_html_report(context)
    except AttributeError as exc:
        raise AssertionError(f"malformed structured outputs payload should not break report rendering: {exc}") from exc

    rendered = markdown + html
    assert "台積電" in rendered
    assert "bad-structured-output-map" not in rendered


def test_report_renderers_preserve_string_key_agent_payload_maps():
    context = _context("v3")
    context["analyses"] = {str(key): value for key, value in context["analyses"].items()}
    context["structured_outputs"] = {
        "19": {
            "analysis_markdown": "## 一、泡沫狙擊結論\n字串鍵結構化結論應保留。",
            "recommendation": {
                "建議": "放空",
                "短期目標（3個月）": "NT$90",
                "中期目標（6個月）": "NT$85",
                "長期目標（12個月）": "NT$80",
                "信心指數": "6/10",
            },
            "scenario_triggers": [
                {"trigger_condition": "財測下修", "action": "加碼避險"},
            ],
        }
    }

    markdown = report_gen.generate_markdown_report(context)
    html = report_gen.generate_html_report(context)

    agent17_start = markdown.index("## 1. 泡沫情緒與極端預期 (Agent 17)")
    agent18_start = markdown.index("\n---\n\n## 2. 法證財務與籌碼派發", agent17_start)
    agent17_section = markdown[agent17_start:agent18_start]
    rendered = markdown + html
    assert "AI 題材已過熱" in agent17_section
    assert "分析進行中" not in agent17_section
    assert "字串鍵結構化結論應保留" in rendered
    assert "若「財測下修」：建議 加碼避險" in rendered


def test_report_renderers_preserve_mapping_safe_agent_payload_child_maps():
    from types import MappingProxyType

    context = _context("v3")
    context["analyses"] = {str(key): value for key, value in context["analyses"].items()}
    context["structured_outputs"] = {
        "19": MappingProxyType(
            {
                "analysis_markdown": "## 一、泡沫狙擊結論\nRead-only 結構化結論應保留。",
                "recommendation": {
                    "建議": "放空",
                    "短期目標（3個月）": "NT$90",
                    "中期目標（6個月）": "NT$85",
                    "長期目標（12個月）": "NT$80",
                    "信心指數": "6/10",
                },
                "scenario_triggers": [
                    {"trigger_condition": "財測下修", "action": "加碼避險"},
                ],
            }
        )
    }

    markdown = report_gen.generate_markdown_report(context)
    html = report_gen.generate_html_report(context)

    rendered = markdown + html
    assert "Read-only 結構化結論應保留" in rendered
    assert "若「財測下修」：建議 加碼避險" in rendered


def test_report_renderers_normalize_string_agent_sequence_ids():
    context = _context("v3")
    context["agent_sequence"] = ["17", "18", "20", "21", "19"]
    context["analyses"] = {str(key): value for key, value in context["analyses"].items()}
    context["structured_outputs"] = {
        "19": {
            "analysis_markdown": "## 一、泡沫狙擊結論\n字串序列結構化結論應保留。",
            "recommendation": {
                "建議": "放空",
                "短期目標（3個月）": "NT$90",
                "中期目標（6個月）": "NT$85",
                "長期目標（12個月）": "NT$80",
                "信心指數": "6/10",
            },
        }
    }

    markdown = report_gen.generate_markdown_report(context)
    html = report_gen.generate_html_report(context)

    rendered = markdown + html
    assert "## 1. 泡沫情緒與極端預期 (Agent 17)" in markdown
    assert "Agent 17 (Agent 17)" not in markdown
    assert "字串序列結構化結論應保留" in rendered


def test_report_renderers_fallback_malformed_agent_sequence_payload():
    context = _context("v3")
    context["agent_sequence"] = b"bad-agent-sequence"

    markdown = report_gen.generate_markdown_report(context)
    html = report_gen.generate_html_report(context)

    rendered = markdown + html
    assert "Agent 17 → Agent 18 → Agent 20 → Agent 21 → Agent 19" in rendered
    assert "## 1. 泡沫情緒與極端預期 (Agent 17)" in markdown
    assert "Agent 98" not in rendered
    assert "Agent 100" not in rendered


def test_report_renderers_skip_boolean_moat_scores():
    context = _context("v1")
    context["parsed"]["moat_scores"] = {
        "品牌影響力": True,
        "網路效應": 6,
        "整體護城河": False,
    }

    markdown = report_gen.generate_markdown_report(context)
    html = report_gen.generate_html_report(context)

    rendered = markdown + html
    assert "網路效應: 6" in markdown
    assert "品牌影響力: True" not in rendered
    assert "整體護城河: False/10" not in rendered
    assert "整體護城河: N/A/10" in markdown


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
