"""CapEx definitions use synthetic replayable original cash-flow components."""
from copy import deepcopy
from hashlib import sha256
from datetime import datetime, timezone
import time
from xml.etree import ElementTree as ET

import pytest

from test_tewc_quarterly_reference import reference, IX


def projected():
    from official_response_evidence import archive_response, read_response
    from official_financial_projection import project_official_financials
    value = reference()
    amounts = {
        'annual_document': {'d2025': (133317, 6352)},
        'quarterly_document': {'d2026': (21312, 0), 'd2025': (103238, 229)},
    }
    for name, periods in amounts.items():
        doc = value[name]
        root = ET.fromstring(read_response(doc['raw_receipt']))
        for node in root.iter(IX + 'nonFraction'):
            pair = periods.get(node.get('contextRef'))
            tag = node.get('name', '')
            index = 0 if 'PurchaseOfPropertyPlantAndEquipment' in tag else 1 if 'PurchaseOfIntangible' in tag else None
            if pair is not None and index is not None:
                node.text = str(pair[index])
                node.attrib.pop('sign', None)
                if pair[index]:
                    node.set('sign', '-')
        raw = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        doc.update(sha256=sha256(raw).hexdigest(), raw_receipt=archive_response(
            raw, source_url=doc['url'], retrieved_at=time.time()))
    return project_official_financials({'ticker': '1623.TW', 'company_name': '大東電',
        'financial_currency': 'TWD'}, value)


def checked(text, data=None):
    from evidence_exit_gate import evaluate_report_evidence
    result = evaluate_report_evidence(text, {'data': projected() if data is None else data})
    claims = [c for c in result['sampled_claims'] if c.get('financial_capex')]
    return claims


@pytest.mark.parametrize('period,ppe,total,scope', [
    ('2025年度', '1.33317', '1.39669', 'prior_annual'),
    ('TTM（2025-07-01至2026-06-30）', '0.51391', '0.57514', 'ttm'),
])
def test_explicit_ppe_and_total_bind_different_components_and_exact_period(period, ppe, total, scope):
    data = projected(); before = deepcopy(data)
    claims = checked(f'本公司{period}CapEx（PPE）為{ppe}億元，加上無形資產購置合計約{total}億元。', data)
    assert len(claims) == 2
    assert [c['status'] for c in claims] == ['verified', 'verified'], claims
    assert claims[0]['financial_definition'] != claims[1]['financial_definition']
    assert claims[0]['matched_path'].endswith(f'cashflows.{scope}.ppe_purchase')
    assert len(claims[1]['financial_component_paths']) == 2
    assert claims[0]['source_signed_raw_twd'] < 0
    assert claims[0]['expected_value_raw_twd'] > 0
    assert claims[0]['financial_amount_convention'] == 'cash_purchase_outflow_magnitude'
    assert claims[0]['financial_period'] == ('2025-01-01/2025-12-31' if scope == 'prior_annual' else '2025-07-01/2026-06-30')
    doc = data['official_financial_projection']['reference']['annual_document' if scope == 'prior_annual' else 'quarterly_document']
    # ISO timestamps preserve microseconds; normalize the receipt to that
    # same representation before comparing, without any timing tolerance.
    assert datetime.fromisoformat(claims[0]['source_acquired_at']) == datetime.fromtimestamp(
        doc['raw_receipt']['retrieved_at'], tz=timezone.utc)
    assert claims[0]['source_url'] == doc['url'] and claims[0]['source_document_sha256'] == doc['sha256']
    assert len(claims[0]['financial_source_documents']) == (1 if scope == 'prior_annual' else 2)
    assert data == before


@pytest.mark.parametrize('text', [
    '2025年Capex（購置不動產廠房設備）為0.51391億元，加上無形資產購置合計約0.57514億元；截至2026-06-30 TTM官方個別FCF為-2.47269億元。',
    '本公司2025年度CapEx（PPE）為0.51391億元，TTM CapEx（PPE及無形資產）為0.57514億元。',
    '本公司TTM CapEx（PPE及無形資產）為0.57514億元；本公司2025年度CapEx（PPE）為0.51391億元。',
])
def test_annual_wrong_amount_cannot_borrow_later_or_previous_ttm(text):
    claims = checked(text)
    wrong = next(c for c in claims if c['reported_value'] == .51391)
    assert wrong['status'] == 'mismatch', claims
    assert wrong['expected_value_raw_twd'] == 133317000
    assert wrong['financial_period'] == '2025-01-01/2025-12-31'


