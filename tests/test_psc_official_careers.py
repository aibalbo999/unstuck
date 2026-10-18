"""Public issuer job evidence must be usable without inventing recent postings."""
import base64
from datetime import datetime, timedelta
from hashlib import sha256
import json
import time
from zoneinfo import ZoneInfo

import pytest

from data_trust import source_record_count

LISTING_URL = 'https://ehrweb.104.com.tw/job.do?uno=23218183'
LIST_API = 'https://ehrweb.104.com.tw/dwr/call/plaincall/normalAjaxService.searchJobs.dwr'
DETAIL_API = 'https://ehrweb.104.com.tw/dwr/call/plaincall/normalAjaxService.getJobDetailByCustId.dwr'
LEGAL = '統一綜合證券股份有限公司'
JOB_ID = '1613781649555324659'
PREFIX = ('//#DWR-INSERT\n//#DWR-REPLY\n//#DWR-START#\n(function(){\n'
          'if(!window.dwr)return;\nvar dwr=window.dwr._[0];\n'
          'dwr.engine.remote.handleCallback("0","0",')
SUFFIX = ');\n})();\n//#DWR-END#\n'


def literal(payload):
    return (PREFIX + json.dumps({'code': 11, 'data': payload}, ensure_ascii=True) + SUFFIX).encode()


def source_bodies():
    updated = (datetime.now(ZoneInfo('Asia/Taipei')) - timedelta(days=1)).strftime('%Y/%m/%d %H:%M:%S')
    row = {'id': JOB_ID, 'custId': '9900000736', 'enable': True, 'cleanI18nName': '總公司稽核人員'}
    detail = {'id': JOB_ID, 'custId': '9900000736', 'custNo': '23218183000', 'coName': LEGAL,
              'enable': True, 'job': row['cleanI18nName'], 'formattedCreateDate': '2024/04/10 07:45:35',
              'formattedInputDate': '2024/04/10', 'formattedUpdateDate': updated,
              'formattedCloseDate': '無', 'closeDate': None, 'deleteDate': None,
              'roleString': '全職', 'needEmpString': '1', 'salaryString': '月薪: NT$40,000以上',
              'i18nAddressRegion': '台北市松山區',
              'peer': {'i18nDescription': '1.稽核例行、專案查核作業\n2.主管交辦事項', 'i18nOthers': ''}}
    return literal([1, [row]]), literal(detail), row, detail


def receipt(raw, url, stamp, job_id=None):
    return {'url': url, 'method': 'POST', 'request_identity': {'cust_id': '9900000736', 'job_id': job_id},
            'body_b64': base64.b64encode(raw).decode('ascii'), 'sha256': sha256(raw).hexdigest(),
            'fetched_at_epoch': stamp}


def issuer_data():
    now = time.time()
    return {'ticker': '2855.TW', 'company_name': '統一證', 'quote_type': 'EQUITY',
            'company_identity': {'ticker': '2855.TW', 'official_name': '統一證', 'stock_id': '2855',
                                 'instrument_type': 'EQUITY', 'legal_name': None},
            'official_receipt': {'ticker': '2855.TW', 'official_short_name': '統一證',
                                'legal_name': LEGAL, 'official_ubn': '23218183',
                                'source_url': 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L',
                                'response_sha256': 'a' * 64,
                                'as_of': datetime.now(ZoneInfo('Asia/Taipei')).date().isoformat(),
                                'fetched_at_epoch': now}}


def expected_value():
    now = time.time()
    listing, detail, row, info = source_bodies()
    return {'status': 'success', 'ticker': '2855.TW', 'company_name': LEGAL, 'official_ubn': '23218183',
            'job_count': None, 'recent_company_job_count': None, 'current_open_job_count': 1,
            'source': 'President Securities official careers', 'source_url': LIST_API,
            'listing_url': LISTING_URL, 'evidence_kind': 'official_company_job_postings',
            'query_scope': 'exact_issuer_current_open_postings',
            'coverage_status': 'current_open_posting_sample', 'listing_total': 1, 'raw_count': 1, 'rejected_count': 0,
            'response_sha256': sha256(listing).hexdigest(), 'fetched_at_epoch': now,
            'message': '僅採當時開放且原件可核對的職缺樣本；建立／異動日不推定首次刊登日，也不推論近期新增或擴編。',
            'job_postings': [{'job_no': JOB_ID, 'title': row['cleanI18nName'], 'employer': LEGAL,
                              'employer_id': '23218183000', 'url': LISTING_URL, 'source_url': DETAIL_API,
                              'is_open': True, 'description': info['peer']['i18nDescription'],
                              'conditions': '', 'employment_type': '全職', 'headcount_text': '1',
                              'salary_text': info['salaryString'], 'location': info['i18nAddressRegion'],
                              'source_created_at': info['formattedCreateDate'],
                              'source_input_date': info['formattedInputDate'],
                              'source_updated_at': info['formattedUpdateDate'],
                              'published_date': None, 'date_semantics': 'source_creation_and_modification_not_first_publication',
                              'response_sha256': sha256(detail).hexdigest(), 'source_receipt_fetched_at_epoch': now}],
            'source_record_archive': {'schema': 'psc-careers.v1', 'listing_receipt': receipt(listing, LIST_API, now),
                                     'detail_receipts': [receipt(detail, DETAIL_API, now, JOB_ID)]}}


