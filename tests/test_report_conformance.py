import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _conforming_artifacts():
    html = """
    <section>本報告資料可信度</section>
    <section>執行邏輯與模型檢查</section>
    <section>報告模板與閱讀路徑</section>
    <section>一頁式摘要</section>
    <section>長線投資論文與決策紀律</section>
    <section>關鍵數據來源對照</section>
    <section>來源審計</section>
    <section>最終投資建議</section>
    """
    markdown = """
## 本報告資料可信度
## 執行邏輯與模型檢查
## 報告模板與閱讀路徑
## 一頁式摘要
## 長線投資論文與決策紀律
## 關鍵數據來源對照
## 來源審計
## 🎯 最終投資建議
"""
    return html, markdown


class BrokenConformanceGateGet(dict):
    def get(self, key, default=None):
        raise RuntimeError("report conformance gate get unavailable")


def test_report_conformance_decision_tree_passes_visible_contracts():
    from reporting.conformance import evaluate_report_conformance

    html, markdown = _conforming_artifacts()
    result = evaluate_report_conformance(
        html,
        markdown,
        context={
            "data": {"data_trust": {"status": "fresh"}},
            "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
        },
        snapshot={"data_trust": {"status": "fresh"}},
        report_lint={"status": "passed", "blocking_issues": [], "warnings": []},
        evidence_exit_gate={"verdict": "approved", "failed_count": 0},
    )

    assert result["status"] == "passed"
    assert result["summary"] == "報告符合輸出契約。"
    assert [step["id"] for step in result["decision_tree"]] == [
        "report_lint",
        "required_visibility",
        "final_audit",
        "evidence_exit_gate",
        "content_credibility",
        "data_trust",
    ]


def test_report_conformance_keeps_quality_gate_mappings_when_accessor_fails():
    from reporting.conformance import evaluate_report_conformance

    html, markdown = _conforming_artifacts()
    result = evaluate_report_conformance(
        html,
        markdown,
        context={
            "data": {"data_trust": {"status": "fresh"}},
            "final_audit": BrokenConformanceGateGet(
                {
                    "status": "warning",
                    "critical": [],
                    "warnings": [{"id": "audit_warning"}],
                }
            ),
        },
        snapshot={"data_trust": {"status": "fresh"}},
        report_lint=BrokenConformanceGateGet(
            {
                "status": "warning",
                "blocking_issues": [],
                "warnings": [{"id": "lint_warning"}],
            }
        ),
        evidence_exit_gate=BrokenConformanceGateGet(
            {
                "verdict": "rejected",
                "failed_count": 1,
            }
        ),
        content_credibility=BrokenConformanceGateGet(
            {
                "status": "blocked",
                "blocking_issues": [{"id": "credibility_blocker"}],
                "warnings": [],
            }
        ),
    )

    assert result["status"] == "blocked"
    assert [step["status"] for step in result["decision_tree"]] == [
        "warning",
        "passed",
        "warning",
        "blocked",
        "blocked",
        "passed",
    ]
    assert {issue["id"] for issue in result["blocking_issues"]} == {
        "evidence_exit_gate",
        "content_credibility",
    }
    assert {issue["id"] for issue in result["warnings"]} == {
        "report_lint",
        "final_audit",
    }


def test_report_conformance_blocks_missing_required_visibility_and_rejected_evidence():
    from reporting.conformance import evaluate_report_conformance

    result = evaluate_report_conformance(
        "<section>一頁式摘要</section>",
        "## 一頁式摘要\n",
        context={"data": {"data_trust": {"status": "fresh"}}},
        snapshot={"data_trust": {"status": "fresh"}},
        report_lint={"status": "passed", "blocking_issues": [], "warnings": []},
        evidence_exit_gate={"verdict": "rejected", "failed_count": 2},
    )

    assert result["status"] == "blocked"
    assert any(issue["id"] == "required_visibility" for issue in result["blocking_issues"])
    assert any(issue["id"] == "evidence_exit_gate" for issue in result["blocking_issues"])


