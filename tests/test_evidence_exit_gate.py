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


def test_evidence_exit_gate_uses_eps_value_when_claim_starts_with_a_date():
    from evidence_exit_gate import extract_numeric_claims

    markdown = "- **Factset EPS 下修預警**：7 月底曾有機構將 EPS 下修至 26 元，目標價設於 234.5 TWD。"

    claims = extract_numeric_claims(markdown)

    assert claims == [
        {
            "id": 1,
            "label": "Factset EPS 下修預警",
            "reported_value": 26.0,
            "unit": "元",
            "line_number": 1,
            "raw_text": markdown,
        }
    ]


def test_evidence_claims_ignore_period_and_alphanumeric_identifier_numbers():
    from evidence_exit_gate import extract_numeric_claims

    markdown = (
        "- **事件摘要:** 目標價：109.0 TWD（52週高點壓力位）。"
        "近期催化劑：52U液冷機櫃；程式碼狀態：5a35737a。"
    )

    claims = extract_numeric_claims(markdown)

    assert any(claim["reported_value"] == 109.0 and claim["unit"] == "TWD" for claim in claims)
    assert not any(claim["reported_value"] in {5.0, 52.0} for claim in claims)


def test_evidence_gate_does_not_match_confidence_to_unrelated_snapshot_numbers():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = "- **估值風險:** 嚴重度：high；信心：0.85。"
    snapshot = {"data": {"dupont_identity_note": 0.891}}

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    claim = result["sampled_claims"][0]
    assert claim["label"] == "high；信心"
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""
    assert claim["matched_value"] is None
    assert result["failed_count"] == 0
    assert result["unverifiable_count"] == 1


def test_evidence_gate_does_not_compare_factset_claims_to_other_provider_values():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = """
- 研究摘要：目標價：234.5元（Factset預估值）。
- Factset EPS 下修預警: 26 元（機構下修值）。
"""
    snapshot = {
        "data": {
            "trailing_eps": 22.85,
            "quant_metrics": {"dcf_intrinsic_value": 156.45},
        },
        "rerun_context": {
            "structured_outputs": {
                "24": {"target_price": "265.0 TWD（突破 249.0 TWD）"},
            },
        },
    }

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    assert result["failed_count"] == 0
    assert result["unverifiable_count"] == 2
    assert all(item["status"] == "unverifiable" for item in result["sampled_claims"])


def test_evidence_gate_uses_canonical_value_for_structured_target_text():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = "- 目標價: 249.0 TWD"
    snapshot = {
        "rerun_context": {
            "structured_outputs": {
                "24": {"target_price": "265.0 TWD（突破 249.0 TWD）"},
            },
        },
    }

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    claim = result["sampled_claims"][0]
    assert claim["status"] == "mismatch"
    assert claim["matched_value"] == 265.0
    assert result["failed_count"] == 1


def test_evidence_gate_skips_horizon_prefix_in_structured_target_text():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = "- 目標價: 298.5 TWD"
    snapshot = {
        "rerun_context": {
            "structured_outputs": {
                "24": {"target_price": "52 週高點與心理壓力位 298.5 - 310.0 TWD"},
            },
        },
    }

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_value"] == 298.5


def test_evidence_claims_ignore_iso_timestamp_hour_tokens():
    from evidence_exit_gate import extract_numeric_claims

    markdown = (
        "- **市場資料時間:** 2026-08-20T13:13:09.248089+00:00\n"
        "| 來源 | 抓取時間 |\n"
        "| 市場資料 | 2026-08-20T07:32:43.231417+00:00 |"
    )

    claims = extract_numeric_claims(markdown)

    assert not any(claim["label"].startswith("T") for claim in claims)
    assert not any(claim["reported_value"] in {7.0, 13.0} for claim in claims)


def test_evidence_claims_do_not_treat_operating_margin_year_as_a_value():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims("- Operating Margin: 2022 (6.4%) -> 2025 (15.3%).")

    assert claims == []


def test_evidence_claims_ignore_dates_na_cells_and_range_prefixes():
    from evidence_exit_gate import extract_numeric_claims

    markdown = (
        "引用 `twse_margin_short_sales` 資料（資料日期：2026-08-20）：\n"
        "- **1-2週目標價:** 1-2週目標價看近期高點壓力位1950.0 TWD\n"
        "| 近期催化劑 | Free news waterfall | 成功 | N/A | N/A | 5 |"
    )

    claims = extract_numeric_claims(markdown)

    assert not any(claim["reported_value"] in {1.0, 5.0, 2026.0} for claim in claims)