@pytest.mark.parametrize('text', [
    '本公司2025年度CapEx（PPE）為1.39669億元。',
    '本公司2025年度CapEx（PPE及無形資產）為1.33317億元。',
    '本公司2025年度CapEx（PPE）為9.87654億元。',
    '本公司2025年度CapEx（PPE）為-1.33317億元。',
    '本公司2025年度CapEx（PPE）現金流入為1.33317億元。',
])
def test_explicit_definition_value_and_direction_mismatches_are_not_ttm_number_heuristics(text):
    claims = checked(text)
    assert len(claims) == 1 and claims[0]['status'] == 'mismatch', claims


@pytest.mark.parametrize('text', [
    '本公司2024年度CapEx（PPE）為0.51391億元。',
    '本公司2025上半年CapEx（PPE）為1.33317億元。',
    '本公司CapEx（PPE）為1.33317億元。',
    '本公司2025年度CapEx為1.33317億元。',
    '本公司2025年度CapEx（PPE合併報表）為1.33317億元。',
    '本公司2025年度CapEx（PPE，屬於同業華通）為1.33317億元。',
    '本公司2025年度CapEx（PPE年度餘額）為1.33317億元。',
    '同業華通2025年度CapEx（PPE）為1.33317億元。',
    '本公司2025年度合併CapEx（PPE）為1.33317億元。',
    '本公司2025年度CapEx（PPE）為1.33317億美元。',
    '本公司2025年度CapEx（PPE）為1.33317億元（同業華通）。',
    '本公司2025年度CapEx（PPE）為1.33317億元，此為合併報表口徑。',
    '本公司2025年度CapEx（PPE）為1.33317億元（預期）。',
    '若本公司2025年度CapEx（PPE）為1.33317億元，則提高評價。',
    '本公司2025年度CapEx（PPE）並非1.33317億元。',
    '本公司2025年度含無形資產購置合計為1.39669億元。',
    '同業華通：\n- 2025年度CapEx（PPE）為1.33317億元。',
    '## 同業比較\n2025年度CapEx（PPE）為1.33317億元。',
    '本公司TTM（2024-07-01至2025-06-30）CapEx（PPE）為0.51391億元。',
])
def test_unknown_owner_period_definition_and_foreign_currency_remain_in_denominator(text):
    claims = checked(text)
    assert len(claims) == 1 and claims[0]['status'] == 'unverifiable', claims
    assert not claims[0]['independent_primary_source_verified']


@pytest.mark.parametrize('damage', ['missing_intangible', 'prior_year', 'raw_receipt', 'missing_projection'])
def test_modified_or_incomplete_components_never_qualify(damage):
    data = projected(); projection = data['official_financial_projection']
    if damage == 'missing_intangible':
        projection['facts']['cashflows']['prior_annual'].pop('intangible_purchase')
    elif damage == 'prior_year':
        projection['facts']['prior_annual_year'] = 2024
    elif damage == 'raw_receipt':
        projection['reference']['annual_document']['sha256'] = '0' * 64
    else:
        data.pop('official_financial_projection')
    claims = checked('本公司2025年度CapEx（PPE及無形資產）為1.39669億元。', data)
    assert len(claims) == 1 and claims[0]['status'] == 'unverifiable', claims


def test_early_feedback_reuses_period_and_definition_gate_without_rewriting_text():
    from financial_money_claims import financial_money_claim_issues
    data = projected()
    bad = '2025年Capex（購置不動產廠房設備）為0.51391億元，加上無形資產購置合計約0.57514億元。'
    messages = financial_money_claim_issues(bad, data)
    assert len(messages) == 2 and all('2025-01-01/2025-12-31' in message for message in messages)
    assert any('1.33317億' in message for message in messages)
    assert any('1.39669億' in message for message in messages)
    good = bad.replace('0.51391', '1.33317').replace('0.57514', '1.39669')
    assert financial_money_claim_issues(good, data) == []
