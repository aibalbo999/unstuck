import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import final_audit  # noqa: E402
import decision_tracking  # noqa: E402
import prompt_builder  # noqa: E402
import structured_outputs  # noqa: E402
from agent_runtime.prompting import build_prompt  # noqa: E402
from state_memory import initialize_agent_state  # noqa: E402


def _recommendation_payload(confidence: str = "9/10") -> dict:
    return {
        "reasoning_steps": ["檢查估值", "檢查風險", "形成建議"],
        "recommendation": {
            "建議": "持有",
            "短期目標（3個月）": "NT$100",
            "中期目標（6個月）": "NT$105",
            "長期目標（12個月）": "NT$110",
            "長期潛力（5年）": "穩健",
            "信心指數": confidence,
        },
        "confidence_basis": {
            "evidence_items": ["估值區間可用", "財務資料可用", "風險已揭露"],
            "key_risks_acknowledged": ["資料過期", "籌碼波動"],
            "data_gaps": [],
        },
        "scenario_triggers": [
            {"trigger_condition": "資料可信度降至 error", "action": "降低信心分數", "direction": "neutral_review"},
            {"trigger_condition": "12個月目標價偏離估值區間", "action": "重新評估建議", "direction": "neutral_review"},
        ],
        "analysis_markdown": "資料限制已揭露的正式段落。",
    }


def test_valuation_prompt_includes_state_view_and_deemphasizes_previous_summary():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "revenue_history": [100, 120],
    }
    state = initialize_agent_state(data, run_id="prompt-1")
    state.quant_metrics = {
        "calculations": {
            "dcf_scenarios_default": {
                "base": {"price_per_share_twd": 100},
            }
        }
    }
    context = {
        "analyses": {1: "早期商業模式完整分析 " * 200},
        "structured_outputs": {},
        "agent_state": state,
    }

    prompt = build_prompt(4, data, context)

    assert "AgentState view" in prompt
    assert '"quant_metrics"' in prompt
    assert "你不再讀取前序摘要" in prompt


def test_valuation_prompts_and_rules_require_state_paths_and_closed_breaker():
    agents = json.loads((ROOT / "backend" / "prompts" / "agents.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "backend" / "prompts" / "runtime_rules.json").read_text(encoding="utf-8"))

    for agent_num in ("4", "14"):
        prompt = agents["analysis_prompts"][agent_num]
        valuation_rules = rules["numeric_tool_instructions"][agent_num]["rules"]

        assert "AgentState view" in prompt
        assert "circuit_breaker.status" in prompt
        assert any("state path" in rule and "AgentState view" in rule for rule in valuation_rules)


def test_prompt_payload_includes_data_trust_and_audit_summary():
    prompt = prompt_builder.format_data_for_prompt(
        {
            "data_schema_version": 4,
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "data_trust": {
                "status": "partial",
                "critical_failures": ["financial_statements"],
                "stale_sources": [],
                "last_market_data_at": "2026-06-07T00:00:00+00:00",
                "notes": ["fixture trust note"],
            },
            "source_audit": [
                {
                    "source": "financial_statements",
                    "provider": "FinMind",
                    "status": "error",
                    "record_count": 0,
                    "cache_hit": False,
                    "stale": False,
                    "error_kind": "RuntimeError",
                    "message": "failed",
                }
            ],
        }
    )

    payload_text = prompt.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0]
    payload = json.loads(payload_text)

    assert payload["data_trust"]["status"] == "partial"
    assert payload["source_audit_summary"][0]["source"] == "financial_statements"
    assert payload["source_audit_summary"][0]["status"] == "error"
    assert "不得在沒有額外佐證下給出高信心" in prompt


def test_prompt_payload_includes_global_market_and_international_news_context():
    data = {
        "data_schema_version": 4,
        "ticker": "2330.TW",
        "company_name": "台積電",
        "global_market_context": {
            "as_of": "2026-06-12T00:00:00+00:00",
            "lookback_days": 5,
            "items": [
                {"symbol": "QQQ", "category": "us_growth", "change_5d_pct": 3.2, "source": "yfinance"},
                {"symbol": "SMH", "category": "semiconductors_ai", "change_5d_pct": 4.1, "source": "yfinance"},
                {"symbol": "NVDA", "category": "semiconductors_ai", "change_5d_pct": 5.0, "source": "yfinance"},
                {"symbol": "TSM", "category": "semiconductors_ai", "change_5d_pct": 2.5, "source": "yfinance"},
            ],
            "coverage_notes": [],
        },
        "international_news_context": {
            "lookback_days": 7,
            "topics": [
                {"tag": "macro", "headline": "Fed rate path drives global risk appetite", "source": "GDELT"},
                {"tag": "semiconductors_ai", "headline": "AI chip demand lifts suppliers", "source": "GDELT"},
                {"tag": "policy_trade", "headline": "Export controls remain in focus", "source": "GDELT"},
            ],
            "coverage_notes": [],
        },
    }

    prompt = prompt_builder.format_data_for_prompt(data)
    compact_prompt = prompt_builder.format_data_for_prompt(data, compact=True)
    payload = json.loads(prompt.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0])
    compact_payload = json.loads(compact_prompt.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0])

    assert payload["global_market_context"]["items"][0]["symbol"] == "QQQ"
    assert payload["international_news_context"]["topics"][0]["tag"] == "macro"
    assert [item["symbol"] for item in compact_payload["global_market_context"]["items"]] == ["QQQ", "SMH", "NVDA"]
    assert [item["headline"] for item in compact_payload["international_news_context"]["topics"]] == [
        "Fed rate path drives global risk appetite",
        "AI chip demand lifts suppliers",
    ]
    assert "美股帶動" in prompt
    assert "global_market_context" in prompt


