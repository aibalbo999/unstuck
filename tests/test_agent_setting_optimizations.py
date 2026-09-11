import asyncio
import json


def test_numbered_agents_use_role_specific_generation_profiles():
    from agent_runtime.generation_config import build_generation_config

    profiles = {
        agent: build_generation_config(agent, "system")
        for agent in (1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24)
    }

    assert profiles[4].temperature == 0.2
    assert profiles[4].max_output_tokens == 6144
    assert profiles[6].temperature == 0.6
    assert profiles[20].max_output_tokens == 1024
    assert profiles[24].max_output_tokens == 2048
    assert len({(config.temperature, config.top_p, config.max_output_tokens) for config in profiles.values()}) > 5


def test_decision_agents_use_more_thinking_only_on_supported_models():
    from agent_runtime.generation_config import apply_model_generation_policy, build_generation_config

    decision = apply_model_generation_policy(build_generation_config(16, "system"), "gemini-3.8-flash", 16)
    evidence = apply_model_generation_policy(build_generation_config(2, "system"), "gemini-3.8-flash", 2)

    assert decision.thinking_config.thinking_level.value == "MEDIUM"
    assert evidence.thinking_config.thinking_level.value == "LOW"


def test_structured_agents_do_not_attach_tools_but_unstructured_math_roles_keep_guarded_tools():
    from agent_runtime.generation_config import agent_request_budget_options
    from agent_runtime.routing import get_agent_function_tools

    for agent in (3, 4, 12, 14):
        assert agent_request_budget_options(agent) == {}
    for agent in (2, 13, 18):
        assert get_agent_function_tools(agent)
        assert agent_request_budget_options(agent) == {"request_units": 6}


def test_waiting_position_plan_cannot_keep_entry_orders():
    from structured_output_normalizer_payloads import _coerce_position_plan_payload

    result = _coerce_position_plan_payload({
        "action": "等待",
        "entry_zone": "突破 100 元立即買進",
        "position_size": "30%",
        "stop_loss": "95",
        "risk_reward": "2:1",
        "target_price": "110",
        "invalidation_condition": "法說會公布後重估",
    })

    assert result["action"] == "等待"
    assert result["entry_zone"] == "N/A"
    assert result["position_size"] == "0%"
    assert result["stop_loss"] == "N/A"
    assert result["risk_reward"] == "N/A"
    assert result["target_price"] is None
    assert result["invalidation_condition"] == "法說會公布後重估"


def test_non_short_recommendation_cannot_keep_executable_short_setup():
    from structured_output_normalizer import normalize_structured_output

    payload = {
        "reasoning_steps": ["一", "二", "三"],
        "recommendation": {
            "建議": "避免",
            "短期目標（3個月）": "N/A",
            "中期目標（6個月）": "N/A",
            "長期目標（12個月）": "N/A",
            "長期潛力（5年）": "N/A",
            "信心指數": "5/10",
        },
        "confidence_basis": {
            "evidence": ["證據一", "證據二", "證據三"],
            "risks": ["風險一", "風險二"],
        },
        "scenario_triggers": [
            {"trigger_condition": "條件一", "expected_effect": "效果一"},
            {"trigger_condition": "條件二", "expected_effect": "效果二"},
        ],
        "next_catalysts": [{"trigger_condition": "條件一", "expected_effect": "效果一"}],
        "short_setup": {
            "entry_trigger": "跌破 100 元立即放空",
            "downside_target": "80",
            "cover_stop": "110",
            "squeeze_risk": "可能軋空",
            "thesis_invalidation": "營收回升",
        },
        "analysis_markdown": "## 泡沫狙擊結論\n目前不宜放空。",
    }

    result = normalize_structured_output(19, payload)

    assert result["short_setup"]["entry_trigger"].startswith("目前不建立空方部位")
    assert result["short_setup"]["downside_target"] == "N/A"
    assert result["short_setup"]["cover_stop"] == "N/A"


def test_neutral_or_incomplete_trade_setup_is_forced_to_safe_observation():
    from structured_output_normalizer import normalize_structured_output

    neutral = normalize_structured_output(24, {
        "trade_direction": "Neutral",
        "entry_zone": "突破 100 元買進",
        "target_price": "110",
        "stop_loss": "95",
        "support_level": "95",
        "resistance_level": "100",
        "core_catalyst": "等待量價確認",
        "risk_level": "Medium",
    })
    incomplete = normalize_structured_output(24, {
        "trade_direction": "Long",
        "entry_zone": "98-100",
        "target_price": "N/A",
        "stop_loss": "95",
        "support_level": "95",
        "resistance_level": "110",
        "core_catalyst": "量價突破",
        "risk_level": "Medium",
    })

    assert neutral["entry_zone"] == "N/A"
    assert neutral["target_price"] == "N/A"
    assert neutral["stop_loss"] == "N/A"
    assert incomplete["trade_direction"] == "Neutral"
    assert incomplete["risk_level"] == "High"
    assert incomplete["entry_zone"] == "N/A"


