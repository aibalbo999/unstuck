"""A real helper boundary can add transport evidence, never another acquisition."""
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
import sqlite3
from copy import deepcopy
from types import SimpleNamespace

import pytest

import httpx


def payload():
    from official_institutional_source import TWSE_FIELDS
    return {'stat': 'OK', 'date': '20261005', 'fields': TWSE_FIELDS,
            'hints': '單位：股', 'data': [['1623', '大東電', '10000', '2000', '8000',
                '0', '0', '0', '2000', '1000', '1000', '-500', '500', '1000',
                '-500', '0', '0', '0', '8500']]}


def fetch_native(monkeypatch, *, enabled=True, source_name="institutional_trading", response_change=None,
                 injected=False, primary_status=None, primary_timeout=False):
    import official_institutional_source as source
    import external_http_client
    import search_provider_runtime as runtime
    import official_source_runtime
    import search_admission
    from provider_correlation import correlation_scope, source_operation
    from finmind_transport_receipts import receipt_observation_scope

    @contextmanager
    def admission(*args, **kwargs):
        yield lambda: True

    monkeypatch.setattr(search_admission, 'endpoint_admission', admission)
    monkeypatch.setattr(runtime, 'cooldown_state', lambda *args: {})
    monkeypatch.setattr(official_source_runtime, 'failure_state_snapshot', lambda *args: {})
    monkeypatch.setattr(official_source_runtime, 'reset_failure_history_after_success', lambda *args, **kwargs: None)
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        monkeypatch.delenv(key, raising=False)
    raw = json.dumps(payload(), ensure_ascii=False).encode()
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if len(calls)==1 and primary_timeout:
            raise httpx.ConnectTimeout('existing primary transport timeout')
        status = primary_status if len(calls)==1 and primary_status else 200
        response = httpx.Response(status, content=raw, request=httpx.Request('GET', url),
                                  headers={'content-type': 'application/json'})
        if response_change:
            response_change(response)
        return response

    monkeypatch.setattr(external_http_client.httpx, 'get', get)
    if injected:
        monkeypatch.setattr(external_http_client, 'sync_get', get)
    with correlation_scope(ticker='1623.TW', fetch_id='native-official-test'), \
            source_operation(source_name, 'FinMind'), receipt_observation_scope(enabled):
        report = source._fetch_report('TWSE', '2026-10-05', 8)
    assert len(calls) == (2 if primary_timeout else 1)
    return report, raw


def test_existing_native_get_binds_full_body_iso_time_and_zero_record_child(monkeypatch):
    import provider_sla
    from official_response_evidence import read_response
    from provider_acquisition import get_provider_acquisition_summary
    report, raw = fetch_native(monkeypatch)
    receipt = report.get('native_http_receipt')
    assert isinstance(receipt, dict)
    assert receipt['http_status_observed'] is True and receipt['response_complete'] is True
    assert receipt['cache_hit'] is False and read_response(receipt) == raw
    assert receipt['raw_response_sha256'] == sha256(raw).hexdigest()
    assert datetime.fromisoformat(report['raw_evidence']['retrieved_at']).timestamp() == receipt['retrieved_at']
    assert read_response(report['raw_evidence']) == raw
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as db:
        rows = list(db.execute('select provider,record_count,details_json from provider_sla_events'))
    children = [q for q in rows if q[0] == 'TWSE T86 native HTTP']
    assert len(children) == 1 and children[0][1] == 0
    details = json.loads(children[0][2])
    assert details['original_http_receipts'][0]['response_sha256'] == sha256(raw).hexdigest()
    assert 'raw_response_path' not in children[0][2] and 'native_http_manifest' not in children[0][2]
    summary = get_provider_acquisition_summary('all')['sources'][0]
    assert summary['fetch_attempts'] == summary['fetched_count'] == 1
    assert summary['aggregate_count'] == 1


@pytest.mark.parametrize('change', ['from_cache', 'cache_extension', 'cookie', 'authorization',
                                  'content_range', 'short_length', 'wrong_method', 'wrong_url'])
def test_native_boundary_refuses_ambiguous_transport_without_changing_parser(monkeypatch,change):
    def alter(response):
        if change=='from_cache':response.from_cache=True
        elif change=='cache_extension':response.extensions['cache_hit']=True
        elif change in ('cookie','authorization'):response.request.headers[change]='fixture-not-a-secret'
        elif change=='content_range':response.headers['content-range']='bytes 0-99/999'
        elif change=='short_length':response.headers['content-length']='999'
        elif change=='wrong_method':response.request.method='POST'
        else:response.request=httpx.Request('GET','https://www.twse.com.tw/wrong')
    report,_=fetch_native(monkeypatch,response_change=alter)
    assert 'native_http_receipt'not in report
    assert report['rows']['1623']['foreign']==8000


@pytest.mark.parametrize('options',[{'enabled':False},{'source_name':'other_source'},{'injected':True}])
def test_research_wrong_owner_and_injected_helper_cannot_make_native_receipt(monkeypatch,options):
    report,_=fetch_native(monkeypatch,**options)
    assert 'native_http_receipt'not in report


def test_native_receive_epoch_precedes_parser_and_floors_iso_microseconds(monkeypatch):
    import external_http_client
    from datetime import timezone
    arrived=datetime.fromisoformat('2026-10-05T14:29:59.999999+00:00').timestamp()
    monkeypatch.setattr(external_http_client,'time',SimpleNamespace(time=lambda:arrived))
    report,_=fetch_native(monkeypatch)
    stamp=datetime.fromisoformat(report['raw_evidence']['retrieved_at'])
    assert stamp<datetime(2026,10,5,14,30,tzinfo=timezone.utc)
    assert stamp.timestamp()==report['native_http_receipt']['retrieved_at']<=arrived


