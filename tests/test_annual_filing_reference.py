"""Synthetic annual originals exercise the independent supplementary contract."""
from copy import deepcopy
from contextlib import nullcontext
from hashlib import sha256
import time

import pytest

from test_report_official_annual_cash_flow import filing_index, filing_url, inline_filing


def reference(ticker='2892.TW'):
    from official_response_evidence import archive_response
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    from data_fetch.market_sources.financial_institution_xbrl import FIELDS
    years = list(range(2021, 2026))
    issuer = ticker.split('.')[0]
    fields = {tag: -10 if 'PurchaseOf' in tag else 1000 for tag in FIELDS}
    index = filing_index(issuer, [(year, 'C') for year in years])
    documents = []
    for year in years:
        raw = inline_filing(issuer, year, fields)
        from xml.etree import ElementTree as ET
        from data_fetch.market_sources.official_xbrl_financial import IX
        root = ET.fromstring(raw)
        for tag, text in {'CompanyID': issuer, 'CompanyChineseName': 'Synthetic financial holding',
                          'Year': str(year), 'Quarter': '4', 'ReportCategory': 'Consolidated report',
                          'IndustrySector': 'Financial holding', 'ReportType': 'Financial report (general)'}.items():
            ET.SubElement(root, IX+'nonNumeric', name='tifrs-notes:'+tag, contextRef=f'd{year}').text = text
        raw = ET.tostring(root, encoding='utf-8')
        url = filing_url(issuer, year, 'C')
        documents.append({'year': year, 'url': url, 'sha256': sha256(raw).hexdigest(),
                          'raw_receipt': archive_response(raw, source_url=url, retrieved_at=time.time())})
    return {'schema': 'official-annual-filing-reference:v1', 'ticker': ticker,
            'report_scope': 'consolidated', 'statement_taxonomy': 'financial_holding',
            'published_index_receipt': archive_response(index, source_url=INDEX_URL, retrieved_at=time.time()),
            'documents': documents}


def test_holding_supplement_replays_full_originals_without_replacing_saved_values():
    from data_fetch.market_sources.annual_filing_reference import replay_reference
    value = reference()
    before = deepcopy(value)
    result = replay_reference(value, '2892.TW')
    assert result['status'] == 'annual_originals_verified'
    assert result['five_year_history_verified'] is True
    assert result['raw_scalar_period_verified'] is False
    assert result['industrial_dcf_applicable'] is False
    assert result['raw_twd_by_year']['2025']['free_cash_flow'] == 980000
    assert value == before


@pytest.mark.parametrize('damage', ['scope', 'ticker', 'hash', 'receipt', 'year', 'index'])
def test_changed_supplement_cannot_pass(damage):
    from data_fetch.market_sources.annual_filing_reference import replay_reference
    value = reference()
    if damage == 'scope': value['report_scope'] = 'individual'
    elif damage == 'ticker': value['ticker'] = '2883.TW'
    elif damage == 'hash': value['documents'][0]['sha256'] = '0'*64
    elif damage == 'receipt': value['documents'][0]['raw_receipt']['retrieved_at'] = time.time()+3600
    elif damage == 'year': value['documents'][0]['year'] = True
    else: value['published_index_receipt']['raw_response_sha256'] = '0'*64
    assert replay_reference(value, '2892.TW')['status'] == 'unverified'


def test_only_profiled_exact_native_urls_are_allowed():
    from data_fetch.market_sources.annual_filing_reference import native_contract
    assert native_contract(filing_url('2892', 2025, 'C'))[0] == 6000000
    for url in (filing_url('2892', 2025, 'A'), filing_url('2330', 2025, 'C'),
                filing_url('2892', 2025, 'C')+'&extra=1', filing_url('2892', 2025, 'C')+'#fragment'):
        with pytest.raises(ValueError): native_contract(url)


def test_incomplete_latest_history_keeps_its_scope_and_does_not_claim_five_years():
    from data_fetch.market_sources.annual_filing_reference import replay_reference
    value = reference()
    value['documents'] = value['documents'][-1:]
    result = replay_reference(value, '2892.TW')
    assert result['status'] == 'unverified'  # Do not omit indexed required originals.
    value['coverage'] = 'latest_annual_only'
    result = replay_reference(value, '2892.TW')
    assert result['status'] == 'annual_originals_verified'
    assert result['years'] == ['2025'] and result['five_year_history_verified'] is False


