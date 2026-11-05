"""All selected bodies and frozen exclusions remain necessary native proof."""
from copy import deepcopy
import json
import pytest
from test_current_104_postings import raw,ISSUER,NOW,JOB,packets
from test_current_104_expired_selection import mixed,OTHER
from test_current_104_evidence import DATA
from data_fetch.market_sources import current_104_evidence as e

SCHEMA='104-current-enabled-originals:mixed-expiry:v2'
def prepare_mixed(monkeypatch,deadline='2024-02-22',good_deadline='',start=NOW-10):
    from cache_store import set_cache_json
    monkeypatch.setattr(e,'verified_issuer',lambda issuer,now=None:issuer==ISSUER)
    a,d=mixed(deadline);d[JOB]['data']['closeDate']=good_deadline
    objects=[a,d[JOB],d[OTHER]];urls=[e.list_url(ISSUER),e.detail_url(JOB),e.detail_url(OTHER)]
    receipts=[e.archive_original(raw(v),u,start+n,{'ticker':ISSUER['ticker'],'fetch_id':'f','operation_id':'o'})for n,(v,u)in enumerate(zip(objects,urls))]
    batch=e.make_batch(receipts,ISSUER,now=start+3)
    saved={'value':batch,'fetched_at_epoch':start+3,'fresh_until_epoch':start+e.TTL}
    set_cache_json(e.cache_key(ISSUER),saved,ttl_seconds=e.TTL)
    return e.replay_batch(batch,ISSUER,now=start+3),batch,saved,receipts

def read_manifest(batch):
    stamp=batch['manifest']['retrieved_at']
    return json.loads(e._read(batch['manifest'],e.list_url(ISSUER),stamp,'private_acquisition_manifest',None,32768))
def replace_manifest(batch,content):
    from official_response_evidence import archive_response
    proof=archive_response(e._dump(content),source_url=e.list_url(ISSUER),retrieved_at=batch['manifest']['retrieved_at'],http_status=None,evidence_kind='private_acquisition_manifest',max_bytes=32768)
    return {'schema':content['schema'],'manifest':e._pathless(proof)}

def test_mixed_batch_freezes_every_selected_id_and_exact_exclusion(monkeypatch):
    p,b,owner,receipts=prepare_mixed(monkeypatch)
    assert b['schema']==SCHEMA
    content=read_manifest(b)
    assert content['schema']==SCHEMA and len(content['receipts'])==3
    assert content['selection']=={'selected_job_ids':[JOB,OTHER],'eligible_job_ids':[JOB],'excluded_postings':p['excluded_postings']}
    assert e.verified_count(p,DATA,ISSUER,now=NOW)==1
    assert 'raw_response_path'not in json.dumps(p)and 'jobDescription'not in json.dumps(p)
    from data_trust import source_record_count
    monkeypatch.setattr(e.time,'time',lambda:NOW)
    assert source_record_count('alternative_data',{**DATA,'alternative_data':{'job_openings_104_current':p,'company_legal_name_evidence':ISSUER}})==1

@pytest.mark.parametrize('change',['eligible','reason','selected','removed','legacy_schema','unknown_schema'])
def test_manifest_cannot_change_exclusions_or_omit_an_expired_body(monkeypatch,change):
    p,b,owner,r=prepare_mixed(monkeypatch);content=read_manifest(b)
    if change=='eligible':content['selection']['eligible_job_ids'].append(OTHER)
    if change=='reason':content['selection']['excluded_postings'][0]['reason_code']='not_interested'
    if change=='selected':content['selection']['selected_job_ids'].reverse()
    if change=='removed':content['receipts'].pop()
    if change=='legacy_schema':content['schema']=e.SCHEMA;content.pop('selection')
    if change=='unknown_schema':content['schema']='104-current-enabled-originals:mixed-expiry:v3'
    fake=replace_manifest(b,content)
    with pytest.raises(ValueError):e.replay_batch(fake,ISSUER,now=NOW)

@pytest.mark.parametrize('field,value',[('excluded_postings',[]),('selected_job_ids',[JOB]),('selected_detail_count',1),('observed_sample_posting_count',2)])
def test_public_eligible_and_excluded_counts_are_not_self_authenticating(monkeypatch,field,value):
    p,_,_,_=prepare_mixed(monkeypatch);p[field]=value
    assert e.verified_count(p,DATA,ISSUER,now=NOW)==0

