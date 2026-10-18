"""Presentation repairs must not change saved research decisions or inputs."""

from copy import deepcopy

from report_preview import build_report_preview
from reporting.analysis_structured_overlays import build_management_sentiment


def test_position_action_is_primary_and_research_rating_remains_separate():
    snapshot = {"rerun_context": {"parsed": {"position_plan": {
        "action": "等待", "entry_zone": "N/A", "stop_loss": "N/A",
        "position_size": "0%", "invalidation": "等待下一份財報",
    }}}}
    before = deepcopy(snapshot)
    result = build_report_preview("v2", "TEST.TW", {"recommendation": "買入"}, snapshot=snapshot)
    assert result["primary"]["value"] == "等待"
    assert result["primary"]["tone"] == "is-neutral"
    assert any(row["label"] == "研究評級" and row["value"] == "買入" for row in result["metrics"])
    assert result["targets"][0]["missing_category"] == "not_applicable"
    assert snapshot == before


def test_short_setup_is_authoritative_not_a_shared_markdown_heading():
    snapshot = {"rerun_context": {"parsed": {"short_setup": {
        "entry_trigger": "目前不建立空方部位；等待可驗證條件後重新評估。",
        "cover_stop": "N/A", "downside_target": "N/A",
    }}}}
    result = build_report_preview("v3", "TEST.TW", {}, snapshot=snapshot,
                                  markdown_text="## 做空觸發條件與防軋空停損點\n等待財報。")
    assert result["targets"][0]["value"].startswith("目前不建立")
    assert [row["missing_category"] for row in result["targets"][1:]] == ["not_applicable"] * 2


def test_real_short_prices_and_source_failure_reasons_are_not_hidden():
    setup = {"entry_trigger": "跌破 NT$100 後做空", "cover_stop": "NT$110", "downside_target": "NT$80"}
    result = build_report_preview("v3", "TEST.TW", {}, snapshot={"rerun_context": {"parsed": {"short_setup": setup}}})
    assert [row["value"] for row in result["targets"]] == list(setup.values())
    setup.update(entry_trigger="目前不建立空方部位。", cover_stop="來源異常（原件取得逾時）")
    result = build_report_preview("v3", "TEST.TW", {}, snapshot={"rerun_context": {"parsed": {"short_setup": setup}}})
    assert result["targets"][1]["missing_category"] == "source_error"
    assert result["targets"][2]["value"] == "NT$80"


def test_unassessed_management_has_reason_not_zero_percent_but_assessed_zero_survives():
    raw = {"guidance_tone": "資料不足", "confidence": 0.0, "highlights": [],
           "analysis_markdown": "法說會逐字稿缺漏，無法可靠判斷管理層 Guidance 語氣。"}
    before = deepcopy(raw)
    value = build_management_sentiment({"structured_outputs": {20: raw}})
    assert value["confidence"] is None
    assert value["missing_category"] == "unconfirmed"
    assert "逐字稿" in value["reason"]
    assert raw == before
    assessed = build_management_sentiment({"structured_outputs": {20: {
        "guidance_tone": "保守", "confidence": 0.0, "highlights": [{"keyword": "展望", "quote": "需求下降"}]}}})
    assert assessed["confidence"] == 0.0


def test_empty_legacy_stop_cannot_consume_the_next_heading():
    result = build_report_preview('v3', 'TEST.TW', {},
        markdown_text='- **防軋空停損點:**\n\n## 其他資料\n不相關文字')
    assert result['targets'][1]['missing_category'] == 'unconfirmed'
    assert '其他資料' not in result['targets'][1]['value']


def test_position_actions_are_not_normalized_into_research_ratings_in_history_or_tracking():
    from test_report_display_consistency import javascript
    html = javascript('''(() => {
        const ui = window.StockAgentUi;
        const renderer = window.StockAgentHistoryPanelRenderers.create({
            escapeHtml: ui.escapeHtml, normalizeRecommendation: ui.normalizeRecommendation,
            recommendationTone: ui.recommendationTone
        });
        const report = {ticker:'TEST.TW', pipeline_id:'v2', filename:'sample.html',
            recommendation:{recommendation:'買入'}, preview:{kind:'position_plan',
                primary:{value:'減碼',tone:'is-avoid'}}};
        return renderer.renderHistoryList([report]) + renderer.renderReportCard(report, true);
    })()''')
    assert html.count('>減碼</span>') == 2
    assert '>避免</span>' not in html
