"""Official annual references cannot replace undated inputs or five-year gates."""
from copy import deepcopy
from contextlib import nullcontext
from hashlib import sha256
import json
import time
from xml.etree import ElementTree as ET

import pytest

from report_reader_assets import reader_observations
from report_evidence_gap_details import cash_flow_detail


TEMPLATE = b'/* synthetic TWD-thousands annual renderer contract for isolated tests */'


@pytest.fixture(autouse=True)
def synthetic_renderer_contract(monkeypatch):
    # Only the external renderer identity is substituted, not the admission logic.
    from data_fetch.market_sources.mops_public_annual import TEMPLATE_HASHES
    monkeypatch.setitem(TEMPLATE_HASHES, 't164sb05', sha256(TEMPLATE).hexdigest())


def filing_url(issuer, year, scope):
    return ('https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01'
            f'&step=9&co_id={issuer}&year={year}&season=4&report_id={scope}')


def filing_index(issuer, periods):
    return ''.join(f'<a href="{filing_url(issuer, year, scope).replace("&", "&amp;")}">synthetic</a>'
                   for year, scope in periods).encode()


def inline_filing(issuer, year, fields, *, individual=False):
    """Construct small synthetic bodies; never bundle acquired issuer originals."""
    from data_fetch.market_sources.official_xbrl_financial import IX, XBRLI
    root = ET.Element('{http://www.w3.org/1999/xhtml}html')
    for period in (year, year-1):
        for kind in ('d', 'i'):
            context = ET.SubElement(root, XBRLI+'context', id=f'{kind}{period}')
            entity = ET.SubElement(context, XBRLI+'entity')
            ET.SubElement(entity, XBRLI+'identifier', scheme='http://www.twse.com.tw').text = issuer
            duration = ET.SubElement(context, XBRLI+'period')
            if kind == 'd':
                ET.SubElement(duration, XBRLI+'startDate').text = f'{period}-01-01'
                ET.SubElement(duration, XBRLI+'endDate').text = f'{period}-12-31'
            else:
                ET.SubElement(duration, XBRLI+'instant').text = f'{period}-12-31'
        for tag, amount in fields.items():
            instant = tag in {'ifrs-full:Assets', 'ifrs-full:Equity',
                              'ifrs-full:EquityAttributableToOwnersOfParent'}
            attributes = {'name': tag, 'contextRef': f'{"i" if instant else "d"}{period}',
                          'unitRef': 'TWD', 'scale': '3', 'decimals': '-3', 'format': 'ixt:numdotdecimal'}
            if amount < 0:
                attributes['sign'] = '-'
            ET.SubElement(root, IX+'nonFraction', attributes).text = str(abs(amount))
    unit = ET.SubElement(root, XBRLI+'unit', id='TWD')
    ET.SubElement(unit, XBRLI+'measure').text = 'iso4217:TWD'
    if individual:
        from data_fetch.market_sources.ordinary_individual_annual import ISSUERS
        notes = {'CompanyID': issuer, 'CompanyChineseName': ISSUERS[issuer+'.TW'],
                 'Year': str(year), 'Quarter': '4', 'ReportCategory': 'Individual report',
                 'ReportType': 'Financial report (general)', 'IndustrySector': 'Commercial and industrial'}
        for tag, text in notes.items():
            ET.SubElement(root, IX+'nonNumeric', name='tifrs-notes:'+tag,
                          contextRef=f'd{year}').text = text
    return ET.tostring(root, encoding='utf-8')


