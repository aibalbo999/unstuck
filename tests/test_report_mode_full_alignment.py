import asyncio
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from final_audit_mode_contracts import v4_trade_setup_contract_issues  # noqa: E402
from agent_runtime.prompt_config import ANALYSIS_PROMPTS  # noqa: E402
from pipeline_modes import get_structured_agent_num  # noqa: E402
from reporting.legacy_report_gen import generate_html_report, generate_markdown_report  # noqa: E402
from reporting.markdown_decision_context import build_markdown_decision_section  # noqa: E402
from reporting.mode_focus_context import build_mode_focus_context  # noqa: E402
from reporting.mode_templates import get_report_template_profile  # noqa: E402
from reporting.tear_sheet_summary import build_tear_sheet_summary  # noqa: E402
from structured_output_models import build_structured_output_instruction, get_structured_response_schema  # noqa: E402
from structured_output_normalizer import normalize_structured_output  # noqa: E402
from structured_output_parser import parse_structured_data  # noqa: E402
from structured_output_report_text import structured_output_to_report_text  # noqa: E402


def _recommendation_payload() -> dict:
    return {
        "reasoning_steps": ["估值", "風險", "催化"],
        "recommendation": {
            "建議": "持有",
            "短期目標（3個月）": "NT$110",
            "中期目標（6個月）": "NT$115",
            "長期目標（12個月）": "NT$120",
            "長期潛力（5年）": "NT$150",
            "信心指數": "7/10",
        },
        "confidence_basis": {
            "evidence_items": ["估值", "財務", "籌碼"],
            "key_risks_acknowledged": ["需求", "估值"],
            "data_gaps": [],
        },
        "scenario_triggers": [
            {"trigger_condition": "毛利率下修", "action": "降低部位", "direction": "bearish_downgrade"},
            {"trigger_condition": "財測上修", "action": "重新評估", "direction": "bullish_upgrade"},
        ],
        "next_catalysts": [
            {
                "event_name": "法說會",
                "expected_timeframe": "一個月內",
                "impact_direction": "volatile",
                "trigger_condition": "財測更新",
            }
        ],
        "analysis_markdown": "正式決策正文",
    }


def _report_context(pipeline_id: str) -> dict:
    recommendation = _recommendation_payload()["recommendation"]
    trade_setup = {
        "trade_direction": "Long",
        "entry_zone": "NT$98-102",
        "target_price": "NT$112",
        "stop_loss": "NT$94",
        "support_level": "NT$96",
        "resistance_level": "NT$114",
        "core_catalyst": "下週法說會",
        "risk_level": "Medium",
    }
    return {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": pipeline_id,
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "market_cap_fmt": "NT$100億",
            "pe_ratio": "20x",
            "pb_ratio": "5x",
            "gross_margin": "50%",
            "roe": "20%",
            "dividend_yield": "2%",
            "beta": "1.0",
            "years": ["2024", "2025"],
            "revenue_history": [10, 12],
            "net_income_history": [2, 3],
            "fcf_history": [1, 2],
            "gross_margin_history": [50, 52],
            "op_margin_history": [30, 31],
            "net_margin_history": [20, 25],
            "roe_history": [18, 20],
            "source_audit": [],
            "data_trust": {
                "status": "fresh",
                "critical_failures": [],
                "stale_sources": [],
                "notes": [],
            },
        },
        "analyses": {},
        "structured_outputs": {},
        "parsed": {
            "recommendation": recommendation,
            "price_targets": {"熊市情境": 80, "基本情境": 120, "牛市情境": 140},
            "moat_scores": {"整體護城河": 8},
            "position_plan": {
                "action": "進場",
                "entry_zone": "NT$98-102",
                "position_size": "25%",
                "stop_loss": "NT$94",
                "risk_reward": "2.5:1",
                "invalidation_condition": "外資連續轉賣",
            },
            "short_setup": {
                "entry_trigger": "跌破 NT$96 且放量",
                "downside_target": "NT$82",
                "cover_stop": "站回 NT$105",
                "squeeze_risk": "融券回補推升波動",
                "thesis_invalidation": "財測與毛利率同步上修",
            },
            "trade_setup": trade_setup,
        },
        "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
    }


