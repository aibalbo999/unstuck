"""Cashflow components may use only English names found in both source filings."""
from copy import deepcopy
from hashlib import sha256
import time
from xml.etree import ElementTree as ET

import pytest

from data_fetch.market_sources.official_xbrl_financial import IX
from official_cashflow_components import read_official_cashflow_components
from official_financial_projection import project_official_financials
from official_response_evidence import archive_response, read_response
from test_official_income_native_summary_heading import data_with_english, TITLE


def component_data(**options):
    reference = deepcopy(data_with_english(**options)['official_financial_projection']['reference'])
    for key, values in [('annual_document', {'d2025': -5000}),
                        ('quarterly_document', {'d2026': -7000, 'd2025': -4000})]:
        document = reference[key]
        root = ET.fromstring(read_response(document['raw_receipt']))
        for context, value in values.items():
            node = ET.SubElement(root, IX + 'nonFraction',
                name='ifrs-full:AdjustmentsForDecreaseIncreaseInInventories',
                contextRef=context, unitRef='TWD', scale='3', decimals='-3',
                format='ixt:numdotdecimal', sign='-')
            node.text = str(abs(value))
        raw = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        document.update(sha256=sha256(raw).hexdigest(), raw_receipt=archive_response(
            raw, source_url=document['url'], retrieved_at=time.time()))
    return project_official_financials({'ticker': '1623.TW', 'company_name': '大東電',
                                      'financial_currency': 'TWD'}, reference)


def component_claims(data, title=TITLE):
    from evidence_exit_gate import evaluate_report_evidence
    text = (title + '\n\n## 一頁式摘要\n'
        '大東電業廠股份有限公司官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）'
        '存貨變動現金影響為 -0.08000 億元。')
    result = evaluate_report_evidence(text, {'data': data})
    return [claim for claim in result['sampled_claims']
            if claim.get('financial_metric') == '存貨變動現金影響']


def test_component_alias_is_replayed_from_both_originals_without_mutating_input():
    data = component_data(); before = deepcopy(data)
    facts = read_official_cashflow_components(data)
    assert facts['issuer_english_name'] == 'TA TUN ELECTRIC WIRE & CABLE CO., LTD.'
    claims = component_claims(data)
    assert claims and all(claim['status'] == 'verified' for claim in claims)
    assert data == before
    assert facts['native_acquisition'] is False and facts['historical_pit_verified'] is False


@pytest.mark.parametrize('options', [{'quarterly_name': 'OTHER COMPANY'}, {'duplicate': True}])
def test_disagreeing_or_ambiguous_original_alias_cannot_qualify_title(options):
    data = component_data(**options)
    data['company_identity'] = {'allowed_aliases': ['Ta Tun Electric Wire & Cable Co., Ltd.']}
    facts = read_official_cashflow_components(data)
    assert facts and 'issuer_english_name' not in facts
    claims = component_claims(data)
    assert claims and all(claim['status'] == 'unverifiable' for claim in claims)


@pytest.mark.parametrize('wrong', ['2330.TW', '台積電', '2024年度'])
def test_other_issuer_or_period_heading_remains_unverifiable(wrong):
    claims = component_claims(component_data(), TITLE + '\n# ' + wrong)
    assert claims and all(claim['status'] == 'unverifiable' for claim in claims)


def test_changed_original_hash_cannot_supply_components_or_english_name():
    data = component_data()
    data['official_financial_projection']['reference']['annual_document']['sha256'] = '0' * 64
    assert read_official_cashflow_components(data) is None
