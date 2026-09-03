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
    assert all(item["verification_reason_code"] == "matched_snapshot_value" for item in result["sampled_claims"])
    assert all(item["candidate_count"] >= 1 for item in result["sampled_claims"])


def test_evidence_gate_reports_verified_sample_count():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 股價: NT$100.0\n- 未知評分: 0.85",
        {"data": {"current_price": 100.0, "other_value": 0.85}},
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verified_count"] == 1
    assert result["unverifiable_count"] == 1


def test_evidence_projection_exposes_stale_analysis_context_without_changing_verdict():
    from reporting.evidence_exit_gate_projection import project_evidence_exit_gate

    result = project_evidence_exit_gate(
        {
            "data": {"current_price": 100.0},
            "conclusion_generated_at": "2026-08-20T13:14:01+00:00",
            "snapshot_refreshed_at": "2026-08-21T07:59:30+00:00",
            "decision_validity_status": "needs_rerun",
            "refreshed_without_analysis_rerun": True,
            "requires_rerun_reason": "資料快照已刷新，但分析本文尚未重跑。",
        },
        "- 股價: NT$99.00",
    )

    assert result["verdict"] == "rejected"
    assert result["failed_count"] == 1
    assert result["freshness_context"] == {
        "status": "needs_rerun",
        "requires_rerun": True,
        "conclusion_generated_at": "2026-08-20T13:14:01+00:00",
        "snapshot_refreshed_at": "2026-08-21T07:59:30+00:00",
        "requires_rerun_reason": "資料快照已刷新，但分析本文尚未重跑。",
    }


def test_evidence_claim_preserves_numeric_horizon_in_label():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "- **3個月目標:** NT$4127\n- **6個月目標:** NT$3641"
    )

    assert [claim["label"] for claim in claims] == ["3個月目標", "6個月目標"]


def test_evidence_claim_preserves_horizon_in_compact_recommendation_row():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "| 最終投資建議 | 建議: 避免；3個月: NT$4127；6個月: NT$3641；12個月: NT$3156；信心: 5/10 |"
    )

    assert [claim["label"] for claim in claims] == [
        "避免；3個月",
        "6個月",
        "12個月",
        "信心",
    ]


