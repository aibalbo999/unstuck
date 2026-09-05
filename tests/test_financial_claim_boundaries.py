"""Regression coverage for financial claim ownership and actual-period pairing."""

import pytest

from financial_output_validator import extract_revenue_mentions, validate_analysis_output


def issues_for(text, agent=14):
    return "\n".join(validate_analysis_output(agent, text, {}))


GROWTH_ISSUES = ("雙重樂觀紅線", "製造業情境紅線", "FCF 品質紅線")


@pytest.mark.parametrize("text", [
    "當前 Forward P/E 28.44x，營收成長偏差0%；利潤率偏差0%；WACC9.88%。",
    "Forward P/E 31x，營收成長9.88%，FCF轉換率106%。",
    "Forward P/E 31x，營收成長-78%，FCF轉換率106%。",
    "Forward P/E 31x，營收成長0%；淨利率88%，FCF轉換率106%。",
    "Forward P/E 31x，營收成長尚待確認。WACC為9.88%，FCF轉換率106%。",
    "Forward P/E 31x，營收成長尚待確認\n利潤率為88%，FCF轉換率106%。",
    "Forward P/E 31x，營收成長偏差0%，利潤率偏差0%，WACC9.88%。",
    "Forward P/E 31x，若營收成長低於60%，則停止買入。",
    "Forward P/E 31x，營收成長60%是加碼條件，尚未達成。",
    "Forward P/E 31x，Forward EPS 隱含營收需成長9.88%。",
    "Forward P/E 31x，營收成長未定，毛利率提升88%。",
    "Forward P/E 31x，營收成長60%才加碼。",
])
def test_growth_rules_do_not_borrow_other_metrics_or_condition_thresholds(text):
    issues = issues_for(text)
    assert not any(issue in issues for issue in GROWTH_ISSUES)


@pytest.mark.parametrize("growth", ["50%", "50.5%", "78%", "196.0%"])
def test_real_growth_double_counting_and_fcf_risk_remain(growth):
    issues = issues_for(f"Forward P/E 給予27x，Forward EPS 隱含營收需成長{growth}，FCF轉換率106.5%。")
    for issue in GROWTH_ISSUES:
        assert issue in issues


def test_manufacturing_forecast_still_needs_capacity_discussion():
    assert "製造業情境紅線" in issues_for("未來一年營收成長70.5%。", agent=5)


def test_low_decimal_fcf_conversion_does_not_match_its_tail():
    assert "FCF 品質紅線" not in issues_for("營收成長73%，FCF轉換率10.106%。", agent=2)


@pytest.mark.parametrize("text", [
    "年度營收554.89億，月營收670.73億。若月營收年增率跌破15%，則停損。",
    "年度營收554.89億，月營收670.73億，月營收年增率為15%。",
    "月營收670.73億，年度營收554.89億，營收年增率15%是停損條件。",
    "2024年營收100億，2025年營收120億。若營收年增率為50%，才加碼。",
    "2024年營收100億，2025年營收120億。營收年增率50%為加碼門檻。",
    "2024年營收100億。樂觀情境：2025年營收200億，營收年增率50%。",
    "2024年營收100億。2025年預估營收200億，營收年增率50%。",
    "2024年營收100億，2025年營收120億。\n## 停損條件\n營收年增率50%。",
    "2024年營收100億。\n## 樂觀情境\n2025年營收200億，營收年增率50%。",
    "A部門營收100億，B部門營收120億，營收年增率50%。",
    "營收100億，營收120億，營收年增率50%。",
    "2023年營收100億，2025年營收120億，營收年增率50%。",
    "2025年7月營收100億，2025年8月營收120億，月營收年增率50%。",
    "2024年營收100億，2025年營收120億，月營收年增率50%。",
])
def test_revenue_arithmetic_requires_comparable_actual_claims(text):
    assert "算術一致性紅線" not in issues_for(text, agent=16)


@pytest.mark.parametrize("text, expected", [
    ("2024年營收100億，2025年營收120億，營收年增率50%。", "20.0%"),
    ("2025年營收120億，2024年營收100億，營收年增率50%。", "20.0%"),
    ("前一年度營收100億，最新年度營收80億，營收成長率50%。", "-20.0%"),
    ("2024年營收100億。2025年營收120億。營收年增率50%。", "20.0%"),
    ("2024年8月營收100億，2025年8月營收120億，月營收年增率50%。", "20.0%"),
    ("上月營收100億，本月營收120億，月營收月增率50%。", "20.0%"),
    ("基期營收100億，本期營收120億，營收成長率50%。", "20.0%"),
    ("2025年營收為72.7B，TTM營收為99.79B，營收年增率高達196.0%。", "37.3%"),
    ("2024年營收10B，2025年營收120億，營收年增率50%。", "20.0%"),
])
def test_actual_revenue_arithmetic_contradictions_remain(text, expected):
    issues = issues_for(text, agent=16)
    assert "算術一致性紅線" in issues
    assert expected in issues


