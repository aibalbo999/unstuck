from copy import deepcopy
import time
import json
from datetime import datetime
from hashlib import sha256
from zoneinfo import ZoneInfo
import pytest
import cache_store
from data_fetch.market_sources.caa_operating_parse import INDEX,DIRECTORY,TTL
from data_fetch.market_sources.caa_operating_evidence import (native_receipt as _native_receipt,receipt_body,raw_key,
    native_batch,batch_key,project,verified_count,RAW_PREFIX,PROVIDER)
from provider_correlation import correlation_scope,source_operation
from caa_operating_fixtures import index_page,directory,ods,master

def transport(raw):
    return {'http_status':200,'http_status_observed':True,'response_complete':True,'http_request_sent':True,
      'return_code':0,'ssl_verify_result':0,'proxy_used':0,'num_redirects':0,'response_bytes':len(raw)}

def native_receipt(*args):
    # Synthetic transport seam in an isolated test; no actual source HTTP claim.
    with correlation_scope(replace=True,ticker='2610.TW',fetch_id='unit-evidence'),source_operation('alternative_data',PROVIDER):
        return _native_receipt(*args)

def test_complete_raw_replay_requires_current_unchanged_owner(monkeypatch):
    now=time.time();raw=b'<html>'+b'x'*120+b'</html>'
    receipt=native_receipt(raw,INDEX,now,transport(raw))
    owner={raw_key(INDEX):{'value':deepcopy(receipt),'fetched_at_epoch':now,'fresh_until_epoch':now+TTL}}
    monkeypatch.setattr(cache_store,'peek_cache_json',lambda key:deepcopy(owner.get(key)))
    assert receipt_body(receipt,INDEX,now+1)==raw

@pytest.fixture
def owned_dataset(monkeypatch):
    from official_response_evidence import archive_response
    from data_fetch.market_sources.official_company_legal_name import parse_roster
    now=datetime(2026,11,5,12,tzinfo=ZoneInfo('Asia/Taipei')).timestamp();owners={}
    monkeypatch.setattr(cache_store,'peek_cache_json',lambda key:deepcopy(owners.get(key)))
    urls=[INDEX,DIRECTORY,'https://www.caa.gov.tw/FileAtt.ashx?lang=1&id=41753'];bodies=[index_page(),directory(),ods()];receipts=[]
    for url,raw in zip(urls,bodies):
        r=native_receipt(raw,url,now,transport(raw));receipts.append(r)
        owners[raw_key(url)]={'value':deepcopy(r),'fetched_at_epoch':now,'fresh_until_epoch':now+TTL}
    batch=native_batch(receipts,now+1);owners[batch_key()]={'value':deepcopy(batch),'fetched_at_epoch':now+1,'fresh_until_epoch':now+TTL}
    rows=json.loads(master())
    for row in rows:row['出表日期']='1151105'
    raw=json.dumps(rows,ensure_ascii=False).encode();roster=parse_roster(raw,'.TW')
    archive_response(raw,source_url=roster['source_url'],retrieved_at=now,http_status=200)
    master_key='shared_provider:v1:'+sha256(b'official-company-roster:v2:.TW').hexdigest()
    owners[master_key]={'value':roster,'fetched_at_epoch':now,'fresh_until_epoch':now+86400}
    data={'ticker':'2610.TW','quote_type':'EQUITY','company_name':'華航','company_identity':{
      'ticker':'2610.TW','instrument_type':'EQUITY','official_name':'華航','legal_name':'中華航空股份有限公司','official_ubn':'11145904'}}
    return now,owners,batch,data,master_key

def test_full_batch_one_observation_warm_time_unchanged(owned_dataset):
    now,owners,batch,data,_=owned_dataset;before=deepcopy(owners);value=project(batch,data,now+1)
    assert verified_count(value,data,now=now+2)==1
    assert value['fetched_at_epoch']==now and value['year_to_date']['frequency']=='year_to_date'
    assert 'raw_response_path'not in json.dumps(value)and owners==before

def test_new_wrapper_over_live_old_originals_does_not_renew_their_age(owned_dataset):
    now,owners,batch,data,_=owned_dataset
    # A later dataset wrapper keeps the oldest real acquisition and raw deadline.
    owners[batch_key()]['fetched_at_epoch']=now+100
    value=project(batch,data,now+101)
    assert value['fetched_at_epoch']==now and verified_count(value,data,now=now+102)==1
    assert verified_count(value,data,now=now+TTL)==0

@pytest.mark.parametrize('change',['missing_raw','missing_batch','missing_master','extended_raw','extended_batch','owner_value','expired'])
def test_missing_changed_or_renewed_owners_not_public_flags(owned_dataset,change):
    now,owners,batch,data,mk=owned_dataset;value=project(batch,data,now+1);at=now+2
    if change=='missing_raw':owners.pop(raw_key(INDEX))
    elif change=='missing_batch':owners.pop(batch_key())
    elif change=='missing_master':owners.pop(mk)
    elif change=='extended_raw':owners[raw_key(INDEX)]['fresh_until_epoch']+=100
    elif change=='extended_batch':owners[batch_key()]['fresh_until_epoch']+=100
    elif change=='owner_value':owners[raw_key(INDEX)]['value']['method']='POST'
    elif change=='expired':at=now+TTL
    original=deepcopy(owners);assert verified_count(value,data,now=at)==0 and owners==original

@pytest.mark.parametrize('change',['numeric','period','issuer','public_stamp','transport','manifest','private_path','unknown_inference'])
def test_public_value_or_receipt_mutation_rejected(owned_dataset,change):
    now,owners,batch,data,_=owned_dataset;v=project(batch,data,now+1)
    if change=='numeric':v['monthly_history'][0]['values']['passengers']['native_numeric_string']='9999'
    elif change=='period':v['year']=2025
    elif change=='issuer':v['issuer']['legal_name']='華信航空股份有限公司'
    elif change=='public_stamp':v['fetched_at_epoch']+=1
    elif change=='transport':v['caa_operating_receipt']['originals'][0]['native_transport']['response_complete']=False
    elif change=='manifest':v['caa_operating_receipt']['metadata_manifest']['raw_response_sha256']='0'*64
    elif change=='private_path':v['caa_operating_receipt']['originals'][0]['raw_receipt']['raw_response_path']='/tmp/forged'
    else:v['competitive_moat_score']=5
    assert verified_count(v,data,now=now+2)==0

@pytest.mark.parametrize('change',[{'http_status':429},{'response_complete':False},{'proxy_used':1},{'num_redirects':1},{'ssl_verify_result':1},{'response_bytes':False},{'http_request_sent':1}])
def test_native_transport_must_be_exact_observed_types(change):
    raw=b'x'*120;t=transport(raw);t.update(change)
    with pytest.raises(ValueError):native_receipt(raw,INDEX,time.time(),t)

def test_cross_group_or_wrong_quote_is_never_carrier(owned_dataset):
    now,owners,batch,data,_=owned_dataset;value=project(batch,data,now+1)
    wrong=deepcopy(data);wrong['company_identity']['legal_name']='華信航空股份有限公司'
    assert verified_count(value,wrong,now=now+2)==0
    wrong=deepcopy(data);wrong['quote_type']='ETF';assert verified_count(value,wrong,now=now+2)==0

def test_public_flags_without_actual_source_frame_cannot_write_receipt():
    raw=b'x'*120
    with pytest.raises(ValueError):_native_receipt(raw,INDEX,time.time(),transport(raw))
