import sys
import asyncio
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting import ReportRenderer, ReportRequest  # noqa: E402
from reporting.audit_trust import build_audit_markdown  # noqa: E402
from reporting.lint import ReportLintError, assert_report_lint_passed, get_critical_lint_rules, lint_report_artifacts  # noqa: E402


def test_report_lint_passes_clean_artifacts():
    result = assert_report_lint_passed("<h1>台積電投資建議</h1>", "# 台積電投資建議\n\n內容乾淨。")

    assert result["status"] == "passed"
    assert result["blocking_issues"] == []


def test_critical_lint_rules_expose_recommendation_and_target_price_contracts():
    rules = get_critical_lint_rules()
    rule_ids = {rule["id"] for rule in rules}

    assert {"missing_recommendation", "missing_target_price"}.issubset(rule_ids)
    assert all("pattern" in rule and "label" in rule for rule in rules)


def test_report_lint_blocks_prompt_and_execution_failure_leaks():
    result = lint_report_artifacts(
        "<section>Senior Financial Media Host</section>",
        "# 報告\n\n[Agent 14 執行失敗：所有模型/Key 不可用，最後錯誤：429 RESOURCE_EXHAUSTED]",
    )

    assert result["status"] == "blocked"
    labels = {issue["label"] for issue in result["blocking_issues"]}
    assert {"prompt_role_leak", "agent_execution_failure"}.issubset(labels)
    with pytest.raises(ReportLintError):
        assert_report_lint_passed("<p>ok</p>", "peer_reasoning: leaked JSON key")


def test_report_lint_allows_visible_audit_repair_notice():
    result = assert_report_lint_passed(
        '<div class="audit-banner">系統異常提醒：本報告已保留供檢視。自動修復失敗：模型修復暫不可用。</div>',
        "## 系統異常提醒\n\n- 自動修復失敗：模型修復暫不可用。",
    )

    assert result["status"] == "warning"
    assert result["blocking_issues"] == []


def test_audit_banner_masks_agent_execution_failure_before_lint():
    markdown = build_audit_markdown({
        "final_audit": {
            "critical": ["估值模型與成長預測 輸出為失敗訊息，不能產生正式報告。"],
            "warnings": [],
            "corrections": [],
        },
        "audit_repair_log": [
            "估值模型與成長預測 自動修復失敗：[Agent 14 執行失敗：所有模型/Key 不可用，最後錯誤：503 UNAVAILABLE]"
        ],
    })

    assert "執行失敗" not in markdown
    assert "所有模型/Key 不可用" not in markdown
    assert "503 UNAVAILABLE" not in markdown
    assert_report_lint_passed("<p>ok</p>", markdown)


def test_report_renderer_stores_lint_summary_in_snapshot(monkeypatch):
    async def fake_html(_context):
        return "<html><body><h1>乾淨報告</h1></body></html>"

    def fake_markdown(_context):
        return "# 乾淨報告\n\n內容。"

    import reporting.renderer as renderer_module

    monkeypatch.setattr(renderer_module, "generate_html_report_async", fake_html)
    monkeypatch.setattr(renderer_module, "generate_markdown_report", fake_markdown)
    bundle = asyncio.run(
        ReportRenderer().render_async(
            ReportRequest(
                context={
                    "ticker": "2330.TW",
                    "company_name": "台積電",
                    "pipeline_id": "v1",
                    "data": {"ticker": "2330.TW", "source_audit": []},
                },
                pipeline_id="v1",
                filename="2330_TW_v1_report_20260607_000000.html",
            )
        )
    )

    assert bundle.data_snapshot["report_lint"]["status"] == "passed"
    assert bundle.metadata["report_lint"]["status"] == "passed"


def test_report_renderer_scrubs_structured_key_leaks_before_final_lint(monkeypatch):
    async def fake_html(_context):
        return "<html><body><p>analysis_markdown: 正文仍可閱讀。</p></body></html>"

    def fake_markdown(_context):
        return "# 報告\n\npeer_reasoning: 同業比較推論摘要。"

    import reporting.renderer as renderer_module

    monkeypatch.setattr(renderer_module, "generate_html_report_async", fake_html)
    monkeypatch.setattr(renderer_module, "generate_markdown_report", fake_markdown)
    bundle = asyncio.run(
        ReportRenderer().render_async(
            ReportRequest(
                context={
                    "ticker": "2330.TW",
                    "company_name": "台積電",
                    "pipeline_id": "v1",
                    "data": {"ticker": "2330.TW", "source_audit": []},
                },
                pipeline_id="v1",
                filename="2330_TW_v1_report_20260607_000000.html",
            )
        )
    )

    assert "analysis_markdown" not in bundle.html
    assert "peer_reasoning" not in bundle.markdown
    assert "分析正文" in bundle.html
    assert "同業比較推論" in bundle.markdown
    assert bundle.metadata["report_lint"]["status"] == "passed"


def test_report_renderer_still_blocks_non_structured_lint_issues(monkeypatch):
    async def fake_html(_context):
        return "<html><body>Senior Financial Media Host</body></html>"

    def fake_markdown(_context):
        return "# 報告\n\nanalysis_markdown: 正文。"

    import reporting.renderer as renderer_module

    monkeypatch.setattr(renderer_module, "generate_html_report_async", fake_html)
    monkeypatch.setattr(renderer_module, "generate_markdown_report", fake_markdown)

    with pytest.raises(ReportLintError):
        asyncio.run(
            ReportRenderer().render_async(
                ReportRequest(
                    context={
                        "ticker": "2330.TW",
                        "company_name": "台積電",
                        "pipeline_id": "v1",
                        "data": {"ticker": "2330.TW", "source_audit": []},
                    },
                    pipeline_id="v1",
                    filename="2330_TW_v1_report_20260607_000000.html",
                )
            )
        )
