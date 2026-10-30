"""The Yahoo growth scalar must bind to its own claim, never the whole report."""

import pytest

from financial_output_validator import validate_analysis_output


def growth_issues(text, source="-9.5%", **data):
    return [issue for issue in validate_analysis_output(
        6, text, {"yahoo_revenue_growth": source, **data}
    ) if issue.startswith("成長率口徑紅線")]


@pytest.mark.parametrize("text", [
    "年度營收年增率20.62%。\nYahoo即期成長率-9.5%，短期承壓。",
    "年度營收年增率20.62%，Yahoo即期成長率-9.5%。",
    "年度營收年增率20.62%而Yahoo即期成長率-9.5%。",
    "年度營收年增率20.62%（Yahoo即期成長率-9.5%）。",
    "- 年度營收年增率：20.62%\n- Yahoo即期成長率：-9.5%",
    "| 指標 | 數值 |\n| --- | --- |\n| 年度營收年增率 | 20.62% |\n| Yahoo即期成長率 | -9.5% |",
    "| 年度營收年增率 | Yahoo即期成長率 |\n| --- | --- |\n| 20.62% | -9.5% |",
    "季度營收年增率-9.5%。",
    "Yahoo近期營收年增率-9.5%。",
    "不可將Yahoo revenueGrowth -9.5%寫成TTM營收成長。",
    "營收年增率-9.5%是錯誤示例，不採用。",
    "同業營收年增率-9.5%。",
    "本公司年度營收年增率19.5%。",
    "本公司年度營收年增率-19.5%。",
    "本公司年度營收年增率+9.5%。",
    "本公司年度營收年增率9.50%。",
    "2025年第4季營收年增率-9.5%。",
    "Yahoo即期營收成長率-9.5%，不可直接稱為年度營收年增率。",
    "Yahoo即期營收成長率-9.5%不可直接稱為年度營收年增率。",
    "2025年Yahoo近期營收年增率-9.5%。",
    "| 公司 | 年度營收年增率 |\n| --- | --- |\n| 同業 | -9.5% |",
    "| 年度營收年增率 | 季度營收年增率 |\n| --- | --- |\n| 20.62% | -9.5% |",
])
def test_unrelated_values_and_valid_scopes_do_not_borrow_yahoo_growth(text):
    assert growth_issues(text) == []


@pytest.mark.parametrize("text", [
    "年度營收年增率-9.5%。",
    "TTM營收成長-9.5%。",
    "全年營收成長率為-9.50%。",
    "Yahoo revenueGrowth為-9.5%，可視為TTM營收成長。",
    "年度營收年增率-9.5%。\n其他資料採季度口徑。",
    "年度營收年增率-9.5%，另列Yahoo近期成長率20%。",
    "Yahoo近期營收年增率-9.5%，因此TTM營收年增率-9.5%。",
    "Yahoo近期營收年增率-9.5%，可視為年度營收成長。",
    "- **年度營收年增率**：**−9.5%**\n- 季度口徑資料另見附表。",
    "| 指標 | 數值 |\n| --- | --- |\n| TTM營收年增率 | -9.5% |",
    "| 年度營收年增率 | Yahoo近期成長率 |\n| --- | --- |\n| -9.5% | -9.5% |",
    "| 公司 | 指標 | 數值 | 期間 |\n| --- | --- | --- | --- |\n| 本公司 | 營收成長率 | -9.5% | 年度 |",
    "# 年度營收\n營收成長率-9.5%。",
    "同業營收年增率20%，本公司年度營收年增率-9.5%。",
    "2025年營收成長率-9.5%。",
    "Yahoo季度營收成長率-9.5%等同全年營收成長率。",
    "年度營收年增率-9.5%，季度口徑資料另見附表。",
    "年度營收年增率-9.5%，其他數據不可直接稱為年度值。",
    "| 公司 | 年度營收年增率 |\n| --- | --- |\n| 同業 | 20% |\n| 本公司 | -9.5% |",
    "# 同業比較\n本公司年度營收年增率-9.5%。",
])
def test_actual_annual_relabelling_stays_blocked_with_local_evidence(text):
    assert growth_issues(text)