def bank_data():
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.market_sources.financial_institution_xbrl import BANK_FIELDS, assemble_histories
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    from official_response_evidence import archive_response
    fields = {tag: -100 if field == 'ppe_purchase' else -20 if field == 'intangible_purchase' else 1000
              for tag, field in BANK_FIELDS.items()}
    years = list(range(2021, 2026))
    value = assemble_histories({year: {tag: amount*1000 for tag, amount in fields.items()}
                                for year in years}, expected_years=years)
    documents = []
    for year in years:
        raw = inline_filing('2834', year, fields)
        url = filing_url('2834', year, 'C')
        proof = archive_response(raw, source_url=url, retrieved_at=time.time(),
                                 evidence_kind='decoded_http_response_body_bytes')
        documents.append({'year': year, 'url': url, 'sha256': sha256(raw).hexdigest(),
                          'report_scope': 'consolidated', 'statement_taxonomy': 'bank',
                          'source_record_archive': proof})
    value.update(ticker='2834.TW', currency='TWD', report_scope='consolidated',
                 source_url=INDEX_URL, documents=documents, comparative_revisions=[])
    return {**project_source_value(value, '2834.TW'), 'ticker': '2834.TW',
            'financial_currency': 'TWD', 'free_cash_flow_raw': -10,
            'sector_specific_financials': value}


def test_full_bank_originals_can_verify_annual_fcf_without_certifying_industrial_dcf():
    data = bank_data()
    before = deepcopy(data)
    detail = cash_flow_detail(data)
    assert detail['status'] == 'sector_annual_originals_verified'
    assert detail['period_start'] == '2025-01-01' and detail['period_end'] == '2025-12-31'
    assert detail['free_cash_flow_twd'] == 880000
    assert detail['industrial_dcf_applicable'] is False
    assert detail['raw_scalar_period_verified'] is False
    assert data == before


@pytest.mark.parametrize('damage', ['receipt', 'history', 'scope', 'currency'])
def test_financial_reference_still_requires_full_originals_and_matching_saved_history(damage):
    data = bank_data()
    if damage == 'receipt': data['sector_specific_financials']['documents'][0]['source_record_archive']['raw_response_sha256'] = '0'*64
    elif damage == 'history': data['fcf_history'][-1] += 1
    elif damage == 'scope': data['sector_specific_financials']['report_scope'] = 'individual'
    else: data['financial_currency'] = 'USD'
    assert cash_flow_detail(data)['status'] != 'sector_annual_originals_verified'


def cash_flow_body(year):
    return json.dumps({'code': 200, 'result': {
        'reportType': '合併', 'year': str(year-1911), 'season': '4', 'fiscalYear': '',
        'companyAbbreviation': 'Synthetic', 'subsidiary': [], 'subsidiaryCompanyId': '',
        'urlList': [{'name': 'XBRL資訊平台', 'url':
                    f'https://mopsov.twse.com.tw/server-java/t164sb01?step=1&CO_ID=3443&SYEAR={year}&SSEASON=4&REPORT_ID=C'}],
        'titles': [{'main': '會計項目', 'sub': []},
                   {'main': f'{year-1911}年度', 'sub': [{'main': '金額', 'sub': []}]},
                   {'main': f'{year-1912}年度', 'sub': [{'main': '金額', 'sub': []}]}],
        'reportList': [['營業活動之淨現金流入（流出）', '1,000', '900'],
                       ['取得不動產、廠房及設備', '-100', '-90'], ['取得無形資產', '-20', '-10']]
    }}, ensure_ascii=False).encode()


def reference():
    from official_response_evidence import archive_response
    from data_fetch.market_sources.mops_public_annual import payload, api_url, template_url
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    index = filing_index('3443', [(2025, 'C')])
    return {'schema': 'official-annual-cash-flow-reference:v1', 'ticker': '3443.TW', 'year': 2025,
        'index_request': {'step': '1', 'firstin': 'ture', 'off': '1', 'queryName': 'co_id', 'inpuType': 'co_id', 'TYPEK': 'all', 'co_id': '3443'},
        'statement_request': payload('3443', 2025),
        'index_receipt': archive_response(index, source_url=INDEX_URL, retrieved_at=time.time()),
        'template_receipt': archive_response(TEMPLATE, source_url=template_url('CashflowStatement'), retrieved_at=time.time()),
        'statement_receipt': archive_response(cash_flow_body(2025), source_url=api_url('CashflowStatement'), retrieved_at=time.time())}


