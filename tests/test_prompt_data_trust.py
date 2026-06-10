import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import final_audit  # noqa: E402
import decision_tracking  # noqa: E402
import prompt_builder  # noqa: E402
import structured_outputs  # noqa: E402


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
        "analysis_markdown": "資料限制已揭露的正式段落。",
    }


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