def test_2855_complete_current_open_source_survives_acquisition_gate():
    data = issuer_data()
    value = expected_value()
    assert source_record_count('alternative_data', {**data, 'alternative_data': {
        'company_legal_name_evidence': data['official_receipt'], 'job_openings_official': value}}) == 1


def test_missing_primary_jobs_use_public_full_details_and_skip_redundant_keyword_search(monkeypatch):
    import alternative_data_fetcher as search
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name, psc_careers, taiwanjobs_company_jobs
    from data_fetch.types import FetchRequest

    data = issuer_data()
    value = expected_value()
    calls, legacy = [], []
    monkeypatch.setattr(official_company_legal_name, 'get_official_legal_name', lambda *a: data['official_receipt'])
    monkeypatch.setattr(search, 'fetch_104_company_jobs', lambda *a, **k: {'status': 'unavailable', 'reason_code': 'exact_employer_unverified'})
    monkeypatch.setattr(search, 'fetch_104_company_jobs_by_ubn', lambda *a, **k: {'status': 'unavailable'})
    monkeypatch.setattr(taiwanjobs_company_jobs, 'fetch_taiwanjobs_company_jobs', lambda *a: {'status': 'unavailable'})
    monkeypatch.setattr(taiwanjobs_company_jobs, 'fetch_taiwanjobs_regional_jobs', lambda *a: {'status': 'unavailable'})
    monkeypatch.setattr(search, 'fetch_104_job_openings_count', lambda *a, **k: legacy.append('104') or {'status': 'unavailable'})
    monkeypatch.setattr(search, 'fetch_1111_job_openings_count', lambda *a, **k: legacy.append('1111') or {'status': 'unavailable'})
    def read(self, job_id=None):
        calls.append(job_id)
        archive = value['source_record_archive']
        return archive['listing_receipt'] if job_id is None else archive['detail_receipts'][0]
    monkeypatch.setattr(psc_careers.PscCareersHttp, 'get_receipt', read)
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2855.TW'), {'data': data})
    assert result.audit['record_count'] == 1
    assert calls == [None, JOB_ID] and legacy == []
    assert result.value['job_openings_104']['reason_code'] == 'exact_employer_unverified'
    assert result.value['job_openings_official']['job_postings'][0]['published_date'] is None


def test_full_http_receipts_stay_in_snapshot_without_bloating_model_prompt():
    from prompt_builder import format_data_for_prompt
    data = issuer_data()
    value = expected_value()
    snapshot = {**data, 'alternative_data': {'company_legal_name_evidence': data['official_receipt'],
                                           'job_openings_official': value}}
    text = format_data_for_prompt(snapshot)
    assert 'body_b64' not in text and 'detail_receipts' not in text
    assert 'source_created_at' in text and '2024/04/10 07:45:35' in text
    assert '稽核例行' in text and 'source_updated_at' in text and 'published_date' in text
    assert source_record_count('alternative_data', snapshot) == 1


