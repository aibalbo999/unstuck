from copy import deepcopy
import json

import pytest

from official_financial_projection import project_official_financials
from official_income_prompt import official_income_prompt_facts
from test_tewc_income_reference import income_reference


def selected_income():
    return project_official_financials({'ticker': '1623.TW', 'company_name': '大東電',
        'financial_currency': 'TWD', 'net_income_ttm_raw': 999, 'free_cash_flow_raw': 123},
        income_reference()['financial_reference'])


def test_official_income_has_its_own_basis_without_replacing_provider_or_input():
    data = selected_income(); before = deepcopy(data)
    facts = official_income_prompt_facts(data)
    assert facts['net_income_ttm_raw'] == 3200000
    assert data['net_income_ttm_raw'] == 999 and data == before
    assert facts['currency'] == 'TWD' and facts['report_scope'] == 'individual'
    assert facts['monetary_amount_unit'] == 'TWD' and facts['ratio_unit'] == 'percent'
    assert facts['ttm_eps_verified'] is False and facts['share_count_bridge_verified'] is False
    assert facts['historical_pit_verified'] is False and facts['native_acquisition'] is False
    assert 'raw_response_path' not in json.dumps(facts)
    assert 'financial_reference' not in facts and 'ttm_eps' not in facts


@pytest.mark.parametrize('compact,dense,role', [(False,False,False),(True,True,False),(True,True,True)])
def test_prompt_carries_qualified_income_and_eps_limit_without_private_receipts(compact,dense,role):
    from prompt_builder import format_data_for_prompt
    data = selected_income(); data['_prompt_agent_num'] = 6; before = deepcopy(data)
    text = format_data_for_prompt(data,compact=compact,dense=dense,role_scoped=role)
    assert 'official_income_facts' in text and '3200000' in text
    assert 'share_count_bridge_verified' in text and 'weighted-average-share bridge' in text
    assert 'raw_response_path' not in text and 'official-response-evidence' not in text
    assert data == before


def test_unverified_selected_reference_never_supplies_income():
    data = selected_income()
    data['official_financial_projection']['reference']['quarterly_document']['sha256'] = '0' * 64
    assert official_income_prompt_facts(data) is None


def test_legacy_quote_or_caller_income_does_not_become_official():
    assert official_income_prompt_facts({'ticker':'1623.TW', 'financial_currency':'TWD',
        'net_income_ttm_raw':3200000, 'official_income_facts':{'status':'income_originals_verified'}}) is None