def test_compact_prompt_keeps_macro_commodity_and_regional_context_representatives():
    data = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "global_market_context": {
            "items": [
                {"symbol": "SPY", "category": "us_broad", "change_5d_pct": 0.2, "source": "yfinance"},
                {"symbol": "QQQ", "category": "us_growth", "change_5d_pct": 1.1, "source": "yfinance"},
                {"symbol": "SMH", "category": "semiconductors_ai", "change_5d_pct": 1.4, "source": "yfinance"},
                {"symbol": "^TNX", "category": "rates", "change_5d_pct": -0.5, "source": "yfinance"},
                {"symbol": "DX-Y.NYB", "category": "fx", "change_5d_pct": 0.4, "source": "yfinance"},
                {"symbol": "CL=F", "category": "commodity_energy", "change_5d_pct": 2.3, "source": "yfinance"},
                {"symbol": "^TWII", "category": "regional_taiwan", "change_5d_pct": 1.7, "source": "yfinance"},
            ],
            "coverage_notes": [],
        },
    }

    compact_prompt = prompt_builder.format_data_for_prompt(data, compact=True)
    compact_payload = json.loads(compact_prompt.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0])
    symbols = {item["symbol"] for item in compact_payload["global_market_context"]["items"]}

    assert {"^TNX", "DX-Y.NYB", "CL=F", "^TWII"}.issubset(symbols)


def test_runtime_rules_require_agents_to_cite_or_disclose_global_context():
    rules = json.loads((ROOT / "backend" / "prompts" / "runtime_rules.json").read_text(encoding="utf-8"))
    enrichment_rules = rules["data_enrichment_instructions"]

    assert any("global_market_context" in rule for rule in enrichment_rules["1"]["rules"])
    assert any("international_news_context" in rule for rule in enrichment_rules["1"]["rules"])
    assert any("global_market_context" in rule and "Round 3" in rule for rule in enrichment_rules["6"]["rules"])
    assert any("international_news_context" in rule and "最終" in rule for rule in enrichment_rules["7"]["rules"])
    assert any("global_market_context" in rule for rule in enrichment_rules["11"]["rules"])
    assert any("international_news_context" in rule for rule in enrichment_rules["11"]["rules"])
    assert any("global_market_context" in rule and "籌碼" in rule for rule in enrichment_rules["15"]["rules"])
    assert any("global_market_context" in rule and "最終" in rule for rule in enrichment_rules["16"]["rules"])