@pytest.mark.parametrize('mutation', [
    lambda v: v.update(current_open_job_count=True),
    lambda v: v.update(recent_company_job_count=1),
    lambda v: v.update(job_count=138),
    lambda v: v.update(published_date='2026-10-09'),
    lambda v: v.update(message='近三十日新增138人'),
    lambda v: v['job_postings'][0].update(title='subsidiary jobs'),
    lambda v: v['job_postings'][0].update(published_date='2026-10-09'),
    lambda v: v['job_postings'][0].update(source_updated_at='2026/10/09 00:00:00'),
    lambda v: v['source_record_archive']['listing_receipt'].update(sha256='0' * 64),
    lambda v: v['source_record_archive']['detail_receipts'][0].update(method='GET'),
    lambda v: v['source_record_archive']['detail_receipts'][0].update(fetched_at_epoch=float('nan')),
    lambda v: v['source_record_archive']['detail_receipts'][0].update(fetched_at_epoch=time.time() + 1),
    lambda v: v['source_record_archive']['detail_receipts'].append(v['source_record_archive']['detail_receipts'][0]),
])
def test_altered_claims_receipts_and_false_recent_dates_are_rejected(mutation):
    data, value = issuer_data(), expected_value()
    mutation(value)
    assert source_record_count('alternative_data', {**data, 'alternative_data': {
        'company_legal_name_evidence': data['official_receipt'], 'job_openings_official': value}}) == 0


@pytest.mark.parametrize('change', [
    {'quote_type': 'ETF'}, {'ticker': '2855.TWO'},
    {'company_identity': {'ticker': '2855.TW', 'official_name': '統一期貨', 'instrument_type': 'EQUITY'}},
    {'company_identity': {'ticker': '2882.TW', 'official_name': '統一證', 'instrument_type': 'EQUITY'}},
])
def test_other_security_or_issuer_cannot_inherit_job_evidence(change):
    data, value = issuer_data(), expected_value()
    assert source_record_count('alternative_data', {**data, **change, 'alternative_data': {
        'company_legal_name_evidence': data['official_receipt'], 'job_openings_official': value}}) == 0


def test_historical_official_anchor_does_not_prove_current_employer():
    data, value = issuer_data(), expected_value()
    data['official_receipt']['fetched_at_epoch'] = time.time() - 2 * 86400
    assert source_record_count('alternative_data', {**data, 'alternative_data': {
        'company_legal_name_evidence': data['official_receipt'], 'job_openings_official': value}}) == 0


@pytest.mark.parametrize('changed', [
    {'custNo': '23218184000'}, {'coName': '統一證券投資信託股份有限公司'},
    {'custId': '9900000737'}, {'id': '1613781649555324660'}, {'job': 'other job'},
    {'enable': False}, {'deleteDate': {'dwr_date_epoch_ms': 1791530000000}},
    {'formattedUpdateDate': '2099/10/05 18:21:54'}, {'formattedCreateDate': '2099/04/10 07:45:35'},
    {'formattedInputDate': '2024/04/11'}, {'closeDate': {'dwr_date_epoch_ms': 1791530000000}},
    {'peer': {'i18nDescription': '', 'i18nOthers': ''}},
])
def test_real_detail_subject_open_fields_or_dates_must_match_listing(changed):
    from data_fetch.market_sources.psc_careers import parse_psc_jobs
    listing, _, _, detail = source_bodies()
    detail.update(changed)
    now = time.time()
    with pytest.raises(ValueError):
        parse_psc_jobs(receipt(listing, LIST_API, now), [receipt(literal(detail), DETAIL_API, now, JOB_ID)])


@pytest.mark.parametrize('body', [
    b'{code:11,code:11,data:{}}', b'{code:true,data:{}}', b'{code:0,data:{}}',
    b'{code:11,data:(function(){return {}})()}', b'{code:11,data:Infinity}',
    b'{code:11,data:' + b'1' * 400 + b'}', b'{code:11,data:new Date(true)}',
    b'{code:11,data:' + b'[' * 30 + b'0' + b']' * 30 + b'}',
])
def test_public_callback_accepts_data_only_and_finite_bounded_literals(body):
    from data_fetch.market_sources.psc_careers_literals import decode_public_callback
    with pytest.raises(ValueError):
        decode_public_callback(PREFIX.encode() + body + SUFFIX.encode())


def test_dwr_date_is_parsed_as_data_without_javascript_execution():
    from data_fetch.market_sources.psc_careers_literals import decode_public_callback
    raw = PREFIX.encode() + b'{code:11,data:{x:new Date(1791530000000)}}' + SUFFIX.encode()
    assert decode_public_callback(raw)['data']['x'] == {'dwr_date_epoch_ms': 1791530000000}


