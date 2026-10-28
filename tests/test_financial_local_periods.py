"""Local observed amounts must not inherit a different claim's period."""
import pytest

from evidence_exit_gate import evaluate_report_evidence


def data():
    return {'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
            'years': ['2022', '2023', '2024', '2025'],
            'revenue_history': [3.90, 4.6, 5.48, 6.61],
            'fcf_history': [0.1, 0.2, 0.08, -0.23],
            'net_income_history': [0.3, 0.4, 0.6, 0.82],
            'recent_monthly_revenue': ['2026年7月: NT$6.19億',
                                       '2026年8月: NT$4.82億',
                                       '2026年9月: NT$5.19億']}


def claims(text):
    result = evaluate_report_evidence(text, {'data': data()})
    assert result['coverage_complete']
    return [c for c in result['sampled_claims'] if c.get('financial_amount')]


@pytest.mark.parametrize('text,value', [
    ('反證：2026 年 9 月單月營收 5.19 億元。', 5.19),
    ('然而，2026 年 9 月單月營收為 5.19 億元。', 5.19),
    ('2025 年度 FCF 為 -2.3 億元；反證：2024 年度 FCF 為正值 0.8 億元。', 0.8),
    ('- **現金流持續承壓**：2025 年度歷史 FCF 為 -2.3 億元。', -2.3),
    ('大東電因自由現金流為負值（2025 年度 FCF 為 -2.3 億元），DCF unavailable。', -2.3),
    ('大東電 2025 年度淨利為 8.2 億元，但同年度自由現金流為 -2.3 億元。', -2.3),
    ('## 成長與估值假設對照\n  - 成長分析引文：*註：2025 年公司營收 66.1 億元（來源：data.history.rows）僅為已觀測之銷售基準。', 66.1),
    ('## 成長與估值假設對照\n  - 估值分析引文：大東電因自由現金流為負值（2025 年度 FCF 為 -2.3 億元），DCF unavailable。', -2.3),
])
def test_explicit_observed_local_period_has_its_own_source(text, value):
    selected = [c for c in claims(text) if c['reported_value'] == value]
    assert selected and all(c['status'] == 'verified' for c in selected)


@pytest.mark.parametrize('text', [
    '## 成長與估值假設對照\n- 成長分析引文：預期2025年公司營收66.1億元。',
    '## 假設情境\n- 成長分析引文：2025年公司營收66.1億元。',
    '## 成長與估值假設對照\n- 成長分析引文：同業華通2025年營收66.1億元。',
    '反證：同業華通2026年9月營收5.19億元。',
    '反證：2026年10月營收5.19億元。',
    '反證：2026年9月營收5.19億元，幣別美元。',
    '可證偽條件：月營收重新突破6億元並維持雙位數年增率。',
    '大東電2025年度淨利8.2億元，但同業華通同年度自由現金流-2.3億元。',
    '2026Q2，2025年度FCF為-2.3億元。',
])
def test_unbound_or_future_claim_does_not_borrow_observed_amount(text):
    selected = claims(text)
    assert selected and not any(c['status'] == 'verified' for c in selected[-1:])


@pytest.mark.parametrize('text', [
    '反證：2026 年 9 月單月營收 51.9 億元。',
    '- **現金流持續承壓**：2025 年度歷史 FCF 為 -0.23 億元。',
    '大東電 2025 年度淨利為 8.2 億元，但同年度自由現金流為 -0.23 億元。',
    '## 成長與估值假設對照\n- 成長分析引文：2025 年公司營收 6.61 億元。',
])
def test_wrong_value_in_new_observed_forms_is_mismatch(text):
    assert any(c['status'] == 'mismatch' for c in claims(text))


def test_observation_language_does_not_turn_a_dated_fact_into_a_forecast():
    from evidence_financial_amounts import extract_financial_amounts
    actual = extract_financial_amounts('若觀察官方個別 TTM（2025-07-01 至 2026-06-30），FCF 流出達 -2.47 億元。', [])
    assert actual and actual[0]['financial_actual']
    future = extract_financial_amounts('若預期官方個別 TTM（2025-07-01 至 2026-06-30），FCF 流出達 -2.47 億元。', [])
    assert future and not future[0]['financial_actual']


@pytest.mark.parametrize('text,values', [
    ('大東電 2022 至 2025 年之 3 年營收 CAGR 達 19.2282%，營收從 39 億元成長至 66.1 億元。', [39, 66.1]),
    ('2026年9月營收5.19億元雖高於8月之4.82億元，但仍低於2026年7月之6.19億元。', [5.19, 4.82, 6.19]),
    ('- 短期營收動能波動：雖然2022-2025年營收CAGR達19.23%，但2026年9月營收5.19億元雖較8月回升，仍未突破7月6.19億元的高點。', [5.19, 6.19]),
])
def test_observed_comparison_counts_every_amount_with_its_own_period(text, values):
    selected = claims(text)
    assert [c['reported_value'] for c in selected] == values
    assert all(c['status'] == 'verified' for c in selected)


