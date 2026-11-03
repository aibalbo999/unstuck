import json
import sqlite3
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

import provider_sla
from provider_acquisition import get_provider_acquisition_summary


def test_http_and_local_block_are_distinct_and_details_persist():
    common = {'source': 'search_upstream', 'provider': 'Brave', 'status': 'unavailable',
              'record_count': 0, 'error_kind': 'rate_limited', 'http_status': 429, 'retry_at': 1900000000,
              'result_quality_satisfied': True, 'result_publisher_count': 3,
              'qualified_result_status': 'sufficient_qualified_results'}
    provider_sla.record_source_audit_entries([
        {**common, 'event_kind': 'http_attempt', 'http_request_sent': True, 'outcome': 'failure'},
        {**common, 'event_kind': 'local_block', 'http_request_sent': False, 'outcome': 'cooldown',
         'api_key': 'must-not-persist'},
    ])
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as conn:
        details = [json.loads(row[0]) for row in conn.execute('SELECT details_json FROM provider_sla_events')]
    assert details[1]['retry_at'] == 1900000000
    assert details[1]['http_request_sent'] is False
    assert 'api_key' not in details[1]
    assert details[0]['result_quality_satisfied'] is True
    assert details[0]['result_publisher_count'] == 3
    assert details[0]['qualified_result_status'] == 'sufficient_qualified_results'
    row = get_provider_acquisition_summary()['sources'][0]
    assert row['http_attempt_count'] == 1
    assert row['local_block_count'] == 1
    assert row['fetch_attempts'] == 1
    assert row['providers'][0]['last_details']['outcome'] == 'cooldown'


def test_legacy_readonly_projection_does_not_require_migration(tmp_path, monkeypatch):
    path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE provider_sla_events(id INTEGER, source TEXT, provider TEXT, status TEXT, record_count INTEGER, message TEXT, created_at REAL)')
        conn.execute("INSERT INTO provider_sla_events VALUES(1, 'news', 'legacy', 'success', 1, '', 100)")
    monkeypatch.setattr(provider_sla, 'TASK_DB_PATH', str(path))
    result = get_provider_acquisition_summary('all')
    assert result['available'] is True
    assert result['sources'][0]['http_attempt_count'] == 0
    assert result['sources'][0]['fetched_count'] == 1


def captured_transport():
    return json.loads((Path(__file__).parent/'fixtures/source_acquisition/mops_2905_transport_20261103.json').read_text())


def test_actual_complete_components_retain_transport_facts_without_raw_urls_in_sql():
    entry=captured_transport();provider_sla.record_source_audit_entries([entry])
    with sqlite3.connect(provider_sla.TASK_DB_PATH)as c:
        raw=c.execute('select details_json from provider_sla_events order by id desc limit 1').fetchone()[0]
    details=json.loads(raw)
    assert len(details['component_statuses'])==19
    for key,original in entry['component_statuses'].items():
        saved=details['component_statuses'][key]
        for field in ('http_request_sent','response_complete','request_method','http_status','response_bytes','response_sha256'):
            assert saved[field]==original[field]
        assert saved['request_url_sha256']==sha256(original['url'].encode()).hexdigest()
    assert 'https://'not in raw and 'raw_response_path'not in raw
    assert details['http_request_count']==19
    summary=get_provider_acquisition_summary()['sources'][0]
    assert summary['fetch_attempts']==summary['fetched_count']==1


def test_list_component_order_and_twenty_item_bound_preserve_partial_and_cache_states():
    from provider_observation_details import observation_details
    complete=deepcopy(captured_transport()['component_statuses']['0'])
    partial={**complete,'response_complete':False,'status':'error','response_bytes':0}
    cached={**complete,'http_request_sent':False,'cache_hit':True}
    values=[partial,None,cached,*[complete]*22]
    result=observation_details({'component_statuses':values})['component_statuses']
    assert isinstance(result,list)and len(result)==20
    assert result[0]['response_complete']is False and result[0]['response_bytes']==0
    assert result[1]=={}
    assert result[2]['http_request_sent']is False and result[2]['cache_hit']is True
    assert result[3]['response_complete']is True