def test_report_conformance_requires_mode_specific_decision_discipline():
    from reporting.conformance import evaluate_report_conformance

    html = """
    <section>本報告資料可信度</section>
    <section>執行邏輯與模型檢查</section>
    <section>報告模板與閱讀路徑</section>
    <section>事件波段摘要</section>
    <section>關鍵數據來源對照</section>
    <section>來源審計</section>
    <section>極短線交易計畫</section>
    """
    markdown = """
## 本報告資料可信度
## 執行邏輯與模型檢查
## 報告模板與閱讀路徑
## 事件波段摘要
## 關鍵數據來源對照
## 來源審計
## 極短線交易計畫
"""

    result = evaluate_report_conformance(
        html,
        markdown,
        context={
            "pipeline_id": "v4",
            "data": {"data_trust": {"status": "fresh"}},
            "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
        },
        snapshot={"data_trust": {"status": "fresh"}},
        report_lint={"status": "passed", "blocking_issues": [], "warnings": []},
        evidence_exit_gate={"verdict": "approved", "failed_count": 0},
    )

    assert result["status"] == "blocked"
    required_visibility = next(issue for issue in result["blocking_issues"] if issue["id"] == "required_visibility")
    assert {"id": "decision_discipline", "label": "交易計畫與風控紀律"} in required_visibility["details"]


def test_report_renderer_attaches_conformance_to_snapshot_metadata_and_final_artifacts(monkeypatch):
    import reporting.renderer as renderer_module
    from reporting import ReportRenderer, ReportRequest

    async def fake_html(context):
        gate = context.get("evidence_exit_gate") or {}
        conformance = context.get("report_conformance") or {}
        gate_line = f"<p>Evidence gate：{gate.get('verdict')}</p>" if gate else ""
        conformance_line = f"<p>Report conformance：{conformance.get('status')}</p>" if conformance else ""
        return (
            "<html><body>"
            "<section>本報告資料可信度</section>"
            "<section>執行邏輯與模型檢查</section>"
            "<section>報告模板與閱讀路徑</section>"
            "<section>一頁式摘要</section>"
            "<section>長線投資論文與決策紀律</section>"
            "<section>關鍵數據來源對照</section>"
            "<section>來源審計</section>"
            "<section>最終投資建議</section>"
            "<p>股價: NT$100.00</p><p>P/E: 20.0x</p><p>營收: 12.0</p>"
            f"{gate_line}{conformance_line}"
            "</body></html>"
        )

    def fake_markdown(context):
        gate = context.get("evidence_exit_gate") or {}
        conformance = context.get("report_conformance") or {}
        gate_line = f"\n- **Evidence gate:** {gate.get('verdict')}\n" if gate else ""
        conformance_line = f"- **Report conformance:** {conformance.get('status')}\n" if conformance else ""
        return (
            "# 報告\n\n"
            "## 本報告資料可信度\n"
            "## 執行邏輯與模型檢查\n"
            "## 報告模板與閱讀路徑\n"
            "## 一頁式摘要\n"
            "## 長線投資論文與決策紀律\n"
            "## 關鍵數據來源對照\n"
            "## 來源審計\n"
            "## 🎯 最終投資建議\n"
            "- 股價: NT$100.00\n- P/E: 20.0x\n- 營收: 12.0\n"
            f"{gate_line}{conformance_line}"
        )

    monkeypatch.setattr(renderer_module, "generate_html_report_async", fake_html)
    monkeypatch.setattr(renderer_module, "generate_markdown_report", fake_markdown)

    bundle = asyncio.run(
        ReportRenderer().render_async(
            ReportRequest(
                context={
                    "ticker": "2330.TW",
                    "company_name": "台積電",
                    "pipeline_id": "v1",
                    "data": {
                        "ticker": "2330.TW",
                        "data_schema_version": 4,
                        "current_price": 100.0,
                        "pe_ratio": "20.0x",
                        "revenue_history": [10.0, 12.0],
                        "source_audit": [{"source": "market_data", "status": "success"}],
                        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
                    },
                    "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
                },
                pipeline_id="v1",
                filename="2330_TW_v1_report_20260628_000000.html",
            )
        )
    )

    assert bundle.metadata["report_conformance"]["status"] == "passed"
    assert bundle.data_snapshot["report_conformance"]["status"] == "passed"
    assert "Report conformance：passed" in bundle.html
    assert "**Report conformance:** passed" in bundle.markdown