def test_agent_20_without_transcript_skips_rag_and_model(monkeypatch):
    from agent_runtime import quality_gates

    async def forbidden(*_args, **_kwargs):
        raise AssertionError("missing transcript must not call RAG, digest, or model")

    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", forbidden)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", forbidden)
    monkeypatch.setattr(quality_gates, "initial_or_checkpointed_draft", forbidden)
    context = {
        "agent_positions": {20: 1},
        "agent_total": 1,
        "agent_sequence": [20],
        "pipeline_id": "v2",
        "pipeline_label": "模式 B",
        "structured_outputs": {},
        "analyses": {},
    }
    data = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "earnings_call": {
            "transcript_available": False,
            "transcript_excerpt": "",
            "coverage_notes": ["免費來源未提供完整逐字稿。"],
        },
    }

    agent, result = asyncio.run(
        quality_gates.run_agent_with_quality_gates_async(20, data, context, object())
    )

    assert agent == 20
    assert "法說會逐字稿缺漏" in result
    assert context["structured_outputs"][20]["guidance_tone"] == "資料不足"
    assert context["structured_outputs"][20]["confidence"] == 0.0


def test_identity_guard_exists_even_without_enriched_company_identity():
    from agent_runtime.prompting import build_company_identity_guard

    guard = build_company_identity_guard(
        {"ticker": "2618.TW", "company_name": "長榮航"},
        agent_num=23,
    )

    assert "2618.TW" in guard
    assert "長榮航" in guard
    assert "技術、籌碼與交易角色" in guard
    assert "同業" in guard


def _valuation_payload(dcf_value=999):
    return {
        "price_targets": {
            "dcf_reasoning": "採用系統 DCF。",
            "peer_reasoning": "同業比較。",
            "scenario_reasoning": "三情境比較。",
            "熊市情境": 90,
            "基本情境": 110,
            "牛市情境": 130,
        },
        "valuation_summary": {
            "primary_method": "normalized_dcf",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "已檢查",
        },
        "dcf_scenarios": [{
            "scenario": "base",
            "method": "fcf_dcf",
            "unit": "twd_per_share",
            "source_ref": "quant_metrics.dcf_scenarios.base",
            "revenue_growth_bias_pct": 0,
            "margin_bias_pct": 0,
            "wacc_pct": 10,
            "intrinsic_value": dcf_value,
        }],
        "analysis_markdown": "相對估值情境仍可供參考；DCF 資料不足時不採用。",
    }


def test_valuation_output_drops_model_dcf_when_canonical_dcf_is_unavailable():
    from quant_engine import QuantEngine
    from structured_output_runtime import process_agent_response

    context = {"data": {"current_price": 100, "quant_metrics": QuantEngine.compute_all({"free_cash_flow_raw": -1})}}

    process_agent_response(4, json.dumps(_valuation_payload(), ensure_ascii=False), context)
    structured = context["structured_outputs"][4]

    assert structured["dcf_scenarios"] == []
    assert structured["valuation_summary"]["primary_method"] == "relative_valuation"
    assert structured["valuation_summary"]["uses_normalized_fcf"] is False
    assert "不可用" in structured["valuation_reasoning"]["dcf_reasoning"]


def test_valuation_output_replaces_model_dcf_with_canonical_rows():
    from quant_engine import QuantEngine
    from structured_output_runtime import process_agent_response

    quant = QuantEngine.compute_all({
        "current_price": 100,
        "shares_raw": 100_000_000,
        "market_cap_raw": 10_000_000_000,
        "total_debt_raw": 0,
        "total_cash_raw": 0,
        "free_cash_flow_raw": 1_000_000_000,
    })
    context = {"data": {"current_price": 100, "quant_metrics": quant}}

    process_agent_response(14, json.dumps(_valuation_payload(), ensure_ascii=False), context)

    rows = context["structured_outputs"][14]["dcf_scenarios"]
    assert {row["scenario"] for row in rows} == {"bear", "base", "bull"}
    assert next(row for row in rows if row["scenario"] == "base")["intrinsic_value"] == quant["dcf_scenarios"]["base"]["intrinsic_value"]
    assert all(row["intrinsic_value"] != 999 for row in rows)


def test_agent_21_structured_risks_include_falsifiable_condition():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text

    result = normalize_structured_output(21, {
        "thesis_summary": "需求可能低於預期。",
        "downside_risks": [{
            "title": "需求下修",
            "evidence": "月營收連續下降。",
            "impact": "獲利預估下修",
            "severity": "high",
            "confidence": 0.8,
            "falsifier": "月營收連續三個月恢復年增。",
        }],
        "analysis_markdown": "反證摘要。",
    })

    assert result["downside_risks"][0]["falsifier"] == "月營收連續三個月恢復年增。"
    assert "可證偽條件：月營收連續三個月恢復年增。" in structured_output_to_report_text(21, result)


