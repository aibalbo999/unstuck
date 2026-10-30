"""A single observed Chinese branded label retains exact legal/UBN checks."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import sys,json,time
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from alternative_data_fetcher import fetch_104_company_jobs_by_ubn,fetch_104_company_jobs
from data_trust_audit import source_record_count
LEGAL='台灣汽電共生股份有限公司';SHORT='台汽電';UBN='86685142';SLUG='13tm3fn4';LABEL='台灣汽電集團_'+LEGAL

class Response:
    def __init__(self,payload):self.text=json.dumps(payload,ensure_ascii=False);self.status_code=200
    def raise_for_status(self):pass
class Session:
    def __init__(self,detail=None,listing=None):
        self.calls=[];self.detail=detail or {'data':{'custNo':SLUG,'header':{'custName':LABEL,'jobName':'法務室-(副)管理師','custUrl':'https://www.104.com.tw/company/'+SLUG,'appearDate':'2026/10/29'}}}
        self.listing=listing or {'data':{'totalCount':1,'totalPages':1,'page':1,'pageSize':20,'list':{'topJobs':[],'normalJobs':[{'jobNo':'5q75u','jobName':'法務室-(副)管理師','jobUrl':'https://www.104.com.tw/job/5q75u','appearDate':'10/29'}]}}}
    def get(self,url,**kw):
        self.calls.append(url);return Response(self.detail if '/job/ajax/content/'in url else self.listing)

def fetch(session=None,**kwargs):
    return fetch_104_company_jobs_by_ubn(LEGAL,UBN,official_short_name=SHORT,session=session or Session(),today='2026-10-30',**kwargs)

def test_published_company_id_remains_bound_to_official_ubn():
    assert int(SLUG,36)==int(UBN)*1000
    value=fetch()
    assert value['status']=='success' and value['recent_company_job_count']==1
    assert value['job_count'] is None and value['job_postings'][0]['source_employer']==LABEL
    assert value['job_postings'][0]['employer_id']==UBN+'000'
    assert value['job_postings'][0]['source_employer_id']==SLUG

@pytest.mark.parametrize('field,bad', [('custName','台灣汽電集團_星能股份有限公司'),('custName','台灣汽電集團_台灣汽電共生股份有限公司子公司'),('custName','任意集團_'+LEGAL),('custUrl','https://www.104.com.tw/company/wimo1dk'),('appearDate','2026/09/01'),('jobName','不同工作')])
def test_wrong_employer_group_period_or_job_remains_unavailable(field,bad):
    s=Session();s.detail['data']['header'][field]=bad
    assert fetch(s)['status']=='unavailable'

def test_wrong_detail_company_id_cannot_borrow_matching_label():
    s=Session();s.detail['data']['custNo']='wimo1dk'
    assert fetch(s)['status']=='unavailable'


def anchor_data(value,monkeypatch):
    today=datetime.now(timezone.utc).date().isoformat()
    return {'ticker':'8926.TW','company_name':SHORT,'company_identity':{'ticker':'8926.TW','official_name':SHORT},
        'alternative_data':{'job_openings_104':value,'company_legal_name_evidence':{
        'ticker':'8926.TW','legal_name':LEGAL,'official_short_name':SHORT,'official_ubn':UBN,'as_of':today,
        'source_url':'https://openapi.twse.com.tw/v1/opendata/t187ap03_L','response_sha256':'a'*64,'fetched_at_epoch':time.time()}}}


def test_source_presence_rechecks_label_ubn_job_id_and_period(monkeypatch):
    value=fetch();assert value['status']=='success';data=anchor_data(value,monkeypatch)
    # Keep the admission's current-day guard valid independently of the fixed
    # capture date used in fetch tests.
    row=data['alternative_data']['job_openings_104']['job_postings'][0]
    row['published_date']=datetime.now(timezone.utc).date().isoformat()
    assert source_record_count('alternative_data',data)==1
    before=deepcopy(data)
    for field,bad in [('source_employer','任意集團_'+LEGAL),('employer_id','86685154000'),('source_employer_id','wimo1dk'),('job_no','123'),('url','https://www.104.com.tw/job/other')]:
        sample=deepcopy(before);sample['alternative_data']['job_openings_104']['job_postings'][0][field]=bad
        assert source_record_count('alternative_data',sample)==0
    sample=deepcopy(before);sample['alternative_data']['company_legal_name_evidence']['official_ubn']='86685154'
    assert source_record_count('alternative_data',sample)==0
    assert data==before


def test_primary_search_uses_same_exact_label_contract_and_job_id_binding():
    row={'custName':LABEL,'custNo':UBN+'000','jobNo':str(int('5q75u',36)),'jobName':'法務室-(副)管理師',
         'appearDate':'20261029','link':{'job':'https://www.104.com.tw/job/5q75u'}}
    payload={'metadata':{'pagination':{'currentPage':1,'lastPage':1}},'data':[row]}
    v=fetch_104_company_jobs(LEGAL,official_short_name=SHORT,official_ubn=UBN,session=Session(listing=payload),today='2026-10-30')
    assert v['status']=='success' and v['recent_company_job_count']==1
    assert v['job_postings'][0]['employer_match_basis']=='official_name_ubn_known_label'
    row['jobNo']='123'
    v=fetch_104_company_jobs(LEGAL,official_short_name=SHORT,official_ubn=UBN,session=Session(listing=payload),today='2026-10-30')
    assert v['status']=='unavailable'


def test_primary_search_source_presence_keeps_all_id_controls(monkeypatch):
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d')
    row={'custName':LABEL,'custNo':UBN+'000','jobNo':str(int('5q75u',36)),
         'jobName':'法務室-(副)管理師','appearDate':stamp,'link':{'job':'https://www.104.com.tw/job/5q75u'}}
    payload={'metadata':{'pagination':{'currentPage':1,'lastPage':1}},'data':[row]}
    value=fetch_104_company_jobs(LEGAL,official_short_name=SHORT,official_ubn=UBN,session=Session(listing=payload))
    data=anchor_data(value,monkeypatch)
    assert source_record_count('alternative_data',data)==1
    for field,bad in [('source_employer','任意集團_'+LEGAL),('employer_id','86685154000'),('job_no','123')]:
        other=deepcopy(data);other['alternative_data']['job_openings_104']['job_postings'][0][field]=bad
        assert source_record_count('alternative_data',other)==0


def test_verified_known_label_postings_skip_unnecessary_keyword_portals(monkeypatch):
    import alternative_data_fetcher as fetcher
    import data_fetch.market_sources.official_company_legal_name as names
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    value=fetch();data=anchor_data(value,monkeypatch)
    data['company_identity']['instrument_type']='EQUITY';data['quote_type']='EQUITY'
    value['job_postings'][0]['published_date']=datetime.now(timezone.utc).date().isoformat()
    monkeypatch.setattr(names,'get_official_legal_name',lambda *args:data['alternative_data']['company_legal_name_evidence'])
    monkeypatch.setattr(fetcher,'fetch_104_company_jobs',lambda *args,**kwargs:value)
    def unexpected(*args,**kwargs):raise AssertionError('Do not repeat keyword portals after exact issuer postings are verified')
    monkeypatch.setattr(fetcher,'fetch_104_job_openings_count',unexpected)
    monkeypatch.setattr(fetcher,'fetch_1111_job_openings_count',unexpected)
    result=AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('8926.TW'),{'data':data})
    assert result.status=='success' and result.audit['record_count']==1
    assert result.value['status']=='partial'
    assert result.value['component_statuses']['keyword_searches']['http_request_sent'] is False
    assert result.value['component_statuses']['keyword_searches']['reason_code']=='verified_recent_exact_company_postings_available'


@pytest.mark.parametrize('field,bad',[('employer_id','86685154000'),('source_employer','任意集團_'+LEGAL)])
def test_unverified_postings_do_not_suppress_other_portals(monkeypatch,field,bad):
    import alternative_data_fetcher as fetcher
    import data_fetch.market_sources.official_company_legal_name as names
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    value=fetch();value['job_postings'][0]['published_date']=datetime.now(timezone.utc).date().isoformat()
    value['job_postings'][0][field]=bad
    data=anchor_data(value,monkeypatch);data['company_identity']['instrument_type']='EQUITY';data['quote_type']='EQUITY'
    monkeypatch.setattr(names,'get_official_legal_name',lambda *args:data['alternative_data']['company_legal_name_evidence'])
    monkeypatch.setattr(fetcher,'fetch_104_company_jobs',lambda *args,**kwargs:value)
    calls=[]
    def portal(*args,**kwargs):calls.append(args);return {'status':'unavailable','job_count':None}
    monkeypatch.setattr(fetcher,'fetch_1111_job_openings_count',portal)
    result=AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker('8926.TW'),{'data':data})
    assert calls and result.audit['record_count']==0
    assert 'keyword_searches' not in result.value['component_statuses']