def test_optional_archive_failure_keeps_original_parser_and_receive_time(monkeypatch):
    import institutional_http_capsule as capsule
    monkeypatch.setattr(capsule,'archive_response',lambda *a,**k:(_ for _ in ()).throw(OSError('fixture archive unavailable')))
    report,_=fetch_native(monkeypatch)
    assert 'native_http_receipt'not in report
    assert report['raw_evidence']['status']=='archived'
    assert report['rows']['1623']['foreign']==8000


@pytest.mark.parametrize('status',[403,429])
def test_access_and_quota_denials_never_trigger_official_mirror(monkeypatch,status):
    with pytest.raises(httpx.HTTPStatusError)as caught:
        fetch_native(monkeypatch,primary_status=status)
    assert caught.value.response.status_code==status


def test_existing_timeout_mirror_get_has_its_own_exact_receipt(monkeypatch):
    report,raw=fetch_native(monkeypatch,primary_timeout=True)
    assert report['fallback_reason']=='timeout'
    assert report['native_http_receipt']['source_url'].startswith('https://wwwc.twse.com.tw/')
    assert report['native_http_receipt']['source_url']==report['raw_evidence']['source_url']


@pytest.mark.parametrize('change',['origin','date','method','complete','epoch','body_size','manifest','iso'])
def test_immutable_binding_rejects_tampered_receipt_and_iso_original(monkeypatch,change):
    from institutional_http_capsule import validate_receipt
    report,_=fetch_native(monkeypatch)
    receipt=deepcopy(report['native_http_receipt']);spec=deepcopy(receipt['source_spec']);iso=deepcopy(report['raw_evidence'])
    if change=='origin':receipt['origin']['fetch_id']='another-fetch'
    elif change=='date':receipt['source_spec']['request_day']='2026-10-06'
    elif change=='method':receipt['request_method']='POST'
    elif change=='complete':receipt['response_complete']=False
    elif change=='epoch':receipt['retrieved_at']+=1
    elif change=='body_size':receipt['raw_response_bytes']+=1
    elif change=='manifest':receipt['native_http_manifest']['raw_response_bytes']+=1
    else:iso['retrieved_at']='2026-10-05T14:30:00+00:00'
    with pytest.raises(ValueError):validate_receipt(receipt,spec,iso)


def test_transport_original_does_not_override_wrong_payload_period(monkeypatch):
    import provider_sla
    wrong=payload();wrong['date']='20261006'
    monkeypatch.setattr(__import__(__name__),'payload',lambda:wrong)
    with pytest.raises(Exception):fetch_native(monkeypatch)
    with sqlite3.connect(provider_sla.TASK_DB_PATH)as db:
        rows=list(db.execute('select provider,status,record_count from provider_sla_events'))
    assert any(r[0]=='TWSE T86 native HTTP'and r[2]==0 for r in rows)
    assert not any(r[2]>0 and r[1]=='success' for r in rows)


@pytest.mark.parametrize('openapi',[False,True])
def test_exact_tpex_native_get_has_zero_record_evidence_without_publication_claim(monkeypatch,openapi):
    import external_http_client as client
    from institutional_http_capsule import request_spec,observe_get,validate_receipt
    from official_institutional_source import _url,TPEX_SOURCE
    from tpex_openapi_institutional import URL,SOURCE
    from provider_correlation import correlation_scope,source_operation
    from finmind_transport_receipts import receipt_observation_scope
    url=URL if openapi else _url('TPEX','2026-10-05');provider=SOURCE if openapi else TPEX_SOURCE
    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
        monkeypatch.delenv(key,raising=False)
    raw=b'[{"transport_only":true}]'
    monkeypatch.setattr(client.httpx,'get',lambda u,**kw:httpx.Response(200,content=raw,request=httpx.Request('GET',u)))
    spec=request_spec('TPEX','2026-10-05',url,provider)
    with correlation_scope(ticker='5314.TWO',fetch_id='tpex-native-test'),source_operation('institutional_trading','FinMind'),receipt_observation_scope(True),observe_get(spec)as holder:
        response=client.sync_get(url,provider=provider)
    assert response.content==validate_receipt(holder['receipt'],spec)==raw
    assert holder['receipt']['source_spec']['market']=='TPEX'
    assert 'publication_observation'not in holder['receipt']


@pytest.mark.parametrize('change',['host','extra_query','day','market','provider'])
def test_request_admission_never_guesses_another_endpoint(change):
    from institutional_http_capsule import request_spec
    from official_institutional_source import _url,TWSE_SOURCE
    args=['TWSE','2026-10-05',_url('TWSE','2026-10-05'),TWSE_SOURCE]
    if change=='host':args[2]=args[2].replace('www.twse.com.tw','evil.example')
    elif change=='extra_query':args[2]+='&unused=true'
    elif change=='day':args[1]='2026-10-06'
    elif change=='market':args[0]='TPEX'
    else:args[3]='FinMind'
    with pytest.raises(ValueError):request_spec(*args)


def test_private_manifest_and_paths_never_enter_projected_prompt(monkeypatch):
    from prompt_evidence import prompt_evidence_copy
    report,_=fetch_native(monkeypatch)
    projected=prompt_evidence_copy(report)
    encoded=json.dumps(projected,ensure_ascii=False)
    assert 'raw_response_path'not in encoded and'native_http_manifest'not in encoded
    assert projected['native_http_receipt']['raw_response_sha256']==report['native_http_receipt']['raw_response_sha256']
    assert projected['rows']==report['rows']
