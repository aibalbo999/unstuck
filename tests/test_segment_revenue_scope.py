"""Product revenue remains a claim, but cannot borrow issuer total revenue."""
import pytest

from evidence_exit_gate import evaluate_report_evidence
from financial_money_claims import financial_money_claim_issues


def source():
    return {'ticker': '1623.TW', 'company_name': '大東電',
            'financial_currency': 'TWD', 'years': ['2024', '2025'],
            'revenue_history': [5.48, 6.61], 'revenue_ttm_raw': 7e9}


def evidence(text):
    return evaluate_report_evidence(text, {'data': source()})


@pytest.mark.parametrize('text', [
    '2025 年特高壓電纜營收達 27.04 億元新臺幣（占營收 40.93%）。',
    '2025年中高壓電纜營收為66.1億元。',
    '2025年甲產品營收為6.61億元。',
    '2025年產品線營收為27.04億元。',
    '2025年A分部營收為27.04億元。',
    '2025年甲事業部營收為27.04億元。',
    '2025年特高壓電纜合計營收為66.1億元。',
    'TTM特高壓電纜營收為70億元。',
    '## 產品分部\n2025年營收為27.04億元。',
    '特高壓電纜：\n- 2025年營收為27.04億元。',
])
def test_explicit_segment_is_retained_unknown_even_when_it_equals_total(text):
    result = evidence(text)
    claims = result['sampled_claims']
    assert claims and result['coverage_complete']
    assert result['claim_count'] == result['sampled_count']
    assert result['failed_count'] == result['verified_count'] == 0
    assert all(c['status'] == 'unverifiable' and not c['matched_path'] for c in claims)
    assert not financial_money_claim_issues(text, source())


@pytest.mark.parametrize('text', [
    '本公司2025年總營收為6.61億元。',
    '2025年營收為6.61億元。',
    '公司業務穩定，2025年總營收為6.61億元。',
    '2025年特高壓電纜營收為27.04億元，公司2025年總營收為6.61億元。',
    '2025年特高壓電纜營收為27.04億元；2025年合計營收為6.61億元。',
    '2025年特高壓電纜營收為27.04億元，而本公司2025年總額營收為6.61億元。',
    '## 產品分部\n本公司2025年總營收為6.61億元。',
])
def test_issuer_total_mismatch_is_not_exempted_by_nearby_segment(text):
    result = evidence(text)
    bad = [c for c in result['sampled_claims'] if c['status'] == 'mismatch']
    assert result['coverage_complete'] and len(bad) == 1
    assert bad[0]['reported_value'] == 6.61
    assert bad[0]['matched_path'] == 'data.revenue_history[1]'
    assert financial_money_claim_issues(text, source())


def test_explicit_total_after_segment_can_still_be_verified():
    result = evidence('2025年特高壓電纜營收為27.04億元，公司2025年總營收為66.1億元。')
    assert result['claim_count'] == 2 and result['coverage_complete']
    assert result['failed_count'] == 0
    assert result['unverifiable_count'] == result['verified_count'] == 1


@pytest.mark.parametrize('text', [
    '同業華通2025年特高壓電纜營收為27.04億元。',
    '同業華通2025年總營收為6.61億元。',
    '2023年特高壓電纜營收為27.04億元。',
    '2023年公司總營收為6.61億元。',
])
def test_other_owner_and_missing_period_do_not_borrow_current_total(text):
    result = evidence(text)
    assert result['claim_count'] and result['coverage_complete']
    assert result['failed_count'] == result['verified_count'] == 0


@pytest.mark.parametrize('text', [
    '## 電纜產業\n本公司2025年營收為6.61億元。',
    '## 電纜產業\n2025年營收為6.61億元。',
    '## 產品概述\n本公司2025年營收為6.61億元。',
    '## 產品分部\n本公司2025年營收為6.61億元。',
    '## 產品分部\n大東電2025年營收為6.61億元。',
])
def test_industry_heading_or_explicit_issuer_does_not_hide_total_mismatch(text):
    result = evidence(text)
    assert result['coverage_complete'] and result['failed_count'] == 1
    assert result['sampled_claims'][0]['matched_path'] == 'data.revenue_history[1]'
    assert financial_money_claim_issues(text, source())


def test_explicit_issuer_does_not_erase_its_local_product_scope():
    result = evidence('## 電纜產業\n本公司2025年特高壓電纜營收為6.61億元。')
    assert result['coverage_complete'] and result['unverifiable_count'] == 1
    assert result['failed_count'] == result['verified_count'] == 0
