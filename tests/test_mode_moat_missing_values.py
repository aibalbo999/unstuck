"""Missing evidence must never become a synthetic moat score."""

import pytest
import json
from pathlib import Path
import shutil
import subprocess

from final_audit import run_final_report_audit
from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text
from structured_output_parser import parse_structured_data
from structured_output_valuation_models import MoatScores


FIELDS = ("品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河")


@pytest.mark.parametrize("value", [None, "N/A", True, float("nan"), float("inf"), -1, 11])
def test_invalid_or_unknown_score_stays_unknown(value):
    output = MoatScores.model_validate({key: value for key in FIELDS})
    assert all(value is None for value in output.model_dump(by_alias=True).values())


@pytest.mark.parametrize("agent,pipeline", [(3, "v1"), (12, "v2")])
def test_missing_scores_survive_normalize_parse_and_display(agent, pipeline):
    payload = {
        "analysis_markdown": "同業與客戶資料不足，本次無法評估護城河。",
        "reasoning_steps": ["缺少客戶資料", "缺少同業資料", "保留未評估"],
    }
    output = normalize_structured_output(agent, payload)
    assert output is not None
    assert output["moat_scores"] == dict.fromkeys(FIELDS)
    parsed = parse_structured_data({"pipeline_id": pipeline, "structured_outputs": {agent: output}})
    assert parsed["moat_assessment"]["status"] == "unassessed"
    text = structured_output_to_report_text(agent, output)
    assert "未評估" in text
    assert "None" not in text
    assert ": 1" not in text


def test_partial_scores_preserve_real_low_score_and_unknowns():
    output = normalize_structured_output(3, {
        "moat_scores": {"品牌影響力": 1, "網路效應": None, "整體護城河": 6.5},
        "reasoning_steps": ["品牌反證", "網路資料不足", "其他證據"],
        "analysis_markdown": "明確品牌反證支持1分，其餘未提供欄位維持未知。",
    })
    assert output["moat_scores"]["品牌影響力"] == 1
    assert output["moat_scores"]["整體護城河"] == 6.5
    assert output["moat_scores"]["網路效應"] is None
    assert output["moat_scores"]["成本優勢"] is None


def test_legacy_missing_analysis_does_not_invent_default_scores():
    parsed = parse_structured_data({"pipeline_id": "v1", "analyses": {3: "護城河資料不足"}})
    assert all(value is None for value in parsed["moat_scores"].values())
    assert parsed["moat_assessment"]["status"] == "unassessed"


@pytest.mark.parametrize("value", ["-1", "11", "N/A（2026年資料待補）", "8..5", "NaN"])
def test_legacy_invalid_or_missing_scores_are_not_clamped_or_parsed_from_dates(value):
    parsed = parse_structured_data({"pipeline_id": "v1", "analyses": {
        3: f"[護城河評分]\n整體護城河：{value}\n[/護城河評分]",
    }})
    assert parsed["moat_scores"]["整體護城河"] is None


def test_final_audit_exposes_unassessed_scores_without_demanding_invention():
    context = {"pipeline_id": "v1", "data": {}, "parsed": {"moat_scores": dict.fromkeys(FIELDS)}}
    audit = run_final_report_audit(context, append_section=False)
    assert any("護城河" in item and "未評估" in item for item in audit["warnings"])
    assert not any("護城河評分缺少欄位" in item for item in audit["critical"])


def test_chart_omits_unknown_scores_and_does_not_render_zero():
    from reporting.html_chart_context import build_html_chart_context

    result = build_html_chart_context({}, {"moat_scores": dict.fromkeys(FIELDS)})
    assert result["moat_values"] == []
    assert result["overall_moat"] is None


@pytest.mark.parametrize("labels,values,expected", [
    (["品牌影響力"], [1], "N/A"),
    (["品牌影響力", "整體護城河"], [1, 6.5], "6.5"),
])
def test_actual_chart_script_does_not_average_partial_scores_into_overall(labels, values, expected):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for actual chart script contract")
    template = Path(__file__).resolve().parents[1] / "backend/templates/includes/charts/moat.html.j2"
    harness = """
const score = {};
const document = {
  getElementById: id => id === 'moatChart' ? {getContext: () => ({})} : score,
  querySelector: () => null
};
function Chart() {}
"""
    harness += "const CHART_DATA = " + json.dumps({"moatLabels": labels, "moatValues": values}) + ";\n"
    harness += template.read_text(encoding="utf-8") + "\nconsole.log(score.textContent);"
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == expected
