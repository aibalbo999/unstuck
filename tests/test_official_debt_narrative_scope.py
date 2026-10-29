from copy import deepcopy

import pytest

from test_tewc_quarterly_reference import reference
from official_financial_projection import project_official_financials
from evidence_exit_gate import evaluate_report_evidence


def projected():
    return project_official_financials({
        'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
        'free_cash_flow_raw': -461411616, 'operating_cash_flow_raw': -189755008,
        'debt_to_equity': '70.65%',
    }, reference())


def claims(text, data=None):
    gate = evaluate_report_evidence(text, {'data': projected() if data is None else data})
    return [row for row in gate['sampled_claims'] if row.get('official_debt_component')]


TEXT = ('- 依據 2026-06-30 官方個別財務報表原件（來源：`balance_sheet.debt_components`），'
        '大東電借款與租賃負債明細為：短期借款 0.01 億元、'
        '一年內到期之長期借款 {amount} 億元、長期借款 0.02 億元、'
        '流動租賃負債 0.003 億元、非流動租賃負債 0.004 億元，'
        '合計 0.042 億元（0.0042 billion_twd）。')


@pytest.mark.parametrize('amount,status', [('0.005', 'verified'), ('0.05', 'mismatch'), ('-0.005', 'mismatch')])
def test_local_original_statement_component_scope(amount, status):
    data = projected()
    before = deepcopy(data)
    row, = claims(TEXT.format(amount=amount), data)
    assert row['status'] == status
    assert row['financial_period'] == '2026-06-30'
    assert row['matched_path'].endswith('.current_portion_longterm_borrowings')
    assert data == before


@pytest.mark.parametrize('old,new', [
    ('大東電', '華通'), ('個別', '合併'), ('2026-06-30', '2025-06-30'),
    ('2026-06-30', ''), ('balance_sheet.debt_components', 'history.rows'),
    ('億元、長期借款', '億港元、長期借款'),
    ('明細為：', '明細預估為：'), ('非流動租賃負債', '其他公司非流動租賃負債'),
    ('。', '（華通資料）。'),
])
def test_unknown_owner_period_currency_source_or_forecast_stays_unknown(old, new):
    row, = claims(TEXT.format(amount='0.005').replace(old, new))
    assert row['status'] == 'unverifiable'
    assert not row['independent_primary_source_verified']


def test_nearby_header_does_not_supply_missing_date():
    text = '# 大東電官方個別2026-06-30\n' + TEXT.format(amount='0.005').replace('2026-06-30', '')
    row, = claims(text)
    assert row['status'] == 'unverifiable'


def test_missing_original_receipt_blocks_narrative_verification():
    data = projected()
    data['official_financial_projection']['reference']['quarterly_document']['sha256'] = '0' * 64
    row, = claims(TEXT.format(amount='0.005'), data)
    assert row['status'] == 'unverifiable'
