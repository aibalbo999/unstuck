"""Native qualification is separate from a public parsed candidate."""
from copy import deepcopy
import json,time
import pytest
from test_current_104_postings import packets,raw,ISSUER,NOW,JOB,SLUG
from data_fetch.market_sources import current_104_evidence as e

DATA={'ticker':ISSUER['ticker'],'company_name':ISSUER['official_short_name'],'quote_type':'EQUITY',
 'company_identity':{'ticker':ISSUER['ticker'],'official_name':ISSUER['official_short_name'],'instrument_type':'EQUITY'}}

def test_public_flags_and_counts_cannot_become_originals():
 from data_fetch.market_sources.current_104_postings import parse_snapshot
 from data_trust import source_record_count
 a,b=packets();p=parse_snapshot(raw(a),{JOB:raw(b)},issuer=ISSUER,observed_at=NOW,now=NOW).public_value()
 p.update(status='partial',native_originals_verified=True)
 assert e.verified_count(p,DATA,ISSUER,now=NOW)==0
 assert source_record_count('alternative_data',{**DATA,'alternative_data':{'job_openings_104_current':p,'company_legal_name_evidence':ISSUER}})==0

@pytest.mark.parametrize('change',[{'quote_type':'ETF'},{'ticker':'9103.TW'},{'stock_id':'1234'},{'company_name':'子公司'}, {'instrument_type':'INDEX'}])
def test_conflicting_identity_stops_before_native_acquisition(change):
 assert not e.valid_context({**DATA,**change},ISSUER)

def test_current_issuer_replays_full_owner_not_supplied_name(monkeypatch):
 monkeypatch.setattr(e,'get_cache_json',lambda _:None)
 assert not e.verified_issuer(ISSUER,now=NOW)


def prepare(monkeypatch):
 """Use isolated archive/cache only. Native source itself is tested separately."""
 import cache_store
 monkeypatch.setattr(e,'verified_issuer',lambda issuer,now=None:issuer==ISSUER)
 a,b=packets();urls=[e.list_url(ISSUER),e.detail_url(JOB)]
 receipts=[e.archive_original(raw(v),u,NOW-2+n,{'ticker':ISSUER['ticker'],'fetch_id':'f','operation_id':'o'}) for n,(v,u) in enumerate(zip([a,b],urls))]
 payload=e.make_batch(receipts,ISSUER,now=NOW)
 cache_store.set_cache_json(e.cache_key(ISSUER),{'value':payload,'fetched_at_epoch':NOW,'fresh_until_epoch':NOW+e.TTL},ttl_seconds=e.TTL)
 return e.replay_batch(payload,ISSUER,now=NOW),payload


def test_originals_and_independent_owner_replay_minimal_public_value(monkeypatch):
 p,_=prepare(monkeypatch)
 assert e.verified_count(p,DATA,ISSUER,now=NOW)==1
 assert p['record_unit']=='advertised_posting'and p['job_count']is None
 assert p['recent_company_job_count']is None and p['hiring_headcount']is None
 s=json.dumps(p,ensure_ascii=False)
 assert 'raw_response_path'not in s and 'needEmp'not in s and 'jobDescription'not in s
 assert 'source_record_archive'in p

@pytest.mark.parametrize('field,value',[('observed_sample_posting_count',99),('native_originals_verified',False),('hiring_headcount',5),('first_publication_verified',True),('recent_company_job_count',1),('company_name','子公司')])
def test_public_mutation_rejected(monkeypatch,field,value):
 p,_=prepare(monkeypatch);p[field]=value
 assert e.verified_count(p,DATA,ISSUER,now=NOW)==0

def test_unknown_or_expired_batch_owner_rejects_without_refresh(monkeypatch):
 p,_=prepare(monkeypatch)
 assert e.verified_count(p,DATA,ISSUER,now=NOW+e.TTL)==0
 monkeypatch.setattr(e,'get_cache_json',lambda _:None)
 assert e.verified_count(p,DATA,ISSUER,now=NOW)==0


def test_altered_private_original_or_wrong_metadata_rejects(monkeypatch):
 p,_=prepare(monkeypatch);p['source_record_archive']['manifest']['retrieved_at']+=1
 assert e.verified_count(p,DATA,ISSUER,now=NOW)==0


