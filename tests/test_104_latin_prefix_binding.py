"""A Latin display prefix never replaces exact legal-name, UBN or job proof."""
from copy import deepcopy
from datetime import datetime,timezone
import json
import time
import pytest
from alternative_data_fetcher import fetch_104_company_jobs,fetch_104_company_jobs_by_ubn

LEGAL='英業達股份有限公司';UBN='04322046';SLUG='1zh8g1c'
SAMPLE=json.loads(r'''{
  "note": "Sanitized unit-test projection of two private native responses; not an HTTP receipt or source success",
  "listing": {
    "data": {
      "totalCount": 415,
      "totalPages": 21,
      "page": 1,
      "pageSize": 20,
      "list": {
        "topJobs": [],
        "normalJobs": [
          {
            "jobNo": "7w58x",
            "jobName": "[Server]實驗室機構不良分析工程師(桃園)",
            "jobUrl": "https://www.104.com.tw/job/7w58x",
            "appearDate": "10/26"
          }
        ]
      }
    }
  },
  "detail": {
    "data": {
      "custNo": "1zh8g1c",
      "header": {
        "custName": "Inventec_英業達股份有限公司",
        "custUrl": "https://www.104.com.tw/company/1zh8g1c",
        "jobName": "[Server]實驗室機構不良分析工程師(桃園)",
        "appearDate": "2026/10/26"
      }
    }
  }
}''')

def fixture():
    return deepcopy(SAMPLE)

class Response:
    def __init__(self,payload):self.text=json.dumps(payload,ensure_ascii=False)
    def raise_for_status(self):pass

class Session:
    def __init__(self,detail=None):
        self.fixture=fixture();self.detail=detail or self.fixture['detail'];self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append(url)
        return Response(self.detail if '/job/ajax/content/'in url else self.fixture['listing'])

def acquire(detail=None):
    session=Session(detail);result=fetch_104_company_jobs_by_ubn(LEGAL,UBN,official_short_name='英業達',session=session,today='2026-10-30')
    return result,session

@pytest.fixture(autouse=True)
def replay_date(monkeypatch):
    import data_trust_audit
    stamp=datetime(2026,10,30,6,tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(time,'time',lambda:stamp)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return cls.fromtimestamp(stamp,tz)
    monkeypatch.setattr(data_trust_audit,'datetime',Clock)

def context(value):
    return {'ticker':'2356.TW','quote_type':'EQUITY','company_identity':{'ticker':'2356.TW','official_name':'英業達','instrument_type':'EQUITY'},
        'alternative_data':{'company_legal_name_evidence':{'ticker':'2356.TW','legal_name':LEGAL,'official_short_name':'英業達',
            'official_ubn':UBN,'source_url':'https://openapi.twse.com.tw/v1/opendata/t187ap03_L',
            'response_sha256':'a'*64,'as_of':'2026-10-28','fetched_at_epoch':time.time(),'stale':False},
            'job_openings_104':value}}


def test_captured_listing_and_detail_recover_one_exact_recent_employer_sample():
    result,session=acquire()
    assert result['status']=='success' and result['recent_company_job_count']==1
    assert result['job_count']is None and result['pagination_truncated']is True
    row=result['job_postings'][0]
    assert row['source_employer']=='Inventec_'+LEGAL and row['employer']==LEGAL
    assert row['source_employer_id']==SLUG and row['employer_id']=='4322046000'
    assert row['published_date']=='2026-10-26'
    assert session.calls==['https://www.104.com.tw/api/companies/1zh8g1c/jobs','https://www.104.com.tw/job/ajax/content/7w58x']


def test_final_source_counter_rechecks_same_identity_without_losing_valid_prefix():
    from data_trust import source_record_count
    result,_=acquire()
    assert source_record_count('alternative_data',context(result))==1


@pytest.mark.parametrize('change',[
    {'custNo':'other'}, {'header':{'custName':'Inventec_英華達股份有限公司'}},
    {'header':{'custName':'Inventec_'+LEGAL+'子公司'}}, {'header':{'custName':'英業達集團_'+LEGAL}},
    {'header':{'custUrl':'https://www.104.com.tw/company/other'}},
    {'header':{'appearDate':'2026/08/01'}}, {'header':{'appearDate':'2026/10/31'}},
    {'header':{'jobName':'Different position'}},
])
def test_display_prefix_cannot_borrow_other_employer_period_or_job(change):
    detail=fixture()['detail']
    if 'header'in change:detail['data']['header'].update(change['header'])
    else:detail['data'].update(change)
    result,_=acquire(detail);assert result['status']=='unavailable'


@pytest.mark.parametrize('change',['ubn','ticker','stale','company','slug','job_url','published'])
def test_final_counter_rejects_mutated_identity_and_source_binding(change):
    from data_trust import source_record_count
    result,_=acquire();data=context(result)
    if result.get('job_postings'):
        receipt=data['alternative_data']['company_legal_name_evidence'];job=result['job_postings'][0]
        if change=='ubn':receipt['official_ubn']='00000001'
        elif change=='ticker':receipt['ticker']='3231.TW'
        elif change=='stale':receipt['stale']=True
        elif change=='company':job['source_employer']='Inventec_英華達股份有限公司'
        elif change=='slug':job['source_employer_id']='other'
        elif change=='job_url':job['url']='https://www.104.com.tw/job/other'
        elif change=='published':job['published_date']='2026-10-31'
    assert source_record_count('alternative_data',data)==0


@pytest.mark.parametrize('identity',[{}, {'official_short_name':'英業達'}, {'official_short_name':'英業達','official_ubn':UBN}])
def test_search_prefix_needs_official_ubn_and_matching_numeric_employer(identity):
    row={'custName':'Inventec_'+LEGAL,'custNo':'4322046000','jobNo':str(int('7w58x',36)),'jobName':'工程師',
         'appearDate':'20261026','link':{'job':'https://www.104.com.tw/job/7w58x'}}
    class Search:
        def get(self,url,**kwargs):return Response({'metadata':{'pagination':{'currentPage':1,'lastPage':1}},'data':[row]})
    result=fetch_104_company_jobs(LEGAL,session=Search(),today='2026-10-30',**identity)
    expected=bool(identity.get('official_ubn'))
    assert (result['status']=='success')is expected
    if expected:
        from data_trust import source_record_count
        assert source_record_count('alternative_data',context(result))==1
        row['custNo']='4322046001'
        assert fetch_104_company_jobs(LEGAL,session=Search(),today='2026-10-30',**identity)['status']=='unavailable'


@pytest.mark.parametrize('field,value',[
    ('employer_id','4322046001'),('source_employer','Inventec_英華達股份有限公司'),
    ('job_no','1'),('url','https://www.104.com.tw/job/other'),
    ('published_date','2026-10-31'),('published_date','2026-08-01'),
])
def test_search_counter_rechecks_saved_prefix_record_without_trusting_producer_status(field,value):
    from data_trust import source_record_count
    raw={'custName':'Inventec_'+LEGAL,'custNo':'4322046000','jobNo':str(int('7w58x',36)),
         'jobName':'工程師','appearDate':'20261026','link':{'job':'https://www.104.com.tw/job/7w58x'}}
    class Search:
        def get(self,url,**kwargs):return Response({'metadata':{'pagination':{'currentPage':1,'lastPage':1}},'data':[raw]})
    result=fetch_104_company_jobs(LEGAL,session=Search(),today='2026-10-30',official_short_name='英業達',official_ubn=UBN)
    assert result['status']=='success'
    result['job_postings'][0][field]=value
    assert source_record_count('alternative_data',context(result))==0
