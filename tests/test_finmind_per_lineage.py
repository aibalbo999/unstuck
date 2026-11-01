import importlib.util,sys,json
from pathlib import Path
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
import pytest,requests,pandas as pd
import finmind_per_lineage as m
from provider_correlation import correlation_scope,source_operation,current_correlation

@pytest.fixture
def case(monkeypatch,tmp_path):
 from settings import storage
 monkeypatch.setattr(storage,'CACHE_DIR',str(tmp_path/'originals'))
 rows=[{'date':f'2026-10-{i:02d}','stock_id':'6409','dividend_yield':1.2,'PER':float(10+i),'PBR':3.4}for i in range(1,29)]
 frame=pd.DataFrame(rows);values=frame.PER.tolist();result={'source':'FinMind 5-year PER quantiles','valuation_basis':'historical_quantiles','historical_quantiles_available':True,'historical_sample_count':28,'multiples':sorted({round(float(pd.Series(values).quantile(q)),1)for q in (.25,.5,.75,.9)}),'eps_twd':[1.1],'bands':{'10x':[11]}}
 request=requests.Request('GET','https://api.finmindtrade.com/api/v4/data',params={'dataset':'TaiwanStockPER','data_id':'6409','start_date':'2021-10-01','end_date':'2026-10-31','token':'private-credential'}).prepare()
 response=requests.Response();response.request=request;response.status_code=200;response._content_consumed=True;response._content=json.dumps({'msg':'success','status':200,'data':rows}).encode()
 with correlation_scope(replace=True,ticker='6409.TW',fetch_id='test-fetch'),source_operation('pe_river_chart','FinMind/default multiples'),correlation_scope(attempt_id='test-attempt'):
  yield SimpleNamespace(rows=rows,frame=frame,result=result,request=request,response=response,context=current_correlation())

def capsule(c):return m.capture_per_response(c.request,c.response,c.context)
def bind(c,cap):return m.bind_per_quantiles(SimpleNamespace(_stock_per_transport_capsules=[cap]),c.frame,c.result,'6409.TW')
def test_exact_original_sdk_rows_and_quantiles_only(case):
 before=deepcopy(case.result);frame=case.frame.copy(deep=True);cap=capsule(case);proof=bind(case,cap)
 assert proof and proof['sdk_row_count']==28 and proof['coverage']=='historical_per_quantiles_only'
 assert proof['eps_and_bands_verified']is proof['independent_primary_source_verified']is proof['historical_pit_verified']is False
 assert 'private-credential'not in str(proof)+str(cap.receipt)
 assert cap.receipt['response_complete']is True and cap.receipt['http_status_observed']is True
 assert case.result==before;pd.testing.assert_frame_equal(case.frame,frame)

@pytest.mark.parametrize('mode',['issuer','future','duplicate_date','missing_column','extra_secret','numeric_string','bool','nan','inf'])
def test_body_ambiguity_is_rejected(case,mode):
 rows=deepcopy(case.rows)
 if mode=='issuer':rows[0]['stock_id']='3653'
 elif mode=='future':rows[0]['date']='2099-10-01'
 elif mode=='duplicate_date':rows[1]['date']=rows[0]['date']
 elif mode=='missing_column':del rows[0]['PBR']
 elif mode=='extra_secret':rows[0]['token']='private-credential'
 elif mode=='numeric_string':rows[0]['PER']='11.0'
 elif mode=='bool':rows[0]['PER']=True
 elif mode=='nan':rows[0]['PER']=float('nan')
 else:rows[0]['PER']=float('inf')
 with pytest.raises((ValueError,ArithmeticError)):m.body_rows(json.dumps({'msg':'success','status':200,'data':rows}).encode(),'6409.TW',date(2021,10,1),date(2026,10,31))

@pytest.mark.parametrize('mode',['cached','redirect','stream','http_error','wrong_request','wrong_dataset','wrong_issuer','mixed_id','duplicate_start','future_end','no_attempt','secret_echo'])
def test_transport_ambiguity_produces_no_capsule(case,mode):
 if mode=='cached':case.response.from_cache=True
 elif mode=='redirect':case.response.history=[requests.Response()]
 elif mode=='stream':case.response._content_consumed=False
 elif mode=='http_error':case.response.status_code=429
 elif mode=='wrong_request':case.response.request=case.request.copy()
 elif mode=='no_attempt':case.context.pop('attempt_id')
 elif mode=='secret_echo':case.response._content=b'private-credential'
 else:
  url=case.request.url
  if mode=='wrong_dataset':url=url.replace('TaiwanStockPER','TaiwanStockNews')
  elif mode=='wrong_issuer':url=url.replace('data_id=6409','data_id=3653')
  elif mode=='mixed_id':url+='&stock_id=6409'
  elif mode=='duplicate_start':url+='&start_date=2021-10-01'
  else:url=url.replace('2026-10-31','2099-10-31')
  case.request=requests.Request('GET',url).prepare();case.response.request=case.request
 assert capsule(case)is None

@pytest.mark.parametrize('mode',['sdk_tamper','quantile_tamper','scenario','sample_count','different_operation','different_owner','expired','body_tamper'])
def test_no_promotion_from_wrong_result_or_context(case,mode):
 cap=capsule(case)
 if mode=='sdk_tamper':case.frame.loc[0,'PER']+=1
 elif mode=='quantile_tamper':case.result['multiples'][0]+=1
 elif mode=='scenario':case.result['valuation_basis']='scenario_assumption'
 elif mode=='sample_count':case.result['historical_sample_count']=29
 elif mode=='different_operation':
  with correlation_scope(operation_id='different'):assert bind(case,cap)is None
  return
 elif mode=='different_owner':
  with source_operation('dynamic_peer_metrics','other'):assert bind(case,cap)is None
  return
 elif mode=='expired':
  from dataclasses import replace
  cap=replace(cap,received=cap.received-181)
 elif mode=='body_tamper':Path(cap.receipt['raw_response_path']).write_bytes(b'bad')
 if mode in ('body_tamper','sdk_tamper'):
  try:proof=bind(case,cap)
  except (ValueError,OSError,EOFError):return
  assert proof is None
 else:assert bind(case,cap)is None


@pytest.mark.parametrize('suffix',['&stock_id=','&stock_id=&device=unit-device'])
def test_exact_native_sdk_empty_alternate_identity_is_not_second_issuer(case,suffix):
 case.request=requests.Request('GET',case.request.url+suffix).prepare();case.response.request=case.request
 cap=capsule(case);assert cap is not None and bind(case,cap)is not None

@pytest.mark.parametrize('suffix',['&stock_id=6409','&stock_id=3653','&stock_id=&stock_id='])
def test_nonempty_or_repeated_alternate_identity_stays_rejected(case,suffix):
 case.request=requests.Request('GET',case.request.url+suffix).prepare();case.response.request=case.request
 assert capsule(case)is None
