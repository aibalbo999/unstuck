"""Keep source transport evidence without inventing new sends or exposing originals."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from provider_observation_details import observation_details

URL='https://example.com/body?access_token=do-not-store'
def receipt():
    return {'status':'archived','source_url':URL,'retrieved_at':1700000000.25,
            'http_status':200,'raw_response_sha256':'a'*64,'raw_response_bytes':123,
            'evidence_kind':'raw_http_response_bytes','request_method':'GET',
            'http_status_observed':True,'response_complete':True,'cache_hit':False,
            'raw_response_path':'/private/secret.gz','body':'secret body',
            'headers':{'Authorization':'secret header'}}

def test_multi_original_components_survive_bounded_projection_without_private_fields():
    r=receipt();entry={'http_request_sent':True,'component_statuses':[
        {'url':URL,'http_request_sent':True,'cache_hit':False,'original_receipt':r}]}
    before=deepcopy(entry);out=observation_details(entry)
    rows=out['original_http_receipts'];assert len(rows)==1
    row=rows[0]
    assert row['source_url_sha256']==sha256(URL.encode()).hexdigest()
    assert row['response_sha256']=='a'*64 and row['response_bytes']==123
    assert row['original_retrieved_at_epoch']==1700000000.25
    assert row['http_status']==200 and row['http_status_observed'] is True
    assert row['http_request_sent'] is True and row['response_complete'] is True
    serialized=json.dumps(out)
    for value in ('do-not-store','/private/secret.gz','secret body','secret header'):
        assert value not in serialized
    assert entry==before

def test_warm_provider_body_keeps_original_receipt_without_claiming_new_http():
    entry={'http_request_sent':False,'cache_hit':True,'raw_http_receipt':receipt()}
    out=observation_details(entry);r=out['original_http_receipts'][0]
    assert r['http_request_sent'] is False and r['cache_hit'] is True
    assert r['original_retrieved_at_epoch']==1700000000.25
    assert out['http_request_sent'] is False

def test_unknown_transport_flags_stay_unknown():
    r=receipt()
    for k in ('http_status_observed','response_complete','cache_hit','request_method'):r.pop(k)
    out=observation_details({'raw_http_receipt':r})['original_http_receipts'][0]
    assert not {'http_request_sent','http_status_observed','response_complete','cache_hit','request_method'} & out.keys()

@pytest.mark.parametrize('field,value', [('raw_response_sha256','bad'),('raw_response_bytes',True),
    ('raw_response_bytes',float('nan')),('raw_response_bytes',-1),('raw_response_bytes',100000001),
    ('retrieved_at',float('inf')),('retrieved_at',False),('http_status',True),
    ('source_url','https://user:secret@example.com/body'),('source_url','file:///private/secret'),('status','error')])
def test_invalid_receipt_never_creates_transport_evidence(field,value):
    r=receipt();r[field]=value
    assert 'original_http_receipts' not in observation_details({'raw_http_receipt':r})

def test_original_components_are_capped():
    out=observation_details({'component_statuses':[{'http_request_sent':True,'original_receipt':receipt()}]*1000})
    assert len(out['original_http_receipts'])==20


@pytest.mark.parametrize('value', [[], {}, 1, True, 'DELETE'])
def test_invalid_method_is_omitted_without_breaking_provider_telemetry(value):
    r=receipt();r['request_method']=value
    assert 'request_method' not in observation_details({'raw_http_receipt':r})['original_http_receipts'][0]


def test_invalid_unicode_url_is_ignored_without_exposing_or_crashing():
    r=receipt();r['source_url']='https://example.com/\ud800'
    assert 'original_http_receipts' not in observation_details({'raw_http_receipt':r})


def test_receipts_do_not_change_acquisition_classification():
    from provider_acquisition import observation_kind
    for status,cache in [('success',False),('skipped_fresh_cache',True),('error',False)]:
        entry={'http_request_sent':not cache,'cache_hit':cache}
        row={'source':'peer_discovery','provider':'fixture','status':status,'record_count':1,'message':'fixture','details':observation_details(entry)}
        old=observation_kind(row)
        entry['raw_http_receipt']=receipt();row['details']=observation_details(entry)
        assert observation_kind(row)==old
