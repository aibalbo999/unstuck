import asyncio
import sys
from pathlib import Path
from types import MappingProxyType


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
            {"claim": "估值結論", "basis": "熊市情境: NT$80；基本情境: NT$120；牛市情境: NT$140", "status": "success"},
            {"claim": "最終投資建議", "basis": "建議: 買入；12個月: NT$130", "status": "success"}
        ],
    }


def test_content_credibility_blocks_buy_when_main_target_is_below_current_price():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="買入", target_12m="NT$90")
    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "blocked"
    assert any(issue["id"] == "buy_target_below_current_price" for issue in result["blocking_issues"])


def test_content_credibility_warns_for_unrecognized_recommendation_label():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="未定", target_12m="NT$130")
    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "warning"
    assert any(issue["id"] == "unrecognized_recommendation_label" for issue in result["warnings"])


def test_content_credibility_uses_target_range_midpoint_after_percent_preface():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="買入", target_12m="上行60％，目標價100-160")
    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "passed"
    assert not any(issue["id"] == "buy_target_below_current_price" for issue in result["blocking_issues"])


def test_content_credibility_warns_when_horizon_targets_reverse_for_buy():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="買入", target_12m="NT$130")
    context["parsed"]["recommendation"]["3個月"] = "NT$150"
    context["parsed"]["recommendation"]["6個月"] = "NT$100"

    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "warning"
    issue = next(issue for issue in result["warnings"] if issue["id"] == "horizon_target_sequence_conflict")
    assert issue["details"]["recommendation"] == "買入"


def test_content_credibility_blocks_when_scenario_targets_are_inverted():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="買入", target_12m="NT$130")
    context["parsed"]["price_targets"] = {
        "熊市情境": 150,
        "基本情境": 120,
        "牛市情境": 90,
    }

    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "blocked"
    issue = next(issue for issue in result["blocking_issues"] if issue["id"] == "scenario_target_order_conflict")
    assert issue["details"]["targets"] == {"熊市情境": 150.0, "基本情境": 120.0, "牛市情境": 90.0}


def test_content_credibility_warns_when_scenario_target_cannot_be_parsed():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105")
    context["parsed"]["price_targets"] = {
        "熊市情境": "尚待估值",
        "基本情境": "NT$120",
        "牛市情境": "NT$140",
    }

    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "warning"
    issue = next(issue for issue in result["warnings"] if issue["id"] == "unparseable_scenario_target")
    assert issue["details"]["label"] == "熊市情境"


def test_content_credibility_compares_outer_scenarios_when_base_target_is_missing():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105")
    context["parsed"]["price_targets"] = {
        "熊市情境": 150,
        "牛市情境": 90,
    }

    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "blocked"
    assert any(issue["id"] == "scenario_target_order_conflict" for issue in result["blocking_issues"])


def test_content_credibility_warns_when_12m_target_exceeds_scenario_range():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="買入", target_12m="NT$200")
    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "warning"
    issue = next(
        issue for issue in result["warnings"]
        if issue["id"] == "recommendation_target_outside_scenario_range"
    )
    assert issue["details"]["target_12m"] == 200.0
    assert issue["details"]["allowed_lower_bound"] == 56.0
    assert issue["details"]["allowed_upper_bound"] == 182.0


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


def test_content_credibility_carries_evidence_reason_summary_into_non_approved_warning():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    snapshot = _base_snapshot(context, evidence_verdict="caution")
    snapshot["evidence_exit_gate"].update(
        claim_count=12,
        sampled_count=3,
        failed_count=0,
        unverifiable_count=2,
        unverifiable_reason_counts={"no_matching_snapshot_path": 2},
    )

    result = evaluate_content_credibility(context, snapshot)

    issue = next(issue for issue in result["warnings"] if issue["id"] == "non_approved_evidence_gate")
    assert issue["details"]["evidence_unverifiable_reason_counts"] == {"no_matching_snapshot_path": 2}
    assert issue["details"]["evidence_failed_count"] == 0


def test_content_credibility_warns_high_confidence_when_evidence_is_unrecorded():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="9/10")
    result = evaluate_content_credibility(context, _base_snapshot(context, evidence_verdict="NaN"))

    assert result["status"] == "warning"
    assert any(issue["id"] == "high_confidence_unrecorded_evidence" for issue in result["warnings"])