def test_evidence_claims_ignore_calendar_date_tokens_after_labeled_colons():
    from evidence_exit_gate import extract_numeric_claims

    markdown = (
        "- 近期支撐: 2026/07/31 的低點 2306.32 TWD\n"
        "- 近期壓力位: 2026-06-30 收盤價 1010.0 TWD\n"
        "| 報告日期 | 2026.08.20 |"
    )

    claims = extract_numeric_claims(markdown)

    assert not any(claim["reported_value"] == 2026.0 for claim in claims)


def test_evidence_claims_keep_bare_years_and_currency_values():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims("- 財測年度: 2026\n- 股價: 2026 TWD")

    assert [claim["reported_value"] for claim in claims] == [2026.0, 2026.0]


def test_evidence_gate_matches_stop_loss_claims_to_structured_output():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **停損點：21.75 TWD**（有效跌破關鍵支撐位）",
        {
            "rerun_context": {
                "structured_outputs": {
                    "24": {"stop_loss": "21.75 TWD"},
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert result["sampled_claims"][0]["matched_path"] == "rerun_context.structured_outputs.24.stop_loss"


def test_evidence_gate_matches_chip_distribution_and_margin_claims():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = """
- Major holders (>1,000 lots): 56.95%.
- Retail holders (<50 lots): 20.33%.
- Margin Balance: 1,412.
- Short Balance: 183.
"""
    snapshot = {
        "data": {
            "chip_data": {
                "tdcc_shareholder_distribution": {
                    "major_holders_gt_1000_lots_pct": 56.95,
                    "retail_holders_lt_50_lots_pct": 20.33,
                },
                "twse_margin_short_sales": {
                    "margin_balance": 1412,
                    "short_balance": 183,
                },
            },
        },
    }

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0, min_sample=4)

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert all(item["status"] == "verified" for item in result["sampled_claims"])


def test_evidence_gate_keeps_k_suffix_with_canonical_thousand_unit():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Margin balance (2026-07-29): 5,290K, slightly down.",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {"margin_balance": 5290},
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert result["sampled_claims"][0]["reported_value"] == 5290.0
    assert result["sampled_claims"][0]["unit"] == "K"


def test_evidence_gate_matches_margin_flow_and_borrowed_short_balance():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = """
- Margin Purchase: 229 / Margin Sale: 327.
- Short Purchase: 67 / Short Sale: 15.
- Borrowed Short Sale Balance: 12,491,496 shares.
"""
    snapshot = {
        "data": {
            "chip_data": {
                "twse_margin_short_sales": {
                    "margin_purchase": 229,
                    "margin_sale": 327,
                    "short_purchase": 67,
                    "short_sale": 15,
                    "borrowed_short_sale_balance": 12491496,
                },
            },
        },
    }

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0, min_sample=5)

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert all(item["status"] == "verified" for item in result["sampled_claims"])


def test_evidence_gate_uses_specific_financial_field_hints_before_broad_labels():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = """
- Forward PE: 37.2535
- `forward_eps_implied_revenue_growth_pct`: 262.715%
- 淨利率: 26.0%
"""
    snapshot = {
        "data": {
            "pe_ratio": "126.6x",
            "net_income_ttm": 26.0,
            "profit_margin": "28.4%",
            "revenue_growth": "42.0%",
        },
    }

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    claims = {claim["label"]: claim for claim in result["sampled_claims"]}
    assert claims["Forward PE"]["status"] == "unverifiable"
    assert claims["epsimpliedrevenuegrowthpct"]["status"] == "unverifiable"
    assert claims["淨利率"]["status"] == "mismatch"
    assert claims["淨利率"]["matched_path"] == "data.profit_margin"


def test_evidence_gate_prefers_scenario_price_over_pe_text_in_table_rows():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = "| **熊市** | 專案延遲，P/E 降至 10x 以下 | NT$178 |"
    snapshot = {
        "data": {"pe_ratio_raw": 13.627188},
        "rerun_context": {"parsed": {"price_targets": {"bear": 178.0}}},
    }

    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "rerun_context.parsed.price_targets.bear"


def test_evidence_claims_ignore_ticker_identifier_followed_by_text():
    from evidence_exit_gate import extract_numeric_claims

    markdown = "一頁式摘要：1623.TW；催化劑為「1623股價和圖表 — TWSE:1623 - TradingView」。"

    claims = extract_numeric_claims(markdown)

    assert not any(claim["reported_value"] == 1623.0 for claim in claims)


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
