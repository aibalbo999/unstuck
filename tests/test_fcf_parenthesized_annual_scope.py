"""A locally dated annual parenthesis must not borrow the preceding TTM."""
import pytest

from evidence_exit_gate import evaluate_report_evidence


ACTUAL = ('- **發現**：現金流品質存在缺口，官方個別財報 TTM（2025-07-01 至 2026-06-30）'
          '自由現金流（FCF）為 -2.47 億元，FCF 轉換率為 -30.16%。'
          '（來源：data.cash_flow.official_reference、data.cash_flow.official_income_facts；'
          'TTM 期間為 2025-07-01 至 2026-06-30，採個別財報口徑。）；'
          '反證：2024 年度曾短暫實現 FCF 正值（0.08 億元），但 2025 年度與最新 TTM 均轉為負值，'
          '顯示營運資金占用或資本支出壓力仍大。')


def checked(text, **changes):
    data = {'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
            'years': ['2024', '2025'], 'fcf_history': [0.08, -0.23],
            'free_cash_flow_raw': -247269000, **changes}
    result = evaluate_report_evidence(text, {'data': data})
    assert result['coverage_complete']
    return result


@pytest.mark.parametrize('number,status', [('0.08', 'mismatch'), ('0.8', 'verified')])
def test_actual_ttm_then_parenthesized_annual_keeps_each_amount_and_own_period(number, status):
    text = '## 證據時點與來源\n' + ACTUAL.replace('0.08 億元', number + ' 億元')
    result = checked(text)
    assert result['claim_count'] == 2
    claim = next(c for c in result['sampled_claims'] if c['reported_value'] == float(number))
    assert claim['status'] == status
    assert claim['financial_period'] == '2024'
    assert claim['source_value'] == 0.08 and claim['source_unit'] == 'billion_twd'
    assert claim['matched_path'] == 'data.fcf_history[0]'
    assert claim['raw_text'] == text.splitlines()[1]
    assert not claim['independent_primary_source_verified']


@pytest.mark.parametrize('text', [
    '大東電2024年度曾短暫實現FCF正值（0.8億元）。',
    '反證：2024年度曾短暫實現自由現金流正值（0.8億元）。',
    '2024年度曾短暫實現FCF正值（0.8億元）；官方個別TTM自由現金流為-2.47269億元。',
])
def test_standalone_or_following_different_period_does_not_erase_annual(text):
    claim = next(c for c in checked(text)['sampled_claims'] if c['reported_value'] == .8)
    assert claim['status'] == 'verified' and claim['financial_period'] == '2024'


@pytest.mark.parametrize('prefix,suffix', [
    ('同業華通', ''), ('未知公司', ''), ('台積電', ''), ('美元', ''), ('韓元', ''),
    ('合併', ''), ('官方個別財報', ''), ('預期', ''), ('若', ''),
    ('2026Q2，', ''), ('2023年度；', ''), ('TTM；', ''),
    ('', '（同業華通）'), ('', '（台積電）'), ('', '（合併）'), ('', '（個別財報）'),
    ('', '（美元）'), ('', '（韓元）'), ('', '（2025年度）'), ('', '，此為台積電資料'),
    ('', '，預期未來實現'),
])
def test_unknown_owner_period_currency_scope_future_and_postfix_cannot_borrow_history(prefix, suffix):
    text = prefix + '2024年度曾短暫實現FCF正值（0.8億元）' + suffix + '。'
    result = checked(text)
    assert result['claim_count'] >= 1
    assert not any(c['status'] == 'verified' for c in result['sampled_claims'])


@pytest.mark.parametrize('prefix', ['同業華通', '未知公司', '美元', '合併'])
def test_previous_other_source_is_not_dropped_at_annual_boundary(prefix):
    text = ACTUAL.replace('官方個別財報 TTM', prefix + '官方個別財報 TTM').replace('0.08 億元', '0.8 億元')
    claim = next(c for c in checked(text)['sampled_claims'] if c['reported_value'] == .8)
    assert claim['status'] != 'verified'


@pytest.mark.parametrize('heading', ['## 同業華通', '## 台積電', '## 合併財報', '## 官方個別財報', '## 預期情境'])
def test_heading_does_not_silently_supply_issuer_or_scope(heading):
    result = checked(heading + '\n2024年度曾短暫實現FCF正值（0.8億元）。')
    assert result['claim_count'] >= 1
    assert not any(c['status'] == 'verified' for c in result['sampled_claims'])


@pytest.mark.parametrize('text', [
    '2024年度曾短暫實現FCF正值（0.8萬元）。',
    '2024年度曾短暫實現FCF正值（0.8十億元）。',
    '2025年度曾短暫實現FCF正值（0.8億元）。',
])
def test_wrong_unit_or_available_year_is_compared_to_actual_year(text):
    assert checked(text)['failed_count'] == 1


@pytest.mark.parametrize('text', [
    '2024年度曾短暫實現FCF正值（-0.8億元）。',
    '2024年度曾短暫實現FCF負值（0.8億元）。',
    '2025年度曾短暫實現FCF正值（-2.3億元）。',
])
def test_parenthesized_direction_cannot_turn_contradictory_sign_into_verified(text):
    assert not any(c['status'] == 'verified' for c in checked(text)['sampled_claims'])


@pytest.mark.parametrize('qualifier', ['同業華通', '未知公司', '合併', '個別財報', '韓元'])
def test_metric_to_parenthesis_link_cannot_hide_unbound_scope(qualifier):
    result = checked('2024年度曾短暫實現FCF' + qualifier + '正值（0.8億元）。')
    assert result['claim_count'] >= 1
    assert result['verified_count'] == 0


def test_missing_financial_currency_or_history_remains_unknown():
    text = '2024年度曾短暫實現FCF正值（0.8億元）。'
    for changes in ({'financial_currency': ''}, {'fcf_history': []}, {'years': ['2023', '2025']}):
        assert checked(text, **changes)['verified_count'] == 0


@pytest.mark.parametrize('tail_year,changes', [
    ('2024', {}), ('2030', {}),
    ('2025', {'fcf_history': [0.08, 0.23]}),
    ('2025', {'fcf_history': [0.08, 0]}),
    ('2025', {'fcf_history': [0.08, float('-inf')]}),
    ('2025', {'fcf_history': [0.08, -0.23, -0.23]}),
    ('2025', {'years': ['2024', '2025', '2025'], 'fcf_history': [0.08, -0.23, -0.23]}),
    ('2025', {'free_cash_flow_raw': None}),
    ('2025', {'free_cash_flow_raw': 0}),
    ('2025', {'free_cash_flow_raw': 247269000}),
    ('2025', {'free_cash_flow_raw': float('-inf')}),
])
def test_annual_negative_tail_requires_a_different_saved_year_and_two_finite_negative_values(tail_year, changes):
    text = '2024年度曾短暫實現FCF正值（0.8億元），但' + tail_year + '年度與最新TTM均轉為負值。'
    result = checked(text, **changes)
    assert result['claim_count'] == 1
    assert result['sampled_claims'][0]['raw_text'] == text
    assert result['sampled_claims'][0]['status'] == 'unverifiable'


def test_saved_negative_tail_does_not_certify_official_ttm_period():
    text = '2024年度曾短暫實現FCF正值（0.8億元），但2025年度與最新TTM均轉為負值。'
    claim = checked(text)['sampled_claims'][0]
    assert claim['status'] == 'verified'
    assert claim['financial_period'] == '2024'
    assert claim['matched_path'] == 'data.fcf_history[0]'
    assert not claim['independent_primary_source_verified']
