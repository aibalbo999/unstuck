"""Public Workday postings for the listed holding company, never its subsidiaries."""
import copy
import json
from datetime import datetime, timezone

import pytest

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc).timestamp()
COMPANY_ID = '1e73f5b107d8012217d8aa3be2e00000'
SOURCE_EMPLOYER = '中國信託金融控股公司'
LEGAL_NAME = '中國信託金融控股股份有限公司'
PATH = '/job/Taipei/-_JR7016'


def listing():
    return {'total': 1, 'jobPostings': [{'title': '金控_企業永續人員', 'externalPath': PATH,
             'bulletFields': ['JR7016']}], 'facets': [{'facetParameter': 'hiringCompany',
             'values': [{'id': COMPANY_ID, 'descriptor': SOURCE_EMPLOYER, 'count': 1}]}]}


def detail():
    return {'jobPostingInfo': {'title': '金控_企業永續人員', 'jobDescription': SOURCE_EMPLOYER + '<p>推動永續金融</p>',
             'startDate': '2026-10-06', 'canApply': True, 'posted': True, 'jobReqId': 'JR7016',
             'jobPostingId': '-_JR7016', 'jobPostingSiteId': 'External',
             'externalUrl': 'https://ctbcholding.wd3.myworkdayjobs.com/External' + PATH},
             'hiringOrganization': {'name': SOURCE_EMPLOYER}}


def mock_source(monkeypatch, listing_payload=None, detail_payload=None):
    from data_fetch.market_sources import ctbc_careers
    lp, dp = listing_payload or listing(), detail_payload or detail()
    monkeypatch.setattr(ctbc_careers.time, 'time', lambda: NOW)
    def download(url, deadline, request=None):
        return json.dumps(lp if request is not None else dp, ensure_ascii=False).encode()
    monkeypatch.setattr(ctbc_careers, '_download', download)
    return ctbc_careers


def test_exact_holding_current_posting_keeps_date_and_public_receipts(monkeypatch):
    source = mock_source(monkeypatch)
    result = source.fetch_official_ctbc_jobs('2891.TW')
    assert result['status'] == 'success'
    assert result['job_count'] is None
    assert result['current_open_job_count'] == 1
    row = result['job_postings'][0]
    assert row['employer'] == LEGAL_NAME
    assert row['source_employer'] == SOURCE_EMPLOYER
    assert row['posted_date'] == '2026-10-06'
    assert row['can_apply'] is True and row['posted'] is True
    assert len(row['response_sha256']) == 64
    assert source.verified_ctbc_job_count(result, '2891.TW', LEGAL_NAME, now=NOW) == 1


@pytest.mark.parametrize('change', [
    {'hiringOrganization': {'name': '中國信託商業銀行'}},
    {'jobPostingInfo': {'canApply': False}}, {'jobPostingInfo': {'posted': False}},
    {'jobPostingInfo': {'canApply': 'true'}}, {'jobPostingInfo': {'startDate': '2026-08-24'}},
    {'jobPostingInfo': {'startDate': '2026-10-10'}}, {'jobPostingInfo': {'jobReqId': 'JR9999'}},
    {'jobPostingInfo': {'jobPostingId': '-_JR9999'}},
    {'jobPostingInfo': {'jobPostingSiteId': 'Internal'}},
    {'jobPostingInfo': {'externalUrl': 'https://evil.example/External' + PATH}},
    {'jobPostingInfo': {'jobDescription': SOURCE_EMPLOYER + '<p>履歷投遞已截止</p>'}},
    {'jobPostingInfo': {'jobDescription': SOURCE_EMPLOYER + '<p>招募截止至2026.05.31</p>'}},
    {'jobPostingInfo': {'jobDescription': SOURCE_EMPLOYER + '<p>Application deadline: 2026-10-08</p>'}},
    {'jobPostingInfo': {'jobDescription': SOURCE_EMPLOYER + '<p>招募截止日期另行公告</p>'}},
])
def test_closed_stale_subsidiary_or_inconsistent_job_is_not_success(monkeypatch, change):
    payload = detail()
    for key, value in change.items():
        payload[key].update(value)
    source = mock_source(monkeypatch, detail_payload=payload)
    result = source.fetch_official_ctbc_jobs('2891.TW')
    assert result['status'] == 'unavailable'
    assert result['current_open_job_count'] is None
    assert source.verified_ctbc_job_count(result, '2891.TW', LEGAL_NAME, now=NOW) == 0


@pytest.mark.parametrize('mutation', ['wrong_company', 'wrong_id', 'unsafe_path', 'conflict', 'bad_total'])
def test_listing_cannot_redirect_or_widen_company_scope(monkeypatch, mutation):
    payload = listing()
    if mutation == 'wrong_company': payload['facets'][0]['values'][0]['descriptor'] = '中國信託商業銀行'
    if mutation == 'wrong_id': payload['facets'][0]['values'][0]['id'] = 'a' * 32
    if mutation == 'unsafe_path': payload['jobPostings'][0]['externalPath'] = '/job/../../userprofile'
    if mutation == 'conflict':
        payload['jobPostings'].append({**payload['jobPostings'][0], 'title': 'other'})
        payload['total'] = payload['facets'][0]['values'][0]['count'] = 2
    if mutation == 'bad_total': payload['total'] = True
    source = mock_source(monkeypatch, listing_payload=payload)
    assert source.fetch_official_ctbc_jobs('2891.TW')['status'] == 'unavailable'