@pytest.mark.parametrize('prefix,suffix', [
    ('同業華通', ''), ('未知公司', ''), ('預期', ''), ('若', ''),
    ('美元', ''), ('', '（合併）'), ('', '（同業華通）'), ('', '（美元）'),
])
def test_comparison_keeps_owner_currency_future_and_scope(prefix, suffix):
    text = prefix + '2022至2025年之3年營收CAGR達19.2%，營收從39億元成長至66.1億元' + suffix + '。'
    selected = claims(text)
    assert len(selected) >= 2
    assert not any(c['status'] == 'verified' for c in selected)


def test_monthly_comparison_does_not_hide_wrong_or_future_amounts():
    selected = claims('2026年9月營收5.19億元雖高於8月之48.2億元，但仍低於2026年7月之6.19億元。可證偽條件：月營收重新突破6億元。')
    assert {c['reported_value'] for c in selected} == {5.19, 48.2, 6.19, 6}
    assert next(c for c in selected if c['reported_value'] == 48.2)['status'] == 'mismatch'
    assert next(c for c in selected if c['reported_value'] == 6)['status'] == 'unverifiable'


@pytest.mark.parametrize('text', [
    '同業華通2026年9月營收5.19億元雖高於8月之4.82億元，但仍低於2026年7月之6.19億元。',
    '2026年9月營收5.19億元雖高於8月之4.82億元，但仍低於2026年7月之6.19億元（美元）。',
    '預期2026年9月營收5.19億元雖高於8月之4.82億元，但仍低於2026年7月之6.19億元。',
    '2026年1月營收5.19億元雖高於12月之4.82億元，但仍低於2026年7月之6.19億元。',
])
def test_monthly_comparison_has_no_unknown_owner_currency_or_year_shortcut(text):
    selected = claims(text)
    assert len(selected) >= 3
    assert not any(c['status'] == 'verified' for c in selected)


def test_empirical_comparison_heading_does_not_forecast_its_dated_facts():
    text = '### 二、 成長預期與媒體報導之實證落差\n- 短期營收動能波動：雖然2022-2025年營收CAGR達19.23%，但2026年9月營收5.19億元雖較8月回升，仍未突破7月6.19億元的高點。'
    selected = claims(text)
    assert len(selected) == 2
    assert all(c['status'] == 'verified' for c in selected)
    selected = claims(text.replace('但2026年9月', '但預期2026年9月'))
    assert not any(c['status'] == 'verified' for c in selected)


@pytest.mark.parametrize('text', [
    '## 成長與估值假設對照\n- 成長分析引文：合併2025年公司營收66.1億元。',
    '## 成長與估值假設對照\n- 估值分析引文：大東電合併2025年度FCF為-2.3億元。',
    '2024年度FCF為0.8億元；反證：合併2025年度FCF為-2.3億元。',
    '合併2022至2025年之3年營收CAGR達19.2%，營收從39億元成長至66.1億元。',
    '合併2026年9月營收5.19億元雖高於8月之4.82億元，但仍低於2026年7月之6.19億元。',
])
def test_new_presentation_routes_do_not_assert_a_consolidated_scope(text):
    assert not any(c['status'] == 'verified' for c in claims(text)[-1:])


@pytest.mark.parametrize('suffix', ['（同業大亞）', '（合併報表）', '（2024年度）', '（淨流入）', '，此為大亞資料'])
def test_new_local_annual_binding_keeps_postfix_scope_and_direction(suffix):
    selected = claims('- 現金流持續承壓：2025年度歷史FCF為-2.3億元' + suffix + '。')
    assert selected and not any(c['status'] == 'verified' for c in selected)


def test_existing_annual_cashflow_with_separate_conversion_ratio_keeps_source():
    checked = claims('- 發現：獲利品質受現金流限制，2025年度FCF為-2.3億元，FCF轉換率（FCF/淨利）為-28.05%。')
    assert checked and checked[0]['status'] == 'verified'
    for suffix in ('（同業華通）', '（合併）', '，此為大亞資料'):
        assert claims('- 發現：獲利品質受現金流限制，2025年度FCF為-2.3億元，FCF轉換率（FCF/淨利）為-28.05%' + suffix + '。')[0]['status'] != 'verified'


@pytest.mark.parametrize('suffix', [
    '（來源：data.history.rows）（同業華通）',
    '（來源：data.history.rows）（合併報表）',
    '（來源：data.history.rows），此為華通資料',
    '（來源：data.history.rows），幣別美元',
    '（來源：data.history.rows）（2024年度）',
    '（來源：data.history.rows），預計明年仍為此金額',
])
def test_source_path_dots_do_not_truncate_quoted_postfix_scope(suffix):
    text = '## 成長與估值假設對照\n- 成長分析引文：2025年公司營收66.1億元' + suffix + '。'
    assert all(c['status'] != 'verified' for c in claims(text))
