from copy import deepcopy
import pytest

from test_tewc_quarterly_reference import reference


def projected():
    from official_financial_projection import project_official_financials
    return project_official_financials({'ticker': '1623.TW', 'company_name': '大東電',
        'financial_currency': 'TWD', 'free_cash_flow_raw': -461411616,
        'operating_cash_flow_raw': -189755008, 'debt_to_equity': '70.65%'}, reference())


def checked(text, data=None):
    from evidence_exit_gate import evaluate_report_evidence
    return evaluate_report_evidence(text, {'data': projected() if data is None else data})['sampled_claims']


@pytest.mark.parametrize('prefix', ['TTM', '本公司TTM', 'TTM期間2025-07-01至2026-06-30',
                                  '本公司2025年7月1日至2026年6月30日'])
def test_official_fcf_exact_period_and_source_are_replayed(prefix):
    claims = checked(prefix + '自由現金流為0.0885億元。')
    assert len(claims) == 1
    claim = claims[0]
    assert claim['status'] == 'verified', claim
    assert claim['independent_primary_source_verified'] is True
    assert claim['historical_pit_verified'] is False
    assert claim['matched_path'].endswith('facts.cashflows.ttm.free_cash_flow')


@pytest.mark.parametrize('prefix', ['2024年度', 'TTM期間2024-07-01至2025-06-30', '同業TTM',
                                  '華通TTM', 'TTM上半年', '本公司2025年7月至2026年6月'])
def test_other_period_or_owner_never_borrows_selected_official_fcf(prefix):
    claim = checked(prefix + '自由現金流為0.0885億元。')[0]
    assert claim['status'] == 'unverifiable', claim


@pytest.mark.parametrize('amount', ['-0.0885', '0.885', '8.85'])
def test_official_fcf_sign_and_units_cannot_be_relaxed(amount):
    assert checked('TTM自由現金流為' + amount + '億元。')[0]['status'] == 'mismatch'


def test_future_scenario_remains_unobserved_and_original_data_is_unchanged():
    data = projected(); before = deepcopy(data)
    claim = checked('若未來TTM自由現金流為0.0885億元，才考慮提高評等。', data)[0]
    assert claim['status'] == 'unverifiable'
    assert claim['verification_reason_code'] == 'financial_projection_not_observed_fact'
    assert data == before


@pytest.mark.parametrize('text,status', [
    ('2026-06-30總負債／權益：66.67%', 'verified'),
    ('2026-06-30總負債／權益：46.67%', 'mismatch'),
    ('2026-06-30借款與租賃負債／權益：46.67%', 'verified'),
    ('2026-06-30負債權益比：46.67%', 'unverifiable'),
    ('2025-06-30總負債／權益：66.67%', 'unverifiable'),
])
def test_ratio_requires_same_date_and_explicit_definition(text, status):
    from evidence_official_financial_claims import official_ratio_claim
    value = float(text.partition('：')[2][:-1])
    claim = {'label': text.partition('：')[0], 'unit': '%', 'reported_value': value, 'raw_text': text}
    result = official_ratio_claim(claim, {'data': projected()}, 1.0)
    assert result['status'] == status


def test_missing_receipt_or_changed_raw_never_inherits_official_verification():
    data = projected()
    data['free_cash_flow_raw'] = 8850000 * 10
    claim = checked('TTM自由現金流為0.885億元。', data)[0]
    assert claim['status'] == 'unverifiable'
    assert claim['independent_primary_source_verified'] is False


@pytest.mark.parametrize('compact,dense,role', [(False,False,False), (True,True,False), (True,True,True)])
def test_model_receives_official_definition_without_private_receipt_paths(compact, dense, role):
    from prompt_builder import format_data_for_prompt
    data = projected(); data['_prompt_agent_num'] = 6
    text = format_data_for_prompt(data, compact=compact, dense=dense, role_scoped=role)
    assert '2025-07-01' in text and '2026-06-30' in text
    assert 'free_cash_flow_definition' in text
    assert 'official-response-evidence' not in text and 'raw_response_path' not in text
    assert 'original_quote_sha256' not in text
