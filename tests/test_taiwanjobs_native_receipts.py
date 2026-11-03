"""HTTP originals explain failed jobs without qualifying the employer or jobs."""
from datetime import date
from hashlib import sha256

import httpx
import pytest

from data_fetch.market_sources import taiwanjobs_company_jobs as jobs


def native_client(monkeypatch, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    def create(**kwargs):
        client.event_hooks = kwargs.get('event_hooks', {})
        return client
    monkeypatch.setattr(jobs.httpx, 'Client', create)
    return client


def test_complete_native_error_body_is_retained_without_a_job_success(monkeypatch):
    from official_response_evidence import read_response
    body = b'<html>Service temporarily unavailable</html>'
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, content=body)

    native_client(monkeypatch, handler)
    value = jobs.fetch_taiwanjobs_company_jobs('5314.TWO', '世紀民生科技股份有限公司', '22099815')
    assert value['status'] == 'unavailable'
    assert value['current_open_job_count'] is None
    assert value['reason_code'] == 'server_error'
    assert value['failure_stage'] == 'search_form'
    assert len(calls) == value['http_request_count'] == 1
    receipt, = value['component_receipts']
    assert receipt['http_request_sent'] is True
    assert receipt['http_status'] == 503
    assert receipt['response_complete'] is True
    assert receipt['response_sha256'] == sha256(body).hexdigest()
    assert read_response(receipt['original_receipt']) == body
    assert receipt['original_receipt']['issuer_and_open_job_semantics_verified'] is False


def test_connect_timeout_is_unknown_http_and_has_no_fabricated_body(monkeypatch):
    def handler(request):
        raise httpx.ConnectTimeout('not a response', request=request)

    native_client(monkeypatch, handler)
    value = jobs.fetch_taiwanjobs_company_jobs('5314.TWO', '世紀民生科技股份有限公司', '22099815')
    assert value['reason_code'] == 'timeout'
    assert value['http_request_count'] == 0
    receipt, = value['component_receipts']
    assert receipt['http_request_sent'] is None
    assert receipt['http_status'] is None
    assert receipt['response_complete'] is False
    assert 'original_receipt' not in receipt


def test_customer_mention_and_wrong_ubn_stay_rejected_after_http_capture(monkeypatch):
    company = '泰豐輪胎股份有限公司'

    def handler(request):
        if request.url.path.endswith('job_search_list.aspx') and request.method == 'GET':
            body = '<form id="form1"><input name="__VIEWSTATE" type="hidden" value="private-state"><input name="ctl00$CPH1$SearchBar$txtKeywordComp" type="text"></form>'
        elif request.method == 'POST':
            return httpx.Response(303, headers={'location': jobs.RESULT_PATH})
        elif request.url.path.lower() == jobs.RESULT_PATH:
            body = f'<a href="../jobwanted/company_desc2.aspx?EMPLOYER_ID=151759&amp;BRANCH_ID=">{company}</a>'
        else:
            body = f'<h2 id="CPH1_h1_COMPNAME">華敏機械有限公司</h2><dl><dt>統一編號</dt><dd>99999999</dd></dl><p>客戶：{company}</p>'
        return httpx.Response(200, text=body)

    native_client(monkeypatch, handler)
    value = jobs.fetch_taiwanjobs_company_jobs('2102.TW', company, '44721408', today=date(2026, 11, 3))
    assert value['status'] == 'unavailable'
    assert value['job_postings'] == []
    assert value['current_open_job_count'] is None
    assert value['reason_code'] == 'employer_identity_mismatch'
    assert value['failure_stage'] == 'company'
    assert value['http_request_count'] == 4  # POST redirect and its actual GET are separate.
    assert [r['request_method'] for r in value['component_receipts']] == ['GET', 'POST', 'GET', 'GET']