def test_moat_output_preserves_evidence_per_dimension_and_renders_refs():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text

    result = normalize_structured_output(3, {
        "reasoning_steps": ["品牌有證據", "成本有同業比較", "整體仍有反證"],
        "moat_scores": {
            "品牌影響力": 7,
            "網路效應": None,
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 6,
            "整體護城河": 6,
        },
        "moat_evidence": {
            "品牌影響力": {
                "finding": "品牌帶來議價力，但直接市佔資料有限。",
                "source_refs": ["ttm_financials.gross_margin_pct"],
                "counterevidence": "缺少品牌溢價的直接同業資料。",
            }
        },
        "analysis_markdown": "護城河分析。",
    })

    evidence = result["moat_evidence"]["品牌影響力"]
    assert evidence["source_refs"] == ["ttm_financials.gross_margin_pct"]
    rendered = structured_output_to_report_text(3, result)
    assert "品牌影響力證據" in rendered
    assert "ttm_financials.gross_margin_pct" in rendered
    assert "反證：缺少品牌溢價的直接同業資料。" in rendered


def test_moat_agents_receive_financial_and_peer_state_evidence():
    from state_memory import initialize_agent_state, state_view_for

    state = initialize_agent_state({
        "ticker": "TEST",
        "company_name": "Fixture",
        "gross_margin_raw": 0.31,
        "profit_margin_raw": 0.12,
        "dynamic_peer_metrics": [{"ticker": "PEER", "gross_margin_pct": 25}],
    })

    for agent in (3, 12):
        view = state_view_for(agent, state)
        assert view["normalized_financials"]["gross_margin_raw"] == 0.31
        assert view["peer_context"]["dynamic_peer_metrics"][0]["ticker"] == "PEER"


def test_evidence_roles_use_auditable_as_of_and_source_schema():
    from structured_output_models import build_structured_output_instruction, get_structured_response_schema
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text

    payload = {
        "as_of_date": "2026-09-11",
        "confidence": "medium",
        "evidence_items": [{
            "finding": "外資近五日偏買方，但二十日仍未形成一致趨勢。",
            "source_refs": ["institutional_trading.foreign"],
            "freshness_note": "資料截至 2026-09-11 收盤。",
            "counterevidence": "投信同期偏賣方。",
        }],
        "analysis_markdown": "籌碼結論仍需等待方向一致。",
    }

    for agent in (11, 15, 22, 23):
        assert get_structured_response_schema(agent) is not None
        assert "as_of_date" in build_structured_output_instruction(agent)
        result = normalize_structured_output(agent, payload)
        assert result["as_of_date"] == "2026-09-11"
        assert result["evidence_items"][0]["source_refs"] == ["institutional_trading.foreign"]
        rendered = structured_output_to_report_text(agent, result)
        assert "資料時點：2026-09-11" in rendered
        assert "institutional_trading.foreign" in rendered


def test_evidence_roles_are_quality_gate_structured_agents():
    from agent_runtime.quality_structured_outputs import is_structured_agent

    for pipeline, agents in {
        "v1": (11,),
        "v2": (11, 15),
        "v4": (22, 23),
    }.items():
        for agent in agents:
            assert is_structured_agent(agent, {"pipeline_id": pipeline})


def test_tear_sheet_missing_only_model_reports_deterministic_fallback(monkeypatch):
    import tear_sheet_tasks as tasks

    class FakeRotator:
        def get_key(self, *_args):
            return "offline-key"

    events = []
    monkeypatch.setattr(tasks, "KeyRotator", FakeRotator)
    monkeypatch.setattr(tasks, "_tear_sheet_model_sequence", lambda: ["missing-model"])
    monkeypatch.setattr(tasks, "_generate_tear_sheet_content", lambda *_args: (_ for _ in ()).throw(RuntimeError("missing")))
    monkeypatch.setattr(tasks, "is_missing_model_error", lambda _message: True)
    monkeypatch.setattr(tasks, "emit_context_event", lambda _context, event, _callback=None: events.append(event))

    tasks.ensure_tear_sheet_summary(
        {"pipeline_id": "v1", "data": {}, "parsed": {}, "analyses": {}},
        FakeRotator(),
    )

    assert events[-1]["phase"] == "tear_sheet_fallback"
    assert "deterministic fallback" in events[-1]["message"]


def test_swing_normalizer_downgrades_incomplete_long_to_neutral():
    from structured_output_normalizer import normalize_structured_output

    result = normalize_structured_output(24, {
        "trade_direction": "Long",
        "entry_zone": "100-102",
        "target_price": "資料不足",
        "stop_loss": "96",
        "support_level": "96",
        "resistance_level": "105",
        "core_catalyst": "等待事件確認",
        "risk_level": "Medium",
    })

    assert result["trade_direction"] == "Neutral"
    assert result["entry_zone"] == "N/A"
    assert result["target_price"] == "N/A"
    assert result["stop_loss"] == "N/A"
    assert result["risk_level"] == "High"