def test_partial_batch_or_cross_operation_rejected(monkeypatch):
 monkeypatch.setattr(e,'verified_issuer',lambda issuer,now=None:True)
 a,b=packets();r=e.archive_original(raw(a),e.list_url(ISSUER),NOW-2,{'ticker':ISSUER['ticker'],'fetch_id':'f','operation_id':'o'})
 with pytest.raises(ValueError):e.make_batch([r],ISSUER,now=NOW)
 r2=e.archive_original(raw(b),e.detail_url(JOB),NOW-1,{'ticker':ISSUER['ticker'],'fetch_id':'f','operation_id':'different'})
 with pytest.raises(ValueError):e.make_batch([r,r2],ISSUER,now=NOW)


def test_real_issuer_validator_requires_full_current_roster_and_exact_saved_owner(monkeypatch):
 from cache_store import set_cache_json,get_cache_json
 from official_response_evidence import archive_response
 from data_fetch.market_sources.official_company_legal_name import parse_roster,select_legal_name,URLS
 from datetime import datetime
 from zoneinfo import ZoneInfo
 stamp=time.time()-2;day=datetime.fromtimestamp(stamp,ZoneInfo('Asia/Taipei')).date()
 roc=f'{day.year-1911:03d}{day.month:02d}{day.day:02d}'
 rows=[{'SecuritiesCompanyCode':str(n),'CompanyName':f'測試{n}股份有限公司','CompanyAbbreviation':f'測試{n}','Date':roc,'UnifiedBusinessNo.':'22099815'}for n in range(4000,4600)]
 rows.append({'SecuritiesCompanyCode':'5314','CompanyName':ISSUER['legal_name'],'CompanyAbbreviation':ISSUER['official_short_name'],'Date':roc,'UnifiedBusinessNo.':ISSUER['official_ubn']})
 body=raw(rows);archive_response(body,source_url=URLS['.TWO'],retrieved_at=stamp)
 roster=parse_roster(body,'.TWO');issuer={**select_legal_name(roster,ISSUER['ticker'],ISSUER['official_short_name'],today=day),'fetched_at_epoch':stamp}
 key='shared_provider:v1:'+e.sha256(b'official-company-roster:v2:.TWO').hexdigest()
 saved={'value':roster,'fetched_at_epoch':stamp,'fresh_until_epoch':stamp+86400}
 set_cache_json(key,saved,ttl_seconds=86400)
 assert e.verified_issuer(issuer)
 for field,value in [('official_ubn','12345678'),('legal_name','子公司股份有限公司'),('as_of','2020-01-01'),('response_sha256','0'*64)]:
  assert not e.verified_issuer({**issuer,field:value})
 changed=deepcopy(saved);changed['value']['entries']['5314']['legal_name']='變更股份有限公司'
 set_cache_json(key,changed,ttl_seconds=86400)
 assert not e.verified_issuer(issuer)
 set_cache_json(key,{**saved,'fresh_until_epoch':time.time()-1},ttl_seconds=86400)
 assert not e.verified_issuer(issuer)


def test_explicit_deadline_is_rechecked_at_read_not_only_acquisition(monkeypatch):
 from cache_store import set_cache_json
 monkeypatch.setattr(e,'verified_issuer',lambda issuer,now=None:True)
 a,b=packets();b['data']['closeDate']='2026/11/06'
 start=NOW+14*3600+50*60 # Nov5 23:50, expires after midnight.
 receipts=[e.archive_original(raw(v),url,start+n,{'ticker':ISSUER['ticker'],'fetch_id':'f','operation_id':'o'})for n,(v,url)in enumerate(zip([a,b],[e.list_url(ISSUER),e.detail_url(JOB)]))]
 batch=e.make_batch(receipts,ISSUER,now=start+2)
 set_cache_json(e.cache_key(ISSUER),{'value':batch,'fetched_at_epoch':start+2,'fresh_until_epoch':start+e.TTL},ttl_seconds=e.TTL)
 p=e.replay_batch(batch,ISSUER,now=start+2)
 assert e.verified_count(p,DATA,ISSUER,now=start+2)==1
 assert e.verified_count(p,DATA,ISSUER,now=start+601)==0
