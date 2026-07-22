import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.content_credibility_data_confidence import evaluate_data_confidence_target_guardrail  # noqa: E402


def test_data_confidence_guardrail_blocks_explicit_target_when_score_is_low():
    context = {
        "parsed": {
            "recommendation": {"12個月": "NT$120"},
            "price_targets": {"基本情境": 120},
        }
    }
    data_trust = {"status": "partial", "score": 45}

    result = evaluate_data_confidence_target_guardrail(context, data_trust)

    assert result["blocking_issues"][0]["id"] == "explicit_target_price_low_data_confidence"
    assert result["warnings"] == []
    assert result["checks"][0]["id"] == "data_confidence_target_guardrail"
    assert result["checks"][0]["status"] == "blocked"
    assert result["blocking_issues"][0]["details"]["data_confidence_score"] == 45.0


def test_data_confidence_guardrail_warns_for_non_fresh_data_without_explicit_targets():
    context = {"parsed": {"recommendation": {"建議": "持有"}}}
    data_trust = {"status": "partial", "score": 80}

    result = evaluate_data_confidence_target_guardrail(context, data_trust)

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "non_fresh_data_trust"
    assert result["checks"][0]["status"] == "warning"
    assert result["warnings"][0]["details"]["data_trust_label"] == "部分異常"


def test_data_confidence_guardrail_drops_string_empty_status_tokens():
    context = {"parsed": {"recommendation": {"建議": "持有"}}}
    data_trust = {"status": "NaN", "score": 80}

    result = evaluate_data_confidence_target_guardrail(context, data_trust)

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "non_fresh_data_trust"
    assert result["warnings"][0]["details"]["data_trust_status"] == "unknown"
    assert result["warnings"][0]["details"]["data_trust_label"] == "未記錄"
    rendered = str(result).lower()
    assert "nan" not in rendered
    assert "infinity" not in rendered


def test_data_confidence_guardrail_passes_when_data_is_fresh():
    result = evaluate_data_confidence_target_guardrail(
        {"parsed": {}},
        {"status": "fresh", "score": 92},
    )

    assert result["blocking_issues"] == []
    assert result["warnings"] == []
    assert result["checks"][0]["status"] == "passed"
    assert result["checks"][0]["details"]["data_confidence_score"] == 92.0