def test_http_200_digest_and_size_never_invent_send_completion_or_method():
    from provider_observation_details import observation_details
    result=observation_details({'component_statuses':{'unknown':{'http_status':200,'response_sha256':'a'*64,'response_bytes':200}}})
    item=result['component_statuses']['unknown']
    assert not {'http_request_sent','response_complete','http_status_observed','request_method','request_url_sha256'}&set(item)


@pytest.mark.parametrize('bad',[1,0,'true','false',[],{},None])
def test_transport_flags_are_only_booleans(bad):
    from provider_observation_details import observation_details
    item=observation_details({'component_statuses':{'x':{'http_request_sent':bad,'response_complete':bad,'http_status_observed':bad}}})['component_statuses']['x']
    assert not {'http_request_sent','response_complete','http_status_observed'}&set(item)


@pytest.mark.parametrize('url',['https://name:secret@example.com/path','file:///Volumes/private/key','http://example.com/path','https://[invalid','https://example.com/\nsecret','https://example.com/'+'x'*4096])
def test_invalid_or_credential_bearing_url_does_not_get_a_transport_fingerprint(url):
    from provider_observation_details import observation_details
    result=observation_details({'component_statuses':{'x':{'url':url,'request_method':'GET /?api_key=secret','api_key':'secret','headers':{'authorization':'secret'},'body':'secret','raw_response_path':'/Volumes/private/key'}}})
    assert 'request_url_sha256'not in result['component_statuses']['x']
    assert 'request_method'not in result['component_statuses']['x']
    assert 'secret'not in json.dumps(result)and '/Volumes/'not in json.dumps(result)


@pytest.mark.parametrize('values',[{'http_status':True,'response_bytes':False,'response_sha256':'secret'},
    {'http_status':999,'response_bytes':-1,'response_sha256':'a'*63},
    {'http_status':200.0,'response_bytes':float('inf'),'response_sha256':'A'*64},
    {'http_status':float('nan'),'response_bytes':10**400,'response_sha256':123}])
def test_malformed_http_status_size_and_digest_do_not_persist_as_evidence(values):
    from provider_observation_details import observation_details
    item=observation_details({'component_statuses':{'x':values}})['component_statuses']['x']
    assert not {'http_status','response_bytes','response_sha256'}&set(item)


def test_query_is_only_fingerprinted_and_never_saved_with_headers_or_body():
    from provider_observation_details import observation_details
    url='https://example.com/data?api_key=private-key&company=2905'
    result=observation_details({'component_statuses':{'x':{'url':url,'request_method':'POST',
        'headers':{'Authorization':'private-key'},'request':{'token':'private-key'},'body':'private-key'}}})
    assert result['component_statuses']['x']['request_url_sha256']==sha256(url.encode()).hexdigest()
    assert result['component_statuses']['x']['request_method']=='POST'
    assert 'private-key'not in json.dumps(result)and 'company=2905'not in json.dumps(result)


def test_bad_component_number_cannot_erase_the_actual_failed_fetch_denominator():
    entry={'source':'financial_statements','provider':'isolated failed source','status':'error','record_count':0,
        'http_request_sent':True,'http_request_count':1,'event_kind':'aggregate',
        'component_statuses':{'partial':{'status':'error','response_bytes':10**400,'response_complete':False,'http_request_sent':True}}}
    provider_sla.record_source_audit_entries([entry])
    with sqlite3.connect(provider_sla.TASK_DB_PATH)as c:
        rows=c.execute('select status,record_count,details_json from provider_sla_events').fetchall()
    assert len(rows)==1 and rows[0][:2]==('error',0)
    item=json.loads(rows[0][2])['component_statuses']['partial']
    assert 'response_bytes'not in item and item['response_complete']is False
    summary=get_provider_acquisition_summary()['sources'][0]
    assert summary['fetch_attempts']==1 and summary['fetched_count']==0