def test_expired_original_still_required_even_if_eligible_original_is_intact(monkeypatch):
    p,b,_,receipts=prepare_mixed(monkeypatch);target=receipts[-1]['raw_receipt']['raw_response_sha256'];old=e._read
    def read(proof,*args):
        if proof.get('raw_response_sha256')==target:raise ValueError('original unavailable')
        return old(proof,*args)
    monkeypatch.setattr(e,'_read',read)
    assert e.verified_count(p,DATA,ISSUER,now=NOW)==0

def test_eligible_deadline_crossing_invalidates_frozen_mixed_batch_without_reselection(monkeypatch):
    start=NOW+14*3600+50*60
    p,b,saved,_=prepare_mixed(monkeypatch,good_deadline='2026-11-06',start=start)
    assert e.verified_count(p,DATA,ISSUER,now=start+4)==1
    assert e.verified_count(p,DATA,ISSUER,now=start+601)==0
    from cache_store import get_cache_json
    assert get_cache_json(e.cache_key(ISSUER))==saved

def test_all_valid_v1_original_and_output_are_unchanged(monkeypatch):
    from test_current_104_evidence import prepare
    p,b=prepare(monkeypatch)
    assert b['schema']==e.SCHEMA and p['schema']=='104-current-enabled-advertisements:v1'
    assert set(read_manifest(b))=={'schema','issuer','receipts'}
    assert not {'excluded_postings','selected_job_ids','selected_detail_count'} & set(p)


def test_native_mixed_transport_uses_all_selected_bodies_once_and_keeps_warm_owner(monkeypatch):
    import httpx
    from data_fetch.market_sources import current_104_transport as transport
    from test_current_104_transport import fetch
    from cache_store import get_cache_json
    from data_trust import source_record_count
    from prompt_evidence import prompt_evidence_copy
    monkeypatch.setattr(e,'verified_issuer',lambda issuer,now=None:issuer==ISSUER)
    a,d=mixed();calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs))
        obj=a if url==e.list_url(ISSUER)else d[url.rsplit('/',1)[-1]]
        return httpx.Response(200,content=raw(obj),headers={'content-type':'application/json'},request=httpx.Request('GET',url))
    monkeypatch.setattr(transport,'sync_get',get)
    result=fetch();assert result is not None and result.status=='success'
    value=result.value['job_openings_104_current']
    assert value['schema']=='104-current-enabled-advertisements:mixed-expiry:v2'
    assert result.audit['record_count']==1 and result.audit['http_request_count']==3
    assert [url for url,_ in calls]==[e.list_url(ISSUER),e.detail_url(JOB),e.detail_url(OTHER)]
    assert all(0<args['timeout']<=5 for _,args in calls)
    assert source_record_count('alternative_data',{**DATA,'alternative_data':result.value})==1
    owner=deepcopy(get_cache_json(e.cache_key(ISSUER)))
    again=fetch()
    assert len(calls)==3 and get_cache_json(e.cache_key(ISSUER))==owner
    assert again.audit['cache_hit'] and not again.audit['http_request_sent']and again.audit['http_request_count']==0
    assert again.value==result.value
    prompt=prompt_evidence_copy({'alternative_data':result.value})
    s=json.dumps(prompt)
    assert 'raw_response_path'not in s and 'jobDescription'not in s and 'needEmp'not in s


def test_same_fixed_first_five_no_replacement_for_expired_rows(monkeypatch):
    import httpx
    from data_fetch.market_sources import current_104_transport as transport
    from test_current_104_transport import fetch
    monkeypatch.setattr(e,'verified_issuer',lambda issuer,now=None:True)
    a,d=mixed();base=deepcopy(a['data']['list']['normalJobs'][0])
    for n in range(4):
        ident='extra'+str(n)
        row={**base,'jobNo':ident,'jobUrl':'https://www.104.com.tw/job/'+ident}
        a['data']['list']['normalJobs'].append(row);d[ident]=deepcopy(d[JOB])
    a['data']['totalCount']=6;calls=[]
    def get(url,**kwargs):
        calls.append(url);obj=a if url==e.list_url(ISSUER)else d[url.rsplit('/',1)[-1]]
        return httpx.Response(200,content=raw(obj),headers={'content-type':'application/json'},request=httpx.Request('GET',url))
    monkeypatch.setattr(transport,'sync_get',get)
    result=fetch();assert result is not None
    assert len(calls)==6 and calls[-1]==e.detail_url('extra2')and e.detail_url('extra3')not in calls
    p=result.value['job_openings_104_current']
    assert p['selected_detail_count']==5 and p['observed_sample_posting_count']==4
    assert len(p['excluded_postings'])==1
