from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from zoneinfo import ZoneInfo
import json,time
import pytest,cache_store
from provider_correlation import correlation_scope,source_operation
from data_fetch.market_sources import delta_press_evidence as e
from data_fetch.market_sources.delta_press_parse import INDEX,TTL
from delta_press_fixtures import index,article,URL,master,context

@pytest.fixture
def owned_statement(monkeypatch):
    from official_response_evidence import archive_response
    from data_fetch.market_sources.official_company_legal_name import parse_roster
    now=datetime(2026,11,5,12,tzinfo=ZoneInfo('Asia/Taipei')).timestamp();owners={}
    # Freeze downstream freshness/order clocks too, so this saved-day fixture
    # cannot become a future CI failure merely because the wall clock advances.
    monkeypatch.setattr(time,'time',lambda:now+2)
    monkeypatch.setattr(cache_store,'peek_cache_json',lambda key:deepcopy(owners.get(key)))
    receipts=[]
    with correlation_scope(replace=True,ticker='2308.TW',fetch_id='unit-evidence'),source_operation('recent_catalysts',e.PROVIDER):
        for url,raw in((INDEX,index()),(URL,article())):
            r=e.native_receipt(raw,url,now,e.transport_for(raw));receipts.append(r)
            owners[e.raw_key(url)]={'value':deepcopy(r),'fetched_at_epoch':now,'fresh_until_epoch':now+TTL}
    batch=e.native_batch(receipts,now+1);owners[e.batch_key()]={'value':deepcopy(batch),'fetched_at_epoch':now+1,'fresh_until_epoch':now+TTL}
    raw=master();roster=parse_roster(raw,'.TW');archive_response(raw,source_url=roster['source_url'],retrieved_at=now,http_status=200)
    mk='shared_provider:v1:'+sha256(b'official-company-roster:v2:.TW').hexdigest()
    owners[mk]={'value':roster,'fetched_at_epoch':now,'fresh_until_epoch':now+86400}
    return now,owners,batch,context(),mk

def test_exact_full_replay_read_only_without_private_path(owned_statement):
    now,owners,batch,data,_=owned_statement;before=deepcopy(owners);v=e.project(batch,data,now+2)
    assert e.verified_record(v,data,now=now+3)=='台達電'
    assert 'raw_response_path'not in json.dumps(v)and owners==before
    assert v['publication_clock_and_timezone']is None and v['date']=='2026-10-14'

@pytest.mark.parametrize('change',['raw','batch','master','raw_extension','batch_extension','raw_value','expired','renewed_observation'])
def test_current_independent_unextended_owners_mandatory(owned_statement,change):
    now,owners,batch,data,mk=owned_statement;v=e.project(batch,data,now+2);at=now+3
    if change=='raw':owners.pop(e.raw_key(URL))
    elif change=='batch':owners.pop(e.batch_key())
    elif change=='master':owners.pop(mk)
    elif change=='raw_extension':owners[e.raw_key(URL)]['fresh_until_epoch']+=100
    elif change=='batch_extension':owners[e.batch_key()]['fresh_until_epoch']+=100
    elif change=='raw_value':owners[e.raw_key(URL)]['value']['method']='POST'
    elif change=='expired':at=now+TTL
    else:v['delta_press_receipt']['fetched_at_epoch']+=1
    before=deepcopy(owners);assert e.verified_record(v,data,now=at)is None and owners==before

@pytest.mark.parametrize('change',['body','date','timezone','issuer','inference','manifest','transport','path'])
def test_public_flags_or_mutated_record_not_evidence(owned_statement,change):
    now,owners,batch,data,_=owned_statement;v=e.project(batch,data,now+1)
    if change=='body':v['text']='captions'
    elif change=='date':v['date']='2026-11-05'
    elif change=='timezone':v['publication_clock_and_timezone']='UTC'
    elif change=='issuer':v['ticker']='2412.TW'
    elif change=='inference':v['catalyst_verified']=True
    elif change=='manifest':v['delta_press_receipt']['metadata_manifest']['raw_response_sha256']='0'*64
    elif change=='transport':v['delta_press_receipt']['originals'][1]['native_transport']['response_complete']=False
    else:v['delta_press_receipt']['originals'][1]['raw_receipt']['raw_response_path']='/tmp/forged'
    assert e.verified_record(v,data,now=now+2)is None

@pytest.mark.parametrize('change',['legal','ETF','ticker','company'])
def test_subsidiary_wrong_quote_or_context_rejected(owned_statement,change):
    now,owners,batch,data,_=owned_statement;v=e.project(batch,data,now+1);wrong=deepcopy(data)
    if change=='legal':wrong['company_identity']['legal_name']='台達電子泰國股份有限公司'
    elif change=='ETF':wrong['quote_type']='ETF'
    elif change=='ticker':wrong['ticker']='2308.TWO'
    else:wrong['company_name']='Other Delta'
    assert e.verified_record(v,wrong,now=now+2)is None

@pytest.mark.parametrize('field,value',[('response_complete',False),('http_status',429),('proxy_used',1),('num_redirects',1),('http_request_sent',1),('ssl_verify_result',False)])
def test_native_transport_exact_type_and_frame(field,value):
    raw=index();transport=e.transport_for(raw);transport[field]=value
    with correlation_scope(replace=True,ticker='2308.TW',fetch_id='unit-type'),source_operation('recent_catalysts',e.PROVIDER),pytest.raises(ValueError):
        e.native_receipt(raw,INDEX,time.time(),transport)

def test_no_native_context_cannot_archive_source():
    with pytest.raises(ValueError):e.native_receipt(index(),INDEX,time.time(),e.transport_for(index()))

def test_new_wrapper_cannot_renew_original_time(owned_statement):
    now,owners,batch,data,_=owned_statement;owners[e.batch_key()]['fetched_at_epoch']=now+100
    v=e.project(batch,data,now+101);assert v['fetched_at_epoch']==now
    assert e.verified_record(v,data,now=now+TTL)is None

@pytest.mark.parametrize('field,value',[('網址','https://preprod-www.deltaww.com'),('英文簡稱','OTHER'),('公司名稱','台達電子泰國股份有限公司'),('營利事業統一編號','12345678')])
def test_current_full_master_must_independently_anchor_exact_issuer(owned_statement,field,value):
    from official_response_evidence import archive_response
    from data_fetch.market_sources.official_company_legal_name import parse_roster
    now,owners,batch,data,mk=owned_statement;v=e.project(batch,data,now+1);rows=json.loads(master())
    rows[-1][field]=value;raw=json.dumps(rows,ensure_ascii=False).encode();roster=parse_roster(raw,'.TW')
    archive_response(raw,source_url=roster['source_url'],retrieved_at=now,http_status=200)
    owners[mk]['value']=roster
    assert e.verified_record(v,data,now=now+2)is None

def test_short_master_or_stale_observation_is_not_current_identity(owned_statement):
    now,owners,batch,data,mk=owned_statement;v=e.project(batch,data,now+1)
    owners[mk]['fetched_at_epoch']=now-86400
    assert e.verified_record(v,data,now=now+2)is None