def test_one_complete_annual_cash_flow_is_separate_from_the_missing_five_year_history():
    data = {'ticker': '3443.TW', 'financial_currency': 'TWD', 'free_cash_flow_raw': 123,
            'years': ['2024', '2025'], 'fcf_history': [1, 2]}
    snapshot = {'data': data, '_reader_annual_cash_flow_review': reference()}
    before = deepcopy(snapshot)
    cash = reader_observations(snapshot)['evidence_gaps']['cash_flow']
    detail = cash.get('annual_reference') or {}
    assert detail.get('status') == 'official_annual_cash_flow_verified'
    assert detail['period_end'] == '2025-12-31'
    assert detail['free_cash_flow_twd'] == 880000
    assert detail['five_year_history_verified'] is False
    assert detail['raw_scalar_period_verified'] is False
    assert cash['status'] == 'unverified' and cash['raw_scalar'] == 123
    assert 'raw_response_path' not in json.dumps(detail)
    assert snapshot == before


@pytest.mark.parametrize('damage', ['ticker', 'year', 'quarter', 'hash', 'index', 'template', 'unit_contract', 'missing_purchase', 'future', 'currency'])
def test_bad_annual_reference_cannot_be_admitted(damage):
    from official_response_evidence import read_response, archive_response
    review = reference()
    data = {'ticker': '3443.TW', 'financial_currency': 'TWD'}
    if damage == 'ticker': review['ticker'] = '2330.TW'
    elif damage == 'year': review['year'] = True
    elif damage == 'quarter': review['statement_request']['season'] = '3'
    elif damage == 'hash': review['statement_receipt']['raw_response_sha256'] = '0'*64
    elif damage == 'index': review['index_receipt']['source_url'] += '?other=1'
    elif damage == 'template': review['template_receipt']['raw_response_sha256'] = '0'*64
    elif damage == 'unit_contract':
        proof = review['template_receipt']
        review['template_receipt'] = archive_response(b'changed unit contract', source_url=proof['source_url'], retrieved_at=time.time())
    elif damage == 'future': review['statement_receipt']['retrieved_at'] = time.time()+86400
    elif damage == 'currency': data['financial_currency'] = 'USD'
    else:
        proof = review['statement_receipt']
        body = json.loads(read_response(proof))
        body['result']['reportList'] = [r for r in body['result']['reportList'] if r[0].strip() != '取得無形資產']
        review['statement_receipt'] = archive_response(json.dumps(body).encode(), source_url=proof['source_url'], retrieved_at=time.time())
    cash = reader_observations({'data': data, '_reader_annual_cash_flow_review': review})['evidence_gaps']['cash_flow']
    detail = cash.get('annual_reference') or {}
    assert detail.get('status') == 'unverified'
    assert detail['raw_scalar_period_verified'] is False


def test_annual_collector_uses_only_three_bounded_requests_and_keeps_its_own_audit():
    from data_fetch.market_sources.official_annual_cash_flow import fetch_reference
    review = reference()
    from official_response_evidence import read_response
    from data_fetch.market_sources.mops_public_annual import api_url, template_url
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    class Http:
        def __init__(self):
            self.components = []
            self.deadline = time.monotonic()+45
        def batch(self): return nullcontext()
        def request(self, url, **kwargs):
            expected = {INDEX_URL: ('index_receipt', {'request': review['index_request']}),
                template_url('CashflowStatement'): ('template_receipt', {}),
                api_url('CashflowStatement'): ('statement_receipt', {'json_body': review['statement_request']})}
            key, parameters = expected[url]
            assert kwargs == parameters
            self.components.append({'url': url, 'http_request_sent': True, 'http_status': 200})
            return read_response(review[key]), review[key]
    result = fetch_reference({'ticker': '3443.TW', 'quote_type': 'EQUITY',
                             'currency': 'TWD', 'financial_currency': 'TWD'}, transport=Http())
    assert result['audit']['source'] == 'annual_cash_flow_reference'
    assert result['audit']['coverage_status'] == 'single_annual_cash_flow_only'
    assert result['audit']['http_request_count'] == 3
    assert result['audit']['record_count'] == 1
    assert result['value']['year'] == 2025