def test_reader_reference_keeps_new_financial_annuals_separate_and_hides_private_receipts():
    import json
    from data_fetch.market_sources.annual_filing_reference import cash_flow_reference
    data = {'ticker': '2892.TW', 'financial_currency': 'TWD', 'free_cash_flow_raw': -99}
    review = {'schema': 'official-annual-cash-flow-reference:v1', 'ticker': '2892.TW', 'year': 2025,
              'annual_filing_reference': reference()}
    before = deepcopy((data, review))
    result = cash_flow_reference(data, review)
    assert result['status'] == 'official_annual_cash_flow_verified'
    assert result['free_cash_flow_twd'] == 980000
    assert result['raw_scalar_period_verified'] is False and result['industrial_dcf_applicable'] is False
    assert 'DCF' in result['reason'] and 'raw_response_path' not in json.dumps(result)
    assert (data, review) == before
    data['financial_currency'] = 'USD'
    assert cash_flow_reference(data, review)['status'] == 'unverified'


def test_conflicting_incomplete_holding_comparative_remains_blocked():
    from xml.etree import ElementTree as ET
    from official_response_evidence import read_response, archive_response
    from data_fetch.market_sources.official_xbrl_financial import IX
    from data_fetch.market_sources.annual_filing_reference import replay_reference
    value = reference()
    document = value['documents'][2]
    root = ET.fromstring(read_response(document['raw_receipt']))
    for node in list(root):
        if node.tag != IX+'nonFraction' or node.get('contextRef') != 'd2022': continue
        if 'IntangibleAssetsClassified' in node.get('name', ''): root.remove(node)
        if node.get('name') == 'tifrs-bsci-fh:NetIncomeLoss': node.text = '900'
    raw = ET.tostring(root, encoding='utf-8')
    document.update(sha256=sha256(raw).hexdigest(), raw_receipt=archive_response(raw, source_url=document['url'], retrieved_at=time.time()))
    before = deepcopy(value)
    result = replay_reference(value, '2892.TW')
    assert result['status'] == 'annual_originals_verified'  # Latest year remains independently usable.
    assert result['five_year_history_verified'] is False
    assert 'conflicting incomplete' in result['comparative_issue']
    diagnostics = result['comparative_diagnostics'][0]
    assert diagnostics['period_year'] == 2022 and diagnostics['comparative_filing_year'] == 2023
    assert diagnostics['conflicting_facts']['tifrs-bsci-fh:NetIncomeLoss'] == {'original_twd': 1000000, 'comparative_twd': 900000}
    assert diagnostics['missing_facts'] == ['ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities']
    assert value == before


def test_missing_latest_intangible_never_becomes_zero_in_financial_reference():
    from xml.etree import ElementTree as ET
    from official_response_evidence import read_response, archive_response
    from data_fetch.market_sources.official_xbrl_financial import IX
    from data_fetch.market_sources.annual_filing_reference import replay_reference, cash_flow_reference
    value = reference()
    document = value['documents'][-1]
    root = ET.fromstring(read_response(document['raw_receipt']))
    for node in list(root):
        if node.tag == IX+'nonFraction' and 'IntangibleAssetsClassified' in node.get('name', ''): root.remove(node)
    raw = ET.tostring(root, encoding='utf-8')
    document.update(sha256=sha256(raw).hexdigest(), raw_receipt=archive_response(raw, source_url=document['url'], retrieved_at=time.time()))
    result = replay_reference(value, '2892.TW')
    assert result['status'] == 'annual_components_verified'
    assert result['five_year_history_verified'] is False
    assert result['raw_twd_by_year']['2025']['free_cash_flow'] is None
    review = {'schema': 'official-annual-cash-flow-reference:v1', 'ticker': '2892.TW', 'year': 2025,
              'annual_filing_reference': value}
    reader = cash_flow_reference({'ticker': '2892.TW', 'financial_currency': 'TWD'}, review)
    assert reader['status'] == 'unverified' and reader['components_verified'] is True
    assert '缺列不當成零' in reader['reason']
    assert '已核對營業現金流、設備購置支出' in reader['reason']
    assert '尚缺明列無形資產購置支出' in reader['reason']
    assert reader['missing_cash_flow_components'] == ['intangible_purchase']
    assert '未明列營業現金流' not in reader['reason']