def test_structured_output_warns_on_high_confidence_with_low_trust():
    context = {
        "data": {"data_trust": {"status": "stale"}},
        "analyses": {},
    }

    report_text = structured_outputs.process_agent_response(
        7,
        json.dumps(_recommendation_payload("9/10"), ensure_ascii=False),
        context,
    )

    assert "[投資建議]" in report_text
    assert context["structured_outputs"][7]["recommendation"]["信心指數"] == "9/10"
    assert context["structured_quality_warnings"]
    assert "data_trust=stale" in context["structured_quality_warnings"][0]


def test_final_audit_warns_on_high_confidence_with_low_trust():
    context = {
        "pipeline_id": "v1",
        "agent_sequence": [7],
        "data": {
            "current_price": 100,
            "data_trust": {"status": "partial"},
        },
        "analyses": {7: "正式最終投資建議段落。"},
        "structured_outputs": {7: _recommendation_payload("8.5/10")},
        "parsed": {
            "moat_scores": {
                "品牌影響力": 5,
                "網路效應": 5,
                "轉換成本": 5,
                "成本優勢": 5,
                "專利技術": 5,
                "整體護城河": 5,
            },
            "price_targets": {"熊市情境": 80, "基本情境": 100, "牛市情境": 120},
            "recommendation": {
                "建議": "持有",
                "3個月": "NT$100",
                "6個月": "NT$105",
                "12個月": "NT$110",
                "信心": "8.5/10",
            },
        },
    }

    audit = final_audit.run_final_report_audit(context, append_section=False)

    assert any("data_trust=partial" in warning for warning in audit["warnings"])
    assert audit["confidence_calibration"]["status"] == "needs_downgrade"
    assert audit["confidence_calibration"]["max_recommended_confidence"] == 7
    assert any("建議信心上限 7/10" in warning for warning in audit["warnings"])


def test_final_audit_warns_when_final_decision_omits_available_global_context():
    context = {
        "pipeline_id": "v1",
        "agent_sequence": [7],
        "data": {
            "current_price": 100,
            "global_market_context": {
                "items": [{"symbol": "QQQ", "change_5d_pct": 2.4, "source": "yfinance"}],
            },
            "international_news_context": {
                "topics": [{"tag": "macro", "headline": "Fed path drives risk appetite", "source": "GDELT"}],
            },
            "data_trust": {"status": "fresh"},
        },
        "analyses": {7: "正式最終投資建議段落，只討論估值與財務。"},
        "structured_outputs": {7: _recommendation_payload("6/10")},
        "parsed": {
            "moat_scores": {
                "品牌影響力": 5,
                "網路效應": 5,
                "轉換成本": 5,
                "成本優勢": 5,
                "專利技術": 5,
                "整體護城河": 5,
            },
            "price_targets": {"熊市情境": 80, "基本情境": 100, "牛市情境": 120},
            "recommendation": _recommendation_payload("6/10")["recommendation"],
        },
    }

    audit = final_audit.run_final_report_audit(context, append_section=False)

    assert any("全球市場脈絡" in warning and "國際新聞脈絡" in warning for warning in audit["warnings"])

    context["analyses"][7] = "最終建議已檢查全球市場脈絡與國際新聞脈絡；兩者未改變持有結論。"
    clean_audit = final_audit.run_final_report_audit(context, append_section=False)

    assert not any("全球市場脈絡" in warning and "國際新聞脈絡" in warning for warning in clean_audit["warnings"])


def test_decision_tracking_includes_confidence_calibration_from_snapshot(tmp_path):
    snapshot_path = tmp_path / "report.data.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "data_trust": {
                    "status": "stale",
                    "critical_failures": [],
                    "stale_sources": ["market_data"],
                    "last_market_data_at": "2026-06-07T00:00:00+00:00",
                    "notes": ["市場資料過期。"],
                },
                "data": {"current_price": 100},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tracking = decision_tracking.build_decision_tracking(
        {
            "recommendation": "持有",
            "current_price": "NT$100",
            "target_3m": "NT$100",
            "target_6m": "NT$105",
            "target_12m": "NT$110",
            "confidence": "9/10",
        },
        str(snapshot_path),
    )

    assert tracking["confidence_calibration"]["status"] == "needs_downgrade"
    assert tracking["confidence_calibration"]["max_recommended_confidence"] == 7