def test_read_timeout_after_headers_retains_known_http_without_complete_body(monkeypatch):
    class Interrupted(httpx.SyncByteStream):
        def __iter__(self):
            yield b'<html>partial'
            raise httpx.ReadTimeout('body did not finish')
    native_client(monkeypatch, lambda request: httpx.Response(200, stream=Interrupted()))
    value = jobs.fetch_taiwanjobs_company_jobs('5314.TWO', '世紀民生科技股份有限公司', '22099815')
    assert value['status'] == 'unavailable'
    assert value['reason_code'] == 'timeout'
    assert value['http_request_count'] == 1
    receipt, = value['component_receipts']
    assert receipt['http_request_sent'] is True
    assert receipt['http_status'] == 200
    assert receipt['response_complete'] is False
    # httpx did not expose the partial decoded bytes to this caller.
    assert 'response_bytes' not in receipt
    assert 'response_sha256' not in receipt
    assert 'original_receipt' not in receipt


def test_transport_sql_receipt_does_not_change_acquisition_denominator(monkeypatch):
    from provider_correlation import correlation_scope
    from provider_acquisition import project_acquisition_events
    import provider_sla
    import json

    recorded = []
    monkeypatch.setattr(provider_sla, 'record_source_audit_entries', lambda rows: recorded.extend(rows))
    native_client(monkeypatch, lambda request: httpx.Response(200, text='<html>not a search form</html>'))
    with correlation_scope(replace=True, ticker='5314.TWO', fetch_id='native-test'):
        with jobs.receipt_observation_scope(True):
            value = jobs.fetch_taiwanjobs_company_jobs('5314.TWO', '世紀民生科技股份有限公司', '22099815')
    assert value['status'] == 'unavailable'
    row, = recorded
    assert row['event_kind'] == 'http_transport_receipt'
    assert row['selection_policy'] == 'transport-receipt-only:v1'
    assert row['record_count'] == 0
    assert row['http_status'] == 200
    assert row['raw_http_receipt']['response_complete'] is True
    assert 'private-state' not in json.dumps(row)
    projected = project_acquisition_events([
        {'source': row['source'], 'provider': row['provider'], 'status': row['status'],
         'record_count': 0, 'message': row['message'], 'created_at': 1000,
         'details_json': json.dumps(row)}], window='last_24h', now=1001)
    source, = projected['sources']
    assert source['fetch_attempts'] == source['fetched_count'] == 0
    assert source['http_attempt_count'] == 1


def test_native_receipt_reaches_sql_with_only_public_fingerprints(monkeypatch):
    import json
    import sqlite3
    import provider_sla
    from provider_correlation import correlation_scope

    body = b'<html>private-state not a job listing</html>'
    native_client(monkeypatch, lambda request: httpx.Response(200, content=body))
    with correlation_scope(replace=True, ticker='5314.TWO', fetch_id='native-sql-test'):
        with jobs.receipt_observation_scope(True):
            value = jobs.fetch_taiwanjobs_company_jobs('5314.TWO', '世紀民生科技股份有限公司', '22099815')
    assert value['status'] == 'unavailable'
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as db:
        saved, = db.execute("SELECT details_json FROM provider_sla_events WHERE json_extract(details_json,'$.fetch_id')='native-sql-test'").fetchone()
    receipt, = json.loads(saved)['original_http_receipts']
    assert receipt['response_sha256'] == sha256(body).hexdigest()
    assert receipt['source_url_sha256'] == sha256(jobs.SEARCH_URL.encode()).hexdigest()
    assert receipt['request_method'] == 'GET'
    assert receipt['response_complete'] is True
    assert receipt['http_status_observed'] is True
    assert receipt['original_cache_hit'] is False
    for forbidden in ('private-state', '__VIEWSTATE', 'https://', 'raw_response_path', 'headers'):
        assert forbidden not in saved


