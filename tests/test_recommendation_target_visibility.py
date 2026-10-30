"""Existing target content must remain visible to readers and final lint."""
import copy

import pytest

from final_audit_lint import critical_lint_issues_for_pipeline
from structured_output_parser import parse_recommendation_from_text
from structured_output_rendering import format_recommendation_block


TARGETS = ("短期目標（3個月）", "中期目標（6個月）", "長期目標（12個月）", "長期潛力（5年）")


@pytest.mark.parametrize("value", ["資料不足，信心低於門檻", "NT$100–120"])
def test_complete_target_fields_satisfy_visibility_without_changing_values(value):
    rec = {"建議": "避免", **dict.fromkeys(TARGETS, value), "信心指數": "5/10"}
    before = copy.deepcopy(rec)
    text = format_recommendation_block(7, rec)
    assert critical_lint_issues_for_pipeline("v1", text) == []
    assert parse_recommendation_from_text(text) == before
    assert rec == before


@pytest.mark.parametrize("missing", [None, "", "N/A"])
def test_missing_target_content_is_not_hidden_by_a_generated_heading(missing):
    rec = {"建議": "避免", **dict.fromkeys(TARGETS, "資料不足，信心低於門檻")}
    if missing is None:
        rec.pop(TARGETS[0])
    else:
        rec[TARGETS[0]] = missing
    text = format_recommendation_block(7, rec)
    assert any("目標價" in issue for issue in critical_lint_issues_for_pipeline("v1", text))
