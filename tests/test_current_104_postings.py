"""Separate current enabled-ad snapshot; never relax recent30-day semantics."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from data_fetch.market_sources.current_104_postings import parse_snapshot,SnapshotError

NOW=datetime(2026,11,5,9,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
ISSUER={'ticker':'5314.TWO','legal_name':'世紀民生科技股份有限公司','official_short_name':'世紀*','official_ubn':'22099815'}
SLUG='a5hnqe0';JOB='89p62';TITLE='大數據、AI軟體工程師'
def raw(value):return json.dumps(value,ensure_ascii=False).encode()
def packets():
 item={'jobNo':JOB,'jobName':TITLE,'jobUrl':'https://www.104.com.tw/job/'+JOB,'appearDate':'10/02'}
 index={'data':{'totalCount':1,'totalPages':1,'page':1,'pageSize':20,'list':{'topJobs':[],'normalJobs':[item]}},'metadata':{}}
 detail={'data':{'header':{'jobName':TITLE,'appearDate':'2026/10/02','custName':ISSUER['legal_name'],'custUrl':'https://www.104.com.tw/company/'+SLUG},'custNo':SLUG,'switch':'on','closeDate':'','jobDetail':{'jobDescription':'開發企業資料平台，建置資料處理流程，維護模型與程式品質並協助團隊技術文件。','needEmp':'5人'}},'metadata':{}}
 return index,detail

def parse(index=None,detail=None,**kwargs):
 a,b=packets();return parse_snapshot(raw(a if index is None else index),{JOB:raw(b if detail is None else detail)},issuer=ISSUER,observed_at=NOW,now=NOW,**kwargs)

def test_34day_enabled_ad_is_current_snapshot_not_recent_or_headcount():
 p=parse().public_value()
 assert p['query_scope']=='exact_company_current_enabled_advertisements'
 assert p['observed_sample_posting_count']==1 and p['job_count']is None
 assert p['recent_company_job_count']is None and p['hiring_headcount']is None
 assert p['first_publication_verified']is False and p['hiring_growth_verified']is False
 assert p['job_postings'][0]['source_appear_or_update_date']=='2026-10-02'
 assert p['job_postings'][0]['source_enabled_state']=='on'
 assert p['job_postings'][0]['deadline']is None and not p['job_postings'][0]['deadline_provided']
 assert p['native_originals_verified']is False
 assert 'jobDescription'not in json.dumps(p)

def test_pure_parser_candidate_cannot_be_counted_as_native_acquisition():
 from data_trust import source_record_count
 assert source_record_count('alternative_data',{'ticker':'5314.TWO','alternative_data':{'job_openings_104_current':parse().public_value()}})==0

@pytest.mark.parametrize('field,value',[('switch','off'),('switch','ON'),('switch',True),('switch',None),('custNo','other'),('closeDate',None),('closeDate','2026/11/04'),('closeDate','2026/11/05'),('closeDate','明年截止')])
def test_inactive_mismatched_or_unproven_deadline_rejects(field,value):
 _,d=packets();d['data'][field]=value
 with pytest.raises(SnapshotError):parse(detail=d)

@pytest.mark.parametrize('key',['switch','closeDate','custNo'])
def test_missing_explicit_observation_not_treated_as_unknown_but_enabled(key):
 _,d=packets();del d['data'][key]
 with pytest.raises(SnapshotError):parse(detail=d)

@pytest.mark.parametrize('field,value',[('jobName','Different title'),('custName','子公司股份有限公司'),('custUrl','https://evil.invalid/company/'+SLUG),('custUrl','http://www.104.com.tw/company/'+SLUG),('appearDate','2026/10/03'),('appearDate','2027/10/02')])
def test_header_identity_or_dates_do_not_relax(field,value):
 _,d=packets();d['data']['header'][field]=value
 with pytest.raises(SnapshotError):parse(detail=d)

def test_declared_future_deadline_preserved():
 _,d=packets();d['data']['closeDate']='2026/12/01'
 p=parse(detail=d).public_value()['job_postings'][0]
 assert p['deadline']=='2026-12-01'and p['deadline_provided']

@pytest.mark.parametrize('text',['人才庫履歷資料庫，歡迎常年投遞履歷，此頁僅為儲備人才。','目前無實際職缺，僅供履歷收集與未來聯繫之用。','talent pool for future recruitment only, not currently recruiting.','短文'])
def test_pool_or_nonconcrete_description_does_not_become_posting(text):
 _,d=packets();d['data']['jobDetail']['jobDescription']=text
 with pytest.raises(SnapshotError):parse(detail=d)

def test_real_role_word_reserve_manager_is_not_generic_talent_pool():
 i,d=packets();i['data']['list']['normalJobs'][0]['jobName']='稽核儲備主管';d['data']['header']['jobName']='稽核儲備主管'
 assert parse(i,d).public_value()['observed_sample_posting_count']==1

@pytest.mark.parametrize('field,value',[('totalCount',True),('page',2),('totalPages',0),('pageSize',1000)])
def test_listing_metadata_guard(field,value):
 i,_=packets();i['data'][field]=value
 with pytest.raises(SnapshotError):parse(index=i)

def test_conflicting_duplicate_job_is_not_two_postings_or_first_value():
 i,_=packets();second=dict(i['data']['list']['normalJobs'][0]);second['jobName']='conflict';i['data']['list']['topJobs'].append(second)
 with pytest.raises(SnapshotError):parse(index=i)

def test_selected_detail_set_must_be_complete():
 i,d=packets()
 with pytest.raises(SnapshotError):parse_snapshot(raw(i),{},issuer=ISSUER,observed_at=NOW,now=NOW)
 with pytest.raises(SnapshotError):parse_snapshot(raw(i),{JOB:raw(d),'other':raw(d)},issuer=ISSUER,observed_at=NOW,now=NOW)

def test_duplicate_json_and_overlimit_body_fail_closed():
 i,d=packets()
 with pytest.raises(SnapshotError):parse_snapshot(b'{"data":{},"data":{}}',{JOB:raw(d)},issuer=ISSUER,observed_at=NOW,now=NOW)
 with pytest.raises(SnapshotError):parse_snapshot(b' '*300001,{JOB:raw(d)},issuer=ISSUER,observed_at=NOW,now=NOW)

def test_future_observation_cannot_claim_current_snapshot():
 i,d=packets()
 with pytest.raises(SnapshotError):parse_snapshot(raw(i),{JOB:raw(d)},issuer=ISSUER,observed_at=NOW+1,now=NOW)


@pytest.mark.parametrize('ticker',['006208.TW','9103.TW','0000.TW'])
def test_unsupported_instrument_codes_cannot_be_admitted_by_supplied_name(ticker):
 i,d=packets()
 with pytest.raises(SnapshotError):parse_snapshot(raw(i),{JOB:raw(d)},issuer={**ISSUER,'ticker':ticker},observed_at=NOW,now=NOW)
