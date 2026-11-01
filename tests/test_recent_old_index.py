import httpx
from test_twse_company_history import NOW,INDEX,DETAIL,_row,_detail

def test_old_only_primary_index_checks_existing_official_window_fallback():
 from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
 calls=[]
 old=[_row(day='115/08/06',link=DETAIL.replace('20261006','20260806').replace('SEQ_NO=1','SEQ_NO='+str(i)))for i in range(1,11)]
 def get(url,**kwargs):
  calls.append(('GET',url))
  if url==INDEX:return httpx.Response(200,request=httpx.Request('GET',url),json={'info':{'status':'success','data':{'code':'2855','name':'統一證'}},'news':old,'fina':[],'conference':[]})
  assert url==DETAIL
  return httpx.Response(200,request=httpx.Request('GET',url),text=_detail())
 def post(url,**kwargs):
  calls.append(('POST',url));assert url=='https://mopsov.twse.com.tw/mops/web/ezsearch_query'
  return httpx.Response(200,request=httpx.Request('POST',url),json={'status':'success','data':[{'COMPANY_ID':'2855','COMPANY_NAME':'統一證','TYPEK':'上市','CDATE':'115/10/06','CTIME':'14:15:38','AN_CODE':'M99','SUBJECT':'公告本公司115年9月份損益','HYPERLINK':DETAIL}]})
 rows,audit=fetch_recent_company_announcements('2855.TW',now=NOW,get=get,post=post)
 assert len(rows)==1 and rows[0]['link']==DETAIL
 assert audit['rejected_reason_counts']['outside_window']==10
 assert audit['coverage_status']=='window_complete'and audit['status']=='success'
 assert len(calls)==3 and calls[0]==('GET',INDEX)and calls[-1]==('GET',DETAIL)

import pytest
@pytest.mark.parametrize('problem',['wrong_issuer','wrong_detail','future','refused','rate_limited'])
def test_old_primary_crosscheck_keeps_refusal_issuer_period_and_body_gates(problem):
 from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
 calls=[];old=[_row(day='115/08/06',link=DETAIL.replace('20261006','20260806'))for _ in range(10)]
 def get(url,**kwargs):
  calls.append(('GET',url))
  if url==INDEX:return httpx.Response(200,request=httpx.Request('GET',url),json={'info':{'status':'success','data':{'code':'2855','name':'統一證'}},'news':old,'fina':[],'conference':[]})
  assert url==DETAIL
  return httpx.Response(200,request=httpx.Request('GET',url),text=_detail(code='2851'if problem=='wrong_detail'else'2855'))
 def post(url,**kwargs):
  calls.append(('POST',url));assert url=='https://mopsov.twse.com.tw/mops/web/ezsearch_query'
  if problem in {'refused','rate_limited'}:return httpx.Response(429 if problem=='rate_limited'else 403,request=httpx.Request('POST',url),text='Access denied')
  row={'COMPANY_ID':'9999'if problem=='wrong_issuer'else'2855','COMPANY_NAME':'統一證','TYPEK':'上市','CDATE':'115/10/10'if problem=='future'else'115/10/06','CTIME':'14:15:38','AN_CODE':'M99','SUBJECT':'公告本公司115年9月份損益','HYPERLINK':DETAIL}
  return httpx.Response(200,request=httpx.Request('POST',url),json={'status':'success','data':[row]})
 rows,audit=fetch_recent_company_announcements('2855.TW',now=NOW,get=get,post=post)
 assert rows==[] and audit['status']!='success'
 assert audit['rejected_reason_counts']['outside_window']>=10
 assert sum(method=='POST'for method,url in calls)==1 and len(calls)<=3
 if problem in {'refused','rate_limited'}:assert len(calls)==2 and audit['status']=='error'

@pytest.mark.parametrize('status',[403,429])
def test_primary_refusal_never_opens_other_indexes(status):
 from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
 calls=[]
 def get(url,**kwargs):
  calls.append(url);assert url==INDEX
  return httpx.Response(status,request=httpx.Request('GET',url),text='refused')
 def post(*a,**kw):pytest.fail('no alternate request after primary refusal')
 rows,audit=fetch_recent_company_announcements('2855.TW',now=NOW,get=get,post=post)
 assert not rows and audit['status']=='error'and calls==[INDEX]

def test_elapsed_original_deadline_does_not_start_window_crosscheck(monkeypatch):
 import data_fetch.market_sources.twse_company_history as history
 tick=[1.0];calls=[]
 monkeypatch.setattr(history.time,'monotonic',lambda:tick[0])
 def get(url,**kwargs):
  calls.append(url);assert url==INDEX;tick[0]=50.0
  return httpx.Response(200,request=httpx.Request('GET',url),json={'info':{'status':'success','data':{'code':'2855','name':'統一證'}},'news':[_row(day='115/08/06')for _ in range(10)],'fina':[],'conference':[]})
 def post(*a,**kw):pytest.fail('no new request after existing deadline')
 rows,audit=history.fetch_recent_company_announcements('2855.TW',now=NOW,get=get,post=post)
 assert not rows and audit['status']!='success'and calls==[INDEX]
 assert audit['deadline_seconds']==history.FETCH_BUDGET_SECONDS==20