def test_cache_read_does_not_reclassify_a_date_future_at_original_fetch_as_valid():
    from data_fetch.market_sources.psc_careers import parse_psc_jobs
    listing, _, _, detail = source_bodies()
    now = time.time()
    detail['formattedUpdateDate'] = datetime.fromtimestamp(now - 600, ZoneInfo('Asia/Taipei')).strftime('%Y/%m/%d %H:%M:%S')
    with pytest.raises(ValueError):
        parse_psc_jobs(receipt(listing, LIST_API, now - 1800),
                       [receipt(literal(detail), DETAIL_API, now - 1800, JOB_ID)], now=now)


@pytest.mark.parametrize('component', ['listing_receipt', 'detail_receipts'])
def test_missing_callback_data_fails_closed_in_public_source_counter(component):
    data, value = issuer_data(), expected_value()
    archive = value['source_record_archive']
    raw = PREFIX.encode() + b'{code:11}' + SUFFIX.encode()
    target = archive['listing_receipt'] if component == 'listing_receipt' else archive['detail_receipts'][0]
    target.update(body_b64=base64.b64encode(raw).decode(), sha256=sha256(raw).hexdigest())
    assert source_record_count('alternative_data', {**data, 'alternative_data': {
        'company_legal_name_evidence': data['official_receipt'], 'job_openings_official': value}}) == 0


def test_primary_numeric_total_without_job_evidence_does_not_skip_official_details(monkeypatch):
    import alternative_data_fetcher as search
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name, psc_careers
    from data_fetch.types import FetchRequest
    data, value = issuer_data(), expected_value()
    calls = []
    monkeypatch.setattr(official_company_legal_name, 'get_official_legal_name', lambda *a: data['official_receipt'])
    monkeypatch.setattr(search, 'fetch_104_company_jobs', lambda *a, **k: {'status': 'success', 'job_count': 138, 'evidence_kind': 'job_count'})
    monkeypatch.setattr(search, 'fetch_1111_job_openings_count', lambda *a, **k: {'status': 'unavailable'})
    def read(self, job_id=None):
        calls.append(job_id)
        archive = value['source_record_archive']
        return archive['listing_receipt'] if job_id is None else archive['detail_receipts'][0]
    monkeypatch.setattr(psc_careers.PscCareersHttp, 'get_receipt', read)
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2855.TW'), {'data': data})
    assert calls == [None, JOB_ID]
    assert result.value['job_openings_official']['current_open_job_count'] == 1


def test_blank_headcount_remains_unknown_without_discarding_a_verified_open_job():
    from data_fetch.market_sources.psc_careers import parse_psc_jobs, verified_psc_job_count
    listing, _, _, detail = source_bodies()
    detail['needEmpString'] = ''
    now = time.time()
    result = parse_psc_jobs(receipt(listing, LIST_API, now), [receipt(literal(detail), DETAIL_API, now, JOB_ID)])
    assert result['job_postings'][0]['headcount_text'] is None
    assert verified_psc_job_count(result, '2855.TW', LEGAL, '23218183') == 1


def test_missing_primary_result_still_skips_keywords_after_verified_psc_recovery(monkeypatch):
    import alternative_data_fetcher as search
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name, psc_careers, taiwanjobs_company_jobs
    from data_fetch.types import FetchRequest
    data, value = issuer_data(), expected_value()
    legacy = []
    monkeypatch.setattr(official_company_legal_name, 'get_official_legal_name', lambda *a: data['official_receipt'])
    monkeypatch.setattr(search, 'fetch_104_company_jobs', lambda *a, **k: None)
    monkeypatch.setattr(taiwanjobs_company_jobs, 'fetch_taiwanjobs_company_jobs', lambda *a: {'status': 'unavailable'})
    monkeypatch.setattr(search, 'fetch_104_job_openings_count', lambda *a, **k: legacy.append('104') or {'status': 'unavailable'})
    monkeypatch.setattr(search, 'fetch_1111_job_openings_count', lambda *a, **k: legacy.append('1111') or {'status': 'unavailable'})
    def read(self, job_id=None):
        archive = value['source_record_archive']
        return archive['listing_receipt'] if job_id is None else archive['detail_receipts'][0]
    monkeypatch.setattr(psc_careers.PscCareersHttp, 'get_receipt', read)
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2855.TW'), {'data': data})
    assert legacy == []
    assert result.audit['record_count'] == 1