@pytest.mark.parametrize("source,text", [
    ("9.5%", "營收年增率19.5%。"),
    ("9.5%", "營收年增率-9.5%。"),
    ("9.5%", "營收年增率9.51%。"),
    ("-9.5%", "市場份額-9.5%，本公司年度營收年增率20.62%。"),
    (None, "營收年增率-9.5%。"),
    (True, "營收年增率1%。"),
    ("NaN", "營收年增率-9.5%。"),
])
def test_numeric_identity_is_signed_finite_and_exact(source, text):
    assert growth_issues(text, source) == []


def test_negative_scalar_matches_equivalent_display_precision():
    assert growth_issues("營收年增率−9.50%。")


def test_provider_and_annual_values_can_coincide_without_borrowing():
    assert growth_issues("根據年度財報，年度營收年增率-9.5%。",
                         latest_annual_revenue_growth="-9.5%") == []


def test_explicit_yahoo_relabelling_is_not_excused_by_equal_annual_value():
    assert growth_issues("Yahoo季度口徑-9.5%可直接作為年度營收年增率。",
                         latest_annual_revenue_growth="-9.5%")


def test_yahoo_source_in_adjacent_clause_is_not_certified_by_equal_annual_value():
    assert growth_issues("根據Yahoo資料，年度營收年增率-9.5%。",
                         latest_annual_revenue_growth="-9.5%")


@pytest.mark.parametrize("text", [
    "年度營收年增率：\n-9.5%。",
    "- **TTM營收成長率：**\n  **−9.50%**",
])
def test_explicit_metric_label_binds_a_single_wrapped_percentage(text):
    assert growth_issues(text)


@pytest.mark.parametrize("text", [
    "年度營收年增率：\n\n-9.5%。",
    "年度營收年增率：\nYahoo即期成長率-9.5%。",
    "年度營收年增率20.62%。\n-9.5%。",
    "季度營收年增率：\n-9.5%。",
])
def test_wrapped_value_binding_does_not_merge_independent_paragraphs(text):
    assert growth_issues(text) == []


@pytest.mark.parametrize("text", [
    "Yahoo 即期獲利年增率顯示為 -50.0%，營收年增率為 -9.5%，且 2026 年 5 月單月營收曾降至 3.56 億元。",
    "* **依據**：Yahoo 即期獲利年增率顯示為 -50.0%，營收年增率為 -9.5%。",
    "Yahoo近期盈餘成長率為-50%，營收年增率為-9.5%。",
    "Yahoo季度獲利年增率-50%、營收年增率-9.5%。",
])
def test_yahoo_period_scopes_adjacent_parallel_growth_metrics(text):
    assert growth_issues(text) == []


@pytest.mark.parametrize("text", [
    "Yahoo即期獲利年增率-50%。營收年增率-9.5%。",
    "Yahoo即期獲利年增率-50%；營收年增率-9.5%。",
    "Yahoo即期獲利年增率-50%\n營收年增率-9.5%。",
    "Yahoo即期獲利年增率-50%，年度營收年增率-9.5%。",
    "Yahoo即期獲利年增率-50%，TTM營收成長率-9.5%。",
    "Yahoo即期獲利年增率-50%，營收年增率-9.5%可直接作為年度成長。",
    "同業Yahoo即期獲利年增率-50%，本公司營收年增率-9.5%。",
    "Yahoo即期獲利年增率-50%，但營收年增率-9.5%。",
    "Yahoo即期獲利年增率-50%，相較之下本公司營收年增率-9.5%。",
    "Yahoo即期獲利年增率-50%，另一來源FactSet營收年增率-9.5%。",
    "Yahoo獲利年增率-50%，營收年增率-9.5%。",
    "Yahoo即期獲利年增率-50%，毛利率20%，營收年增率-9.5%。",
])
def test_parallel_metric_period_never_crosses_scope_boundaries(text):
    assert growth_issues(text)