def test_evidence_gate_explains_confidence_metadata_boundary():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **資料信心分數:** 91/100",
        {"data": {"data_confidence_score": 91}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "confidence_metadata_not_evidence"
    assert result["unverifiable_reason_counts"] == {"confidence_metadata_not_evidence": 1}


def test_evidence_gate_explains_analysis_score_metadata_boundary():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 品牌影響力: 3.0\n- FOMO 評分: 4.0",
        {"data": {}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["unverifiable_count"] == 2
    assert all(
        claim["verification_reason_code"] == "analysis_metadata_not_evidence"
        for claim in result["sampled_claims"]
    )
    assert result["unverifiable_reason_counts"] == {"analysis_metadata_not_evidence": 2}


def test_evidence_gate_accepts_markdown_emphasis_between_label_and_value():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        """
- **股價:** NT$100.00
- **P/E:** 20.0x
- **淨利率:** 25.0%
""",
        {
            "data": {
                "current_price": 100.0,
                "pe_ratio": "20.0x",
                "profit_margin": "25.0%",
            },
        },
        sample_ratio=1.0,
        min_sample=3,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert all(item["status"] == "verified" for item in result["sampled_claims"])
    assert all(claim["status"] == "verified" for claim in result["sampled_claims"])


def test_evidence_gate_preserves_thousands_before_parenthetical_note():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "- Margin Purchase: 3,768 / Margin Sale: 2,771. (Net increase in margin)."
    )

    assert [(claim["label"], claim["reported_value"]) for claim in claims] == [
        ("Margin Purchase", 3768.0),
        ("Margin Sale", 2771.0),
    ]


def test_evidence_gate_keeps_markdown_emphasis_mismatch_visible():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **股價:** NT$99.00",
        {"data": {"current_price": 100.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "rejected"
    assert result["failed_count"] == 1
    assert result["sampled_claims"][0]["status"] == "mismatch"


def test_evidence_gate_matches_common_valuation_snapshot_fields():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        """
- **P/B:** 21.23x
- **ROE:** 66.8%
- **Beta:** 0.65
""",
        {
            "data": {
                "pb_ratio": "21.23x",
                "roe": "66.8%",
                "beta": 0.65,
            },
        },
        sample_ratio=1.0,
        min_sample=3,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert [item["matched_path"] for item in result["sampled_claims"]] == [
        "data.pb_ratio",
        "data.roe",
        "data.beta",
    ]


def test_evidence_gate_matches_exact_price_sales_aliases():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- PS: 1.07\n- P/S: 1.07\n- Price/Sales: 1.07",
        {"data": {"ps_ratio": 1.07}},
        sample_ratio=1.0,
        min_sample=3,
    )

    assert result["verdict"] == "approved"
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.ps_ratio",
        "data.ps_ratio",
        "data.ps_ratio",
    ]


def test_evidence_gate_matches_us_cpi_yoy_macro_indicator():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **US CPI YoY:** 3.3039% (2026-07-01).",
        {
            "data": {
                "macro_indicators": {
                    "indicators": {
                        "us_cpi_yoy": {"value": 3.3039},
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["verification_reason_code"] == "matched_snapshot_value"
    assert claim["matched_path"] == "data.macro_indicators.indicators.us_cpi_yoy.value"


def test_evidence_gate_matches_exact_price_label_to_current_price():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- *Price:* 209.0 TWD.",
        {"data": {"current_price": 209.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.current_price"


def test_evidence_gate_does_not_map_price_target_to_current_price():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- *Price Target:* 209.0 TWD.",
        {"data": {"current_price": 209.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "missing_semantic_path"
    assert claim["matched_path"] == ""


def test_evidence_gate_keeps_ps_mismatch_on_ps_path_and_eps_on_eps_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- PS: 31.18\n- EPS: 2.50",
        {"data": {"ps_ratio": 34.65, "eps": 2.50}},
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "rejected"
    assert [claim["status"] for claim in result["sampled_claims"]] == ["mismatch", "verified"]
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.ps_ratio",
        "data.eps",
    ]


def test_evidence_gate_matches_profitability_and_yield_snapshot_fields():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **毛利率:** 28.9%\n- **殖利率:** 0.58%",
        {
            "data": {
                "gross_margin": "28.9%",
                "dividend_yield": "0.58%",
            },
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert [item["matched_path"] for item in result["sampled_claims"]] == [
        "data.gross_margin",
        "data.dividend_yield",
    ]


def test_evidence_gate_ignores_month_day_prefix_before_margin_balance():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **融資餘額變化:** 8/19；**融資餘額:** 2,752 張。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "margin_previous_balance": 2639,
                        "margin_balance": 2752,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_count"] == 1
    assert result["sampled_claims"][0]["reported_value"] == 2752.0
    assert result["sampled_claims"][0]["matched_path"] == (
        "data.chip_data.twse_margin_short_sales.margin_balance"
    )


def test_sample_numeric_claims_prioritizes_explicit_valuation_fields():
    from evidence_exit_gate import sample_numeric_claims

    claims = [
        {"id": index, "label": "一般敘述", "reported_value": float(index), "line_number": index, "raw_text": f"一般敘述: {index}"}
        for index in range(1, 31)
    ] + [
        {"id": 100, "label": "PE TTM", "reported_value": 135.1239, "line_number": 100, "raw_text": "PE TTM: 135.1239"},
        {"id": 101, "label": "Forward PE", "reported_value": 37.2535, "line_number": 101, "raw_text": "Forward PE: 37.2535"},
    ]

    sampled = sample_numeric_claims(claims, sample_ratio=0.0, min_sample=2, max_sample=2)

    assert [item["id"] for item in sampled] == [100, 101]


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
    assert all(
        item["verification_reason_code"] == "snapshot_value_mismatch"
        for item in result["sampled_claims"]
        if item["status"] == "mismatch"
    )
    assert result["unverifiable_reason_counts"] == {}


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


def test_evidence_claims_ignore_derived_trade_plan_health_score():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims("- **交易計畫健康度:** 6/10")

    assert claims == []


def test_evidence_claims_ignore_catalyst_group_period_tokens():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "- Recent catalysts: 5-day jump of 32.16% (around 07-08), but revenue fell 84.05%.\n"
        "- 近期催化劑：5 日漲幅 33.87%，事件日期為 2026-06-25。"
    )

    assert claims == []


def test_evidence_claims_ignore_institutional_trading_lookback_metadata():
    from evidence_exit_gate import extract_numeric_claims

    assert extract_numeric_claims(
        "*   `institutional_trading`: 30-day lookback, latest date 2026-08-20."
    ) == []
    actual_value = extract_numeric_claims("- `institutional_trading`: 30.0k")
    assert actual_value[0]["reported_value"] == 30.0


def test_evidence_claims_ignore_provider_error_codes_and_duration_tokens():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "- deterministic fallback（模型修復暫不可用：429）\n"
        "- **Bear Case:** 30-day cumulative net selling remains elevated.\n"
        "- target price: 429 TWD"
    )

    assert [(claim["label"], claim["reported_value"]) for claim in claims] == [("target price", 429.0)]


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
    assert claim["verification_reason_code"] == "confidence_metadata_not_evidence"
    assert claim["candidate_count"] == 0
    assert result["unverifiable_reason_counts"] == {"confidence_metadata_not_evidence": 1}


def test_evidence_gate_does_not_bind_news_support_or_pressure_to_risk_price():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 近期壓力: 55.8 TWD（根據 `market_catalysts` 新聞）\n"
        "- 近期支撐: 31.75 TWD（參考 `recent_catalysts` 提及價位）",
        {"data": {"risk_price": 55.8, "price_history": {"dates": ["2026-07-30"], "prices": [31.75]}}},
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "caution"
    assert result["unverifiable_count"] == 2
    assert all(claim["status"] == "unverifiable" for claim in result["sampled_claims"])
    assert all(claim["verification_reason_code"] == "news_source_not_canonical" for claim in result["sampled_claims"])


def test_evidence_gate_classifies_intraday_bulletin_support_as_news_source():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 近期支撐：227.0 TWD（參考 2026/07/22 盤中速報大漲點位）。",
        {"data": {"current_price": 282.0, "target_price_candidates": [306.0, 227.0], "risk_price": 227.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "news_source_not_canonical"
    assert claim["matched_path"] == ""
    assert claim["candidate_count"] == 0


def test_evidence_gate_reports_missing_semantic_path_for_unknown_numeric_labels():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence("- 未知評分: 0.85", {"data": {"other_value": 0.85}}, sample_ratio=1.0)

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "missing_semantic_path"
    assert result["unverifiable_reason_counts"] == {"missing_semantic_path": 1}


def test_evidence_gate_maps_composite_52_week_high_low_to_distinct_snapshot_fields():
    from evidence_exit_gate import evaluate_report_evidence, extract_numeric_claims

    markdown = "- 52 週高低：28.95 / 6.25 (market_data)"
    snapshot = {"data": {"week_52_high": 28.95, "week_52_low": 6.25}}

    claims = extract_numeric_claims(markdown)
    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0, min_sample=2)

    assert [claim["reported_value"] for claim in claims] == [28.95, 6.25]
    assert result["verdict"] == "approved"
    assert [item["matched_path"] for item in result["sampled_claims"]] == [
        "data.week_52_high",
        "data.week_52_low",
    ]
    assert all(item["status"] == "verified" for item in result["sampled_claims"])


def test_evidence_gate_does_not_infer_week_52_fields_from_generic_high_low_pair():
    from evidence_exit_gate import evaluate_report_evidence, extract_numeric_claims

    markdown = "- 高低：28.95 / 6.25"
    snapshot = {"data": {"week_52_high": 28.95, "week_52_low": 6.25}}

    claims = extract_numeric_claims(markdown)
    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0)

    assert [claim["reported_value"] for claim in claims] == [28.95]
    assert result["verdict"] == "caution"
    assert result["sampled_claims"][0]["verification_reason_code"] == "missing_semantic_path"


def test_evidence_claims_do_not_split_slash_price_pairs_for_other_labels():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims("- 支撐：31.75 TWD / 22.95 TWD (market_data)")

    assert [claim["reported_value"] for claim in claims] == [31.75]


def test_evidence_gate_keeps_composite_52_week_low_mismatch_on_low_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 52 週高低：28.95 / 7.25 (market_data)",
        {"data": {"week_52_high": 28.95, "week_52_low": 6.25}},
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "rejected"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][1]["status"] == "mismatch"
    assert result["sampled_claims"][1]["matched_path"] == "data.week_52_low"


def test_evidence_gate_explains_legacy_conclusion_without_persisted_snapshot_context():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 長期目標（12個月）: NT$2255",
        {"data": {"current_price": 100}, "rerun_context": {"parsed": {}, "structured_outputs": {}}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "caution"
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "legacy_conclusion_without_snapshot_path"
    assert "_legacy_conclusion_context_missing" not in claim
    assert result["unverifiable_reason_counts"] == {"legacy_conclusion_without_snapshot_path": 1}


def test_evidence_gate_classifies_compact_legacy_recommendation_horizons():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "| 最終投資建議 | 建議: 避免；3個月: NT$4127；6個月: NT$3641；12個月: NT$3156；信心: 5/10 |",
        {"data": {"current_price": 100}, "rerun_context": {"parsed": {}, "structured_outputs": {}}},
        sample_ratio=1.0,
    )

    reasons = {claim["label"]: claim["verification_reason_code"] for claim in result["sampled_claims"]}
    assert reasons["避免；3個月"] == "legacy_conclusion_without_snapshot_path"
    assert reasons["6個月"] == "legacy_conclusion_without_snapshot_path"
    assert reasons["12個月"] == "legacy_conclusion_without_snapshot_path"
    assert reasons["信心"] == "confidence_metadata_not_evidence"
    assert result["verdict"] == "caution"


def test_evidence_gate_classifies_currency_prefixed_legacy_horizons():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "| 最終投資建議 | 建議: 持有；3個月: NT$174.5 - NT$209.0；6個月: NT$209.0 - NT$254.0；12個月: NT$254.0 - NT$327.0；信心: 6/10 |",
        {"rerun_context": {"parsed": {}, "structured_outputs": {}}},
        sample_ratio=1.0,
        min_sample=2,
    )

    reasons = {claim["label"]: claim["verification_reason_code"] for claim in result["sampled_claims"]}
    assert reasons["NT$209.0；6個月"] == "legacy_conclusion_without_snapshot_path"
    assert reasons["NT$254.0；12個月"] == "legacy_conclusion_without_snapshot_path"


def test_evidence_gate_classifies_derived_downside_without_canonical_scalar():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 潛在下行空間：-16.5%",
        {"data": {"current_price": 100, "target_price": 83.5}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "derived_metric_not_canonical"
    assert claim["matched_path"] == ""
    assert result["unverifiable_reason_counts"] == {"derived_metric_not_canonical": 1}


def test_evidence_gate_preserves_canonical_downside_mapping():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 潛在下行空間：-16.5%",
        {"data": {"downside_pct": -16.5}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["verification_reason_code"] == "matched_snapshot_value"
    assert claim["matched_path"] == "data.downside_pct"


def test_evidence_gate_classifies_stop_loss_without_canonical_risk_control():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 防軋空停損點 (Stop-loss level)：1120 TWD",
        {"data": {"current_price": 1000}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "risk_control_not_canonical"
    assert claim["matched_path"] == ""


def test_evidence_gate_preserves_canonical_stop_loss_mapping():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 價格停損條件：NT$1120",
        {"data": {"risk_price": 1120}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["verification_reason_code"] == "matched_snapshot_value"
    assert claim["matched_path"] == "data.risk_price"


def test_evidence_gate_classifies_narrative_technical_levels_without_canonical_scalar():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 心理關卡：300 TWD\n- 第二支撐：13 TWD\n- 關鍵支撐區：502 TWD",
        {"data": {"current_price": 100}, "content_credibility": {"checks": {"target_price": 300}}},
        sample_ratio=1.0,
    )

    claims = result["sampled_claims"]
    assert {claim["label"] for claim in claims} == {"心理關卡", "第二支撐", "關鍵支撐區"}
    assert {claim["status"] for claim in claims} == {"unverifiable"}
    assert {claim["verification_reason_code"] for claim in claims} == {"technical_level_not_canonical"}
    assert {claim["matched_path"] for claim in claims} == {""}


def test_evidence_gate_preserves_canonical_technical_level_mapping():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 心理關卡：300 TWD",
        {"data": {"risk_price": 300}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["verification_reason_code"] == "matched_snapshot_value"
    assert claim["matched_path"] == "data.risk_price"


def test_evidence_gate_classifies_generic_support_levels_without_canonical_scalar():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 近期支撐：179.5 TWD（前述區間上緣）\n- 支撐位：100.5 元（近期技術支撐位）",
        {"data": {"current_price": 100}},
        sample_ratio=1.0,
    )

    assert {claim["verification_reason_code"] for claim in result["sampled_claims"]} == {"technical_level_not_canonical"}
    assert {claim["matched_path"] for claim in result["sampled_claims"]} == {""}


def test_evidence_gate_classifies_explicit_agent_score_context_as_analysis_metadata():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 多頭護城河說明（Agent 3 評分：6）",
        {"data": {"current_price": 100}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "analysis_metadata_not_evidence"
    assert claim["matched_path"] == ""


def test_evidence_gate_keeps_long_agent_score_label_context_after_raw_text_truncation():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- " + "長敘述優勢" * 30 + "（Agent 3 評分：6）",
        {"data": {"current_price": 100}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["verification_reason_code"] == "analysis_metadata_not_evidence"
    assert claim["status"] == "unverifiable"


def test_evidence_gate_classifies_unbacked_scenario_table_target():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "| **熊市** | 專案交付持續遞延，營運資金積壓 | NT$178 |",
        {"data": {"current_price": 100}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "scenario_target_not_canonical"
    assert claim["matched_path"] == ""


def test_evidence_gate_classifies_unbacked_scenario_projection_revenue():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "## 五、成長情境預測（5年）\n"
        "| 情境 | 核心假設 | 5年後年營收 (2030) | CAGR |\n"
        "| :--- | :--- | ---: | ---: |\n"
        "| **保守** | AI 需求放緩 | NT$357 億 | 12% |\n"
        "| **樂觀** | 液冷全面導入 | NT$697 億 | 28% |",
        {"data": {"current_price": 100}},
        sample_ratio=1.0,
    )

    claims = result["sampled_claims"]
    assert {claim["reported_value"] for claim in claims} == {357.0, 697.0}
    assert {claim["status"] for claim in claims} == {"unverifiable"}
    assert {claim["verification_reason_code"] for claim in claims} == {"analysis_metadata_not_evidence"}
    assert {claim["matched_path"] for claim in claims} == {""}


def test_evidence_gate_classifies_scenario_targets_without_canonical_scalar():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 熊市情境：80 TWD\n- 基本情境：100 TWD\n- 牛市情境：120 TWD\n- 熊/基/牛情境：100 TWD",
        {"data": {"current_price": 100}, "content_credibility": {"checks": {"target_price": 100}}},
        sample_ratio=1.0,
    )

    claims = result["sampled_claims"]
    assert len(claims) == 4
    assert {claim["label"] for claim in claims} == {"熊市情境", "基本情境", "牛市情境", "熊/基/牛情境"}
    assert {claim["status"] for claim in claims} == {"unverifiable"}
    assert {claim["verification_reason_code"] for claim in claims} == {"scenario_target_not_canonical"}
    assert {claim["matched_path"] for claim in claims} == {""}
    assert result["unverifiable_reason_counts"] == {"scenario_target_not_canonical": 4}


def test_evidence_gate_preserves_canonical_scenario_target_mapping():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 基本情境：100 TWD",
        {"data": {"price_targets": {"基本情境": 100}}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["verification_reason_code"] == "matched_snapshot_value"
    assert claim["matched_path"] == "data.price_targets.基本情境"


def test_evidence_gate_keeps_compact_horizons_as_missing_when_context_exists():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "| 最終投資建議 | 建議: 避免；3個月: NT$4127；6個月: NT$3641；12個月: NT$3156；信心: 5/10 |",
        {"data": {"current_price": 100}, "rerun_context": {"parsed": {"recommendation": {}}, "structured_outputs": {}}},
        sample_ratio=1.0,
    )

    reasons = {claim["label"]: claim["verification_reason_code"] for claim in result["sampled_claims"]}
    assert reasons["避免；3個月"] == "missing_semantic_path"
    assert reasons["6個月"] == "missing_semantic_path"
    assert reasons["12個月"] == "missing_semantic_path"


def test_evidence_gate_does_not_classify_non_recommendation_horizon_as_legacy():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 近6個月營收增幅: 12%",
        {"data": {"current_price": 100}, "rerun_context": {"parsed": {}, "structured_outputs": {}}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["verification_reason_code"] != "legacy_conclusion_without_snapshot_path"


def test_evidence_gate_keeps_conclusion_without_mapping_as_missing_semantic_path_when_context_exists():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 長期目標（12個月）: NT$2255",
        {"data": {"current_price": 100}, "rerun_context": {"parsed": {"recommendation": {}}, "structured_outputs": {}}},
        sample_ratio=1.0,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "missing_semantic_path"


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
    assert all(item["verification_reason_code"] == "research_source_not_canonical" for item in result["sampled_claims"])
    assert result["unverifiable_reason_counts"] == {"research_source_not_canonical": 2}


def test_evidence_gate_classifies_market_research_target_as_non_canonical():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "研究分類：金融租賃服務。目標價：130元（參考市場研究觀點）。",
        {"data": {"current_price": 130.0, "target_price": 130.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "caution"
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "research_source_not_canonical"
    assert claim["matched_path"] == ""


def test_evidence_gate_does_not_bind_descriptive_target_label_to_dcf_value():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "研究分類：航空運輸業，目標價：43.75元。",
        {"data": {"quant_metrics": {"dcf_scenarios": {"bear": {"intrinsic_value": 32.04}}}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["label"] == "航空運輸業，目標價"
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"


def test_evidence_gate_binds_descriptive_target_label_to_structured_target_only():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "研究分類：航空運輸業，目標價：43.75元。",
        {
            "data": {"quant_metrics": {"dcf_scenarios": {"bear": {"intrinsic_value": 32.04}}}},
            "rerun_context": {
                "structured_outputs": {
                    "24": {"target_price": "近 1-2 週壓力位 43.75 元至 52 週高點 45.65 元"},
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "rerun_context.structured_outputs.24.target_price"
    assert claim["matched_value"] == 43.75


def test_evidence_gate_matches_pe_river_chart_multiple_to_canonical_snapshot_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **PE River Chart (5-year quantiles):** 32.5x, 46.6x, 64.3x, 76.9x",
        {"data": {"pe_river_chart": {"multiples": [32.5, 46.6, 64.3, 76.9]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.pe_river_chart.multiples[0]"


def test_evidence_gate_does_not_match_pe_river_chart_to_generic_pe_snapshot_value():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **PE River Chart (5-year quantiles):** 32.5x",
        {"data": {"pe_ratio": 32.5}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"


def test_evidence_gate_matches_operating_cash_flow_to_dedicated_snapshot_field():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Operating Cash Flow: -0.1898B.",
        {
            "data": {
                "operating_cash_flow": "NT$-1.90億 (-0.19B)",
                "free_cash_flow": "NT$-1.40億 (-0.14B)",
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )
    claim = result["sampled_claims"][0]

    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.operating_cash_flow"


def test_evidence_gate_does_not_match_operating_cash_flow_to_free_cash_flow():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Operating Cash Flow: -0.1898B.",
        {"data": {"free_cash_flow": "NT$-1.90億 (-0.19B)"}},
        sample_ratio=1.0,
        min_sample=1,
    )
    claim = result["sampled_claims"][0]

    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"


def test_evidence_gate_matches_pe_river_band_to_its_multiple_specific_snapshot_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 43.2x (中高分位帶)：29.38 TWD",
        {
            "data": {
                "pe_river_chart": {
                    "bands": {"43.2x": [None, 10.96, -9.07, 42.52, 29.38]},
                    "multiples": [18.9, 33.9, 43.2, 67.1],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )
    claim = result["sampled_claims"][0]

    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.pe_river_chart.bands.43.2x[4]"


def test_evidence_gate_matches_historical_high_percentile_band_to_specific_snapshot_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 67.1x (歷史高分位帶)：45.63 TWD",
        {
            "data": {
                "pe_ratio": 45.63,
                "pe_river_chart": {
                    "bands": {"67.1x": [None, 12.0, 24.0, 36.0, 45.63]},
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.pe_river_chart.bands.67.1x[4]"


def test_evidence_gate_does_not_match_historical_high_percentile_band_to_generic_pe():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 67.1x (歷史高分位帶)：45.63 TWD",
        {"data": {"pe_ratio": 45.63}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "caution"
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"


def test_evidence_gate_does_not_match_pe_river_band_to_multiples_or_generic_pe():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 43.2x (中高分位帶)：29.38 TWD",
        {"data": {"pe_river_chart": {"multiples": [29.38]}, "pe_ratio": 29.38}},
        sample_ratio=1.0,
        min_sample=1,
    )
    claim = result["sampled_claims"][0]

    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"


def test_evidence_gate_matches_river_chart_band_price_to_band_values():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **P/E 河流圖 2025 年最高位階（59.6x 區間）：** 1,379.14 TWD",
        {
            "data": {
                "pe_ratio": 1379.14,
                "pe_river_chart": {
                    "bands": {"59.8x": [752.28, 768.43, 810.89, 1383.77]},
                },
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )
    claim = result["sampled_claims"][0]

    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.pe_river_chart.bands.59.8x[3]"


def test_evidence_gate_does_not_match_river_chart_band_price_to_generic_pe():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **P/E 河流圖 2025 年最高位階（59.6x 區間）：** 1,379.14 TWD",
        {"data": {"pe_ratio": 1379.14}},
        sample_ratio=1.0,
        min_sample=1,
    )
    claim = result["sampled_claims"][0]

    assert result["verdict"] == "caution"
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"


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


def test_evidence_claims_ignore_plain_clock_minutes_in_cutoff_metadata():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims("* market_data (截至 2026-08-19 07:50)")

    assert claims == []


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


def test_evidence_claims_ignore_numeric_currency_table_cells_as_labels():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "| 情境 | 說明 | 營收規模 | 成長率 |\n"
        "|---|---|---|---|\n"
        "| **基本** | AI 伺服器維持穩定增長，液冷冷板滲透率達 30%，車用業務穩健。 | NT$464 億 | 18% |"
    )

    assert not any(claim["label"] == "NT$464 億" for claim in claims)
    value_cell_claims = extract_numeric_claims("| 營收 | NT$464 億 |")
    assert value_cell_claims == [
        {
            "id": 1,
            "label": "營收",
            "reported_value": 464.0,
            "unit": "億",
            "line_number": 1,
            "raw_text": "| 營收 | NT$464 億 |",
        }
    ]


def test_evidence_claims_ignore_month_day_range_after_labeled_colon():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "- 法人加速卡位: 08/17 - 08/18 兩日內，法人合計掃貨逾 3 萬張。"
    )

    assert claims == []


def test_evidence_claims_ignore_month_day_followed_immediately_by_chinese_text():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "- 核心催化劑: 08/17法說會後外資連續5日大幅買超。"
    )

    assert claims == []


def test_evidence_claims_do_not_treat_daily_trend_dates_as_scalar_values():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "- 近 10 日每日趨勢：7/21 (-1115), 7/22 (-3339.73), 7/23 (679.58), 7/24 (-1899.03)。"
    )

    assert claims == []


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


def test_evidence_gate_matches_symbol_specific_global_market_context_change():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 國際風險（QQQ, change_5d_pct: -2.18%）",
        {
            "data": {
                "global_market_context": {
                    "items": [
                        {"symbol": "SPY", "change_5d_pct": -1.13},
                        {"symbol": "QQQ", "change_5d_pct": -2.1842},
                    ],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.global_market_context.items[qqq].change_5d_pct"


def test_evidence_gate_does_not_cross_match_global_market_symbols():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 國際風險（QQQ, change_5d_pct: -2.18%）",
        {
            "data": {
                "global_market_context": {
                    "items": [
                        {"symbol": "SPY", "change_5d_pct": -2.1842},
                        {"symbol": "QQQ", "change_5d_pct": -1.13},
                    ],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "mismatch"
    assert claim["matched_path"] == "data.global_market_context.items[qqq].change_5d_pct"


def test_evidence_gate_matches_indexed_global_market_change_paths_by_symbol():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- VanEck Semiconductor ETF (SMH) (`global_market_context[11].change_1d_pct`: -2.2808%, `global_market_context[11].change_5d_pct`: -1.0943%).",
        {
            "data": {
                "global_market_context": {
                    "items": [{"symbol": "SMH", "change_1d_pct": -2.2808, "change_5d_pct": -1.0943}],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert [claim["status"] for claim in result["sampled_claims"]] == ["verified", "verified"]
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.global_market_context.items[smh].change_1d_pct",
        "data.global_market_context.items[smh].change_5d_pct",
    ]


def test_evidence_gate_does_not_cross_match_indexed_change_to_other_symbol():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- VanEck Semiconductor ETF (SMH) (`global_market_context[11].change_1d_pct`: -2.2808%).",
        {"data": {"global_market_context": {"items": [{"symbol": "QQQ", "change_1d_pct": -2.2808}]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"
    assert claim["matched_path"] == ""


def test_evidence_gate_matches_s_and_p_500_narrative_change_to_spy():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 國際金融環境：S&P 500 與台股加權指數近期震盪（Change 1d: -1.03% ~ -1.09%）。",
        {
            "data": {
                "global_market_context": {
                    "items": [
                        {"symbol": "SPY", "change_1d_pct": -1.0331},
                        {"symbol": "^TWII", "change_1d_pct": -1.0965},
                    ]
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.global_market_context.items[spy].change_1d_pct"


def test_evidence_gate_does_not_cross_match_s_and_p_500_change_to_taiwan_index():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 國際金融環境：S&P 500 與台股加權指數近期震盪（Change 1d: -1.03%）。",
        {
            "data": {
                "global_market_context": {
                    "items": [{"symbol": "^TWII", "change_1d_pct": -1.03}]
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"
    assert claim["matched_path"] == ""


def test_evidence_gate_matches_named_global_market_latest_values():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        """
- Taiwan Weighted Index: 44933.7383.
- USD/TWD: 31.855.
- WTI Crude Oil: 85.7.
""",
        {
            "data": {
                "global_market_context": {
                    "items": [
                        {"symbol": "^TWII", "latest": 44933.7383},
                        {"symbol": "TWD=X", "latest": 31.855},
                        {"symbol": "CL=F", "latest": 85.7},
                    ],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=3,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.global_market_context.items[twii].latest",
        "data.global_market_context.items[twdx].latest",
        "data.global_market_context.items[clf].latest",
    ]


def test_evidence_gate_matches_us10y_and_vix_global_market_aliases():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- US 10Y Yield: 4.696%\n- US 10Y Treasury Yield: 4.696%\n- VIX: 15.77",
        {
            "data": {
                "global_market_context": {
                    "items": [
                        {"symbol": "^TNX", "latest": 4.696},
                        {"symbol": "^VIX", "latest": 15.77},
                    ],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=3,
    )

    assert result["verdict"] == "approved"
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.global_market_context.items[tnx].latest",
        "data.global_market_context.items[tnx].latest",
        "data.global_market_context.items[vix].latest",
    ]


def test_evidence_gate_keeps_us10y_and_vix_paths_from_cross_matching():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- US 10Y Yield: 15.77%\n- VIX: 4.696",
        {
            "data": {
                "global_market_context": {
                    "items": [
                        {"symbol": "^TNX", "latest": 4.696},
                        {"symbol": "^VIX", "latest": 15.77},
                    ],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "rejected"
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.global_market_context.items[tnx].latest",
        "data.global_market_context.items[vix].latest",
    ]
    assert all(claim["status"] == "mismatch" for claim in result["sampled_claims"])


def test_evidence_gate_keeps_us_cpi_unverifiable_without_canonical_macro_node():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- US CPI YoY: 3.3039%",
        {"data": {"global_market_context": {"items": [{"symbol": "^TNX", "latest": 3.3039}]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "caution"
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"


def test_evidence_gate_keeps_named_global_market_latest_mismatch_visible():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Taiwan Weighted Index: 45811.0117.",
        {
            "data": {
                "global_market_context": {
                    "items": [
                        {"symbol": "^TWII", "latest": 44933.7383},
                        {"symbol": "EWT", "latest": 45811.0117},
                    ],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "mismatch"
    assert claim["matched_path"] == "data.global_market_context.items[twii].latest"


def test_evidence_gate_does_not_promote_bare_global_market_alias():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- WTI: 85.7.",
        {
            "data": {
                "global_market_context": {
                    "items": [{"symbol": "CL=F", "latest": 85.7}],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""


def test_evidence_gate_matches_explicit_tdcc_concentration_labels():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        """
- Concentration: 72.78% (>1000 lots).
- Retail: 14.85% (<50 lots).
""",
        {
            "data": {
                "chip_data": {
                    "tdcc_shareholder_distribution": {
                        "major_holders_gt_1000_lots_pct": 72.78,
                        "retail_holders_lt_50_lots_pct": 14.85,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert [item["matched_path"] for item in result["sampled_claims"]] == [
        "data.chip_data.tdcc_shareholder_distribution.major_holders_gt_1000_lots_pct",
        "data.chip_data.tdcc_shareholder_distribution.retail_holders_lt_50_lots_pct",
    ]


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


def test_evidence_gate_classifies_explicitly_unavailable_short_balance():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Short Balance: 0 (or null/not provided as a significant number).",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "short_balance": None,
                    }
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "snapshot_field_unavailable"
    assert claim["candidate_count"] == 0
    assert result["unverifiable_reason_counts"] == {"snapshot_field_unavailable": 1}


def test_evidence_gate_preserves_comma_grouped_integer_before_sentence_punctuation():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Borrowed short return today: 1,177,000. Borrowed short sale today: 21,000.",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "borrowed_short_return_today": 1177000,
                        "borrowed_short_sale_today": 21000,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert result["failed_count"] == 0
    assert [claim["reported_value"] for claim in result["sampled_claims"]] == [1177000.0, 21000.0]


def test_evidence_gate_matches_reordered_borrowed_short_return_label():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Today's borrowed short return: 525,000.",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "borrowed_short_return_today": 525000,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.chip_data.twse_margin_short_sales.borrowed_short_return_today"


def test_evidence_gate_matches_exact_chinese_borrowed_short_aliases():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 借券餘額：286000 張。\n- 當日借券賣出：40000 張。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "borrowed_short_sale_balance": 286000,
                        "borrowed_short_sale_today": 40000,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert all(claim["status"] == "verified" for claim in result["sampled_claims"])
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.chip_data.twse_margin_short_sales.borrowed_short_sale_balance",
        "data.chip_data.twse_margin_short_sales.borrowed_short_sale_today",
    ]


def test_evidence_gate_matches_compact_return_after_borrowed_short_sale():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Today's borrowed short sale: 4,199,000; return: 2,844,160.",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "borrowed_short_sale_today": 4199000,
                        "borrowed_short_return_today": 2844160,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    claims = result["sampled_claims"]
    assert result["verdict"] == "approved"
    assert all(claim["status"] == "verified" for claim in claims)
    assert claims[1]["label"] == "return"
    assert claims[1]["matched_path"] == "data.chip_data.twse_margin_short_sales.borrowed_short_return_today"


def test_evidence_gate_does_not_cross_match_borrowed_return_to_sale_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Today's borrowed short return: 525,000.",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "borrowed_short_sale_today": 525000,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""


def test_evidence_gate_matches_borrowed_short_sale_after_vs_label_in_thousands():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Borrowed Short Return Today: 463k vs Sale Today: 156k (Net return/covering).",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "borrowed_short_sale_today": 156000,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["label"] == "vs Sale Today"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.chip_data.twse_margin_short_sales.borrowed_short_sale_today"
    assert claim["matched_value"] == 156.0


def test_evidence_gate_keeps_margin_short_ratio_unverifiable_without_canonical_scalar():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **券資比 (融券餘額 / 融資餘額)：** 1.25% (34張 / 2713張)。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "short_balance": 34,
                        "margin_balance": 2713,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "derived_metric_not_canonical"
    assert claim["matched_path"] == ""


def test_evidence_gate_converts_borrowed_short_return_shares_to_lots():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 當日借券還券：40 張。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "borrowed_short_return_today": 40000,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.chip_data.twse_margin_short_sales.borrowed_short_return_today"
    assert claim["matched_value"] == 40.0


def test_evidence_gate_does_not_compare_borrowed_return_raw_shares_as_lots():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 當日借券還券：40000 張。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "borrowed_short_return_today": 40000,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "mismatch"
    assert claim["matched_path"] == "data.chip_data.twse_margin_short_sales.borrowed_short_return_today"
    assert claim["matched_value"] == 40.0


def test_evidence_gate_verifies_zero_borrowed_return_after_unit_conversion():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 當日借券還券：0 張。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "borrowed_short_return_today": 0,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "verified"


def test_evidence_gate_matches_historical_dupont_margin_to_dupont_note():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **依據與說明**：`history` 顯示其 ROE 23.1% 高度由 **26.0% 的高淨利率** 驅動（杜邦恒等式：26.0% × 0.725x × 1.225x）。",
        {
            "data": {
                "profit_margin": "28.4%",
                "dupont_identity_note": "淨利率 26.0% × 資產周轉率 0.725x × 權益乘數 1.225x = ROE 23.1%",
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert result["sampled_claims"][0]["matched_path"] == "data.dupont_identity_note"


def test_evidence_gate_matches_explicit_week_52_price_source_paths():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        """
- **壓力位**：41.4706 TWD（`market_data.week_52_high_twd`）。
- **支撐位**：22.6961 TWD（`market_data.week_52_low_twd`）。
""",
        {"data": {"week_52_high": 41.47059, "week_52_low": 22.696077}},
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert [item["matched_path"] for item in result["sampled_claims"]] == [
        "data.week_52_high",
        "data.week_52_low",
    ]


def test_evidence_gate_matches_week_52_source_path_with_citation_wording():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        """
- **關鍵壓力位**：**56.4 元**（引用 `market_data.week_52_high_twd`），為近期最高壓力點。
- **關鍵支撐位**：**12.1 元**（引用 `market_data.week_52_low_twd`），為近期最低支撐點。
""",
        {"data": {"week_52_high": 56.4, "week_52_low": 12.1}},
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert [item["matched_path"] for item in result["sampled_claims"]] == [
        "data.week_52_high",
        "data.week_52_low",
    ]


def test_evidence_gate_matches_markdown_formatted_week_52_label_source():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "*   **52 週高點：** 78.2 TWD（`market_data` 提供之歷史阻力）。",
        {"data": {"week_52_high": 78.2}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert result["sampled_claims"][0]["matched_path"] == "data.week_52_high"


def test_evidence_gate_does_not_apply_later_week_52_source_to_prior_claim():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期壓力位**：419.15 TWD（2026-05-29 高點）以及 460.0 TWD（`market_data.week_52_high_twd`）。",
        {"data": {"week_52_high": 460.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "caution"
    assert result["sampled_claims"][0]["status"] == "unverifiable"


def test_evidence_gate_matches_current_price_and_prefixed_week_52_source_paths():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        """
- **當前價格**：85.5 元（`market_data.current_price_twd`）。
- **52週高點**：112.3 TWD（data.market_data.week_52_high_twd）。
""",
        {"data": {"current_price": 85.5, "week_52_high": 112.3}},
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert [item["matched_path"] for item in result["sampled_claims"]] == [
        "data.current_price",
        "data.week_52_high",
    ]


def test_evidence_gate_matches_explicit_week_52_labels_without_cross_number_leakage():
    from evidence_exit_gate import evaluate_report_evidence

    high_low = evaluate_report_evidence(
        """
- 52 週高點：2,585.0 TWD；52 週低點：619.0 TWD。
""",
        {"data": {"week_52_high": 2585.0, "week_52_low": 619.0}},
        sample_ratio=1.0,
        min_sample=2,
    )

    pressure_support = evaluate_report_evidence(
        """
- **壓力位：21.6 TWD**（52 週高點）。
- **支撐位：17.6 TWD**（52 週低點）。
""",
        {"data": {"week_52_high": 21.6, "week_52_low": 17.6}},
        sample_ratio=1.0,
        min_sample=2,
    )

    false_positive = evaluate_report_evidence(
        """
- 近期高點壓力：659.0 元（2026 年 6 月 30 日收盤價），上方 52 週高點為 796.0 元。
- 防軋空停損點 (Stop-loss level)：55.0 TWD（參考 52 週高點 70.8 TWD）。
""",
        {"data": {"week_52_high": 796.0}},
        sample_ratio=1.0,
        min_sample=2,
    )

    assert high_low["verdict"] == "approved"
    assert pressure_support["verdict"] == "approved"
    assert [claim["matched_path"] for claim in high_low["sampled_claims"]] == [
        "data.week_52_high",
        "data.week_52_low",
    ]
    assert [claim["matched_path"] for claim in pressure_support["sampled_claims"]] == [
        "data.week_52_high",
        "data.week_52_low",
    ]
    assert all(claim["status"] == "unverifiable" for claim in false_positive["sampled_claims"])


def test_evidence_gate_matches_previous_chip_balances_by_local_context():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        """
- Margin Balance: 12,654 (Previous: 13,826) -> Decreasing.
- **Margin Balance:** 23,822 (Previous: 26,402). Trend: Decreasing.
- **Short Balance:** 673 (Previous: 525). Trend: Slight increase.
""",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "margin_balance": 12654,
                        "margin_balance_alt": 23822,
                        "short_balance": 673,
                        "margin_previous_balance": 13826,
                        "margin_previous_balance_alt": 26402,
                        "short_previous_balance": 525,
                    },
                },
            },
        },
        sample_ratio=1.0,
        min_sample=3,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert [item["matched_path"] for item in result["sampled_claims"]] == [
        "data.chip_data.twse_margin_short_sales.margin_balance",
        "data.chip_data.twse_margin_short_sales.margin_previous_balance",
        "data.chip_data.twse_margin_short_sales.margin_balance_alt",
        "data.chip_data.twse_margin_short_sales.margin_previous_balance_alt",
        "data.chip_data.twse_margin_short_sales.short_balance",
        "data.chip_data.twse_margin_short_sales.short_previous_balance",
    ]


def test_evidence_gate_extracts_external_previous_chip_balance_without_false_claim():
    from evidence_exit_gate import evaluate_report_evidence, extract_numeric_claims

    markdown = "\n".join(
        [
            "- Margin balance: 26,331 (thousand shares). Previous: 26,504. (Slight decrease).",
            "- Short balance: 382 (thousand shares). Previous: 375. (Slight increase).",
        ]
    )
    claims = extract_numeric_claims(markdown)
    result = evaluate_report_evidence(
        markdown,
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "margin_balance": 26331,
                        "margin_previous_balance": 26504,
                        "short_balance": 382,
                        "short_previous_balance": 375,
                    }
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert [(claim["label"], claim["reported_value"]) for claim in claims] == [
        ("Margin balance", 26331.0),
        ("Previous", 26504.0),
        ("Short balance", 382.0),
        ("Previous", 375.0),
    ]
    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert [item["matched_path"] for item in result["sampled_claims"]] == [
        "data.chip_data.twse_margin_short_sales.margin_balance",
        "data.chip_data.twse_margin_short_sales.margin_previous_balance",
        "data.chip_data.twse_margin_short_sales.short_balance",
        "data.chip_data.twse_margin_short_sales.short_previous_balance",
    ]


def test_evidence_gate_binds_explicit_price_history_claims_to_reported_date():
    from evidence_exit_gate import evaluate_report_evidence

    snapshot = {
        "data": {
            "price_history": {
                "dates": ["2026-05-29", "2026-06-30"],
                "prices": [104.76, 107.15],
            },
        },
    }
    verified = evaluate_report_evidence(
        "- **近期月度高點**: 107.15 TWD (2026年6月30日收盤價，AgentState view.normalized_financials.price_history.prices)。",
        snapshot,
        sample_ratio=1.0,
        min_sample=1,
    )
    wrong_date = evaluate_report_evidence(
        "- **近期月度高點**: 107.15 TWD (2026-05-29，AgentState view.normalized_financials.price_history.prices)。",
        snapshot,
        sample_ratio=1.0,
        min_sample=1,
    )

    assert verified["verdict"] == "approved"
    assert verified["sampled_claims"][0]["matched_path"] == "data.price_history[2026-06-30].prices[1]"
    assert wrong_date["verdict"] == "rejected"
    assert wrong_date["sampled_claims"][0]["status"] == "mismatch"
    assert wrong_date["sampled_claims"][0]["matched_path"] == "data.price_history[2026-05-29].prices[0]"


def test_evidence_gate_extracts_all_values_from_three_month_price_series():
    from evidence_exit_gate import evaluate_report_evidence, extract_numeric_claims

    markdown = "\n".join(
        [
            "- Based on `price_history`, 2026 年 6 月 reached 42.78.",
            "- 觀察近三個月價格（6/30: 42.78, 7/31: 43.3, 8/21: 42.6）。",
        ]
    )
    snapshot = {"data": {"price_history": {"dates": ["2026-06-30", "2026-07-31", "2026-08-21"], "prices": [42.78, 43.3, 42.6]}}}
    claims = extract_numeric_claims(markdown)
    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0, min_sample=1)

    assert [claim["label"] for claim in claims] == ["觀察近三個月價格（6/30", "7/31", "8/21"]
    assert result["verdict"] == "approved"
    assert [claim["status"] for claim in result["sampled_claims"]] == ["verified", "verified", "verified"]
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.price_history[2026-06-30].prices[0]",
        "data.price_history[2026-07-31].prices[1]",
        "data.price_history[2026-08-21].prices[2]",
    ]


def test_evidence_gate_does_not_guess_year_for_three_month_price_series():
    from evidence_exit_gate import evaluate_report_evidence

    markdown = "\n".join(
        [
            "- Based on `price_history`, 2026 年 6 月 reached 42.78.",
            "- 觀察近三個月價格（6/30: 42.78, 7/31: 43.3, 8/21: 42.6）。",
        ]
    )
    snapshot = {"data": {"price_history": {"dates": ["2025-06-30", "2026-06-30", "2026-07-31", "2026-08-21"], "prices": [40.0, 42.78, 43.3, 42.6]}}}
    result = evaluate_report_evidence(markdown, snapshot, sample_ratio=1.0, min_sample=1)

    claim = result["sampled_claims"][0]
    assert claim["label"] == "觀察近三個月價格（6/30"
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "missing_semantic_path"
    assert claim["matched_path"] == ""


def test_evidence_gate_binds_dated_latest_price_to_exact_price_history_point():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 最新價格 (2026-07-24): 18.8 元。",
        {"data": {"current_price": 18.8, "price_history": {"dates": ["2026-07-24"], "prices": [18.8]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[2026-07-24].prices[0]"


def test_evidence_gate_does_not_fallback_dated_latest_price_to_current_price():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 最新價格 (2026-07-24): 18.8 元。",
        {"data": {"current_price": 18.8, "price_history": {"dates": ["2026-07-23"], "prices": [18.8]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["verification_reason_code"] == "no_matching_snapshot_path"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_binds_dated_support_to_exact_price_history_point():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 支撐位：36.0 TWD（2026-07-31 價格基準）。",
        {"data": {"price_history": {"dates": ["2026-07-31"], "prices": [36.0]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[2026-07-31].prices[0]"


def test_evidence_gate_does_not_bind_news_support_to_price_history():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 近期支撐：15.1 元（2026-06-25 催化劑提到之價格）。",
        {"data": {"price_history": {"dates": ["2026-06-25"], "prices": [15.1]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_does_not_bind_dated_catalyst_low_point_to_close_history():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 近期低點/支撐參考：15.1（2026-06-25 催化劑提到之價格）。",
        {"data": {"risk_price": 15.1, "price_history": {"dates": ["2026-06-25"], "prices": [15.1]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "caution"
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "news_source_not_canonical"
    assert claim["matched_path"] == ""


def test_evidence_gate_binds_month_end_support_to_exact_price_history_point():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 近期支撐：33.0 TWD（2026/07/31 月底價）。",
        {"data": {"price_history": {"dates": ["2026-07-31"], "prices": [33.0]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[2026-07-31].prices[0]"


def test_evidence_gate_does_not_bind_later_historical_price_to_support_claim():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 支撐位：100.5 元（TWD/股）構成近期重要心理及技術支撐位。此外，歷史價格中 2026 年 2 月 26 日的 110.0 元亦可視為下方支撐。",
        {"data": {"price_history": {"dates": ["2026-02-26"], "prices": [110.0]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_binds_historical_support_before_later_news_value():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 關鍵支撐位：30.1 TWD（2026-07-31 之近期低點）。此外，2026-07-22 新聞提及之漲停價 42.35 TWD 可視為短期心理支撐。",
        {"data": {"price_history": {"dates": ["2026-07-31"], "prices": [30.1]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[2026-07-31].prices[0]"


def test_evidence_gate_binds_support_when_date_follows_explicit_this_is_phrase():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 關鍵支撐位：30.1 TWD。此為 2026-07-31 之近期低點。此外，2026-07-22 新聞提及之漲停價 42.35 TWD 可視為短期心理支撐。",
        {"data": {"price_history": {"dates": ["2026-07-31"], "prices": [30.1]}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[2026-07-31].prices[0]"


def test_evidence_gate_binds_dated_price_claim_without_field_marker():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期高點壓力**：659.0 元（2026 年 6 月 30 日收盤價）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-05-29", "2026-06-30"],
                    "prices": [587.97, 659.0],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[2026-06-30].prices[1]"


def test_evidence_gate_binds_dated_high_point_without_close_phrase():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期高點**：22.05（2026-06-30）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30", "2026-07-24"],
                    "prices": [22.05, 18.8],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )
    wrong_date = evaluate_report_evidence(
        "- **近期高點**：22.05（2026-07-24）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30", "2026-07-24"],
                    "prices": [22.05, 18.8],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[2026-06-30].prices[0]"
    assert wrong_date["verdict"] == "rejected"
    assert wrong_date["sampled_claims"][0]["status"] == "mismatch"
    assert wrong_date["sampled_claims"][0]["matched_path"] == "data.price_history[2026-07-24].prices[1]"


def test_evidence_gate_binds_dated_extremum_inside_pressure_sentence():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期壓力位**：419.15 TWD（2026-05-29 高點）以及 460.0 TWD（`market_data.week_52_high_twd`）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-05-29", "2026-07-31"],
                    "prices": [419.15, 292.0],
                },
                "week_52_high": 460.0,
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[2026-05-29].prices[0]"


def test_evidence_gate_binds_daily_institutional_value_to_its_date():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* Latest Date: 2026-08-20.\n"
        "* Last 10 trading days daily total net buy (thousand shares):\n"
        "  * Aug 13: -6,574",
        {
            "data": {
                "institutional_trading": {
                    "daily_total_net_buy_last_10": [
                        {"date": "2026-08-13", "net_buy_thousand_shares": -6574.44},
                        {"date": "2026-08-14", "net_buy_thousand_shares": -915.46},
                    ]
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == (
        "data.institutional_trading.daily_total_net_buy_last_10[2026-08-13].net_buy_thousand_shares"
    )


def test_evidence_gate_keeps_daily_institutional_date_mismatch_on_its_date():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* Latest Date: 2026-08-20.\n"
        "* Last 10 trading days daily total net buy (thousand shares):\n"
        "  * Aug 13: -915",
        {
            "data": {
                "institutional_trading": {
                    "daily_total_net_buy_last_10": [
                        {"date": "2026-08-13", "net_buy_thousand_shares": -6574.44},
                        {"date": "2026-08-14", "net_buy_thousand_shares": -915.46},
                    ]
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "rejected"
    assert claim["status"] == "mismatch"
    assert claim["matched_path"].endswith("[2026-08-13].net_buy_thousand_shares")


def test_evidence_gate_does_not_guess_standalone_month_day_as_daily_institutional_value():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* Aug 13: -6,574",
        {
            "data": {
                "institutional_trading": {
                    "daily_total_net_buy_last_10": [
                        {"date": "2026-08-13", "net_buy_thousand_shares": -6574.44}
                    ]
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "caution"
    assert result["sampled_claims"][0]["status"] == "unverifiable"


def test_evidence_gate_does_not_bind_dated_news_extremum_to_close_history():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期壓力位**：55.8 TWD（2026-07-30 高點，根據 `market_catalysts` 新聞）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-07-30"],
                    "prices": [53.7],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "caution"
    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_does_not_bind_dated_news_high_point_to_close_history():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期高點**：55.8（根據 2026-07-30 `market_catalysts` 新聞）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-07-30"],
                    "prices": [53.7],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "caution"
    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_maps_explicit_key_pressure_to_week_high():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **關鍵壓力：** 569.0 TWD (52 週最高價，`market_data`)。",
        {"data": {"week_52_high": 569.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["matched_path"] == "data.week_52_high"


def test_evidence_gate_maps_key_pressure_point_week_high_variant():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **關鍵壓力位：24.5 TWD**。此為 `market_data` 紀錄之 52 週最高價（Week 52 High）。",
        {"data": {"week_52_high": 24.5}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["matched_path"] == "data.week_52_high"


def test_evidence_gate_maps_numbered_swing_pressure_to_week_high():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **波段壓力二**：294.0 TWD（52 週最高價），為長期結構性壓力。",
        {"data": {"week_52_high": 294.0, "week_52_low": 64.4}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.week_52_high"


def test_evidence_gate_does_not_infer_numbered_swing_pressure_without_week_marker():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **波段壓力二**：294.0 TWD（長期結構性壓力）。",
        {"data": {"week_52_high": 294.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["matched_path"] != "data.week_52_high"


def test_evidence_gate_maps_long_term_defense_line_to_week_low():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **長期防線：** 19.15 TWD（52 週最低價）。",
        {"data": {"week_52_high": 51.9, "week_52_low": 19.15}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.week_52_low"


def test_evidence_gate_does_not_infer_defense_line_without_week_marker():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **長期防線：** 19.15 TWD（長期支撐區）。",
        {"data": {"week_52_low": 19.15}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["matched_path"] != "data.week_52_low"


def test_evidence_gate_matches_code_style_previous_short_balance_key():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **短期籌碼**：`short_previous_balance`: 1,501。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {"short_previous_balance": 1501}
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == (
        "data.chip_data.twse_margin_short_sales.short_previous_balance"
    )


def test_evidence_gate_matches_yearless_daily_net_buy_heading_using_snapshot_year():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **Daily Net Buy (Last 10 days):**\n"
        "  - Aug 24: -7,632.94k\n"
        "  - Aug 31: -4,058.72k",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-08-29"],
                    "prices": [100.0],
                },
                "institutional_trading": {
                    "daily_total_net_buy_last_10": [
                        {"date": "2026-08-24", "net_buy_thousand_shares": -7632.94},
                        {"date": "2026-08-31", "net_buy_thousand_shares": -4058.72},
                    ]
                },
            }
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.institutional_trading.daily_total_net_buy_last_10[2026-08-24].net_buy_thousand_shares",
        "data.institutional_trading.daily_total_net_buy_last_10[2026-08-31].net_buy_thousand_shares",
    ]


def test_evidence_gate_matches_week_high_key_followed_by_value():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **突破 52 週新高壓力**：當前價格 34.0 TWD 已觸及並站上 52 週高價區間（`week_52_high_twd`: 34.0）。",
        {"data": {"week_52_high": 34.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.week_52_high"


def test_evidence_gate_matches_week_high_source_followed_by_parenthesized_value():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **關鍵壓力位：35.1 TWD**。目前價格已接近 `market_data.week_52_high_twd` (35.1 TWD)。",
        {"data": {"week_52_high": 35.1}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.week_52_high"


def test_evidence_gate_maps_dated_pressure_labeled_as_week_high_to_week_high():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期壓力**：305.5 TWD（2026-05-25 創下之 52 週高點，來源：`market_data`）。",
        {"data": {"week_52_high": 305.5}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.week_52_high"


def test_evidence_gate_maps_yearless_close_support_to_unique_price_history_date():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐：** 31.6 TWD（8/31 收盤價，初步支撐）；22.05 TWD（前波頸線位置，強支撐）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-07-31", "2026-08-31"],
                    "prices": [9.5, 31.6],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.price_history[2026-08-31].prices[1]"


def test_evidence_gate_does_not_guess_year_for_ambiguous_yearless_close_support():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐：** 31.6 TWD（8/31 收盤價，初步支撐）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2025-08-31", "2026-08-31"],
                    "prices": [31.6, 31.6],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""


def test_evidence_gate_does_not_bind_yearless_close_support_from_news():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐：** 31.6 TWD（8/31 收盤價，新聞速報）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-08-31"],
                    "prices": [31.6],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""


def test_evidence_gate_ignores_normalized_financials_examples_in_data_limitations():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "* **短期均線資料不足：** 由於 `normalized_financials` 僅提供月份端點值與近兩日價格（8/31: 60.0, 9/1: 57.5），無法精確計算均線。"
    )

    assert claims == []


def test_evidence_gate_matches_support_to_both_dates_of_sideways_range_bottom():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **強勁支撐**：29.72 TWD（2026-03-31 至 2026-04-30 之橫盤區間底）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-03-31", "2026-04-30"],
                    "prices": [29.72, 29.72],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.price_history[2026-03-31].prices[0]"


def test_evidence_gate_matches_horizon_targets_to_persisted_recommendation_keys():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 短期目標（3個月）：NT$18.5\n"
        "- 中期目標（6個月）：NT$12.5\n"
        "- 長期目標（12個月）：NT$6.5\n"
        "- 長期潛力（5年）：NT$8.0",
        {
            "rerun_context": {
                "parsed": {
                    "recommendation": {
                        "短期目標（3個月）": "NT$18.5",
                        "中期目標（6個月）": "NT$12.5",
                        "長期目標（12個月）": "NT$6.5",
                        "長期潛力（5年）": "NT$8.0",
                    }
                }
            }
        },
        sample_ratio=1.0,
        min_sample=4,
    )

    assert result["verdict"] == "approved"
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "rerun_context.parsed.recommendation.短期目標（3個月）",
        "rerun_context.parsed.recommendation.中期目標（6個月）",
        "rerun_context.parsed.recommendation.長期目標（12個月）",
        "rerun_context.parsed.recommendation.長期潛力（5年）",
    ]


def test_evidence_gate_classifies_fomo_overheat_score_as_analysis_metadata():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "**FOMO/過熱評分：7 / 10**",
        {"data": {}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "analysis_metadata_not_evidence"


def test_evidence_gate_does_not_treat_plain_key_pressure_as_week_high():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **關鍵壓力位：24.5 TWD**。短線壓力區需人工確認。",
        {"data": {"week_52_high": 24.5}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["matched_path"] != "data.week_52_high"


def test_evidence_gate_classifies_generic_pressure_without_canonical_scalar():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期壓力：** 34.0 TWD（心理關卡與目前最高價）。",
        {"data": {"week_52_high": 34.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "technical_level_not_canonical"
    assert claim["matched_path"] == ""


def test_evidence_gate_maps_month_low_support_to_month_minimum():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **強勁支撐：** 292.5 元（2026 年 7 月之近期低點）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-07-01", "2026-07-31", "2026-08-21"],
                    "prices": [300.0, 292.5, 461.5],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[month=2026-07].low"


def test_evidence_gate_keeps_month_low_value_mismatch_on_month_extremum():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **強勁支撐：** 300.0 元（2026 年 7 月之近期低點）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-07-01", "2026-07-31"],
                    "prices": [300.0, 292.5],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "rejected"
    assert claim["status"] == "mismatch"
    assert claim["matched_path"] == "data.price_history[month=2026-07].low"


def test_evidence_gate_does_not_bind_later_month_extremum_to_prior_support():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期支撐**：179.5 TWD（前述區間上緣）以及 130.0 TWD（2026-07 低點，資料來源：`price_history`）。",
        {"data": {"price_history": {"dates": ["2026-07-31"], "prices": [130.0]}}},
        sample_ratio=1.0,
        min_sample=2,
    )

    claims = result["sampled_claims"]
    assert claims[0]["reported_value"] == 179.5
    assert claims[0]["status"] == "unverifiable"
    assert claims[0]["matched_path"] == ""
    assert claims[1]["reported_value"] == 130.0
    assert claims[1]["status"] == "verified"
    assert claims[1]["matched_path"] == "data.price_history[month=2026-07].low"


def test_evidence_gate_maps_month_high_pressure_to_month_maximum():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期壓力：** 40.15 TWD（2026-06 盤中高點區域）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-01", "2026-06-30"],
                    "prices": [38.0, 40.15],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[month=2026-06].high"


def test_evidence_gate_maps_unique_yearless_month_high_support_to_month_maximum():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐：** 367.41 TWD（6 月份高點轉支撐）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-05-29", "2026-06-30", "2026-07-31"],
                    "prices": [266.26, 367.41, 263.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.price_history[month=2026-06].high"


def test_evidence_gate_does_not_infer_yearless_month_high_across_years():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐：** 367.41 TWD（6 月份高點轉支撐）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2025-06-30", "2026-06-30"],
                    "prices": [367.41, 350.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""


def test_evidence_gate_does_not_bind_yearless_month_high_to_news():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐：** 367.41 TWD（6 月份高點，來源：`market_catalysts`）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30"],
                    "prices": [367.41],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""


def test_evidence_gate_maps_unique_yearless_month_end_support_to_price_history():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **強勁支撐：** 481.0 元（7 月底低點）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30", "2026-07-31", "2026-08-20"],
                    "prices": [659.0, 481.0, 650.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["matched_path"] == "data.price_history[month-end=2026-07]"


def test_evidence_gate_maps_month_end_close_support_to_price_history():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐：** 33.0 TWD（7 月底收盤價）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30", "2026-07-31"],
                    "prices": [35.0, 33.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.price_history[month-end=2026-07]"


def test_evidence_gate_maps_explicit_year_month_end_close_pressure():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期壓力一**：267.0 TWD（2026 年 5 月底收盤價）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-05-29", "2026-06-30"],
                    "prices": [267.0, 281.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["matched_path"] == "data.price_history[month-end=2026-05]"


def test_evidence_gate_maps_explicit_month_end_close_for_prior_high_label():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **波段前高：** 214.85 TWD（2026 年 5 月收盤價）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-04-30", "2026-05-29", "2026-06-30"],
                    "prices": [163.33, 214.85, 207.07],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.price_history[month-end=2026-05]"


def test_evidence_gate_maps_explicit_close_for_bottom_boundary_label():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 強勁底部分界：207.09 TWD（2026-07-31 收盤價）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30", "2026-07-31", "2026-08-19"],
                    "prices": [219.97, 207.09, 273.5],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.price_history[2026-07-31].prices[1]"


def test_evidence_gate_does_not_infer_bottom_boundary_from_platform_wording():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 強勁底部分界：207.09 TWD（2026-07-31 平台位置）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-07-31"],
                    "prices": [207.09],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""


def test_evidence_gate_does_not_infer_prior_high_without_close_marker():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **波段前高：** 214.85 TWD（2026 年 5 月平台位置）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-05-29"],
                    "prices": [214.85],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["matched_path"] != "data.price_history[month-end=2026-05]"


def test_evidence_gate_does_not_treat_month_end_platform_as_close_evidence():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **第二支撐：** 13.0 TWD（6 月底的平台位置）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30"],
                    "prices": [13.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "caution"
    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""


def test_evidence_gate_keeps_yearless_month_end_ambiguous_across_years():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **強勁支撐：** 481.0 元（7 月底低點）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2025-07-31", "2026-07-31"],
                    "prices": [320.0, 481.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "caution"
    assert result["sampled_claims"][0]["status"] == "unverifiable"


def test_evidence_gate_keeps_month_end_value_mismatch_on_exact_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **強勁支撐：** 500.0 元（7 月底低點）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30", "2026-07-31"],
                    "prices": [659.0, 481.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "rejected"
    assert claim["status"] == "mismatch"
    assert claim["matched_path"] == "data.price_history[month-end=2026-07]"


def test_evidence_gate_does_not_bind_month_end_news_to_price_history():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **強勁支撐：** 481.0 元（7 月底低點，根據 `market_catalysts` 新聞）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-07-31"],
                    "prices": [481.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "caution"
    assert result["sampled_claims"][0]["status"] == "unverifiable"


def test_evidence_gate_splits_secondary_price_history_support_value():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐：** 5000.0 TWD（整數心理關卡）及 3445.0 TWD（7 月份收盤平台，資料來源：`price_history`）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30", "2026-07-31", "2026-08-21"],
                    "prices": [3408.83, 3445.0, 5395.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claims = result["sampled_claims"]
    assert result["claim_count"] == 2
    assert result["verdict"] == "caution"
    assert claims[0]["reported_value"] == 5000.0
    assert claims[0]["status"] == "unverifiable"
    assert claims[1]["label"] == "近期支撐（次要價位）"
    assert claims[1]["status"] == "verified"
    assert claims[1]["matched_path"] == "data.price_history[month-end=2026-07]"


def test_evidence_gate_splits_two_month_end_close_support_values():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐**：3998.48 TWD（7 月底收盤價）與 4251.17 TWD（6 月底收盤價）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-06-30", "2026-07-31", "2026-08-20"],
                    "prices": [4251.17, 3998.48, 4100.0],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claims = result["sampled_claims"]
    assert result["claim_count"] == 2
    assert result["verdict"] == "approved"
    assert [claim["status"] for claim in claims] == ["verified", "verified"]
    assert claims[0]["matched_path"] == "data.price_history[month-end=2026-07]"
    assert claims[1]["matched_path"] == "data.price_history[month-end=2026-06]"


def test_evidence_gate_splits_news_and_month_end_support_values_by_context():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* **近期支撐**：31.75 TWD（參考 `recent_catalysts` 提及價位）及 22.95 TWD（7 月底低點）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-07-31", "2026-08-20"],
                    "prices": [22.95, 36.6],
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claims = result["sampled_claims"]
    assert result["claim_count"] == 2
    assert claims[0]["reported_value"] == 31.75
    assert claims[0]["status"] == "unverifiable"
    assert claims[1]["reported_value"] == 22.95
    assert claims[1]["status"] == "verified"
    assert claims[1]["matched_path"] == "data.price_history[month-end=2026-07]"


def test_evidence_gate_does_not_bind_dated_news_pressure_to_close_history():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期壓力**：55.8 TWD（根據 2026-07-30 `market_catalysts` 新聞）。",
        {
            "data": {
                "price_history": {
                    "dates": ["2026-07-30"],
                    "prices": [53.7],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "caution"
    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_matches_explicit_institutional_total_net_buy_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 延續劇本：法人累計買進（`total_net_buy_thousand_shares`: 2407.25）之籌碼支撐。",
        {
            "data": {
                "institutional_trading": {
                    "total_net_buy_thousand_shares": 2407.25,
                    "last_5_trading_days_net_buy_thousand_shares": 1341.01,
                    "daily_total_net_buy_last_10": [{"net_buy_thousand_shares": 2407.25}],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert result["sampled_claims"][0]["matched_path"] == "data.institutional_trading.total_net_buy_thousand_shares"


def test_evidence_gate_matches_explicit_institutional_last_5_net_buy_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Last 5 trading days net buy: `last_5_trading_days_net_buy_thousand_shares`: 59913.89.",
        {
            "data": {
                "institutional_trading": {
                    "total_net_buy_thousand_shares": 59913.89,
                    "last_5_trading_days_net_buy_thousand_shares": 59913.89,
                    "daily_total_net_buy_last_10": [{"net_buy_thousand_shares": 59913.89}],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert result["sampled_claims"][0]["matched_path"] == "data.institutional_trading.last_5_trading_days_net_buy_thousand_shares"


def test_evidence_gate_matches_labelled_institutional_last_5_net_buy_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Last 5 trading days net buy: 12,467.35k.",
        {
            "data": {
                "institutional_trading": {
                    "total_net_buy_thousand_shares": 12467.35,
                    "last_5_trading_days_net_buy_thousand_shares": 12467.35,
                    "daily_total_net_buy_last_10": [{"net_buy_thousand_shares": 12467.35}],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["unverifiable_count"] == 0
    assert result["sampled_claims"][0]["matched_path"] == "data.institutional_trading.last_5_trading_days_net_buy_thousand_shares"


def test_evidence_gate_matches_compact_last_5_days_net_buy_alias():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* Last 5 days Net Buy: 22,514.34k.",
        {
            "data": {
                "institutional_trading": {
                    "last_5_trading_days_net_buy_thousand_shares": 22514.34,
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.institutional_trading.last_5_trading_days_net_buy_thousand_shares"


def test_evidence_gate_does_not_verify_last_5_days_alias_from_total_only():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "* Last 5 days Net Buy: 22,514.34k.",
        {
            "data": {
                "institutional_trading": {
                    "total_net_buy_thousand_shares": 22514.34,
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] != "data.institutional_trading.total_net_buy_thousand_shares"


def test_evidence_gate_matches_compact_5_day_net_buy_label_to_last_5_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 5-day: 4,504.85k (Net Buy).",
        {"data": {"institutional_trading": {"last_5_trading_days_net_buy_thousand_shares": 4504.85}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "approved"
    assert claim["label"] == "day"
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.institutional_trading.last_5_trading_days_net_buy_thousand_shares"


def test_evidence_gate_does_not_promote_10_day_net_buy_to_last_5_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 10-day: 4,504.85k (Net Buy).",
        {"data": {"institutional_trading": {"last_5_trading_days_net_buy_thousand_shares": 4504.85}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_matches_dealer_label_to_category_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Dealer: 22,401.41",
        {
            "data": {
                "institutional_trading": {
                    "net_buy_thousand_shares_by_category": {
                        "dealer": 22401.41,
                        "foreign_investors": 999.0,
                    }
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.institutional_trading.net_buy_thousand_shares_by_category.dealer"


def test_evidence_gate_matches_foreign_and_investment_trust_labels_to_category_paths():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Foreign: 22,509.2\n- Investment Trust: 3,144.84",
        {
            "data": {
                "institutional_trading": {
                    "net_buy_thousand_shares_by_category": {
                        "foreign": 22509.2,
                        "investment_trust": 3144.84,
                        "dealer": 22401.41,
                    }
                }
            }
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    assert result["verdict"] == "approved"
    assert [claim["status"] for claim in result["sampled_claims"]] == ["verified", "verified"]
    assert [claim["matched_path"] for claim in result["sampled_claims"]] == [
        "data.institutional_trading.net_buy_thousand_shares_by_category.foreign",
        "data.institutional_trading.net_buy_thousand_shares_by_category.investment_trust",
    ]


def test_evidence_gate_does_not_cross_match_foreign_or_investment_trust_to_total_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Foreign: 22,509.2\n- Investment Trust: 3,144.84",
        {
            "data": {
                "institutional_trading": {
                    "total_net_buy_thousand_shares": 22509.2,
                }
            }
        },
        sample_ratio=1.0,
        min_sample=2,
    )

    assert all(claim["status"] == "unverifiable" for claim in result["sampled_claims"])
    assert all(claim["matched_path"] == "" for claim in result["sampled_claims"])


def test_evidence_gate_matches_compact_total_after_institutional_categories():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        """*   Dealer: 22401.41
*   Foreign: 22509.2
*   Investment Trust: 3144.84
*   Total: 48055.45
""",
        {
            "data": {
                "institutional_trading": {
                    "total_net_buy_thousand_shares": 48055.45,
                },
            },
        },
        sample_ratio=1.0,
        min_sample=4,
    )

    total_claim = next(claim for claim in result["sampled_claims"] if claim["label"] == "Total")
    assert total_claim["status"] == "verified"
    assert total_claim["matched_path"] == "data.institutional_trading.total_net_buy_thousand_shares"


def test_evidence_gate_does_not_promote_bare_total_without_institutional_categories():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Total: 48055.45",
        {"data": {"institutional_trading": {"total_net_buy_thousand_shares": 48055.45}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_matches_total_net_buy_30_day_label_to_total_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Total Net Buy (30 days): 118,065.81k.",
        {
            "data": {
                "institutional_trading": {
                    "total_net_buy_thousand_shares": 118065.81,
                    "last_5_trading_days_net_buy_thousand_shares": 2400.0,
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.institutional_trading.total_net_buy_thousand_shares"


def test_evidence_gate_does_not_cross_match_dealer_to_total_net_buy_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Dealer: 22,401.41",
        {"data": {"institutional_trading": {"total_net_buy_thousand_shares": 22401.41}}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_does_not_promote_daily_net_buy_to_last_5_field():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Daily total net buy: 12,467.35k.",
        {
            "data": {
                "institutional_trading": {
                    "last_5_trading_days_net_buy_thousand_shares": 12.0,
                    "daily_total_net_buy_last_10": [{"net_buy_thousand_shares": 12467.35}],
                },
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_matches_latest_balance_in_margin_context():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 融資餘額變化：**最新餘額：** 9,626 張（較前一交易日 10,915 張減少 1,289 張）。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "margin_balance": 9626,
                        "margin_previous_balance": 10915,
                        "short_balance": 489,
                    }
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.chip_data.twse_margin_short_sales.margin_balance"
    assert "context_text" not in result["sampled_claims"][0]


def test_evidence_gate_uses_adjacent_margin_heading_for_latest_balance():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 融資餘額變化（至 2026-08-19）：\n  - **最新餘額：** 9,626 張（較前一交易日 10,915 張減少 1,289 張）。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "margin_balance": 9626,
                        "margin_previous_balance": 10915,
                    }
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.chip_data.twse_margin_short_sales.margin_balance"


def test_evidence_gate_keeps_unqualified_latest_balance_unverifiable():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **最新餘額：** 9,626 張。",
        {
            "data": {
                "chip_data": {
                    "twse_margin_short_sales": {
                        "margin_balance": 9626,
                        "short_balance": 9626,
                    }
                }
            }
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "caution"
    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_matches_explicit_current_price_snapshot_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **當前價位：** 26.7 TWD（參考資料：`market_data.current_price_twd`）",
        {"data": {"current_price": 26.7}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.current_price"


def test_evidence_gate_matches_current_quote_alias_to_current_price():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **當前報價：** 85.5 TWD。",
        {"data": {"current_price": 85.5}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.current_price"


def test_evidence_gate_surfaces_current_quote_snapshot_mismatch():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **當前報價：** 1885.0 TWD。",
        {"data": {"current_price": 1750.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert result["verdict"] == "rejected"
    assert claim["status"] == "mismatch"
    assert claim["verification_reason_code"] == "snapshot_value_mismatch"
    assert claim["matched_path"] == "data.current_price"


def test_evidence_gate_does_not_cross_match_current_quote_to_other_numeric_fields():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **當前報價：** 85.5 TWD。",
        {"data": {"current_ratio": 85.5}},
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "no_matching_snapshot_path"
    assert claim["matched_path"] == ""


def test_evidence_gate_matches_52_week_high_price_label_to_canonical_field():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **近期壓力：** 1025.0 TWD（52 週最高價，來源：`market_data`）。",
        {"data": {"week_52_high": 1025.0, "current_price": 910.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.week_52_high"


def test_evidence_gate_matches_52_week_high_after_short_sentence_connector():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **關鍵壓力位**：**18.25 TWD**。此為 52 週最高價（`market_data`），目前價格 18.1 TWD。",
        {"data": {"week_52_high": 18.25, "current_price": 18.1}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.week_52_high"


def test_evidence_gate_matches_english_week_high_label_to_canonical_field():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 52 Week High: 125.0",
        {"data": {"week_52_high": 125.0, "week_52_low": 80.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.week_52_high"


def test_evidence_gate_does_not_cross_match_english_week_high_to_week_low():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 52 Week High: 125.0",
        {"data": {"week_52_low": 125.0}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_matches_paired_english_week_low_to_canonical_field():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 52-week high: 72.3 / low: 31.7476.",
        {"data": {"week_52_high": 72.3, "week_52_low": 31.747572}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    claims = {claim["label"]: claim for claim in result["sampled_claims"]}
    assert claims["week high"]["matched_path"] == "data.week_52_high"
    assert claims["low"]["status"] == "verified"
    assert claims["low"]["matched_path"] == "data.week_52_low"


def test_evidence_gate_keeps_bare_low_label_unverifiable():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- low: 31.7476.",
        {"data": {"week_52_low": 31.747572}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_matches_latest_annual_net_income_growth_path():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Net Income Growth (Latest Annual): 70.6%.",
        {"data": {"earnings_growth": 70.6, "latest_annual_net_income_growth": 70.6}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "data.latest_annual_net_income_growth"


def test_evidence_gate_does_not_use_generic_earnings_growth_for_latest_annual_label():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- Net Income Growth (Latest Annual): 70.6%.",
        {"data": {"earnings_growth": 70.6}},
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["sampled_claims"][0]["status"] == "unverifiable"
    assert result["sampled_claims"][0]["matched_path"] == ""


def test_evidence_gate_matches_week_target_to_v4_trade_setup_target():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- **1-2週目標:** 47.45 TWD（52週高點壓力位）",
        {
            "rerun_context": {
                "structured_outputs": {"24": {"target_price": "47.45 TWD（52週高點壓力位）"}},
                "parsed": {"trade_setup": {"target_price": "47.45 TWD（52週高點壓力位）"}},
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    assert result["verdict"] == "approved"
    assert result["sampled_claims"][0]["status"] == "verified"
    assert result["sampled_claims"][0]["matched_path"] == "rerun_context.structured_outputs.24.target_price"


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


def test_evidence_gate_verifies_implied_growth_from_snapshot_cross_checks():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- `forward_eps_implied_revenue_growth_pct`: 262.715%",
        {
            "financial_cross_checks": {
                "forward_eps_implied_revenue_growth_pct": 262.715,
            },
        },
        sample_ratio=1.0,
        min_sample=1,
    )

    claim = result["sampled_claims"][0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "financial_cross_checks.forward_eps_implied_revenue_growth_pct"


def test_evidence_gate_does_not_borrow_price_history_for_scenario_target():
    from evidence_exit_gate import evaluate_report_evidence

    result = evaluate_report_evidence(
        "- 熊市情境: NT$820",
        {"data": {"price_history_ranges": {"ranges": {"1m": {"prices": [820.0]}}}}},
        sample_ratio=1.0,
        min_sample=1,
    )
    claim = result["sampled_claims"][0]

    assert claim["status"] == "unverifiable"
    assert claim["matched_path"] == ""
    assert claim["verification_reason_code"] == "scenario_target_not_canonical"
    assert claim["candidate_count"] == 0


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


def test_evidence_claims_ignore_numbered_narrative_headings():
    from evidence_exit_gate import extract_numeric_claims

    claims = extract_numeric_claims(
        "- **🐂 做多核心論點：** 1. AI 伺服器需求升溫。\n"
        "- **數據/證據：** 1. 市場資料仍需人工確認。"
    )

    assert not any(claim["reported_value"] == 1.0 for claim in claims)


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