def test_native_schemas_preserve_mode_specific_execution_plans():
    position_payload = {
        **_recommendation_payload(),
        "position_plan": {
            "action": "進場",
            "entry_zone": "NT$98-102",
            "position_size": "25%",
            "stop_loss": "NT$94",
            "risk_reward": "2.5:1",
            "invalidation_condition": "外資連續轉賣",
        },
    }
    short_payload = {
        **_recommendation_payload(),
        "short_setup": {
            "entry_trigger": "跌破 NT$96 且放量",
            "downside_target": "NT$82",
            "cover_stop": "站回 NT$105",
            "squeeze_risk": "融券回補推升波動",
            "thesis_invalidation": "財測與毛利率同步上修",
        },
    }
    swing_payload = {
        "trade_direction": "Long",
        "entry_zone": "NT$98-102",
        "target_price": "NT$112",
        "stop_loss": "NT$94",
        "support_level": "NT$96",
        "resistance_level": "NT$114",
        "core_catalyst": "下週法說會",
        "risk_level": "Medium",
    }

    position = get_structured_response_schema(16).model_validate(position_payload).model_dump(by_alias=True)
    short = get_structured_response_schema(19).model_validate(short_payload).model_dump(by_alias=True)
    swing = get_structured_response_schema(24).model_validate(swing_payload).model_dump(by_alias=True)

    assert position["position_plan"]["action"] == "進場"
    assert short["short_setup"]["cover_stop"] == "站回 NT$105"
    assert swing["support_level"] == "NT$96"
    assert swing["resistance_level"] == "NT$114"


def _trade_setup_with_target(target_price: str) -> dict:
    return {
        "trade_direction": "Long",
        "entry_zone": "NT$98-102",
        "target_price": target_price,
        "stop_loss": "NT$94",
        "support_level": "NT$96",
        "resistance_level": "NT$114",
        "core_catalyst": "下週法說會",
        "risk_level": "Medium",
    }


def test_parsed_context_exposes_mode_specific_execution_plans():
    position_payload = {
        **_recommendation_payload(),
        "position_plan": {
            "action": "等待",
            "entry_zone": "突破 NT$105 後回測",
            "position_size": "0%，等待觸發",
            "stop_loss": "NT$99",
            "risk_reward": "2:1",
            "invalidation_condition": "量能不足",
        },
    }
    short_payload = {
        **_recommendation_payload(),
        "short_setup": {
            "entry_trigger": "跌破 NT$96",
            "downside_target": "NT$82",
            "cover_stop": "站回 NT$105",
            "squeeze_risk": "借券資料不足",
            "thesis_invalidation": "財測上修",
        },
    }

    parsed_v2 = parse_structured_data({"pipeline_id": "v2", "structured_outputs": {16: position_payload}, "analyses": {}})
    parsed_v3 = parse_structured_data({"pipeline_id": "v3", "structured_outputs": {19: short_payload}, "analyses": {}})

    assert get_structured_agent_num("position_plan", "v2") == 16
    assert get_structured_agent_num("short_setup", "v3") == 19
    assert parsed_v2["position_plan"]["action"] == "等待"
    assert parsed_v3["short_setup"]["entry_trigger"] == "跌破 NT$96"


def test_mode_contracts_reject_missing_or_ambiguous_execution_fields():
    import final_audit_mode_contracts as contracts

    assert contracts.v2_position_plan_contract_issues({})
    assert contracts.v3_short_setup_contract_issues({})
    issues = v4_trade_setup_contract_issues({
        "trade_direction": "Long",
        "entry_zone": "NT$98-102",
        "target_price": "上方壓力 NT$112，下方支撐 NT$94",
        "stop_loss": "NT$94",
        "support_level": "NT$96",
        "resistance_level": "NT$114",
        "core_catalyst": "下週法說會",
        "risk_level": "Medium",
    })
    assert any("target_price" in issue and "多個" in issue for issue in issues)