def test_content_credibility_warns_when_confidence_exceeds_data_trust_cap():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(
        recommendation="持有",
        target_12m="NT$105",
        confidence="9/10",
        trust={"status": "partial", "score": 72, "critical_failures": [], "stale_sources": [], "notes": []},
    )
    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "warning"
    issue = next(issue for issue in result["warnings"] if issue["id"] == "confidence_exceeds_data_trust_cap")
    assert issue["details"]["data_trust_status"] == "partial"
    assert issue["details"]["max_recommended_confidence"] == 7


def test_content_credibility_blocks_when_final_audit_has_critical_issue():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    context["final_audit"] = {
        "status": "needs_attention",
        "critical": ["缺少 Agent 輸出：7"],
        "warnings": [],
        "corrections": [],
    }

    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "blocked"
    issue = next(issue for issue in result["blocking_issues"] if issue["id"] == "final_audit_critical")
    assert issue["details"]["critical"] == ["缺少 Agent 輸出：7"]


def test_content_credibility_warns_when_final_audit_has_warning_but_no_critical_issue():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    context["final_audit"] = {
        "status": "needs_attention",
        "critical": [],
        "warnings": ["最終建議未說明國際新聞脈絡"],
        "corrections": [],
    }

    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "warning"
    assert any(issue["id"] == "final_audit_warning" for issue in result["warnings"])


def test_content_credibility_does_not_escalate_final_audit_corrections_alone():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    context["final_audit"] = {
        "status": "passed",
        "critical": [],
        "warnings": [],
        "corrections": ["已修正格式化價格"],
    }

    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "passed"
    assert not any(issue["id"].startswith("final_audit_") for issue in result["blocking_issues"] + result["warnings"])


def test_content_credibility_reconciles_final_audit_from_stored_conformance():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    context.pop("final_audit")
    snapshot = _base_snapshot(context)
    snapshot["report_conformance"] = {
        "decision_tree": [
            {
                "id": "final_audit",
                "status": "blocked",
                "message": "最終稽核存在 critical 問題。",
                "details": ["缺少 Agent 輸出：7"],
            }
        ]
    }

    result = evaluate_content_credibility(context, snapshot)

    assert result["status"] == "blocked"
    issue = next(issue for issue in result["blocking_issues"] if issue["id"] == "final_audit_critical")
    assert issue["details"]["critical"] == ["缺少 Agent 輸出：7"]


def test_content_credibility_reconciles_final_audit_warning_from_stored_conformance():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    context.pop("final_audit")
    snapshot = _base_snapshot(context)
    snapshot["report_conformance"] = {
        "decision_tree": [
            {
                "id": "final_audit",
                "status": "warning",
                "message": "最終稽核有警示需揭露。",
                "details": ["高信心需揭露資料限制"],
            }
        ]
    }

    result = evaluate_content_credibility(context, snapshot)

    assert result["status"] == "warning"
    issue = next(issue for issue in result["warnings"] if issue["id"] == "final_audit_warning")
    assert issue["details"]["warnings"] == ["高信心需揭露資料限制"]


def test_final_audit_alignment_deduplicates_semantically_equivalent_confidence_warnings():
    from reporting.content_credibility_final_audit import evaluate_final_audit_alignment

    first = "Agent 16 在 data_trust=fresh 時給出高信心（7/10），建議信心上限 6/10，報告需明確揭露資料限制。"
    equivalent = "Agent 16 在 data_trust=fresh 時給出高信心（7/10），建議信心上限 6/10，需於報告中明確說明資料限制。"
    result = evaluate_final_audit_alignment({
        "status": "warning",
        "critical": [],
        "warnings": [first, equivalent, "另一個需要人工確認的警示。"],
    })

    issue = result["warnings"][0]
    assert issue["details"]["warnings"] == [first, "另一個需要人工確認的警示。"]