def test_qualified_individual_history_stays_individual_in_the_separate_reference():
    from data_fetch.market_sources.ordinary_individual_annual import FIELDS, fetch_annual_histories
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    from official_response_evidence import archive_response
    fields = {'ifrs-full:'+tag: -100 if field == 'ppe_purchase' else -20 if field == 'intangible_purchase' else 1000
              for tag, field in FIELDS.items()}
    bodies = {filing_url('2646', year, 'A'): inline_filing('2646', year, fields, individual=True)
              for year in range(2021, 2026)}
    bodies[INDEX_URL] = filing_index('2646', [(year, 'A') for year in range(2021, 2026)])
    class Http:
        deadline = time.monotonic()+45
        def batch(self): return nullcontext()
        def request(self, url, **kwargs):
            raw = bodies[url]
            return raw, archive_response(raw, source_url=url, retrieved_at=time.time())
    value = fetch_annual_histories('2646.TW', Http())
    snapshot = {'data': {'ticker': '2646.TW', 'financial_currency': 'TWD', 'free_cash_flow_raw': -99},
        '_reader_annual_cash_flow_review': {'schema': 'official-annual-cash-flow-reference:v1',
            'ticker': '2646.TW', 'year': 2025, 'individual_history': value}}
    before = deepcopy(snapshot)
    detail = reader_observations(snapshot)['evidence_gaps']['cash_flow']['annual_reference']
    assert detail['status'] == 'official_annual_cash_flow_verified'
    assert detail['scope'] == 'individual'
    assert detail['raw_scalar_period_verified'] is False
    assert detail['five_year_history_verified'] is True
    assert detail['free_cash_flow_twd'] == 880000
    assert snapshot == before
    value['documents'][0]['raw_receipt']['raw_response_sha256'] = '0'*64
    assert reader_observations(snapshot)['evidence_gaps']['cash_flow']['annual_reference']['status'] == 'unverified'


def test_explicit_fund_identity_is_not_a_missing_corporate_cash_flow():
    data = {'ticker': '0050.TW', 'instrument_type': 'ETF', 'financial_currency': 'TWD'}
    before = deepcopy(data)
    assert cash_flow_detail(data)['status'] == 'not_applicable'
    assert data == before
    data.pop('instrument_type')
    assert cash_flow_detail(data)['status'] == 'unverified'


def test_newer_individual_period_does_not_date_an_older_consolidated_reference():
    from official_response_evidence import archive_response
    from data_fetch.market_sources.official_annual_cash_flow import replay_reference
    from data_fetch.market_sources.mops_public_annual import api_url, payload
    review = reference()
    review['year'] = 2024
    review['statement_request'] = payload('3443', 2024)
    review['statement_receipt'] = archive_response(cash_flow_body(2024), source_url=api_url('CashflowStatement'), retrieved_at=time.time())
    index = ''.join(f'<a href="/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=3443&year={year}&season=4&report_id={scope}">filing</a>'
                    for year, scope in [(2024, 'C'), (2025, 'A')]).encode()
    review['index_receipt'] = archive_response(index, source_url=review['index_receipt']['source_url'], retrieved_at=time.time())
    detail = replay_reference({'ticker': '3443.TW', 'financial_currency': 'TWD'}, review)
    assert detail['period_end'] == '2024-12-31'
    assert detail['newer_individual_years'] == [2025]
    assert detail['raw_scalar_period_verified'] is False
