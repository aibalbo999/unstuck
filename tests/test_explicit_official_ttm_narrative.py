from copy import deepcopy

import pytest

from evidence_official_financial_claims import official_fcf_claim
from test_official_financial_claim_binding import projected


def claim(prefix, *, suffix='', amount=0.0885):
    return {'financial_metric': 'FCF', 'financial_period_text': prefix,
            'financial_heading': '', 'financial_parent_context': '',
            'financial_amount_suffix': suffix, 'raw_text': prefix + 'FCF為' + str(amount) + '億元' + suffix,
            'reported_value': amount, 'financial_display_precision': 4, 'unit': '億元'}


@pytest.mark.parametrize('prefix', [
    '2025年度FCF為0.1億元，官方個別TTM（2025-07-01至2026-06-30）',
    '2025年度FCF轉換率為-28.05%（來源：工具計算），且官方個別TTM（2025-07-01至2026-06-30）',
    '風險摘要：\n獲利品質風險：2025年度FCF轉換率為-28.05%（來源：工具計算），且官方個別TTM（2025-07-01至2026-06-30）',
    '1.獲利品質受限於持續性負現金流：接受Agent21觀點。2025年度FCF為0.1億元，官方個別TTM（2025-07-01至2026-06-30）',
    '根據官方個別TTM（2025-07-01至2026-06-30）數據，營業現金流為0.12億元，加計總資本支出（CapEx）0.0315億元後，TTM',
])
def test_completed_annual_clause_cannot_replace_new_exact_ttm_scope(prefix):
    data = projected(); before = deepcopy(data)
    result = official_fcf_claim(claim(prefix), data, scale=100000000, tolerance_pct=1)
    assert result and result['status'] == 'verified', result
    assert result['financial_period'] == '2025-07-01/2026-06-30'
    assert result['independent_primary_source_verified'] is True
    assert result['historical_pit_verified'] is False
    assert data == before


@pytest.mark.parametrize('prefix', [
    '華通2025年度FCF為0.1億元，官方個別TTM（2025-07-01至2026-06-30）',
    '2025年度FCF為0.1億元，官方合併TTM（2025-07-01至2026-06-30）',
    '2025年度FCF為0.1億元，官方個別TTM（2024-07-01至2025-06-30）',
    '2025年度FCF為0.1億美元，官方個別TTM（2025-07-01至2026-06-30）',
    '根據官方個別TTM（2025-07-01至2026-06-30）數據，營業現金流為0.11億元，加計總資本支出（CapEx）0.0115億元後，TTM',
    '根據官方個別TTM（2025-07-01至2026-06-30）數據，營業現金流為0.10億元，加計總資本支出（CapEx）0.115億元後，TTM',
    '根據官方個別TTM（2025-07-01至2026-06-30）數據，營業現金流淨流出0.10億元，加計總資本支出（CapEx）0.0115億元後，TTM',
    '2025年度FCF為0.1億元，TTM',
    '風險摘要：華通2025年度FCF為0.1億元，官方個別TTM（2025-07-01至2026-06-30）',
    '1.獲利品質受限於持續性負現金流：接受Agent21觀點。華通2025年度FCF為0.1億元，官方個別TTM（2025-07-01至2026-06-30）',
    '根據官方個別TTM（2025-07-01至2026-06-30）數據，營業現金流淨流入-0.12億元，加計總資本支出（CapEx）0.0315億元後，TTM',
    '根據官方個別TTM（2025-07-01至2026-06-30）數據，營業現金流為0.1200000000000000000000000000000000000000億元，加計總資本支出（CapEx）0.0315億元後，TTM',
])
def test_bad_context_cannot_borrow_a_matching_ttm_amount(prefix):
    assert official_fcf_claim(claim(prefix), projected(), scale=100000000, tolerance_pct=1) is None


@pytest.mark.parametrize('suffix', ['，此為華通資料', '，以美元計價', '（合併口徑）', '，同業資料',
    '（台積電）', '（2024年度）', '（韓元）', '（日元）', '，此乃台積電數據'])
def test_trailing_owner_currency_or_statement_scope_remains_bound(suffix):
    text = '2025年度FCF為0.1億元，官方個別TTM（2025-07-01至2026-06-30）'
    assert official_fcf_claim(claim(text, suffix=suffix), projected(), scale=100000000, tolerance_pct=1) is None


def test_wrong_value_remains_a_mismatch_and_reference_change_fails_closed():
    text = '2025年度FCF為0.1億元，官方個別TTM（2025-07-01至2026-06-30）'
    data = projected()
    assert official_fcf_claim(claim(text, amount=0.885), data, scale=100000000, tolerance_pct=1)['status'] == 'mismatch'
    data['official_financial_projection']['reference']['quarterly_document']['sha256'] = '0' * 64
    assert official_fcf_claim(claim(text), data, scale=100000000, tolerance_pct=1) is None