def test_mode_contracts_preserve_single_target_or_explicit_range_only():
    assert v4_trade_setup_contract_issues(_trade_setup_with_target("NT$112")) == []
    assert v4_trade_setup_contract_issues(_trade_setup_with_target("NT$108-112")) == []

    no_price = v4_trade_setup_contract_issues(
        _trade_setup_with_target("突破後下一個可驗證前高")
    )
    mixed_range = v4_trade_setup_contract_issues(
        _trade_setup_with_target("NT$108-112，另看 NT$120")
    )
    prefixed_mixed_range = v4_trade_setup_contract_issues(
        _trade_setup_with_target("目標價 NT$108-112，另看 NT$120")
    )
    prefixed_three_targets = v4_trade_setup_contract_issues(
        _trade_setup_with_target("目標價 NT$108，另看 NT$112 與 NT$120")
    )
    horizon_only = v4_trade_setup_contract_issues(
        _trade_setup_with_target("1-2週內上看前高")
    )
    prefixed_horizon_only = v4_trade_setup_contract_issues(
        _trade_setup_with_target("未來1-2週內上看前高")
    )
    english_horizon_only = v4_trade_setup_contract_issues(
        _trade_setup_with_target("next 1-2 weeks: retest prior high")
    )
    bare_third_target = v4_trade_setup_contract_issues(
        _trade_setup_with_target("目標價 108-112，另看 120")
    )
    negative_currency = v4_trade_setup_contract_issues(_trade_setup_with_target("NT$-10"))
    negative_unit = v4_trade_setup_contract_issues(_trade_setup_with_target("-10元"))
    slash_targets = v4_trade_setup_contract_issues(_trade_setup_with_target("NT$108/112"))
    non_finite_target = v4_trade_setup_contract_issues(
        _trade_setup_with_target("NT$" + "9" * 400)
    )
    mixed_non_finite_targets = [
        v4_trade_setup_contract_issues(_trade_setup_with_target("NT$" + "9" * 400 + " 或 NT$112")),
        v4_trade_setup_contract_issues(_trade_setup_with_target("Infinity 或 NT$112")),
        v4_trade_setup_contract_issues(_trade_setup_with_target("NaN 或 NT$112")),
        v4_trade_setup_contract_issues(_trade_setup_with_target("1e309 或 NT$112")),
    ]
    zero_range = v4_trade_setup_contract_issues(_trade_setup_with_target("NT$0-112"))
    zero_alternative = v4_trade_setup_contract_issues(_trade_setup_with_target("NT$0 或 NT$112"))
    horizon_with_price = v4_trade_setup_contract_issues(
        _trade_setup_with_target("1-2週目標 NT$112")
    )

    assert any("至少一個可解析價格" in issue for issue in no_price)
    assert any("單一目標或一個明確價格區間" in issue for issue in mixed_range)
    assert any("單一目標或一個明確價格區間" in issue for issue in prefixed_mixed_range)
    assert any("單一目標或一個明確價格區間" in issue for issue in prefixed_three_targets)
    assert any("至少一個可解析價格" in issue for issue in horizon_only)
    assert any("至少一個可解析價格" in issue for issue in prefixed_horizon_only)
    assert any("至少一個可解析價格" in issue for issue in english_horizon_only)
    assert any("單一目標或一個明確價格區間" in issue for issue in bare_third_target)
    assert negative_currency
    assert negative_unit
    assert any("單一目標或一個明確價格區間" in issue for issue in slash_targets)
    assert any("至少一個可解析價格" in issue for issue in non_finite_target)
    assert all(any("無效或非有限" in issue for issue in issues) for issues in mixed_non_finite_targets)
    assert zero_range
    assert zero_alternative
    assert any("不得包含交易期間" in issue for issue in horizon_with_price)


def test_position_plan_normalizer_does_not_invent_valid_action_or_zero_position():
    import final_audit_mode_contracts as contracts

    valid_fields = {
        "entry_zone": "NT$98-102",
        "position_size": "25%",
        "stop_loss": "NT$94",
        "risk_reward": "2.5:1",
        "invalidation_condition": "外資連續轉賣",
    }
    cases = (
        ({**valid_fields}, "action"),
        ({**valid_fields, "action": "加碼"}, "action"),
        ({**valid_fields, "action": "進場", "position_size": ""}, "position_size"),
    )

    for position_plan, expected_missing_field in cases:
        normalized = normalize_structured_output(
            16,
            {**_recommendation_payload(), "position_plan": position_plan},
        )

        assert normalized is not None
        assert "資料不足" in normalized["position_plan"][expected_missing_field]
        assert contracts.v2_position_plan_contract_issues(normalized["position_plan"])