@pytest.mark.parametrize('enabled', [False, None])
def test_disabled_provider_telemetry_cannot_write_native_rows(monkeypatch, enabled):
    import provider_sla
    from provider_correlation import correlation_scope
    recorded = []
    monkeypatch.setattr(provider_sla, 'record_source_audit_entries', lambda rows: recorded.extend(rows))
    native_client(monkeypatch, lambda request: httpx.Response(503, content=b'unavailable'))
    with correlation_scope(replace=True, ticker='5314.TWO', fetch_id='disabled-test'):
        with jobs.receipt_observation_scope(enabled):
            value = jobs.fetch_taiwanjobs_company_jobs('5314.TWO', '世紀民生科技股份有限公司', '22099815')
    assert value['status'] == 'unavailable'
    assert value['http_request_count'] == 1
    assert recorded == []


def test_injected_client_cannot_claim_new_native_http():
    from test_taiwanjobs_company_jobs import FakeClient
    value = jobs.fetch_taiwanjobs_company_jobs('3023.TW', '信邦電子股份有限公司', '23542766',
                                              client=FakeClient(), today=date(2026, 11, 3))
    assert value['status'] == 'success'
    assert value['http_request_count'] == 0
    assert all(row['http_request_sent'] is None and 'original_receipt' not in row
               for row in value['component_receipts'])


def test_unbound_redirect_query_cannot_be_archived_as_public_evidence(monkeypatch):
    import json
    import sqlite3
    import provider_sla
    from provider_correlation import correlation_scope
    def handler(request):
        if not request.url.query:
            return httpx.Response(302, headers={'location': jobs.SEARCH_URL + '?token=private-query'})
        return httpx.Response(200, text='<html>not a search form</html>')
    native_client(monkeypatch, handler)
    with correlation_scope(replace=True, ticker='5314.TWO', fetch_id='query-privacy-test'):
        with jobs.receipt_observation_scope(True):
            value = jobs.fetch_taiwanjobs_company_jobs('5314.TWO', '世紀民生科技股份有限公司', '22099815')
    assert value['status'] == 'unavailable'
    last = value['component_receipts'][-1]
    assert last['source_url'] is None
    assert 'original_receipt' not in last
    assert 'private-query' not in str(value)
    assert value['http_request_count'] == 2
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as db:
        rows = db.execute("SELECT details_json FROM provider_sla_events WHERE json_extract(details_json,'$.fetch_id')='query-privacy-test'ORDER BY id").fetchall()
    assert len(rows) == 2
    saved = rows[-1][0]
    assert json.loads(saved)['component_statuses']['transport']['response_complete'] is True
    assert 'private-query' not in saved and '?token=' not in saved


def test_cached_http_response_cannot_become_a_native_sample(monkeypatch):
    def handler(request):
        response = httpx.Response(200, text='<html>not a search form</html>')
        response.from_cache = True
        return response
    native_client(monkeypatch, handler)
    value = jobs.fetch_taiwanjobs_company_jobs('5314.TWO', '世紀民生科技股份有限公司', '22099815')
    receipt, = value['component_receipts']
    assert value['http_request_count'] == 0
    assert receipt['cache_hit'] is True and receipt['http_request_sent'] is False
    assert 'original_receipt' not in receipt


@pytest.mark.parametrize('expires,expected', [('2026/12/31', 1), ('2026/11/02', 0)])
def test_native_originals_do_not_replace_open_job_qualification(monkeypatch, expires, expected):
    from test_taiwanjobs_company_jobs import FakeClient
    fake = FakeClient(expires=expires)

    def handler(request):
        if request.method == 'POST':
            return httpx.Response(303, headers={'location': jobs.RESULT_PATH})
        result = (fake.post(str(request.url), {}) if request.url.path == jobs.RESULT_PATH
                  else fake.get(str(request.url)))
        return httpx.Response(200, content=result.content)

    native_client(monkeypatch, handler)
    value = jobs.fetch_taiwanjobs_company_jobs('3023.TW', '信邦電子股份有限公司', '23542766',
                                              today=date(2026, 11, 3))
    assert value['http_request_count'] == 5
    assert jobs.verified_taiwanjobs_job_count(value, '3023.TW', '信邦電子股份有限公司', '23542766') == expected
    assert value['status'] == ('success' if expected else 'unavailable')
    assert all(r['response_complete'] is True for r in value['component_receipts'])
