import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _base_context(*, recommendation="買入", target_12m="NT$130", confidence="7/10", trust=None):
    data_trust = trust or {
        "status": "fresh",
        "score": 90,
        "critical_failures": [],
        "stale_sources": [],
        "notes": [],
    }
    return {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "data_schema_version": 4,
            "current_price": 100.0,
            "current_price_fmt": "NT$100.00",
            "pe_ratio": "20.0x",
            "revenue_history": [10.0, 12.0],
            "source_audit": [{"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1}],
            "data_trust": data_trust,
        },
        "parsed": {
            "recommendation": {
                "建議": recommendation,
                "3個月": "NT$110",
                "6個月": "NT$120",
                "12個月": target_12m,
                "信心": confidence,
            },
            "price_targets": {"熊市情境": 80, "基本情境": 120, "牛市情境": 140},
        },
        "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
    }


def _base_snapshot(context, *, evidence_verdict="approved", evidence_matrix=None):
    data = context["data"]
    return {
        "pipeline": context.get("pipeline_id"),
        "data": data,
        "data_trust": data["data_trust"],
        "data_confidence_score": data["data_trust"].get("score", 90),
        "evidence_exit_gate": {"verdict": evidence_verdict, "failed_count": 0},
        "evidence_matrix": evidence_matrix if evidence_matrix is not None else [
            {"claim": "最終投資建議", "basis": "建議: 買入；12個月: NT$130", "status": "success"}
        ],
    }


def test_content_credibility_blocks_buy_when_main_target_is_below_current_price():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="買入", target_12m="NT$90")
    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "blocked"
    assert any(issue["id"] == "buy_target_below_current_price" for issue in result["blocking_issues"])


def test_content_credibility_blocks_explicit_targets_when_data_confidence_is_low():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(
        recommendation="持有",
        target_12m="NT$120",
        trust={"status": "partial", "score": 45, "critical_failures": [], "stale_sources": [], "notes": []},
    )
    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "blocked"
    assert any(issue["id"] == "explicit_target_price_low_data_confidence" for issue in result["blocking_issues"])


def test_content_credibility_blocks_high_confidence_when_evidence_is_rejected():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="9/10")
    result = evaluate_content_credibility(context, _base_snapshot(context, evidence_verdict="rejected"))

    assert result["status"] == "blocked"
    assert any(issue["id"] == "high_confidence_rejected_evidence" for issue in result["blocking_issues"])


def test_content_credibility_warns_when_final_recommendation_lacks_evidence_matrix_coverage():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    result = evaluate_content_credibility(context, _base_snapshot(context, evidence_matrix=[]))

    assert result["status"] == "warning"
    assert any(issue["id"] == "missing_final_recommendation_evidence" for issue in result["warnings"])


def test_report_renderer_attaches_content_credibility_to_snapshot_and_metadata(monkeypatch):
    import reporting.renderer as renderer_module
    from reporting import ReportRenderer, ReportRequest

    async def fake_html(context):
        return fake_html_sync(context)

    def fake_html_sync(context):
        gate = context.get("content_credibility") or {}
        gate_line = f"<p>Content credibility：{gate.get('status')}</p>" if gate else ""
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
            f"{gate_line}"
            "</body></html>"
        )

    def fake_markdown(context):
        gate = context.get("content_credibility") or {}
        gate_line = f"\n- **Content credibility:** {gate.get('status')}\n" if gate else ""
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
            f"{gate_line}"
        )

    monkeypatch.setattr(renderer_module, "generate_html_report_async", fake_html)
    monkeypatch.setattr(renderer_module, "generate_markdown_report", fake_markdown)

    context = _base_context(recommendation="買入", target_12m="NT$90")
    bundle = asyncio.run(
        ReportRenderer().render_async(
            ReportRequest(
                context=context,
                pipeline_id="v1",
                filename="2330_TW_v1_report_20260708_000000.html",
            )
        )
    )

    assert bundle.metadata["content_credibility"]["status"] == "blocked"
    assert bundle.data_snapshot["content_credibility"]["status"] == "blocked"
    assert "Content credibility：blocked" in bundle.html
    assert "**Content credibility:** blocked" in bundle.markdown


def test_report_conformance_blocks_when_content_credibility_is_blocked():
    from reporting.conformance import evaluate_report_conformance

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
        content_credibility={"status": "blocked", "blocking_issues": [{"id": "buy_target_below_current_price"}]},
    )

    assert result["status"] == "blocked"
    assert any(issue["id"] == "content_credibility" for issue in result["blocking_issues"])
    assert "content_credibility" in [step["id"] for step in result["decision_tree"]]