def test_position_plan_provider_schema_exposes_only_auditable_actions():
    schema_cls = get_structured_response_schema(16)
    schema = schema_cls.model_json_schema()

    assert schema["$defs"]["PositionPlan"]["properties"]["action"]["enum"] == [
        "進場",
        "續抱",
        "減碼",
        "等待",
    ]

    invalid_payload = {
        **_recommendation_payload(),
        "position_plan": {
            "action": "資料不足",
            "entry_zone": "NT$98-102",
            "position_size": "25%",
            "stop_loss": "NT$94",
            "risk_reward": "2.5:1",
            "invalidation_condition": "外資連續轉賣",
        },
    }
    with pytest.raises(ValueError):
        schema_cls.model_validate(invalid_payload)


def test_mode_contracts_do_not_treat_compatibility_fallbacks_as_complete():
    import final_audit_mode_contracts as contracts

    normalized_v2 = normalize_structured_output(16, _recommendation_payload())
    normalized_v3 = normalize_structured_output(19, _recommendation_payload())
    normalized_v4 = normalize_structured_output(24, {
        "trade_direction": "Neutral",
        "entry_zone": "等待突破確認",
        "target_price": "等待價格確認",
        "stop_loss": "型態失效即停止",
        "core_catalyst": "等待近期事件",
        "risk_level": "High",
    })

    assert contracts.v2_position_plan_contract_issues(normalized_v2["position_plan"])
    assert contracts.v3_short_setup_contract_issues(normalized_v3["short_setup"])
    assert contracts.v4_trade_setup_contract_issues(normalized_v4)


def test_pipeline_contract_documents_native_mode_fields_and_legacy_behavior():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    for marker in ("position_plan", "short_setup", "support_level", "resistance_level"):
        assert marker in contract
    assert "舊報告" in contract
    assert "資料不足" in contract
    assert "不會在查看時重新套用" in contract
    assert "必須重新產出" in contract


def test_structured_report_text_surfaces_mode_specific_execution_plans():
    position = {
        **_recommendation_payload(),
        "position_plan": {
            "action": "進場",
            "entry_zone": "NT$98-102",
            "position_size": "25%",
            "stop_loss": "NT$94",
            "risk_reward": "2.5:1",
            "invalidation_condition": "外資連續轉賣",
        },
    }
    short = {
        **_recommendation_payload(),
        "short_setup": {
            "entry_trigger": "跌破 NT$96 且放量",
            "downside_target": "NT$82",
            "cover_stop": "站回 NT$105",
            "squeeze_risk": "融券回補推升波動",
            "thesis_invalidation": "財測與毛利率同步上修",
        },
    }
    swing = {
        "trade_direction": "Long",
        "entry_zone": "NT$98-102",
        "target_price": "NT$112",
        "stop_loss": "NT$94",
        "support_level": "NT$96",
        "resistance_level": "NT$114",
        "core_catalyst": "下週法說會",
        "risk_level": "Medium",
    }

    position_text = structured_output_to_report_text(16, position)
    short_text = structured_output_to_report_text(19, short)
    swing_text = structured_output_to_report_text(24, swing)

    assert "## 部位執行計畫" in position_text
    assert "部位大小：25%" in position_text
    assert "做空觸發條件（Catalyst for crash）\n- 跌破 NT$96 且放量" in short_text
    assert "防軋空停損點（Stop-loss level）\n- 站回 NT$105" in short_text
    assert "支撐位：NT$96" in swing_text
    assert "壓力位：NT$114" in swing_text