def test_content_credibility_keeps_passed_when_stored_conformance_final_audit_passes():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    context.pop("final_audit")
    snapshot = _base_snapshot(context)
    snapshot["report_conformance"] = {
        "decision_tree": [{"id": "final_audit", "status": "passed", "message": "最終稽核通過。"}]
    }

    result = evaluate_content_credibility(context, snapshot)

    assert result["status"] == "passed"
    assert not any(issue["id"].startswith("final_audit_") for issue in result["blocking_issues"] + result["warnings"])


def test_content_credibility_warns_when_final_recommendation_lacks_evidence_matrix_coverage():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    result = evaluate_content_credibility(context, _base_snapshot(context, evidence_matrix=[]))

    assert result["status"] == "warning"
    assert any(issue["id"] == "missing_final_recommendation_evidence" for issue in result["warnings"])


def test_content_credibility_uses_trade_setup_alignment_for_mode_d():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="N/A", target_12m="N/A")
    context["pipeline_id"] = "v4"
    context["parsed"]["recommendation"] = {}
    context["parsed"]["trade_setup"] = {
        "trade_direction": "Neutral",
        "entry_zone": "等待回測 NT$90-95",
        "target_price": "NT$105-106.5",
        "stop_loss": "跌破 NT$73.4",
        "core_catalyst": "營收創高與 AI 算力需求。",
        "risk_level": "High",
    }

    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "passed"
    alignment = next(check for check in result["checks"] if check["id"] == "trade_setup_alignment")
    assert alignment["status"] == "passed"
    assert "略過方向一致性檢查" not in alignment["message"]


def test_content_credibility_accepts_tuple_evidence_matrix_rows():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    evidence_matrix = (
        {"claim": "估值結論", "basis": "熊市情境: NT$80；基本情境: NT$120；牛市情境: NT$140", "status": "success"},
        {"claim": "最終投資建議", "basis": "建議: 持有；12個月: NT$105", "status": "success"},
    )

    result = evaluate_content_credibility(context, _base_snapshot(context, evidence_matrix=evidence_matrix))

    assert result["status"] == "passed"
    assert not any(issue["id"] == "missing_final_recommendation_evidence" for issue in result["warnings"])


def test_content_credibility_accepts_mapping_safe_evidence_matrix_rows():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="持有", target_12m="NT$105", confidence="6/10")
    evidence_matrix = (
        MappingProxyType({"claim": "估值結論", "basis": "熊市情境: NT$80；基本情境: NT$120；牛市情境: NT$140", "status": "success"}),
        MappingProxyType({"claim": "最終投資建議", "basis": "建議: 持有；12個月: NT$105", "status": "success"}),
    )

    result = evaluate_content_credibility(context, _base_snapshot(context, evidence_matrix=evidence_matrix))

    assert result["status"] == "passed"
    assert not any(issue["id"] == "missing_final_recommendation_evidence" for issue in result["warnings"])


def test_content_credibility_accepts_mapping_safe_context_and_snapshot():
    from reporting.content_credibility import evaluate_content_credibility

    context = _base_context(recommendation="買入", target_12m="NT$90")
    snapshot = _base_snapshot(context)

    result = evaluate_content_credibility(MappingProxyType(context), MappingProxyType(snapshot))

    assert result["status"] == "blocked"
    assert any(issue["id"] == "buy_target_below_current_price" for issue in result["blocking_issues"])


def test_content_credibility_recommendation_keys_and_values_use_safe_text_fallback():
    from reporting.content_credibility import evaluate_content_credibility

    class MalformedText:
        def __str__(self):
            raise RuntimeError("content credibility text unavailable")

    context = _base_context(recommendation="買入", target_12m="NT$130")
    context["parsed"]["recommendation"] = {
        MalformedText(): "ignored",
        "建議": "買入",
        "12個月": MalformedText(),
        "6個月": "NT$90",
        "信心": MalformedText(),
    }

    result = evaluate_content_credibility(context, _base_snapshot(context))

    assert result["status"] == "blocked"
    issue = next(issue for issue in result["blocking_issues"] if issue["id"] == "buy_target_below_current_price")
    assert issue["details"]["target_source"] == "recommendation.6個月"
    assert issue["details"]["target_price"] == 90.0


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
    assert bundle.data_snapshot["final_audit"]["status"] == "passed"
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