def test_each_actual_growth_claim_is_checked_without_borrowing_forecasts():
    text = (
        "2023年營收100億，2024年營收120億，營收年增率20%。"
        "2024年營收120億，2025年營收144億，營收年增率80%。"
        "樂觀情境：2026年營收200億。"
    )
    issues = issues_for(text, agent=16)
    assert "約為 20.0%，不是 80.0%" in issues
    assert "不是 20.0%" not in issues


@pytest.mark.parametrize("text", [
    "2024年營收100億，2025年營收120億。\n## 月營收\n營收年增率50%。",
    "2024年營收100億，2025年營收120億。假設營收為200億。營收年增率50%。",
    "2024年營收100億，2025年營收120億，營收成長率-17.3%是停損線。",
])
def test_arithmetic_does_not_cross_sections_or_conditional_figures(text):
    assert "算術一致性紅線" not in issues_for(text, agent=16)


def test_actual_claim_before_separate_condition_is_still_checked():
    text = "2024年營收100億，2025年營收120億，營收年增率50%，若動能減弱則停損。"
    assert "算術一致性紅線" in issues_for(text, agent=16)


def test_revenue_mentions_keep_monthly_and_annual_labels():
    mentions = extract_revenue_mentions("年度營收554.89億，月營收670.73億。")
    assert [item["label"] for item in mentions] == ["年度", "月"]


@pytest.mark.parametrize("text", [
    "## 競爭優勢\n具備零組件行業內之供應鏈商譽，但缺乏終端品牌溢價與定價權。",
    "## 競爭優勢\n企業依靠長期交易累積的良好商譽。",
    "公司在客戶間享有商譽，帶來競爭優勢。",
    "公司沒有併購商譽，獲利穩健。",
])
def test_reputation_is_not_accounting_goodwill(text):
    assert "商譽盲點紅線" not in issues_for(text, agent=12)


@pytest.mark.parametrize("text", [
    "公司收購後認列大量商譽，獲利穩健。",
    "資產負債表列示商譽120億，ROE高。",
    "商譽帳面價值200億，具備競爭優勢。",
    "## 競爭優勢\n公司享有供應鏈商譽。另有併購產生的商譽80億。",
])
def test_accounting_goodwill_risk_is_not_disabled(text):
    assert "商譽盲點紅線" in issues_for(text, agent=12)


@pytest.mark.parametrize("text", [
    "美國10年期公債殖利率處於4.784%高位。缺乏足夠的安全邊際來吸引機構資金。",
    "美國公債殖利率12%，具有吸引力。",
    "公司債殖利率12%，建議買入。",
    "股票殖利率4.784%，建議買入。",
    "股息殖利率10.5%，但不具吸引力。",
    "股息殖利率12%，缺乏足夠的安全邊際來吸引機構資金。",
    "股息殖利率12%，不建議買入。",
    "股息殖利率12%，不能視為低估或優質配息。",
    "股息殖利率12%，尚不足以吸引資金。",
    "股息殖利率12%。技術面低估，建議買入。",
    "公司股息殖利率2%，公債殖利率12%，值得買入。",
    "公司股息殖利率12%，公債殖利率4.8%具有吸引力。",
    "公司股息殖利率12%，並不吸引投資人。",
    "## 美國公債\n殖利率12%，具有吸引力。",
    "公司股息殖利率12%，公債4.8%具有吸引力。",
    "股息殖利率12%，未具吸引力。",
])
def test_dividend_risk_requires_equity_yield_and_affirmative_local_claim(text):
    assert "高殖利率陷阱紅線" not in issues_for(text, agent=15)


@pytest.mark.parametrize("yield_value", ["10%", "10.5%", "12%", "25.75%", "100%"])
def test_real_high_dividend_buy_claims_remain(yield_value):
    assert "高殖利率陷阱紅線" in issues_for(f"公司股息殖利率{yield_value}，值得買入。", agent=15)


def test_bond_context_does_not_hide_a_separate_stock_yield_claim():
    text = "美國公債殖利率4.8%。公司股息殖利率10.5%，具備吸引力。"
    assert "高殖利率陷阱紅線" in issues_for(text, agent=15)


def test_explicit_stock_subject_overrides_bond_heading():
    text = "## 公債比較\n公司股息殖利率10.5%，具有吸引力。"
    assert "高殖利率陷阱紅線" in issues_for(text, agent=15)


def test_negated_claim_does_not_hide_a_later_affirmative_yield_claim():
    text = "股息殖利率12%，不建議買入。但股息殖利率15%，已具備吸引力。"
    assert "高殖利率陷阱紅線" in issues_for(text, agent=15)


def test_irrelevant_negation_does_not_hide_actual_high_growth():
    text = "目前WACC並不低，營收成長78%，Forward P/E 給予27x。"
    assert "雙重樂觀紅線" in issues_for(text)