def test_financial_original_scope_metadata_must_agree_with_the_index_route():
    from xml.etree import ElementTree as ET
    from official_response_evidence import read_response, archive_response
    from data_fetch.market_sources.official_xbrl_financial import IX
    from data_fetch.market_sources.annual_filing_reference import replay_reference
    value = reference()
    document = value['documents'][-1]
    root = ET.fromstring(read_response(document['raw_receipt']))
    for node in root.iter(IX+'nonNumeric'):
        if node.get('name') == 'tifrs-notes:ReportCategory': node.text = 'Individual report'
    raw = ET.tostring(root, encoding='utf-8')
    document.update(sha256=sha256(raw).hexdigest(), raw_receipt=archive_response(raw, source_url=document['url'], retrieved_at=time.time()))
    assert replay_reference(value, '2892.TW')['status'] == 'unverified'


def test_provider_audit_counts_the_real_bounded_requests(monkeypatch):
    from official_response_evidence import read_response
    from data_fetch.market_sources.annual_filing_reference import fetch_reference
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    value = reference()
    responses = {INDEX_URL: value['published_index_receipt']}
    responses.update({document['url']: document['raw_receipt'] for document in value['documents']})

    class Transport:
        components = []
        deadline = time.monotonic()+45
        def batch(self): return nullcontext()
        def request(self, url, **kwargs):
            proof = responses[url]
            self.components.append({'url': url, 'http_request_sent': True, 'http_status': 200})
            return read_response(proof), proof

    result = fetch_reference('2892.TW', transport=Transport())
    assert result['audit']['status'] == 'success'
    assert result['audit']['source'] == 'annual_filing_reference'
    assert result['audit']['http_request_count'] == 6
    assert result['value']['statement_taxonomy'] == 'financial_holding'


@pytest.mark.parametrize('issuer,years', [('1623', [2025]), ('7799', [2023, 2024, 2025])])
def test_short_individual_originals_never_become_five_year_or_consolidated(issuer, years):
    from xml.etree import ElementTree as ET
    from official_response_evidence import archive_response
    from data_fetch.market_sources.ordinary_individual_annual import REFERENCE_ISSUERS, supports_annual, FIELDS
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL, IX
    from data_fetch.market_sources.annual_filing_reference import replay_reference
    assert supports_annual(issuer+'.TW') is False
    fields = {'ifrs-full:'+tag: -10 if 'PurchaseOf' in tag else 1000 for tag in FIELDS}
    index = filing_index(issuer, [(year, 'A') for year in years])
    docs = []
    for year in years:
        root = ET.fromstring(inline_filing(issuer, year, fields))
        notes = {'CompanyID': issuer, 'CompanyChineseName': REFERENCE_ISSUERS[issuer+'.TW'],
                 'Year': str(year), 'Quarter': '4', 'ReportCategory': 'Individual report',
                 'ReportType': 'Financial report (first time adoption)' if issuer == '7799' and year == 2023
                 else 'Financial report (general)', 'IndustrySector': 'Commercial and industrial'}
        for tag, text in notes.items():
            ET.SubElement(root, IX+'nonNumeric', name='tifrs-notes:'+tag, contextRef=f'd{year}').text = text
        raw = ET.tostring(root, encoding='utf-8')
        url = filing_url(issuer, year, 'A')
        docs.append({'year': year, 'url': url, 'sha256': sha256(raw).hexdigest(),
                     'raw_receipt': archive_response(raw, source_url=url, retrieved_at=time.time())})
    value = {'schema': 'official-annual-filing-reference:v1', 'ticker': issuer+'.TW',
             'report_scope': 'individual', 'statement_taxonomy': 'ordinary_individual',
             'published_index_receipt': archive_response(index, source_url=INDEX_URL, retrieved_at=time.time()),
             'documents': docs}
    result = replay_reference(value, issuer+'.TW')
    assert result['status'] == 'annual_originals_verified'
    assert result['five_year_history_verified'] is False
    assert result['report_scope'] == 'individual'
    assert result['raw_twd_by_year']['2025']['free_cash_flow'] == 980000
    assert result['first_adoption_years'] == ([2023] if issuer == '7799' else [])
    assert supports_annual(issuer+'.TW') is False
