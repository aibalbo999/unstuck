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
    assert all(claim["status"] == "verified" for claim in result["sampled_claims"])


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
