"""Management summaries may not manufacture quotes to meet a fixed count."""
import pytest

from structured_output_risk_models import ManagementSentimentStructuredOutput


@pytest.mark.parametrize("highlights, expected", [
    (None, []), ([], []), ({"bad": "shape"}, []),
    ([None, {"keyword": "missing quote"}], []),
    ([{"keyword": "需求", "quote": "需求穩定"}], [("需求", "需求穩定")]),
])
def test_schema_retains_only_supplied_verbatim_quote_rows(highlights, expected):
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "資料不足", "confidence": 0, "highlights": highlights,
        "analysis_markdown": "僅有實際來源支持的引用。",
    })
    assert [(item.keyword, item.quote) for item in output.highlights] == expected


def test_missing_highlights_is_zero_evidence_not_three_unavailable_quotes():
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "資料不足", "confidence": 0, "analysis_markdown": "未取得逐字稿。",
    })
    assert output.highlights == []


def test_three_valid_quotes_are_retained_after_invalid_rows_without_padding():
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "中立", "confidence": 0.5, "analysis_markdown": "逐字稿引用",
        "highlights": [None, {}, {"keyword": "需求", "quote": "需求穩定"},
                       {"keyword": "成本", "quote": "成本上升"}, {"keyword": "供應", "quote": "供應正常"},
                       {"keyword": "後續", "quote": "無需額外第四段"}],
    })
    assert [item.quote for item in output.highlights] == ["需求穩定", "成本上升", "供應正常"]