def test_mode_profiles_control_report_sections():
    profiles = {pipeline_id: get_report_template_profile(pipeline_id) for pipeline_id in ("v1", "v2", "v3", "v4")}

    assert profiles["v1"]["show_financial_charts"] is True
    assert profiles["v2"]["financial_history_heading"] == "交易背景與財務趨勢"
    assert profiles["v3"]["financial_history_heading"] == "法證財務與估值背景"
    assert profiles["v4"]["show_financial_charts"] is False
    assert profiles["v4"]["show_analysis_overlays"] is False
    assert profiles["v1"]["section_manifest"] == [
        "analysis_overlays",
        "financial_charts",
        "agent_sections",
    ]
    assert profiles["v2"]["section_manifest"] == [
        "market_charts",
        "analysis_overlays",
        "agent_sections",
        "financial_charts",
    ]
    assert profiles["v3"]["section_manifest"] == [
        "market_charts",
        "analysis_overlays",
        "agent_sections",
        "financial_charts",
    ]
    assert profiles["v4"]["section_manifest"] == ["market_charts", "agent_sections"]


def test_html_renderer_uses_mode_section_manifest_order():
    v1_html = generate_html_report(_report_context("v1"))
    v2_html = generate_html_report(_report_context("v2"))
    v4_html = generate_html_report(_report_context("v4"))

    assert v1_html.index('data-report-section="financial_charts"') < v1_html.index(
        'data-report-section="agent_sections"'
    )
    assert v2_html.index('data-report-section="agent_sections"') < v2_html.index(
        'data-report-section="financial_charts"'
    )
    assert 'data-report-section="financial_charts"' not in v4_html
    assert 'id="key-downside-risks"' not in v4_html


def test_mode_decision_prompts_require_the_same_fields_as_report_templates():
    instructions = {agent: build_structured_output_instruction(agent) for agent in (16, 19, 24)}

    for marker in ("position_plan", "action", "position_size", "risk_reward", "invalidation_condition"):
        assert marker in instructions[16]
    for marker in ("short_setup", "entry_trigger", "downside_target", "cover_stop", "squeeze_risk"):
        assert marker in instructions[19]
    for marker in ("support_level", "resistance_level", "單一目標", "明確價格區間"):
        assert marker in instructions[24]

    assert "position_plan" in ANALYSIS_PROMPTS[16]
    assert "short_setup" in ANALYSIS_PROMPTS[19]
    assert "support_level" in ANALYSIS_PROMPTS[24]
    assert "resistance_level" in ANALYSIS_PROMPTS[24]
    assert "無可靠目標價時" in ANALYSIS_PROMPTS[24]
    assert "無可靠價位時以可觀察條件表達" not in ANALYSIS_PROMPTS[24]
    assert "1-2 週期間" in instructions[24]


def test_tear_sheet_prompt_carries_mode_native_execution_contracts():
    from tear_sheet_tasks import _build_tear_sheet_prompt

    context = _report_context("v3")
    prompt = _build_tear_sheet_prompt(context)

    assert '"pipeline_id": "v3"' in prompt
    assert '"short_setup"' in prompt
    assert '"entry_trigger": "跌破 NT$96 且放量"' in prompt


def test_mode_specific_decision_sections_use_native_execution_contracts():
    expectations = {
        "v2": ("**操作動作:** 進場", "**部位大小:** 25%", "**風險報酬:** 2.5:1"),
        "v3": ("**做空觸發:** 跌破 NT$96 且放量", "**回補停損:** 站回 NT$105", "**軋空風險:** 融券回補推升波動"),
        "v4": ("**支撐位:** NT$96", "**壓力位:** NT$114"),
    }

    for pipeline_id, values in expectations.items():
        context = _report_context(pipeline_id)
        markdown = build_markdown_decision_section(
            context["parsed"],
            pipeline_id=pipeline_id,
            mode_template=get_report_template_profile(pipeline_id),
        )

        for value in values:
            assert value in markdown


def test_mode_specific_tear_sheets_prefer_structured_execution_contracts():
    expectations = {
        "v2": ("操作動作「進場」", "進場 NT$98-102", "部位 25%", "停損 NT$94"),
        "v3": ("做空觸發為「跌破 NT$96 且放量」", "下行目標 NT$82", "回補停損為「站回 NT$105」"),
        "v4": ("支撐 NT$96", "壓力 NT$114"),
    }

    for pipeline_id, values in expectations.items():
        context = _report_context(pipeline_id)
        context["analyses"] = {}
        summary = build_tear_sheet_summary(context)

        for value in values:
            assert value in summary