def test_goodwill_reputation_after_acquisition_is_not_an_accounting_balance():
    text = "公司收購工廠後仍維持供應鏈商譽，具有競爭優勢。"
    assert "商譽盲點紅線" not in issues_for(text, agent=12)


@pytest.mark.parametrize("text, issue", [
    ("營收成長73%，FCF轉換率106%，需要拆解營運資金。", "FCF 品質紅線"),
    ("營收成長70%，須增加CapEx。", "製造業情境紅線"),
    ("股息殖利率12%，具吸引力，配息率50%。", "高殖利率陷阱紅線"),
    ("併購產生商譽80億，獲利穩健，但需關注商譽減損。", "商譽盲點紅線"),
])
def test_existing_caveats_still_suppress_respective_rules(text, issue):
    assert issue not in issues_for(text)


@pytest.mark.parametrize("text", [
    "2024年營收100億，2025年營收120億，營收年增率40%，預期明年毛利率改善。",
    "預期明年毛利率改善，2024年營收100億，2025年營收120億，營收年增率40%。",
    "2024年營收100億，預期明年毛利率改善，2025年營收120億，營收年增率40%。",
])
def test_unrelated_metric_outlook_does_not_hide_actual_revenue_arithmetic(text):
    assert "約為 20.0%，不是 40.0%" in issues_for(text, agent=16)


@pytest.mark.parametrize("text", [
    "2024年營收100億，預估2025年營收120億，營收年增率40%。",
    "2024年營收100億，2025年營收120億，預期營收年增率40%。",
    "樂觀情境：2024年營收100億，2025年營收120億，營收年增率40%。",
])
def test_revenue_related_projection_is_not_reclassified_as_actual(text):
    assert "算術一致性紅線" not in issues_for(text, agent=16)


@pytest.mark.parametrize("text", [
    "營收年增率40%，2024年營收100億，2025年營收120億。",
    "2024年營收100億，營收年增率40%，2025年營收120億。",
    "2024年營收80億，2025年營收100億。營收年增率40%，2024年營收100億，2025年營收120億。",
])
def test_growth_claim_can_own_figures_later_in_same_sentence(text):
    assert "約為 20.0%，不是 40.0%" in issues_for(text, agent=16)


@pytest.mark.parametrize("text", [
    "營收年增率40%。2024年營收100億，2025年營收120億。",
    "營收年增率40%，2024年營收100億，預估2025年營收120億。",
    "營收年增率40%，2024年營收100億，月營收120億。",
    "營收年增率40%，營收年增率20%，2024年營收100億，2025年營收120億。",
])
def test_forward_figure_lookup_does_not_cross_claim_or_period_boundaries(text):
    assert "算術一致性紅線" not in issues_for(text, agent=16)


@pytest.mark.parametrize("multiple", ["目標本益比上調至30x", "目標本益比調整為30x", "Forward P/E估值為30x"])
def test_explicit_multiple_modifiers_do_not_bypass_double_counting(multiple):
    text = f"Forward EPS隱含營收成長78%，{multiple}，已考慮CapEx。"
    assert "雙重樂觀紅線" in issues_for(text)


@pytest.mark.parametrize("multiple", ["目標本益比上調至3.30x", "目標本益比上調至-30x", "目標本益比尚未決定，ROE為30%"])
def test_multiple_modifiers_do_not_borrow_other_numbers(multiple):
    text = f"Forward EPS隱含營收成長78%，{multiple}，已考慮CapEx。"
    assert "雙重樂觀紅線" not in issues_for(text)


@pytest.mark.parametrize("continuation", [
    "因此以此高殖利率為主因建議買入。",
    "因此建議買入。",
    "此高殖利率具有吸引力，值得買入。",
])
def test_explicit_adjacent_dividend_rationale_is_checked(continuation):
    assert "高殖利率陷阱紅線" in issues_for("公司股息殖利率12%。" + continuation, agent=15)


@pytest.mark.parametrize("text", [
    "公司股息殖利率12%。技術面低估，建議買入。",
    "公司股息殖利率12%。因此技術面低估，建議買入。",
    "公司股息殖利率12%。營收改善。因此以此高殖利率為主因建議買入。",
    "公司股息殖利率12%。\n\n因此以此高殖利率為主因建議買入。",
    "公司股息殖利率12%\n\n因此以此高殖利率為主因建議買入。",
    "公司股息殖利率12%。\n## 債券\n因此建議買入。",
    "公司股息殖利率12%。因此建議買入公債。",
    "公司股息殖利率12%。因此建議買入公債，同時配置股票。",
    "公司股息殖利率12%。此高殖利率不具吸引力，但技術面低估。",
    "公司股息殖利率12%，公債殖利率4.8%。因此建議買入。",
    "公司股息殖利率12%。此高殖利率為買入條件，尚未達成。",
])
def test_dividend_continuation_must_be_local_affirmative_and_same_subject(text):
    assert "高殖利率陷阱紅線" not in issues_for(text, agent=15)