def test_observed_public_field_subsets_preserve_three_jobs_and_unknown_headcounts():
    from pathlib import Path
    from data_fetch.market_sources.psc_careers import parse_psc_jobs, verified_psc_job_count
    fixture = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/psc_ehr_jobs_20261009.json').read_text())
    stamp = fixture['fetched_at_epoch']
    value = parse_psc_jobs(receipt(literal(fixture['listing_data']), LIST_API, stamp),
        [receipt(literal(row), DETAIL_API, stamp, row['id']) for row in fixture['detail_data']], now=stamp + 2)
    assert verified_psc_job_count(value, '2855.TW', LEGAL, '23218183', now=stamp + 2) == 3
    assert [row['headcount_text'] for row in value['job_postings']] == ['1', None, None]
    assert all(row['published_date'] is None for row in value['job_postings'])


def test_verified_primary_postings_do_not_trigger_psc_http(monkeypatch):
    import alternative_data_fetcher as search
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name, psc_careers
    from data_fetch.types import FetchRequest
    data = issuer_data()
    monkeypatch.setattr(official_company_legal_name, 'get_official_legal_name', lambda *a: data['official_receipt'])
    monkeypatch.setattr(search, 'fetch_104_company_jobs', lambda *a, **k: {
        'status': 'success', 'evidence_kind': 'company_job_postings', 'job_count': None,
        'query_scope': 'exact_company_recent_postings', 'source': '104 Company Jobs API',
        'source_url': 'https://www.104.com.tw/jobs/search/api/jobs?keyword=issuer', 'company_name': LEGAL,
        'recent_company_job_count': 1, 'response_sha256': 'a' * 64,
        'job_postings': [{'title': 'analyst', 'employer': LEGAL, 'source_employer': LEGAL,
                         'employer_id': '23218183000', 'job_no': '12345', 'url': 'https://www.104.com.tw/job/abc12'}]})
    monkeypatch.setattr(search, 'fetch_1111_job_openings_count', lambda *a, **k: {'status': 'unavailable'})
    monkeypatch.setattr(psc_careers.PscCareersHttp, 'get_receipt', lambda *a, **k: pytest.fail('redundant official HTTP'))
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2855.TW'), {'data': data})
    assert result.value['job_openings_official'] is None and result.audit['record_count'] == 1


@pytest.mark.parametrize('component', ['listing', 'detail'])
def test_missing_callback_data_returns_unavailable_without_provider_exception(monkeypatch, component):
    from data_fetch.market_sources import psc_careers
    value = expected_value()
    archive = value['source_record_archive']
    def read(self, job_id=None):
        old = archive['listing_receipt'] if job_id is None else archive['detail_receipts'][0]
        if (job_id is None) == (component == 'listing'):
            raw = PREFIX.encode() + b'{code:11}' + SUFFIX.encode()
            return {**old, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest()}
        return old
    monkeypatch.setattr(psc_careers.PscCareersHttp, 'get_receipt', read)
    result = psc_careers.fetch_official_psc_jobs('2855.TW', LEGAL, '23218183')
    assert result['status'] == 'unavailable' and result['current_open_job_count'] is None


def test_partial_refusal_preserves_individually_verified_prior_content_and_stops_more_http(monkeypatch):
    from data_fetch.market_sources import psc_careers
    from search_provider_runtime import SourceResponseError
    listing, detail, row, _ = source_bodies()
    second = {**row, 'id': '1613781649555324660'}
    now, calls = time.time(), []
    def read(self, job_id=None):
        calls.append(job_id)
        if job_id is None: return receipt(literal([2, [row, second]]), LIST_API, now)
        if job_id == JOB_ID: return receipt(detail, DETAIL_API, now, JOB_ID)
        raise SourceResponseError('rate_limited', status_code=429)
    monkeypatch.setattr(psc_careers.PscCareersHttp, 'get_receipt', read)
    result = psc_careers.fetch_official_psc_jobs('2855.TW', LEGAL, '23218183')
    assert calls == [None, JOB_ID, second['id']]
    assert result['current_open_job_count'] == 1 and result['partial_failure_reasons'] == ['rate_limited']
    assert psc_careers.verified_psc_job_count(result, '2855.TW', LEGAL, '23218183') == 1


def test_snapshot_serialization_preserves_source_archive_and_counter():
    from data_trust_snapshot import build_data_snapshot
    data, value = issuer_data(), expected_value()
    data['alternative_data'] = {'company_legal_name_evidence': data.pop('official_receipt'), 'job_openings_official': value}
    snapshot = json.loads(json.dumps(build_data_snapshot({'data': data}, pipeline_id='v4')))
    assert source_record_count('alternative_data', snapshot['data']) == 1
    assert snapshot['data']['alternative_data']['job_openings_official']['source_record_archive'] == value['source_record_archive']