def test_mode_specific_tear_sheets_override_generic_model_summary():
    for pipeline_id, marker in {
        "v2": "實戰交易摘要",
        "v3": "逆勢風險摘要",
        "v4": "事件波段摘要",
    }.items():
        context = _report_context(pipeline_id)
        context["tear_sheet_summary"] = "通用模型摘要：只談基本面、估值與十二個月目標。"

        summary = build_tear_sheet_summary(context)

        assert summary.startswith(marker)
        assert "通用模型摘要" not in summary


def test_v3_legacy_tear_sheet_excerpt_preserves_price_ranges_and_decimals():
    context = _report_context("v3")
    context["parsed"].pop("short_setup")
    context["analyses"] = {
        19: (
            "## 做空觸發條件（Catalyst for crash）\n"
            "- 跌破 NT$96-98 區間且放量。\n"
            "## 防軋空停損點（Stop-loss level）\n"
            "- 站回 NT$101.5 即回補。"
        )
    }

    summary = build_tear_sheet_summary(context)

    assert "NT$96-98" in summary
    assert "NT$101.5" in summary


def test_v4_missing_trade_setup_uses_mode_specific_data_insufficient_summary():
    context = _report_context("v4")
    context["parsed"].pop("trade_setup")
    context["tear_sheet_summary"] = "通用模型摘要：十二個月基本情境估值。"

    summary = build_tear_sheet_summary(context)

    assert summary.startswith("事件波段摘要")
    assert "資料不足" in summary
    assert "通用模型摘要" not in summary
    assert "十二個月" not in summary


def test_v3_mode_focus_uses_thesis_wording_consistently():
    context = _report_context("v3")

    focus = build_mode_focus_context(context, context["parsed"], pipeline_id="v3")
    labels = [row["label"] for row in focus["rows"]]

    assert "論點失效" in labels
    assert "論文失效" not in labels


def test_non_research_modes_skip_model_tear_sheet_generation(monkeypatch):
    import tear_sheet_tasks as tasks
    from llm_client import KeyRotator

    def unexpected_prompt(_context):
        raise AssertionError("non-research mode must not build a model tear-sheet prompt")

    monkeypatch.setattr(tasks, "_build_tear_sheet_prompt", unexpected_prompt)
    rotator = KeyRotator(["test-key"])

    for pipeline_id in ("v2", "mode_b", "v3", "mode_c", "v4", "mode_d"):
        tasks.ensure_tear_sheet_summary(_report_context(pipeline_id), rotator)
        asyncio.run(tasks.ensure_tear_sheet_summary_async(_report_context(pipeline_id), rotator))


def test_html_and_markdown_focus_sections_render_mode_execution_values():
    expectations = {
        "v1": ("資料新鮮", "8/10", "NT$120"),
        "v2": ("進場", "25%", "2.5:1", "外資連續轉賣"),
        "v3": ("跌破 NT$96 且放量", "NT$82", "站回 NT$105", "融券回補推升波動"),
        "v4": ("下週法說會", "Medium", "NT$96", "NT$114"),
    }

    for pipeline_id, values in expectations.items():
        context = _report_context(pipeline_id)
        html = generate_html_report(context)
        markdown = generate_markdown_report(context)
        focus_html = html.split('class="mode-focus ', 1)[1].split("</section>", 1)[0]
        mode_letter = {"v1": "A", "v2": "B", "v3": "C", "v4": "D"}[pipeline_id]
        focus_marker = f"## 模式 {mode_letter} 模板"
        assert focus_marker in markdown
        focus_markdown = markdown.split(focus_marker, 1)[1].split("## 報告模板與閱讀路徑", 1)[0]

        for value in values:
            assert value in focus_html
            assert value in focus_markdown

    v4_html = generate_html_report(_report_context("v4"))
    assert "歷史財務數據總覽" not in v4_html
    assert 'id="key-downside-risks"' not in v4_html