def test_unrelated_issuer_never_makes_workday_request(monkeypatch):
    from data_fetch.market_sources import ctbc_careers
    monkeypatch.setattr(ctbc_careers, '_download', lambda *a, **kw: pytest.fail('unexpected source fetch'))
    assert ctbc_careers.fetch_official_ctbc_jobs('2882.TW')['status'] == 'unavailable'


def test_provider_and_trust_gate_accept_only_exact_identity(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count
    source = mock_source(monkeypatch)
    monkeypatch.setattr(alternative_data_fetcher, 'fetch_104_company_jobs', lambda *a, **kw: {'status': 'unavailable'})
    monkeypatch.setattr(alternative_data_fetcher, 'fetch_104_job_openings_count', lambda *a, **kw: {'status': 'unavailable'})
    monkeypatch.setattr(alternative_data_fetcher, 'fetch_1111_job_openings_count', lambda *a, **kw: {'status': 'unavailable'})
    data = {'ticker': '2891.TW', 'company_name': '中信金', 'quote_type': 'EQUITY',
            'company_identity': {'ticker': '2891.TW', 'official_name': '中信金',
                                'legal_name': LEGAL_NAME, 'instrument_type': 'EQUITY'}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2891.TW'), {'data': data})
    assert result.status == 'success'
    assert result.audit['record_count'] == 1
    assert result.value['status'] == 'partial'
    assert result.value['component_statuses']['official_careers']['provider'] == source.PROVIDER
    assert source_record_count('alternative_data', {**data, 'alternative_data': result.value}) == 1
    forged = copy.deepcopy(result.value)
    forged['job_openings_official']['job_postings'][0]['source_employer'] = '中國信託商業銀行'
    assert source_record_count('alternative_data', {**data, 'alternative_data': forged}) == 0
    for change in ({'quote_type': 'FUND'}, {'company_identity': {**data['company_identity'], 'ticker': '2882.TW'}},
                   {'company_identity': {**data['company_identity'], 'official_name': '中信銀行'}}):
        assert source_record_count('alternative_data', {**data, **change, 'alternative_data': result.value}) == 0


def test_receipt_revalidation_does_not_trust_status_or_count_alone(monkeypatch):
    source = mock_source(monkeypatch)
    good = source.fetch_official_ctbc_jobs('2891.TW')
    for key, val in [('fetched_at_epoch', NOW-86401), ('fetched_at_epoch', float('nan')),
                     ('response_sha256', None), ('listing_url', 'https://evil.example'),
                     ('current_open_job_count', 999), ('company_id', 'b'*32)]:
        assert source.verified_ctbc_job_count({**good, key: val}, '2891.TW', LEGAL_NAME, now=NOW) == 0
    for key, val in [('can_apply', False), ('posted', 'true'), ('posted_date', '2026-08-24'),
                     ('response_sha256', None), ('source_url', 'https://evil.example'),
                     ('url', 'https://evil.example'), ('title', '')]:
        bad = copy.deepcopy(good)
        bad['job_postings'][0][key] = val
        assert source.verified_ctbc_job_count(bad, '2891.TW', LEGAL_NAME, now=NOW) == 0


def test_official_slug_may_start_with_requisition_id_delimiter(monkeypatch):
    payload, posting = listing(), detail()
    payload['jobPostings'][0].update(externalPath='/job/Taipei/_JR9297', bulletFields=['JR9297'])
    posting['jobPostingInfo'].update(jobReqId='JR9297', jobPostingId='_JR9297',
        externalUrl='https://ctbcholding.wd3.myworkdayjobs.com/External/job/Taipei/_JR9297')
    source = mock_source(monkeypatch, payload, posting)
    assert source.fetch_official_ctbc_jobs('2891.TW')['status'] == 'success'


def test_public_response_fixture_replay_preserves_four_exact_recent_open_jobs(monkeypatch):
    from pathlib import Path
    from data_fetch.market_sources import ctbc_careers as source
    fixture = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/ctbc_2891_jobs_20261009.json').read_text())
    now = fixture['captured_at_epoch']
    monkeypatch.setattr(source.time, 'time', lambda: now)
    monkeypatch.setattr(source, '_download', lambda url, deadline, request=None: fixture['responses'][url].encode())
    result = source.fetch_official_ctbc_jobs('2891.TW')
    assert result['issuer_listing_count'] == 8
    assert result['rejected_count'] == 4
    assert [row['job_no'] for row in result['job_postings']] == ['JR7016', 'JR9297', 'JR7300', 'JR8696']
    assert source.verified_ctbc_job_count(result, '2891.TW', LEGAL_NAME, now=now) == 4


def test_104_success_does_not_call_workday_fallback(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import ctbc_careers
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(ctbc_careers, 'fetch_official_ctbc_jobs', lambda ticker: pytest.fail('redundant fallback'))
    monkeypatch.setattr(alternative_data_fetcher, 'fetch_104_company_jobs', lambda *a, **kw: {
        'status':'success', 'evidence_kind':'company_job_postings', 'job_count':None,
        'query_scope':'exact_company_recent_postings', 'source':'104 Company Jobs API',
        'source_url':'https://www.104.com.tw/jobs/search/api/jobs?keyword=holding',
        'company_name':LEGAL_NAME, 'recent_company_job_count':1, 'response_sha256':'a'*64,
        'job_postings':[{'title':'financial analyst','employer':LEGAL_NAME,'source_employer':LEGAL_NAME,
                         'employer_id':'123000','job_no':'12345','url':'https://www.104.com.tw/job/abc12'}]})
    monkeypatch.setattr(alternative_data_fetcher, 'fetch_1111_job_openings_count', lambda *a, **kw: {'status':'unavailable'})
    data={'ticker':'2891.TW','company_name':'中信金','quote_type':'EQUITY',
          'company_identity':{'ticker':'2891.TW','official_name':'中信金','legal_name':LEGAL_NAME,'instrument_type':'EQUITY'}}
    result=AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2891.TW'),{'data':data})
    assert result.value['job_openings_official'] is None
    assert result.audit['record_count'] == 1


def test_known_old_listing_is_rejected_without_spending_detail_request_budget(monkeypatch):
    source = mock_source(monkeypatch)
    payload = listing()
    payload['jobPostings'][0]['postedOn'] = 'Posted 30+ Days Ago'
    calls = []
    def download(url, deadline, request=None):
        calls.append(url)
        if request is None: pytest.fail('known old posting does not need individual fetch')
        return json.dumps(payload).encode()
    monkeypatch.setattr(source, '_download', download)
    assert source.fetch_official_ctbc_jobs('2891.TW')['status'] == 'unavailable'
    assert calls == [source.API_URL]


@pytest.mark.parametrize('text', ['申請期限：2026-10-08', '招募已停止',
                                 'Applications close on 2026-10-08', '申請期限另行公告'])
def test_closing_synonyms_cannot_pass_posted_can_apply_flags(monkeypatch, text):
    payload = detail()
    payload['jobPostingInfo']['jobDescription'] = SOURCE_EMPLOYER + '<p>' + text + '</p>'
    source = mock_source(monkeypatch, detail_payload=payload)
    assert source.fetch_official_ctbc_jobs('2891.TW')['status'] == 'unavailable'


@pytest.mark.parametrize('text', ['申請期限：2026-10-31', 'Applications close on 2026-10-31'])
def test_explicit_future_closing_date_is_preserved(monkeypatch, text):
    payload = detail()
    payload['jobPostingInfo']['jobDescription'] = SOURCE_EMPLOYER + '<p>' + text + '</p>'
    source = mock_source(monkeypatch, detail_payload=payload)
    result = source.fetch_official_ctbc_jobs('2891.TW')
    assert result['status'] == 'success'
    assert result['job_postings'][0]['closing_date'] == '2026-10-31'


def test_oversized_receipt_timestamp_is_rejected_without_breaking_trust(monkeypatch):
    source = mock_source(monkeypatch)
    good = source.fetch_official_ctbc_jobs('2891.TW')
    good['fetched_at_epoch'] = 10**400
    assert source.verified_ctbc_job_count(good, '2891.TW', LEGAL_NAME, now=NOW) == 0


def test_unverified_104_rows_do_not_suppress_official_fallback(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    mock_source(monkeypatch)
    monkeypatch.setattr(alternative_data_fetcher, 'fetch_104_company_jobs', lambda *a, **kw: {
        'status':'success','evidence_kind':'company_job_postings','job_count':None,
        'job_postings':[{'title':'declared without source receipt'}]})
    monkeypatch.setattr(alternative_data_fetcher, 'fetch_1111_job_openings_count', lambda *a, **kw: {'status':'unavailable'})
    data={'ticker':'2891.TW','company_name':'中信金','quote_type':'EQUITY',
          'company_identity':{'ticker':'2891.TW','official_name':'中信金','legal_name':LEGAL_NAME,'instrument_type':'EQUITY'}}
    result=AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('2891.TW'),{'data':data})
    assert result.value['job_openings_official']['status'] == 'success'
    assert result.audit['record_count'] == 1


@pytest.mark.parametrize('period, expected', [
    ('2026-10-01 至 2026-10-31', 'success'),
    ('2026-10-01 ~ 2026-10-08', 'unavailable'),
    ('2026-10-10 至 2026-10-31', 'unavailable'),
    ('2026-10-01 至另行公告', 'unavailable'),
])
def test_application_period_checks_both_bounds(monkeypatch, period, expected):
    payload = detail()
    payload['jobPostingInfo']['jobDescription'] = SOURCE_EMPLOYER + '<p>申請期間：' + period + '</p>'
    source = mock_source(monkeypatch, detail_payload=payload)
    result = source.fetch_official_ctbc_jobs('2891.TW')
    assert result['status'] == expected
    if expected == 'success':
        assert result['job_postings'][0]['closing_date'] == '2026-10-31'
