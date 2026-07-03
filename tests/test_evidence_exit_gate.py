def test_evidence_exit_gate_extracts_and_approves_snapshot_backed_numbers():
    from evidence_exit_gate import evaluate_report_evidence, extract_numeric_claims

    markdown = """
# 2330.TW 台積電

## 關鍵指標
- 股價: NT$100.00
- P/E: 20.0x

| 指標 | 數值 |
|---|---|
| 營收 | 12.0 |
"""
    snapshot = {
        "data": {
            "current_price": 100.0,
            "pe_ratio": "20.0x",
            "revenue_history": [10.0, 12.0],
        },
        "source_audit": [{"source": "market_data", "status": "success"}],
    }

    claims = extract_numeric_claims(markdown)
    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    assert len(claims) >= 3
    assert result["verdict"] == "approved"
    assert result["sampled_count"] >= 3
    assert result["failed_count"] == 0
    assert all(item["status"] == "verified" for item in result["sampled_claims"])


def test_evidence_exit_gate_rejects_when_sampled_numbers_are_not_in_snapshot():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = """
## 關鍵指標
- 股價: NT$100.00
- P/E: 99.0x
- 營收: 999.0
"""
    snapshot = {
        "data": {
            "current_price": 100.0,
            "pe_ratio": "20.0x",
            "revenue_history": [10.0, 12.0],
        },
        "source_audit": [{"source": "market_data", "status": "success"}],
    }

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    assert result["verdict"] == "rejected"
    assert result["failed_count"] == 2
    assert any(item["status"] == "mismatch" and item["reported_value"] == 999.0 for item in result["sampled_claims"])


def test_evidence_exit_gate_requires_label_relevance_for_numeric_matches():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = """
## 關鍵指標
- 股價: NT$20.0
"""
    snapshot = {
        "data": {
            "current_price": 100.0,
            "pe_ratio": "20.0x",
        },
        "source_audit": [{"source": "market_data", "status": "success"}],
    }

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    assert result["verdict"] == "rejected"
    assert result["failed_count"] == 1
    assert result["sampled_claims"][0]["status"] == "mismatch"
    assert result["sampled_claims"][0]["matched_path"] == "data.current_price"


def test_report_renderer_attaches_evidence_exit_gate_to_snapshot_and_metadata(monkeypatch):
    import asyncio
    import reporting.renderer as renderer_module
    from reporting import ReportRenderer, ReportRequest

    async def fake_html(context):
        return fake_html_sync(context)

    def fake_html_sync(context):
        gate = context.get("evidence_exit_gate") or {}
        gate_line = f"<p>Evidence gate：{gate.get('verdict')}</p>" if gate else ""
        return f"<html><body><p>股價: NT$100.00</p><p>P/E: 20.0x</p><p>營收: 12.0</p>{gate_line}</body></html>"

    def fake_markdown(context):
        gate = context.get("evidence_exit_gate") or {}
        gate_line = f"\n- **Evidence gate:** {gate.get('verdict')}\n" if gate else ""
        return f"# 報告\n\n- 股價: NT$100.00\n- P/E: 20.0x\n- 營收: 12.0\n{gate_line}"

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
                    },
                },
                pipeline_id="v1",
                filename="2330_TW_v1_report_20260628_000000.html",
            )
        )
    )

    assert bundle.metadata["evidence_exit_gate"]["verdict"] == "approved"
    assert bundle.data_snapshot["evidence_exit_gate"]["verdict"] == "approved"
    assert "Evidence gate：approved" in bundle.html
    assert "**Evidence gate:** approved" in bundle.markdown
